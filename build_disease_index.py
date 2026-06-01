#!/usr/bin/env python3
"""
Build a local index of ALL Open Targets diseases.

The Open Targets GraphQL API can only *search* diseases, never list them all,
so to browse the full catalogue the Database Explorer reads from a local
`diseases` table. This script downloads Open Targets' disease.parquet (~7 MB)
once and loads id + name into that table.

Disease GENES are still fetched live at analysis time -- this table is only the
browsable name/ID list. Re-run after a new Open Targets release to refresh.
Safe to run repeatedly: it skips when already populated (use --force to rebuild).
"""
import os
import sys
import subprocess

from sqlalchemy import create_engine, text, inspect
from config import Config

DISEASE_PARQUET_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/"
    "latest/output/disease/disease.parquet"
)
LOCAL_PARQUET = os.path.join(os.path.dirname(__file__), "disease.parquet")

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)


def _table_count():
    if "diseases" not in inspect(engine).get_table_names():
        return 0
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM diseases")).scalar() or 0


def _ensure_pyarrow():
    try:
        import pyarrow.parquet  # noqa: F401
    except ImportError:
        print("[build] Installing pyarrow (one-time, to read the parquet)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pyarrow"])


def _download_parquet():
    import requests
    print("[build] Downloading disease list from Open Targets...")
    r = requests.get(DISEASE_PARQUET_URL, stream=True, timeout=180,
                     verify=Config.EXTERNAL_API_VERIFY_SSL)
    r.raise_for_status()
    with open(LOCAL_PARQUET, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            if chunk:
                f.write(chunk)
    print(f"[build] Downloaded {os.path.getsize(LOCAL_PARQUET) / 1e6:.1f} MB")


# OT's "disease" dataset also contains biological attributes (OBA), gene-ontology
# processes (GO), phenotypic qualities (PATO), etc. Keep only the real
# disease/phenotype ontologies, and drop lab measurement/ratio traits.
ALLOWED_PREFIXES = ("MONDO_", "Orphanet_", "EFO_", "HP_", "DOID_", "NCIT_")
DROP_NAME_SUFFIXES = (" measurement", " measurements", " ratio", " levels")


def _is_disease(efo_id, name):
    if not efo_id.startswith(ALLOWED_PREFIXES):
        return False
    low = name.lower()
    if low.endswith(DROP_NAME_SUFFIXES):
        return False
    return True


def _read_diseases():
    import pyarrow.parquet as pq
    cols = set(pq.read_schema(LOCAL_PARQUET).names)
    if "id" not in cols or "name" not in cols:
        raise RuntimeError(f"Unexpected parquet schema; columns={sorted(cols)}")
    table = pq.read_table(LOCAL_PARQUET, columns=["id", "name"])
    ids = table.column("id").to_pylist()
    names = table.column("name").to_pylist()
    # filter to real diseases/phenotypes and dedupe by id (cross-DB safe INSERT)
    by_id = {i: n for i, n in zip(ids, names) if i and n and _is_disease(i, n)}
    return list(by_id.items())


def build(force=False):
    existing = _table_count()
    if existing > 0 and not force:
        print(f"[build] diseases table already populated ({existing} rows). Use --force to rebuild.")
        return existing

    _ensure_pyarrow()
    if not os.path.exists(LOCAL_PARQUET):
        _download_parquet()

    rows = _read_diseases()
    print(f"[build] Parsed {len(rows)} diseases. Writing to the database...")

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS diseases"))
        conn.execute(text("CREATE TABLE diseases (efo_id TEXT PRIMARY KEY, name TEXT NOT NULL)"))
        conn.execute(
            text("INSERT INTO diseases (efo_id, name) VALUES (:efo_id, :name)"),
            [{"efo_id": i, "name": n} for i, n in rows],
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_diseases_name ON diseases (name)"))

    count = _table_count()

    # Record provenance (for the version footer + staleness check).
    import datetime
    try:
        from opentargets_service import get_open_targets_version
        ot_version = get_open_targets_version() or ""
    except Exception:
        ot_version = ""
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS data_meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
        ))
        for k, v in [
            ("disease_catalogue_count", str(count)),
            ("disease_catalogue_ot_version", ot_version),
            ("disease_catalogue_built", now),
        ]:
            conn.execute(text("DELETE FROM data_meta WHERE key = :k"), {"k": k})
            conn.execute(
                text("INSERT INTO data_meta (key, value, updated_at) VALUES (:k, :v, :u)"),
                {"k": k, "v": v, "u": now},
            )

    print(f"[build] Done. diseases table now has {count} rows (Open Targets {ot_version or '?'}).")
    try:
        os.remove(LOCAL_PARQUET)  # don't leave the 7 MB file lying around
    except OSError:
        pass
    return count


if __name__ == "__main__":
    build(force="--force" in sys.argv)
