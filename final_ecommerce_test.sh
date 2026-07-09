#!/bin/bash

echo "=========================================="
echo "ZuriMarket - Final E-Commerce Test"
echo "=========================================="

# Login
echo -e "\n1. Logging in..."
TOKEN=$(curl -s -X POST http://localhost:8080/auth/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@zurimarket.com","password":"Test123"}' \
  | python -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
echo "Token received: ${TOKEN:0:30}..."

# Create Product
echo -e "\n2. Creating product..."
PRODUCT_RESPONSE=$(curl -s -X POST http://localhost:8080/product/api/products \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "E-Commerce Test Product",
    "description": "Full flow test",
    "price": {"amount": 2500, "currency": "KES"},
    "category": ["Electronics", "Test"],
    "brand": "TestBrand",
    "stock_quantity": 100
  }')

echo $PRODUCT_RESPONSE | python -m json.tool
PRODUCT_ID=$(echo $PRODUCT_RESPONSE | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('_id', ''))")
echo "Product ID: $PRODUCT_ID"

# Add to Cart
echo -e "\n3. Adding to cart..."
curl -s -X POST http://localhost:8080/cart/api/cart/final_user \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "'$PRODUCT_ID'",
    "product_name": "E-Commerce Test Product",
    "quantity": 2,
    "unit_price": 2500,
    "total_price": 5000
  }' | python -m json.tool

# Create Order
echo -e "\n4. Creating order..."
ORDER_RESPONSE=$(curl -s -X POST http://localhost:8080/order/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "final_user",
    "items": [
      {
        "product_id": "'$PRODUCT_ID'",
        "product_name": "E-Commerce Test Product",
        "quantity": 2,
        "unit_price": 2500,
        "total_price": 5000
      }
    ],
    "shipping_address": {
      "street": "123 Main St",
      "city": "Nairobi",
      "country": "Kenya"
    },
    "payment_method": "mpesa"
  }')

echo $ORDER_RESPONSE | python -m json.tool
ORDER_ID=$(echo $ORDER_RESPONSE | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('id', ''))")
echo "Order ID: $ORDER_ID"

# Process Payment
echo -e "\n5. Processing payment..."
curl -s -X POST http://localhost:8080/payment/api/payments/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "'$ORDER_ID'",
    "user_id": "final_user",
    "amount": 5800,
    "currency": "KES",
    "payment_method": "mpesa",
    "phone_number": "+254712345678"
  }' | python -m json.tool

# M-PESA STK Push
echo -e "\n6. Sending M-PESA STK Push..."
curl -s -X POST http://localhost:8080/mpesa/api/mpesa/stk-push \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+254712345678",
    "amount": 5800,
    "order_id": "'$ORDER_ID'",
    "user_id": "final_user"
  }' | python -m json.tool

# Notification
echo -e "\n7. Sending confirmation notification..."
curl -s -X POST http://localhost:8080/notification/api/notifications/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "final_user",
    "user_email": "test@zurimarket.com",
    "type": "email",
    "title": "Order Confirmed",
    "message": "Your order has been confirmed! Order #'$ORDER_ID'",
    "data": {"order_id": "'$ORDER_ID'"}
  }' | python -m json.tool

echo -e "\n=========================================="
echo "✅ E-Commerce Flow Test Complete!"
echo "=========================================="
