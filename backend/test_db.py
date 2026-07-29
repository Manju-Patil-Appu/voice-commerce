import psycopg

conn = psycopg.connect(
    "postgresql://postgres:YOUR_PASSWORD@db.hyjzlghlnscnlwstawzz.supabase.co:5432/postgres"
)

print("Connected successfully!")
conn.close()