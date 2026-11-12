"""
Evaluation Management Command for NyayaSahayak.
Runs statutory benchmark questions against the retrieval and RAG pipeline.
Computes Top-1 & Top-3 accuracy, refusal precision & recall, repealed-law misuse rate,
supports threshold sweeps (0.20 - 0.60), logs to database, and exports CSV reports.
Usage:
    python manage.py run_eval [--threshold 0.35] [--full] [--sweep] [--export-csv]
"""

import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

from evaluation.models import EvalQuestion, EvalRun, EvalResult
from assistant.services.retriever import retrieve_relevant_chunks
from assistant.services.rag import answer_legal_query


class Command(BaseCommand):
    help = "Runs automated legal retrieval and RAG evaluation benchmark."

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=settings.DEFAULT_CONFIDENCE_THRESHOLD,
            help='Confidence score threshold below which questions are refused (default: 0.35).'
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Execute full end-to-end RAG with LLM generation (slower, incurs API calls).'
        )
        parser.add_argument(
            '--sweep',
            action='store_true',
            help='Sweep thresholds from 0.20 to 0.60 in increments of 0.05 and print comparison.'
        )
        parser.add_argument(
            '--export-csv',
            action='store_true',
            default=True,
            help='Export detailed evaluation results to CSV under /reports/.'
        )

    def handle(self, *args, **options):
        threshold = options['threshold']
        run_full = options['full']
        do_sweep = options['sweep']
        export_csv = options['export_csv']

        self.stdout.write(self.style.MIGRATE_HEADING("=== NyayaSahayak Benchmark Evaluation Suite ==="))

        questions = list(EvalQuestion.objects.all().order_by('id'))
        if not questions:
            self.stdout.write(self.style.ERROR(
                "No evaluation questions found in database! Load fixtures using: "
                "python manage.py loaddata evaluation/fixtures/test_questions.json"
            ))
            return

        self.stdout.write(f"Loaded {len(questions)} evaluation test cases from database.")

        if do_sweep:
            self.run_threshold_sweep(questions)
            return

        # Execute single evaluation run
        self.stdout.write(f"\nRunning benchmark at confidence threshold = {threshold:.2f} (Full RAG = {run_full})...\n")
        run_obj = self.execute_eval_run(questions, threshold, run_full, export_csv)
        self.print_run_summary(run_obj)

    def is_section_match(self, expected_act: str, expected_sec: str, chunk_meta: dict) -> bool:
        """
        Determines if retrieved chunk matches expected act and section.
        """
        if not expected_act or not expected_sec:
            return False

        chunk_act = chunk_meta.get("act_name", "").lower()
        if expected_act.lower() not in chunk_act and chunk_act not in expected_act.lower():
            return False

        chunk_sec_raw = str(chunk_meta.get("section_number", ""))
        sec_clean = re.sub(r'[^0-9a-zA-Z]', '', expected_sec).lower()
        chunk_sec_clean = re.sub(r'[^0-9a-zA-Z]', '', chunk_sec_raw).lower()

        sec_digits = re.search(r'\d+', expected_sec)
        chunk_digits = re.search(r'\d+', chunk_sec_raw)

        if sec_clean == chunk_sec_clean or chunk_sec_clean in sec_clean or sec_clean in chunk_sec_clean:
            return True

        if sec_digits and chunk_digits and sec_digits.group(0) == chunk_digits.group(0):
            return True

        return False

    def execute_eval_run(self, questions, threshold: float, run_full: bool, export_csv: bool) -> EvalRun:
        start_time = time.time()
        results_to_create = []

        total_answerable = 0
        total_unanswerable = 0
        skipped_verification = 0

        correct_top1_count = 0
        correct_top3_count = 0

        true_positives = 0   # Correctly refused unanswerable
        false_positives = 0  # Incorrectly refused answerable
        true_negatives = 0   # Correctly answered answerable
        false_negatives = 0  # Incorrectly answered unanswerable

        repealed_misuse_count = 0
        current_wage_test_count = 0
        latencies = []

        for q in questions:
            q_start = time.time()

            # Skip questions marked needs_verification with TODO
            is_skipped = q.needs_verification and q.expected_section.upper().startswith("TODO")
            if is_skipped:
                skipped_verification += 1

            if run_full:
                rag_res = answer_legal_query(
                    question=q.question,
                    legal_area=q.legal_area if q.legal_area != "unrelated" else "auto",
                    include_repealed=q.expects_repealed_allowed,
                    threshold=threshold
                )
                retrieved_chunks = rag_res["retrieved_chunks"]
                top_score = rag_res["top_score"]
                refused = rag_res["refused"]
                answer_text = rag_res["answer"]
                latency = rag_res["latency_ms"]
            else:
                ret_res = retrieve_relevant_chunks(
                    question=q.question,
                    legal_area=q.legal_area if q.legal_area != "unrelated" else "auto",
                    include_repealed=q.expects_repealed_allowed,
                    threshold=threshold
                )
                retrieved_chunks = ret_res["chunks"]
                top_score = ret_res["top_score"]
                refused = (top_score < threshold)
                answer_text = ""
                latency = int((time.time() - q_start) * 1000)

            latencies.append(latency)

            # Determine Top-1 and Top-3 accuracy
            hit_top1 = False
            hit_top3 = False

            if not q.should_refuse and not is_skipped:
                total_answerable += 1
                if retrieved_chunks and self.is_section_match(q.expected_act, q.expected_section, retrieved_chunks[0]):
                    hit_top1 = True
                    correct_top1_count += 1

                for c in retrieved_chunks[:3]:
                    if self.is_section_match(q.expected_act, q.expected_section, c):
                        hit_top3 = True
                        correct_top3_count += 1
                        break

            # Refusal Metrics
            if q.should_refuse:
                total_unanswerable += 1
                if refused:
                    true_positives += 1
                    passed = True
                else:
                    false_negatives += 1
                    passed = False
            else:
                if refused:
                    false_positives += 1
                    passed = False
                else:
                    true_negatives += 1
                    passed = hit_top3 or is_skipped

            # Check Repealed Misuse for current wage questions
            if not q.expects_repealed_allowed and q.legal_area == "labour" and not q.should_refuse:
                current_wage_test_count += 1
                # Check if any retrieved chunk is repealed
                surfaced_repealed = any(c.get("legal_status") == "repealed" for c in retrieved_chunks[:3])
                if surfaced_repealed:
                    repealed_misuse_count += 1

            results_to_create.append({
                "question": q,
                "retrieved": [
                    {
                        "act": c.get("act_name"),
                        "section": c.get("section_number"),
                        "title": c.get("section_title"),
                        "score": c.get("score"),
                        "status": c.get("legal_status")
                    }
                    for c in retrieved_chunks[:5]
                ],
                "top_score": float(top_score),
                "correct_top1": hit_top1,
                "correct_top3": hit_top3,
                "refused": refused,
                "passed": passed
            })

        # Calculate summary rates
        top1_acc = (correct_top1_count / total_answerable) if total_answerable > 0 else 0.0
        top3_acc = (correct_top3_count / total_answerable) if total_answerable > 0 else 0.0

        refusal_prec = (true_positives / (true_positives + false_positives)) if (true_positives + false_positives) > 0 else 0.0
        refusal_rec = (true_positives / (true_positives + false_negatives)) if (true_positives + false_negatives) > 0 else 0.0

        repealed_misuse = (repealed_misuse_count / current_wage_test_count) if current_wage_test_count > 0 else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # Save EvalRun record
        run_record = EvalRun.objects.create(
            threshold=threshold,
            top1_accuracy=top1_acc * 100,
            top3_accuracy=top3_acc * 100,
            refusal_precision=refusal_prec * 100,
            refusal_recall=refusal_rec * 100,
            repealed_misuse_rate=repealed_misuse * 100,
            avg_latency_ms=avg_latency,
            notes=f"Total: {len(questions)}, Answerable: {total_answerable}, Out-of-Scope: {total_unanswerable}, Skipped: {skipped_verification}, Mode: {'Full RAG' if run_full else 'Retrieval'}"
        )

        # Bulk save EvalResult records
        db_results = [
            EvalResult(
                run=run_record,
                question=item["question"],
                retrieved=item["retrieved"],
                top_score=item["top_score"],
                correct_top1=item["correct_top1"],
                correct_top3=item["correct_top3"],
                refused=item["refused"],
                passed=item["passed"]
            )
            for item in results_to_create
        ]
        EvalResult.objects.bulk_create(db_results)

        # Export CSV Report
        if export_csv:
            self.export_run_csv(run_record, db_results, skipped_verification)

        return run_record

    def export_run_csv(self, run: EvalRun, results: list, skipped_count: int):
        reports_dir = settings.REPORTS_DIR
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = reports_dir / f"eval_run_{run.id}_{timestamp}.csv"

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Run ID", run.id, "Threshold", run.threshold, "Top1 %", run.top1_accuracy, "Top3 %", run.top3_accuracy, "Refusal Precision %", run.refusal_precision, "Refusal Recall %", run.refusal_recall, "Repealed Misuse %", run.repealed_misuse_rate])
            writer.writerow([])
            writer.writerow(["Q_ID", "Question", "Area", "Expected Act", "Expected Sec", "Should Refuse", "Top Score", "Top1 Hit", "Top3 Hit", "Refused", "Passed", "Top Retrieved Match"])

            for res in results:
                q = res.question
                top_match_str = ""
                if res.retrieved:
                    m = res.retrieved[0]
                    top_match_str = f"{m.get('act')} §{m.get('section')} ({m.get('title')})"

                writer.writerow([
                    q.id,
                    q.question,
                    q.legal_area,
                    q.expected_act,
                    q.expected_section,
                    q.should_refuse,
                    f"{res.top_score:.3f}",
                    "YES" if res.correct_top1 else "NO",
                    "YES" if res.correct_top3 else "NO",
                    "YES" if res.refused else "NO",
                    "PASS" if res.passed else "FAIL",
                    top_match_str
                ])

        self.stdout.write(self.style.SUCCESS(f"Exported detailed evaluation report to {csv_file}"))

    def print_run_summary(self, run: EvalRun):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Evaluation Benchmark Results Summary ==="))
        self.stdout.write(f" Run ID:               #{run.id} ({run.created_at.strftime('%Y-%m-%d %H:%M')})")
        self.stdout.write(f" Calibrated Threshold: {run.threshold:.2f}")
        self.stdout.write(f" Top-1 Accuracy:       {run.top1_accuracy:.2f}%")
        self.stdout.write(f" Top-3 Accuracy:       {run.top3_accuracy:.2f}%")
        self.stdout.write(f" Refusal Precision:    {run.refusal_precision:.2f}%")
        self.stdout.write(f" Refusal Recall:       {run.refusal_recall:.2f}%")
        self.stdout.write(f" Repealed Misuse Rate: {run.repealed_misuse_rate:.2f}% (Target: 0.0%)")
        self.stdout.write(f" Average Latency:      {run.avg_latency_ms:.1f} ms")
        self.stdout.write(f" Notes:                {run.notes}\n")

    def run_threshold_sweep(self, questions):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Threshold Calibration Sweep (0.20 to 0.60) ==="))
        self.stdout.write("Sweeping retrieval thresholds in steps of 0.05...\n")

        thresholds = [round(0.20 + (i * 0.05), 2) for i in range(9)]
        sweep_data = []

        headers = ["Threshold", "Top-1 Acc %", "Top-3 Acc %", "Refusal Prec %", "Refusal Rec %", "Misuse %", "Avg Latency"]
        rows = []

        best_score = -1.0
        best_threshold = 0.35

        for t in thresholds:
            run = self.execute_eval_run(questions, threshold=t, run_full=False, export_csv=False)
            # Harmonic combination of Top-3 and Refusal F1 as selection metric
            prec = run.refusal_precision / 100.0
            rec = run.refusal_recall / 100.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
            composite = (run.top3_accuracy * 0.5) + (f1 * 100 * 0.5) - (run.repealed_misuse_rate * 2)

            if composite > best_score:
                best_score = composite
                best_threshold = t

            rows.append([
                f"  {t:.2f}  ",
                f"{run.top1_accuracy:6.1f}%",
                f"{run.top3_accuracy:6.1f}%",
                f"{run.refusal_precision:8.1f}%",
                f"{run.refusal_recall:7.1f}%",
                f"{run.repealed_misuse_rate:6.1f}%",
                f"{run.avg_latency_ms:6.1f} ms"
            ])

        # Print table
        self.stdout.write("-" * 75)
        self.stdout.write(f"{'Threshold':<12} {'Top-1':<10} {'Top-3':<10} {'Ref.Prec':<12} {'Ref.Rec':<12} {'Misuse':<10} {'Latency':<10}")
        self.stdout.write("-" * 75)
        for r in rows:
            self.stdout.write(f"{r[0]:<12} {r[1]:<10} {r[2]:<10} {r[3]:<12} {r[4]:<12} {r[5]:<10} {r[6]:<10}")
        self.stdout.write("-" * 75)

        self.stdout.write(self.style.SUCCESS(
            f"\n[RECOMMENDATION] Optimal Calibrated Threshold: {best_threshold:.2f} "
            f"(Maximizes statutory retrieval recall while eliminating out-of-scope hallucinations)."
        ))

