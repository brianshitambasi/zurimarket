# -*- coding: utf-8 -*-
import requests
import json

print("=" * 50)
print("ZuriMarket Health Check")
print("=" * 50)

services = {
    "Auth": {"url": "http://localhost:8000/health", "port": 8000},
    "Product": {"url": "http://localhost:8001/health", "port": 8001},
    "Order": {"url": "http://localhost:8002/health", "port": 8002},
    "Cart": {"url": "http://localhost:8003/health", "port": 8003},
    "Payment": {"url": "http://localhost:8004/health", "port": 8004},
    "Notification": {"url": "http://localhost:8005/health", "port": 8005}
}

print("\nChecking all services...")
print("-" * 50)

running_count = 0
total = len(services)

for name, info in services.items():
    try:
        r = requests.get(info["url"], timeout=3)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "unknown")
            print(f"[OK] {name:12} - Status: {status} (Port {info['port']})")
            running_count += 1
        else:
            print(f"[FAIL] {name:12} - Status Code: {r.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] {name:12} - Not running (Connection refused)")
    except requests.exceptions.Timeout:
        print(f"[FAIL] {name:12} - Timeout")
    except Exception as e:
        print(f"[FAIL] {name:12} - Error: {str(e)[:30]}")

print("-" * 50)
print(f"\nRunning: {running_count}/{total} services")

if running_count == total:
    print("\n[SUCCESS] All services are running!")
else:
    print("\n[WARNING] Some services are not running.")
    print("Start them with:")
    print("  cd backend/services/auth-service && python -m uvicorn app.fixed:app --reload --port 8000")
    print("  cd backend/services/product-service && python -m uvicorn app.fixed_product:app --reload --port 8001")
    print("  cd backend/services/order-service && python -m uvicorn app.main:app --reload --port 8002")
    print("  cd backend/services/cart-service && python -m uvicorn app.main:app --reload --port 8003")
    print("  cd backend/services/payment-service && python -m uvicorn app.main:app --reload --port 8004")
    print("  cd backend/services/notification-service && python -m uvicorn app.main:app --reload --port 8005")

print("\n" + "=" * 50)
