# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
import json
import sqlite3
import logging
from datetime import datetime

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

def get_db():
    conn = sqlite3.connect('orders.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_number TEXT UNIQUE,
            user_id TEXT,
            items TEXT,
            subtotal REAL,
            shipping_fee REAL,
            tax REAL,
            total_amount REAL,
            status TEXT,
            payment_status TEXT,
            shipping_address TEXT,
            payment_method TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

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

def generate_order_number():
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

@app.get("/")
def root():
    return {"service": "Order Service", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "order-service", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/orders")
def create_order(order: OrderCreate):
    subtotal = sum(item.total_price for item in order.items)
    shipping_fee = 0 if subtotal > 50000 else 500
    tax = subtotal * 0.16
    total = subtotal + shipping_fee + tax
    
    order_id = str(uuid.uuid4())
    order_number = generate_order_number()
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (id, order_number, user_id, items, subtotal, shipping_fee, tax, total_amount, status, payment_status, shipping_address, payment_method, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, order_number, order.user_id,
        json.dumps([item.dict() for item in order.items]),
        subtotal, shipping_fee, tax, total,
        "pending", "pending",
        json.dumps(order.shipping_address),
        order.payment_method,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()
    
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

@app.get("/api/orders")
def get_orders(user_id: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    if user_id:
        cur.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    else:
        cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    
    orders = []
    for row in rows:
        order = dict(row)
        order["items"] = json.loads(order["items"])
        order["shipping_address"] = json.loads(order["shipping_address"])
        orders.append(order)
    return orders

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
