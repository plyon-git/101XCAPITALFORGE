#!/usr/bin/env python3
"""Rebuild the included factual research snapshot without fetching new sources."""
import json
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=root/'data/source_cohorts'
manifest=json.loads((source/'manifest.json').read_text())
subprocess.run([sys.executable,str(root/'scripts/merge_sec_brochures.py'),str(source/'sec_leads.jsonl'),str(source/'sec_brochure_leads.jsonl'),str(source/'sec_brochure_frontend_FINAL.jsonl'),'--out',str(source/'sec_enriched_final.jsonl')],check=True)
subprocess.run([sys.executable,str(root/'scripts/assemble_directory.py'),*[str(source/name) for name in manifest['assembly_inputs']],'--out',str(root/'data')],check=True)
