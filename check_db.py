import psycopg
import sys

DB_URL = "postgresql://neondb_owner:npg_PnKROezWT85B@ep-soft-math-b42t1thc-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_vector():
    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                print("Checking extensions...")
                cur.execute("SELECT extname FROM pg_extension;")
                extensions = [r[0] for r in cur.fetchall()]
                print(f"Installed extensions: {extensions}")
                
                if 'vector' not in extensions:
                    print("Vector extension missing. Attempting to enable...")
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    conn.commit()
                    print("Vector extension enabled.")
                
                print("Checking for vector type...")
                cur.execute("SELECT typname FROM pg_type WHERE typname = 'vector';")
                row = cur.fetchone()
                if row:
                    print("Found 'vector' type in pg_type.")
                else:
                    print("CRITICAL: 'vector' type STILL NOT FOUND in pg_type.")
                    
                print("Checking tables...")
                cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';")
                tables = [r[0] for r in cur.fetchall()]
                print(f"Tables in public schema: {tables}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_vector()
