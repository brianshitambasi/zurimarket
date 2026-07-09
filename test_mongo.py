import pymongo

try:
    client = pymongo.MongoClient("mongodb://zuri:zuripass@localhost:27017")
    db = client["zurimarket"]
    
    # Ping the database
    result = db.command("ping")
    print("✅ MongoDB connection successful!")
    print(f"✅ MongoDB Version: {result}")
    
    client.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
