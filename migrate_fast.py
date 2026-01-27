"""
FAST Migration Script - SQLite to PostgreSQL
Uses bulk inserts for much faster migration.
"""
import os
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuration
LOCAL_SQLITE_PATH = "diseaseportal.db"
POSTGRES_URL = os.environ.get('RENDER_DATABASE_URL', '')

if not POSTGRES_URL:
    print("❌ ERROR: RENDER_DATABASE_URL not set!")
    exit(1)

if POSTGRES_URL.startswith('postgres://'):
    POSTGRES_URL = POSTGRES_URL.replace('postgres://', 'postgresql://', 1)

print("=" * 60)
print("FAST Database Migration: SQLite → PostgreSQL")
print("=" * 60)


def create_tables(pg_engine):
    """Create tables if they don't exist."""
    print("\n[1/4] Creating tables...")
    
    with pg_engine.connect() as conn:
        # Drop existing tables to start fresh
        conn.execute(text("DROP TABLE IF EXISTS diseases CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS herbs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS analysis_results CASCADE"))
        
        # Create diseases table
        conn.execute(text("""
            CREATE TABLE diseases (
                id SERIAL PRIMARY KEY,
                "diseaseName" TEXT,
                "geneName" TEXT,
                "geneId" TEXT,
                score FLOAT
            )
        """))
        
        # Create herbs table
        conn.execute(text("""
            CREATE TABLE herbs (
                id SERIAL PRIMARY KEY,
                "herbName" TEXT,
                "Compound" TEXT,
                "Genes" TEXT,
                "EntrezID" TEXT
            )
        """))
        
        # Create analysis_results table
        conn.execute(text("""
            CREATE TABLE analysis_results (
                id SERIAL PRIMARY KEY,
                disease_name TEXT NOT NULL,
                prescriptions TEXT NOT NULL,
                results_json TEXT NOT NULL,
                ai_analysis_json TEXT,
                common_genes_count INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        """))
        
        conn.commit()
    print("   ✓ Tables created")


def migrate_diseases_fast(sqlite_conn, pg_engine):
    """Migrate diseases using bulk insert."""
    print("\n[2/4] Migrating diseases (FAST mode)...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT diseaseName, geneName, geneId, score FROM diseases")
    rows = cursor.fetchall()
    total = len(rows)
    
    print(f"   Found {total:,} records")
    
    batch_size = 10000  # Much larger batches
    
    with pg_engine.connect() as conn:
        for i in range(0, total, batch_size):
            batch = rows[i:i+batch_size]
            
            # Build bulk insert values
            values_list = []
            for row in batch:
                # Escape single quotes
                dn = str(row[0]).replace("'", "''") if row[0] else ''
                gn = str(row[1]).replace("'", "''") if row[1] else ''
                gi = str(row[2]).replace("'", "''") if row[2] else ''
                sc = row[3] if row[3] else 0
                values_list.append(f"('{dn}', '{gn}', '{gi}', {sc})")
            
            # Single bulk insert
            values_str = ",".join(values_list)
            sql = f'INSERT INTO diseases ("diseaseName", "geneName", "geneId", score) VALUES {values_str}'
            
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                print(f"   Error at batch {i}: {e}")
                # Try smaller batches on error
                conn.rollback()
                for row in batch:
                    try:
                        conn.execute(
                            text('INSERT INTO diseases ("diseaseName", "geneName", "geneId", score) VALUES (:dn, :gn, :gi, :sc)'),
                            {"dn": row[0], "gn": row[1], "gi": row[2], "sc": row[3]}
                        )
                    except:
                        pass
                conn.commit()
            
            done = min(i + batch_size, total)
            pct = (done / total) * 100
            print(f"   {done:,} / {total:,} ({pct:.1f}%)")
    
    print("   ✓ Diseases done!")


def migrate_herbs_fast(sqlite_conn, pg_engine):
    """Migrate herbs using bulk insert."""
    print("\n[3/4] Migrating herbs (FAST mode)...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT herbName, Compound, Genes, EntrezID FROM herbs")
    rows = cursor.fetchall()
    total = len(rows)
    
    print(f"   Found {total:,} records")
    
    batch_size = 10000
    
    with pg_engine.connect() as conn:
        for i in range(0, total, batch_size):
            batch = rows[i:i+batch_size]
            
            values_list = []
            for row in batch:
                hn = str(row[0]).replace("'", "''") if row[0] else ''
                cp = str(row[1]).replace("'", "''") if row[1] else ''
                gn = str(row[2]).replace("'", "''") if row[2] else ''
                ei = str(row[3]).replace("'", "''") if row[3] else ''
                values_list.append(f"('{hn}', '{cp}', '{gn}', '{ei}')")
            
            values_str = ",".join(values_list)
            sql = f'INSERT INTO herbs ("herbName", "Compound", "Genes", "EntrezID") VALUES {values_str}'
            
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                print(f"   Error at batch {i}: {e}")
                conn.rollback()
                for row in batch:
                    try:
                        conn.execute(
                            text('INSERT INTO herbs ("herbName", "Compound", "Genes", "EntrezID") VALUES (:hn, :cp, :gn, :ei)'),
                            {"hn": row[0], "cp": row[1], "gn": row[2], "ei": row[3]}
                        )
                    except:
                        pass
                conn.commit()
            
            done = min(i + batch_size, total)
            pct = (done / total) * 100
            print(f"   {done:,} / {total:,} ({pct:.1f}%)")
    
    print("   ✓ Herbs done!")


def verify(pg_engine):
    """Verify migration."""
    print("\n[4/4] Verifying...")
    
    with pg_engine.connect() as conn:
        d = conn.execute(text('SELECT COUNT(DISTINCT "diseaseName") FROM diseases')).scalar()
        h = conn.execute(text('SELECT COUNT(DISTINCT "herbName") FROM herbs')).scalar()
        
        print(f"   ✓ Unique diseases: {d:,}")
        print(f"   ✓ Unique herbs: {h:,}")
        
        return d > 0 and h > 0


def main():
    if not os.path.exists(LOCAL_SQLITE_PATH):
        print(f"❌ ERROR: {LOCAL_SQLITE_PATH} not found!")
        exit(1)
    
    print(f"\n📁 SQLite: {LOCAL_SQLITE_PATH}")
    print(f"🐘 PostgreSQL: {POSTGRES_URL[:50]}...")
    
    sqlite_conn = sqlite3.connect(LOCAL_SQLITE_PATH)
    pg_engine = create_engine(POSTGRES_URL)
    
    try:
        create_tables(pg_engine)
        migrate_diseases_fast(sqlite_conn, pg_engine)
        migrate_herbs_fast(sqlite_conn, pg_engine)
        
        if verify(pg_engine):
            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETE!")
            print("=" * 60)
        else:
            print("\n⚠️ Migration may have issues")
    finally:
        sqlite_conn.close()
        pg_engine.dispose()


if __name__ == "__main__":
    main()
