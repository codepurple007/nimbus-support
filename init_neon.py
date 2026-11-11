import psycopg
import sys
from pathlib import Path

# The connection string from your terminal
DB_URL = "postgresql://neondb_owner:npg_PnKROezWT85B@ep-soft-math-b42t1thc-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def run_sql(path: Path):
    if not path.exists():
        print(f"Error: {path} not found.")
        return False

    sql = path.read_text()
    print(f"Executing {path}...")
    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                # Neon usually comes with vector pre-installed, but we'll try to enable it
                for stmt in sql.split(';'):
                    body = stmt.strip()
                    if body:
                        # Skip extension creation if it fails (Neon handles this differently sometimes)
                        if "CREATE EXTENSION" in body.upper():
                            try:
                                cur.execute(body)
                            except Exception:
                                pass
                        else:
                            cur.execute(body)
            conn.commit()
            return True
    except Exception as e:
        print(f"Failed to execute {path}: {e}")
        return False

if __name__ == "__main__":
    # First, setup the base vector schema
    if run_sql(Path("sql/schema.sql")):
        # Then, setup the app-specific tables
        if run_sql(Path("sql/app_schema.sql")):
            print("\nSuccessfully initialized Neon database with all required tables!")
            print("1. Knowledge Base (pgvector)")
            print("2. Chat Sessions & Tickets")
            print("3. Mock Items Store")
