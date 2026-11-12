"""
Management command to ingest, section-chunk, embed, and index Indian legal acts.
Usage:
    python manage.py ingest_acts [--dry-run] [--force]
"""

import json
import logging
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from legal_data.models import LegalChunk
from legal_data.services.ingest import (
    extract_text_from_file,
    clean_statute_text,
    chunk_statute_by_sections,
    build_faiss_index
)
from legal_data.services.index_loader import reload_index

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingests legal acts from /data/acts/<area>/, extracts sections, and builds the FAISS index."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Extract and display section counts without generating embeddings or saving to database/index.'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-ingestion and rebuild of FAISS index even if existing chunks are present.'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)

        acts_dir = settings.ACTS_DIR
        status_file = acts_dir / "act_status.json"

        self.stdout.write(self.style.MIGRATE_HEADING("=== NyayaSahayak Legal Data Ingestion Pipeline ==="))

        if not status_file.exists():
            raise CommandError(
                f"Missing status registry: {status_file} not found! "
                "act_status.json is mandatory to register enforceability status."
            )

        with open(status_file, "r", encoding="utf-8") as f:
            try:
                status_registry = json.load(f)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in {status_file}: {e}")

        # Find all .pdf and .txt files in consumer, tenancy, labour
        supported_areas = ['consumer', 'tenancy', 'labour']
        found_files = []

        for area in supported_areas:
            area_dir = acts_dir / area
            if area_dir.exists():
                for ext in ('*.pdf', '*.txt', '*.text'):
                    for file_path in area_dir.glob(ext):
                        found_files.append((area, file_path))

        if not found_files:
            self.stdout.write(self.style.WARNING(
                "\n[!] No legal text or PDF files found under data/acts/!\n"
                "Please download official acts from indiacode.nic.in and place them as follows:\n"
                "  - data/acts/consumer/consumer_protection_act_2019.pdf (or .txt)\n"
                "  - data/acts/tenancy/model_tenancy_act_2021.pdf (or .txt)\n"
                "  - data/acts/labour/code_on_wages_2019.pdf (or .txt)\n"
                "  - data/acts/labour/payment_of_wages_act_1936.pdf (or .txt)\n"
                "  - data/acts/labour/minimum_wages_act_1948.pdf (or .txt)\n"
                "\nRefer to data/acts/README.md for exact links and details."
            ))
            return

        self.stdout.write(f"Discovered {len(found_files)} statutory file(s) across {supported_areas}.")

        # Verify every file has an entry in act_status.json (fail loudly if missing)
        all_chunks = []
        act_summary = {}

        for area, file_path in found_files:
            # Check keys: "area/filename", "filename", or posix path
            rel_path = f"{area}/{file_path.name}".replace('\\', '/')
            meta = status_registry.get(rel_path) or status_registry.get(file_path.name)

            if not meta:
                raise CommandError(
                    f"FATAL: Source file '{rel_path}' is NOT registered in act_status.json! "
                    "All statutory files must have explicit legal_status and enforceability metadata."
                )

            act_name = meta.get("act_name")
            act_year = meta.get("act_year")
            legal_status = meta.get("legal_status")
            repealed_on = meta.get("repealed_on")
            superseded_by = meta.get("superseded_by")
            notes = meta.get("notes", "")

            if legal_status not in ("in_force", "repealed"):
                raise CommandError(
                    f"Invalid legal_status '{legal_status}' for {rel_path}. Must be 'in_force' or 'repealed'."
                )

            self.stdout.write(f"-> Processing [{area.upper()}] {act_name} ({file_path.name})...")

            try:
                raw_text = extract_text_from_file(file_path)
            except Exception as e:
                raise CommandError(f"Failed to read/parse {file_path}: {e}")

            cleaned_text = clean_statute_text(raw_text)

            # Generate slug for chunk IDs
            act_slug = f"{area}_{act_year}_" + "".join(c if c.isalnum() else "_" for c in act_name.lower())[:20].strip("_")

            base_meta = {
                "act_name": act_name,
                "act_year": act_year,
                "legal_area": area,
                "legal_status": legal_status,
                "repealed_on": repealed_on,
                "superseded_by": superseded_by,
                "source_file": rel_path,
                "notes": notes,
            }

            chunks = chunk_statute_by_sections(cleaned_text, base_meta, act_slug)
            num_sections = len(chunks)

            # Suspicious section count check
            if num_sections < 20:
                self.stdout.write(self.style.WARNING(
                    f"   [WARNING] Suspiciously low section count ({num_sections}) for '{act_name}'! "
                    "Check PDF formatting, OCR quality, or section regex."
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"   [OK] Extracted {num_sections} section chunks for '{act_name}'."
                ))

            act_summary[act_name] = {
                "sections": num_sections,
                "status": legal_status,
                "area": area,
                "source": rel_path
            }
            all_chunks.extend(chunks)

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Ingestion Summary ==="))
        for act, data in act_summary.items():
            self.stdout.write(f" • {act}: {data['sections']} chunks [{data['status'].upper()}] ({data['source']})")
        self.stdout.write(f"Total Chunks Extracted: {len(all_chunks)}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n[DRY RUN COMPLETE] No database or FAISS index modifications made."))
            return

        # Save to Database (LegalChunk model)
        self.stdout.write("\nWriting chunks to database (LegalChunk model)...")
        with transaction.atomic():
            LegalChunk.objects.all().delete()
            db_objs = [
                LegalChunk(
                    act_name=c["act_name"],
                    act_year=c["act_year"],
                    legal_area=c["legal_area"],
                    legal_status=c["legal_status"],
                    repealed_on=c["repealed_on"] if c.get("repealed_on") else None,
                    superseded_by=c.get("superseded_by"),
                    section_number=c["section_number"],
                    section_title=c.get("section_title", "")[:250],
                    text=c["text"],
                    chunk_id=c["chunk_id"],
                    source_file=c["source_file"]
                )
                for c in all_chunks
            ]
            LegalChunk.objects.bulk_create(db_objs, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"Saved {len(db_objs)} records in database."))

        # Build FAISS Index and persist metadata
        self.stdout.write("Generating multilingual embeddings and building FAISS index...")
        total_vectors, index_file, meta_file = build_faiss_index(all_chunks, settings.INDEX_DIR)

        # Reload index singleton in memory
        reload_index()

        self.stdout.write(self.style.SUCCESS(
            f"\n[SUCCESS] Ingestion complete!\n"
            f"FAISS Index: {index_file} ({total_vectors} vectors)\n"
            f"Metadata: {meta_file}\n"
        ))
