# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from datetime import datetime
import logging
import json
import sqlite3
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Order Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Database ============
def get_db_connection():
    conn = sqlite3.connect('zurimarket.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                order_number TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                items TEXT NOT NULL,
                subtotal REAL NOT NULL,
                shipping_fee REAL DEFAULT 0,
                tax REAL DEFAULT 0,
                total_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'pending',
                shipping_address TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                tracking_number TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("SQLite tables created/verified")
    except Exception as e:
        logger.error(f"Database init error: {e}")

init_db()

# ============ Models ============
class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    total_price: float

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    shipping_address: Dict[str, str]
    payment_method: str

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    tracking_number: Optional[str] = None

# ============ Helper ============
def generate_order_number() -> str:
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

# ============ Routes ============
@app.get("/")
def root():
    return {"service": "Order Service", "database": "sqlite", "status": "running"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "order-service",
        "database": "sqlite",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/orders")
def create_order(order: OrderCreate):
    logger.info(f"Creating order for user: {order.user_id}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        subtotal = sum(item.total_price for item in order.items)
        shipping_fee = 0 if subtotal > 50000 else 500
        tax = subtotal * 0.16
        total = subtotal + shipping_fee + tax
        
        order_id = str(uuid.uuid4())
        order_number = generate_order_number()
        
        items_json = json.dumps([item.dict() for item in order.items])
        shipping_json = json.dumps(order.shipping_address)
        
        cur.execute("""
            INSERT INTO orders (
                id, order_number, user_id, items, subtotal, shipping_fee, tax,
                total_amount, shipping_address, payment_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, order_number, order.user_id,
            items_json,
            subtotal, shipping_fee, tax, total,
            shipping_json,
            order.payment_method
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Order created: {order_number}")
        
        return {
            "id": order_id,
            "order_number": order_number,
            "user_id": order.user_id,
            "items": [item.dict() for item in order.items],
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "tax": tax,
            "total_amount": total,
            "status": "pending",
            "payment_status": "pending",
            "shipping_address": order.shipping_address,
            "payment_method": order.payment_method,
            "created_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Order creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders")
def get_orders(user_id: Optional[str] = None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if user_id:
            cur.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        else:
            cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        
        orders = cur.fetchall()
        cur.close()
        conn.close()
        
        result = []
        for order in orders:
            order_dict = dict(order)
            try:
                order_dict["items"] = json.loads(order_dict["items"])
            except:
                pass
            try:
                order_dict["shipping_address"] = json.loads(order_dict["shipping_address"])
            except:
                pass
            result.append(order_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cur.fetchone()
        cur.close()
        conn.close()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order_dict = dict(order)
        try:
            order_dict["items"] = json.loads(order_dict["items"])
        except:
            pass
        try:
            order_dict["shipping_address"] = json.loads(order_dict["shipping_address"])
        except:
            pass
        
        return order_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
