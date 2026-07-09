import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database="zurimarket",
        user="zuri",
        password="zuripass",
        port=5432
    )
    print("✅ PostgreSQL connection successful!")
    
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    print(f"✅ PostgreSQL Version: {version[0][:50]}...")
    
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
