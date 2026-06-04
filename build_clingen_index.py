#!/usr/bin/env python3
"""
Build a local ClinGen Gene-Disease Validity table.

ClinGen provides expert-curated, clinical-grade gene-disease validity
classifications (Definitive / Strong / Moderate / Limited / Disputed / Refuted).
The app overlays these onto the disease-relevant ("common") genes so the AI can
prioritise clinically-validated targets. Downloaded once into a local
`clingen_validity` table; re-run to refresh.

Run:  python build_clingen_index.py [--force]
"""
import os
import sys
import csv
import io

import requests
from sqlalchemy import create_engine, text, inspect
from config import Config

URL = "https://search.clinicalgenome.org/kb/gene-validity/download"
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)


def _count():
    if "clingen_validity" not in inspect(engine).get_table_names():
        return 0
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM clingen_validity")).scalar() or 0


def build(force=False):
    existing = _count()
    if existing > 0 and not force:
        print(f"[clingen] already populated ({existing} rows). Use --force to rebuild.")
        return existing

    print("[clingen] downloading ClinGen gene-validity CSV...")
    r = requests.get(URL, timeout=120, verify=Config.EXTERNAL_API_VERIFY_SSL)
    r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.text)))

    # Find the column-header row, then read the data rows after it.
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == "GENE SYMBOL":
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("ClinGen header row not found in CSV")

    data = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) < 7:
            continue
        if row[0].strip().startswith("+++"):  # separator lines
            continue
        gene = row[0].strip()
        disease = row[2].strip()
        mondo = row[3].strip().replace(":", "_")   # MONDO:0007179 -> MONDO_0007179
        classification = row[6].strip()
        moi = row[4].strip()
        if gene and classification:
            data.append((gene, disease, mondo, classification, moi))

    print(f"[clingen] parsed {len(data)} gene-disease validity classifications")

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS clingen_validity"))
        conn.execute(text(
            "CREATE TABLE clingen_validity "
            "(gene TEXT, disease TEXT, mondo_id TEXT, classification TEXT, moi TEXT)"
        ))
        conn.execute(
            text("INSERT INTO clingen_validity (gene, disease, mondo_id, classification, moi) "
                 "VALUES (:g, :d, :m, :c, :i)"),
            [{"g": g, "d": d, "m": m, "c": c, "i": i} for g, d, m, c, i in data],
        )
        conn.execute(text("CREATE INDEX idx_clingen_gene ON clingen_validity(gene)"))

    count = _count()
    print(f"[clingen] done. clingen_validity has {count} rows.")
    return count


if __name__ == "__main__":
    build(force="--force" in sys.argv)
