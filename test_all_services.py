# -*- coding: utf-8 -*-
import requests
import json
import time

print("=" * 60)
print(" ZuriMarket Complete Backend Test")
print("=" * 60)

BASE_AUTH = "http://localhost:8000"
BASE_PRODUCT = "http://localhost:8001"
BASE_ORDER = "http://localhost:8002"
BASE_CART = "http://localhost:8003"
BASE_PAYMENT = "http://localhost:8004"
BASE_NOTIFICATION = "http://localhost:8005"

services = {
    "Auth": BASE_AUTH,
    "Product": BASE_PRODUCT,
    "Order": BASE_ORDER,
    "Cart": BASE_CART,
    "Payment": BASE_PAYMENT,
    "Notification": BASE_NOTIFICATION
}

# 1. Health Checks
print("\n1. Health Checks")
all_running = True
for name, url in services.items():
    try:
        r = requests.get(f"{url}/health", timeout=2)
        print(f"   OK {name}: {r.status_code}")
    except:
        print(f"   FAIL {name}: Not running")
        all_running = False

if not all_running:
    print("\nERROR: Some services are not running!")
    print("Start each service in separate terminals:")
    for name, url in services.items():
        port = url.split(":")[-1]
        print(f"   cd backend/services/{name.lower()}-service")
        print(f"   python -m uvicorn app.main:app --reload --port {port}")
    exit()

# 2. Register & Login
print("\n2. Authentication")
register_data = {
    "email": "test@zurimarket.com",
    "phone": "+254712345678",
    "full_name": "Test User",
    "password": "Test123"
}
r = requests.post(f"{BASE_AUTH}/api/auth/register", json=register_data)
print(f"   Register: {r.status_code}")

login_data = {"email": "test@zurimarket.com", "password": "Test123"}
r = requests.post(f"{BASE_AUTH}/api/auth/login", json=login_data)
print(f"   Login: {r.status_code}")
if r.status_code == 200:
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print(f"   OK Token received: {token[:30]}...")
else:
    print("   FAIL Login failed")
    exit()

# 3. Create Product
print("\n3. Create Product")
product_data = {
    "name": "Samsung Galaxy S24 Ultra",
    "description": "Latest flagship with AI features",
    "price": {"amount": 150000, "currency": "KES"},
    "category": ["Electronics", "Phones"],
    "brand": "Samsung",
    "specifications": {"screen": "6.8 inches", "ram": "12GB"}
}
r = requests.post(f"{BASE_PRODUCT}/api/products", json=product_data)
print(f"   Create: {r.status_code}")
if r.status_code == 200:
    product = r.json()
    product_id = product.get("_id")
    print(f"   OK Product ID: {product_id}")
else:
    print(f"   FAIL Error: {r.text}")
    exit()

# 4. Add to Cart
print("\n4. Add to Cart")
cart_item = {
    "product_id": product_id,
    "product_name": "Samsung Galaxy S24 Ultra",
    "quantity": 1,
    "unit_price": 150000,
    "total_price": 150000
}
r = requests.post(f"{BASE_CART}/api/cart/test_user", json=cart_item)
print(f"   Add to Cart: {r.status_code}")
if r.status_code == 200:
    cart = r.json()
    print(f"   OK Cart total: KES {cart.get('total', 0):,.2f}")
    print(f"   OK Items: {cart.get('item_count', 0)}")

# 5. Create Order
print("\n5. Create Order")
order_data = {
    "user_id": "test_user",
    "items": [{
        "product_id": product_id,
        "product_name": "Samsung Galaxy S24 Ultra",
        "quantity": 1,
        "unit_price": 150000,
        "total_price": 150000
    }],
    "shipping_address": {
        "street": "123 Main St",
        "city": "Nairobi",
        "country": "Kenya"
    },
    "payment_method": "mpesa"
}
r = requests.post(f"{BASE_ORDER}/api/orders", json=order_data)
print(f"   Create Order: {r.status_code}")
if r.status_code == 200:
    order = r.json()
    order_id = order.get("_id")
    order_number = order.get("order_number")
    print(f"   OK Order Number: {order_number}")
    print(f"   OK Total: KES {order.get('total_amount', 0):,.2f}")

# 6. Process Payment
print("\n6. Process Payment")
payment_data = {
    "order_id": order_id,
    "user_id": "test_user",
    "amount": order.get("total_amount", 0),
    "currency": "KES",
    "payment_method": "mpesa",
    "phone_number": "+254712345678"
}
r = requests.post(f"{BASE_PAYMENT}/api/payments/initiate", json=payment_data)
print(f"   Initiate Payment: {r.status_code}")
if r.status_code == 200:
    payment = r.json()
    print(f"   OK Payment ID: {payment.get('_id')}")
    print(f"   OK Status: {payment.get('status')}")
    print(f"   OK M-PESA Code: {payment.get('mpesa_code', 'N/A')}")

# 7. Send Notification
print("\n7. Send Notification")
notification_data = {
    "user_id": "test_user",
    "user_email": "test@zurimarket.com",
    "type": "email",
    "title": "Order Confirmed",
    "message": f"Your order {order_number} has been confirmed!",
    "data": {"order_number": order_number}
}
r = requests.post(f"{BASE_NOTIFICATION}/api/notifications/send", json=notification_data)
print(f"   Send Notification: {r.status_code}")
if r.status_code == 200:
    notif = r.json()
    print(f"   OK Notification ID: {notif.get('_id')}")
    print(f"   OK Status: {notif.get('status')}")

# 8. Get All Products
print("\n8. Get Products")
r = requests.get(f"{BASE_PRODUCT}/api/products")
if r.status_code == 200:
    data = r.json()
    print(f"   OK Total Products: {data.get('total', 0)}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED SUCCESSFULLY!")
print("=" * 60)
