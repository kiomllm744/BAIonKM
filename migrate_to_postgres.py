"""
Script to migrate data from local SQLite to Render PostgreSQL.
Run this locally to populate the PostgreSQL database with diseases and herbs data.
"""
import os
from dotenv import load_dotenv
load_dotenv()

import sqlite3
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import sessionmaker

# Configuration
LOCAL_SQLITE_PATH = "diseaseportal.db"  # Your local SQLite database

# Get PostgreSQL URL from environment or paste it directly here
# IMPORTANT: Replace this with your actual Render PostgreSQL Internal URL
POSTGRES_URL = os.environ.get('RENDER_DATABASE_URL', '')

# If not set in environment, you can paste it here temporarily:
# POSTGRES_URL = "postgresql://user:password@host/database"

if not POSTGRES_URL:
    print("❌ ERROR: RENDER_DATABASE_URL not set!")
    print("\nPlease either:")
    print("1. Set RENDER_DATABASE_URL in your .env file")
    print("2. Or paste your Render PostgreSQL Internal URL directly in this script")
    print("\nYour Internal Database URL looks like:")
    print("   postgres://diseaseportal_user:xxxxx@dpg-xxxxx.render.com/diseaseportal")
    exit(1)

# Fix postgres:// to postgresql:// for SQLAlchemy
if POSTGRES_URL.startswith('postgres://'):
    POSTGRES_URL = POSTGRES_URL.replace('postgres://', 'postgresql://', 1)

print("=" * 60)
print("Database Migration: SQLite → PostgreSQL")
print("=" * 60)


def create_tables_in_postgres(pg_engine):
    """Create the necessary tables in PostgreSQL."""
    print("\n[1/4] Creating tables in PostgreSQL...")
    
    metadata = MetaData()
    
    # Diseases table
    diseases = Table(
        'diseases', metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('diseaseName', Text),
        Column('geneName', Text),
        Column('geneId', Text),
        Column('score', Float)
    )
    
    # Herbs table  
    herbs = Table(
        'herbs', metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('herbName', Text),
        Column('Compound', Text),
        Column('Genes', Text),
        Column('EntrezID', Text)
    )
    
    # Analysis results table
    analysis_results = Table(
        'analysis_results', metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('disease_name', Text, nullable=False),
        Column('prescriptions', Text, nullable=False),
        Column('results_json', Text, nullable=False),
        Column('ai_analysis_json', Text, nullable=True),
        Column('common_genes_count', Integer, default=0),
        Column('created_at', DateTime)
    )
    
    metadata.create_all(pg_engine)
    print("   ✓ Tables created successfully")


def migrate_diseases(sqlite_conn, pg_engine):
    """Migrate diseases data from SQLite to PostgreSQL."""
    print("\n[2/4] Migrating diseases data...")
    
    # Read from SQLite
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT diseaseName, geneName, geneId, score FROM diseases")
    rows = cursor.fetchall()
    
    print(f"   Found {len(rows):,} disease records to migrate")
    
    if len(rows) == 0:
        print("   ⚠️  No disease data found in local SQLite!")
        return
    
    # Insert into PostgreSQL in batches
    pg_session = sessionmaker(bind=pg_engine)()
    batch_size = 5000
    
    try:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            
            # Use raw SQL for faster insertion
            for row in batch:
                pg_session.execute(
                    text("INSERT INTO diseases (\"diseaseName\", \"geneName\", \"geneId\", score) VALUES (:dn, :gn, :gi, :sc)"),
                    {"dn": row[0], "gn": row[1], "gi": row[2], "sc": row[3]}
                )
            
            pg_session.commit()
            print(f"   Migrated {min(i+batch_size, len(rows)):,} / {len(rows):,} records...")
        
        print(f"   ✓ Diseases migration complete!")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        pg_session.rollback()
    finally:
        pg_session.close()


def migrate_herbs(sqlite_conn, pg_engine):
    """Migrate herbs data from SQLite to PostgreSQL."""
    print("\n[3/4] Migrating herbs data...")
    
    # Read from SQLite
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT herbName, Compound, Genes, EntrezID FROM herbs")
    rows = cursor.fetchall()
    
    print(f"   Found {len(rows):,} herb records to migrate")
    
    if len(rows) == 0:
        print("   ⚠️  No herb data found in local SQLite!")
        return
    
    # Insert into PostgreSQL in batches
    pg_session = sessionmaker(bind=pg_engine)()
    batch_size = 5000
    
    try:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            
            for row in batch:
                pg_session.execute(
                    text("INSERT INTO herbs (\"herbName\", \"Compound\", \"Genes\", \"EntrezID\") VALUES (:hn, :cp, :gn, :ei)"),
                    {"hn": row[0], "cp": row[1], "gn": row[2], "ei": row[3]}
                )
            
            pg_session.commit()
            print(f"   Migrated {min(i+batch_size, len(rows)):,} / {len(rows):,} records...")
        
        print(f"   ✓ Herbs migration complete!")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        pg_session.rollback()
    finally:
        pg_session.close()


def verify_migration(pg_engine):
    """Verify the migration was successful."""
    print("\n[4/4] Verifying migration...")
    
    pg_session = sessionmaker(bind=pg_engine)()
    
    try:
        # Count diseases
        result = pg_session.execute(text("SELECT COUNT(DISTINCT \"diseaseName\") FROM diseases"))
        disease_count = result.scalar()
        
        # Count herbs
        result = pg_session.execute(text("SELECT COUNT(DISTINCT \"herbName\") FROM herbs"))
        herb_count = result.scalar()
        
        print(f"   ✓ Diseases in PostgreSQL: {disease_count:,}")
        print(f"   ✓ Herbs in PostgreSQL: {herb_count:,}")
        
        return disease_count > 0 and herb_count > 0
    finally:
        pg_session.close()


def main():
    # Check if local SQLite exists
    if not os.path.exists(LOCAL_SQLITE_PATH):
        print(f"❌ ERROR: Local SQLite database not found: {LOCAL_SQLITE_PATH}")
        print("Make sure you're running this from the Disease_Portal directory")
        exit(1)
    
    print(f"\n📁 Local SQLite: {LOCAL_SQLITE_PATH}")
    print(f"🐘 PostgreSQL: {POSTGRES_URL[:50]}...")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(LOCAL_SQLITE_PATH)
    pg_engine = create_engine(POSTGRES_URL)
    
    try:
        # Step 1: Create tables
        create_tables_in_postgres(pg_engine)
        
        # Step 2: Migrate diseases
        migrate_diseases(sqlite_conn, pg_engine)
        
        # Step 3: Migrate herbs
        migrate_herbs(sqlite_conn, pg_engine)
        
        # Step 4: Verify
        success = verify_migration(pg_engine)
        
        print("\n" + "=" * 60)
        if success:
            print("✅ MIGRATION COMPLETE!")
            print("\nYour Render app should now work with the PostgreSQL database.")
            print("The data will persist even after redeployments!")
        else:
            print("⚠️  Migration may have issues. Please check the logs above.")
        print("=" * 60)
        
    finally:
        sqlite_conn.close()
        pg_engine.dispose()


if __name__ == "__main__":
    main()
