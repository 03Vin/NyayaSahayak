"""
Management command to verify project setup, statutory data files,
FAISS index, embedding model, database records, and Gemini API configuration.
Usage:
    python manage.py check_setup
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
import numpy as np

from legal_data.models import LegalChunk
from legal_data.services.index_loader import get_faiss_index_and_metadata, get_embedding_model


class Command(BaseCommand):
    help = "Validates statutory data files, act_status.json, FAISS index, database chunks, and Gemini API config."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== NyayaSahayak System & Data Setup Verification ==="))
        all_passed = True

        # 1. Check act_status.json
        status_file = settings.ACTS_DIR / "act_status.json"
        if status_file.exists():
            self.stdout.write(self.style.SUCCESS(f" [PASS] act_status.json located ({status_file})"))
        else:
            self.stdout.write(self.style.ERROR(f" [FAIL] act_status.json NOT found at {status_file}"))
            all_passed = False

        # 2. Check Database records
        chunk_count = LegalChunk.objects.count()
        if chunk_count > 0:
            self.stdout.write(self.style.SUCCESS(f" [PASS] Database contains {chunk_count} LegalChunk records."))
            # Print breakdown
            for area in ['consumer', 'tenancy', 'labour']:
                cnt = LegalChunk.objects.filter(legal_area=area).count()
                self.stdout.write(f"        • {area.title()}: {cnt} chunks")
        else:
            self.stdout.write(self.style.ERROR(" [FAIL] No LegalChunk records found in database! Run 'python manage.py ingest_acts'."))
            all_passed = False

        # 3. Check FAISS index & metadata
        index, meta = get_faiss_index_and_metadata()
        if index is not None and len(meta) > 0:
            self.stdout.write(self.style.SUCCESS(f" [PASS] FAISS index loaded ({index.ntotal} vectors, {len(meta)} metadata entries)."))

            # Quick search test
            try:
                model = get_embedding_model()
                import faiss
                test_q = "security deposit refund after vacating flat"
                q_vec = model.encode([test_q], convert_to_numpy=True)
                faiss.normalize_L2(q_vec)
                scores, idxs = index.search(q_vec.astype(np.float32), 2)
                top_match = meta[idxs[0][0]]
                self.stdout.write(self.style.SUCCESS(
                    f" [PASS] Sample vector retrieval verified! Top match: '{top_match['act_name']}' Section {top_match['section_number']} (Score: {scores[0][0]:.3f})"
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f" [FAIL] Vector retrieval test failed: {e}"))
                all_passed = False
        else:
            self.stdout.write(self.style.ERROR(" [FAIL] FAISS index or metadata not found at data/index/!"))
            all_passed = False

        # 4. Check LLM Configuration
        api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        model_name = getattr(settings, 'GEMINI_MODEL', '') or os.getenv('GEMINI_MODEL', '')

        if api_key and api_key != 'your_actual_gemini_api_key_here':
            masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
            self.stdout.write(self.style.SUCCESS(f" [PASS] GEMINI_API_KEY configured ({masked_key})"))
        else:
            self.stdout.write(self.style.WARNING(" [WARN] GEMINI_API_KEY is not set or is empty in .env. LLM generation will be unavailable."))

        if model_name:
            self.stdout.write(self.style.SUCCESS(f" [PASS] GEMINI_MODEL set to '{model_name}'"))
        else:
            self.stdout.write(self.style.WARNING(" [WARN] GEMINI_MODEL not set (defaulting to gemini-2.5-flash)."))

        # 5. Check WAGES_CODE_COMMENCEMENT
        commence = getattr(settings, 'WAGES_CODE_COMMENCEMENT', None)
        if commence == '2025-11-21':
            self.stdout.write(self.style.SUCCESS(f" [PASS] WAGES_CODE_COMMENCEMENT set to {commence}"))
        else:
            self.stdout.write(self.style.ERROR(f" [FAIL] WAGES_CODE_COMMENCEMENT must be '2025-11-21', got: {commence}"))
            all_passed = False

        self.stdout.write("\n" + "=" * 55)
        if all_passed:
            self.stdout.write(self.style.SUCCESS("All required components and index structures are ready!"))
        else:
            self.stdout.write(self.style.WARNING("Some checks require attention. See details above."))

