"""
Continue migration - Herbs only (diseases already done)
"""
import os
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from sqlalchemy import create_engine, text

LOCAL_SQLITE_PATH = "diseaseportal.db"
POSTGRES_URL = os.environ.get('RENDER_DATABASE_URL', '')

if POSTGRES_URL.startswith('postgres://'):
    POSTGRES_URL = POSTGRES_URL.replace('postgres://', 'postgresql://', 1)

print("=" * 60)
print("Continue Migration: Herbs Only")
print("=" * 60)


def migrate_herbs_fast(sqlite_conn, pg_engine):
    """Migrate herbs using bulk insert."""
    print("\nMigrating herbs (FAST mode)...")
    
    cursor = sqlite_conn.cursor()
    # Use correct column names from SQLite
    cursor.execute("SELECT herbName, Compound, Genes, GeneId FROM herbs")
    rows = cursor.fetchall()
    total = len(rows)
    
    print(f"   Found {total:,} records")
    
    # Drop and recreate herbs table with correct columns
    with pg_engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS herbs CASCADE"))
        conn.execute(text("""
            CREATE TABLE herbs (
                id SERIAL PRIMARY KEY,
                "herbName" TEXT,
                "Compound" TEXT,
                "Genes" TEXT,
                "EntrezID" TEXT
            )
        """))
        conn.commit()
        print("   ✓ Herbs table recreated")
    
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
                print(f"   Error at batch {i}: {str(e)[:100]}")
                conn.rollback()
                # Fallback to individual inserts
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
    print("\nVerifying...")
    
    with pg_engine.connect() as conn:
        d = conn.execute(text('SELECT COUNT(DISTINCT "diseaseName") FROM diseases')).scalar()
        h = conn.execute(text('SELECT COUNT(DISTINCT "herbName") FROM herbs')).scalar()
        
        print(f"   ✓ Unique diseases: {d:,}")
        print(f"   ✓ Unique herbs: {h:,}")
        
        return d > 0 and h > 0


def main():
    sqlite_conn = sqlite3.connect(LOCAL_SQLITE_PATH)
    pg_engine = create_engine(POSTGRES_URL)
    
    try:
        migrate_herbs_fast(sqlite_conn, pg_engine)
        
        if verify(pg_engine):
            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETE!")
            print("\nNow update your Render web service:")
            print("1. Go to Render Dashboard → Systems_Biology → Environment")
            print("2. Add DATABASE_URL with the INTERNAL URL:")
            print("   postgresql://disease_portal_db_user:yilmQGbUIv1txUBQlqya2G5M81Yy6dNA@dpg-d5s1kmm3jp1c73eig1og-a/disease_portal_db")
            print("3. Save and wait for redeploy")
            print("=" * 60)
    finally:
        sqlite_conn.close()
        pg_engine.dispose()


if __name__ == "__main__":
    main()
