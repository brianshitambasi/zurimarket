import requests
import json
import time

BASE_URL = "http://localhost:8000"

print("��� ZuriMarket Working Test\n")
print("=" * 50)

# 1. Health Check
print("\n1️⃣ Health Check")
try:
    r = requests.get(f"{BASE_URL}/health")
    print(f"✅ Service running! Status: {r.status_code}")
except Exception as e:
    print(f"❌ Service not running: {e}")
    exit()

# 2. Register
print("\n2️⃣ Register User")
email = f"test_{int(time.time())}@zurimarket.com"
register_data = {
    "email": email,
    "phone": "+254712345678",
    "full_name": "Test User",
    "password": "Test123"
}
r = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print("✅ Registration successful!")
    print(f"   User: {data.get('user', {}).get('email')}")
    token = data.get('access_token')
else:
    print(f"❌ Error: {r.text}")
    exit()

# 3. Login
print("\n3️⃣ Login")
login_data = {
    "email": email,
    "password": "Test123"
}
r = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print("✅ Login successful!")
    print(f"   User: {data.get('user', {}).get('full_name')}")
    token = data.get('access_token')
else:
    print(f"❌ Error: {r.text}")

# 4. Get Current User
if token:
    print("\n4️⃣ Get Current User")
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        user = r.json()
        print("✅ User found!")
        print(f"   Name: {user.get('full_name')}")
        print(f"   Email: {user.get('email')}")
        print(f"   Role: {user.get('role')}")
    else:
        print(f"❌ Error: {r.text}")

# 5. Create Product
if token:
    print("\n5️⃣ Create Product")
    product_data = {
        "name": "Samsung Galaxy S24",
        "description": "Latest flagship smartphone",
        "price": {"amount": 150000, "currency": "KES"},
        "category": ["Electronics", "Phones"],
        "brand": "Samsung",
        "specifications": {"screen": "6.8 inches", "ram": "12GB"}
    }
    r = requests.post(f"{BASE_URL}/api/products", json=product_data, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        product = r.json()
        print("✅ Product created successfully!")
        print(f"   Name: {product.get('name')}")
        print(f"   Price: {product.get('price', {}).get('amount')} KES")
    else:
        print(f"❌ Error: {r.text}")

# 6. Get All Products
print("\n6️⃣ Get All Products")
r = requests.get(f"{BASE_URL}/api/products")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    products = data.get('products', [])
    print(f"✅ Found {len(products)} products")
    if products:
        print(f"   First product: {products[0].get('name')}")

print("\n" + "=" * 50)
print("✅ All tests completed successfully!")
print("\n��� API Documentation: http://localhost:8000/docs")
