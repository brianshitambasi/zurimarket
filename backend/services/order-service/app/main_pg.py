# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import uuid
import logging
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import jwt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Order Service (PostgreSQL)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    shipping_address: Dict[str, str]
    payment_method: str

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    tracking_number: Optional[str] = None

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="zurimarket",
        user="zuri",
        password="zuripass",
        port=5432
    )

# Create tables
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(36) PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                items JSONB NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                shipping_fee DECIMAL(10,2) DEFAULT 0,
                tax DECIMAL(10,2) DEFAULT 0,
                total_amount DECIMAL(10,2) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                payment_status VARCHAR(50) DEFAULT 'pending',
                shipping_address JSONB NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                tracking_number VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Order tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

init_db()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
security = HTTPBearer()

def generate_order_number() -> str:
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

@app.get("/")
def root():
    return {"service": "Order Service", "database": "postgresql", "status": "running"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "order-service",
        "database": "postgresql",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/orders")
def create_order(order: OrderCreate):
    logger.info(f"Creating order for user: {order.user_id}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Calculate totals
        subtotal = sum(item.total_price for item in order.items)
        shipping_fee = 0 if subtotal > 50000 else 500
        tax = subtotal * 0.16
        total = subtotal + shipping_fee + tax
        
        order_id = str(uuid.uuid4())
        order_number = generate_order_number()
        
        # Convert items and shipping address to JSON strings
        items_json = json.dumps([item.dict() for item in order.items])
        shipping_json = json.dumps(order.shipping_address)
        
        cur.execute("""
            INSERT INTO orders (
                id, order_number, user_id, items, subtotal, shipping_fee, tax,
                total_amount, shipping_address, payment_method
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            order_id, order_number, order.user_id,
            items_json,
            subtotal, shipping_fee, tax, total,
            shipping_json,
            order.payment_method
        ))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Order created: {order_number}")
        return dict(result)
        
    except Exception as e:
        logger.error(f"❌ Order creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders")
def get_orders(user_id: Optional[str] = None):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if user_id:
            cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        else:
            cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        
        orders = cur.fetchall()
        cur.close()
        conn.close()
        return orders
        
    except Exception as e:
        logger.error(f"❌ Get orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        cur.close()
        conn.close()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return dict(order)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, order_update: OrderUpdate):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        update_fields = []
        params = []
        
        if order_update.status:
            update_fields.append("status = %s")
            params.append(order_update.status)
        if order_update.tracking_number:
            update_fields.append("tracking_number = %s")
            params.append(order_update.tracking_number)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(order_id)
        
        query = f"UPDATE orders SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
        cur.execute(query, params)
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        return dict(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Update order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/orders/{order_id}")
def cancel_order(order_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if order can be cancelled
        cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if result[0] in ['shipped', 'delivered']:
            raise HTTPException(status_code=400, detail="Cannot cancel shipped/delivered order")
        
        cur.execute("UPDATE orders SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (order_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        return {"message": "Order cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Cancel order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
