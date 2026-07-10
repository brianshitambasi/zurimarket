# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import uuid
import logging
import json
import sqlite3
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Cart Service", version="1.0.0")

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
            CREATE TABLE IF NOT EXISTS carts (
                user_id TEXT PRIMARY KEY,
                items TEXT NOT NULL,
                expires_at TEXT NOT NULL
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
class CartItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    image: Optional[str] = None
    variant: Optional[Dict] = None

# ============ Routes ============
@app.get("/")
def root():
    return {"service": "Cart Service", "database": "sqlite", "status": "running"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "cart-service",
        "database": "sqlite",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/cart/{user_id}")
def get_cart(user_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM carts WHERE user_id = ?", (user_id,))
        cart = cur.fetchone()
        cur.close()
        conn.close()
        
        if not cart:
            return {"user_id": user_id, "items": [], "total": 0, "item_count": 0}
        
        items = json.loads(cart["items"])
        total = sum(item.get("total_price", 0) for item in items)
        
        return {
            "user_id": user_id,
            "items": items,
            "total": total,
            "item_count": len(items),
            "expires_at": cart["expires_at"]
        }
    except Exception as e:
        logger.error(f"Get cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cart/{user_id}")
def add_to_cart(user_id: str, item: CartItem):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM carts WHERE user_id = ?", (user_id,))
        cart = cur.fetchone()
        
        current_time = datetime.utcnow().isoformat()
        
        if not cart:
            items = [item.dict()]
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            cur.execute(
                "INSERT INTO carts (user_id, items, expires_at) VALUES (?, ?, ?)",
                (user_id, json.dumps(items), expires_at)
            )
        else:
            items = json.loads(cart["items"])
            product_found = False
            for existing_item in items:
                if existing_item.get("product_id") == item.product_id:
                    existing_item["quantity"] += item.quantity
                    existing_item["total_price"] = existing_item["quantity"] * existing_item["unit_price"]
                    product_found = True
                    break
            if not product_found:
                items.append(item.dict())
            
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            cur.execute(
                "UPDATE carts SET items = ?, expires_at = ? WHERE user_id = ?",
                (json.dumps(items), expires_at, user_id)
            )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return get_cart(user_id)
    except Exception as e:
        logger.error(f"Add to cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/cart/{user_id}/items/{product_id}")
def remove_from_cart(user_id: str, product_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM carts WHERE user_id = ?", (user_id,))
        cart = cur.fetchone()
        
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found")
        
        items = json.loads(cart["items"])
        items = [item for item in items if item.get("product_id") != product_id]
        
        cur.execute(
            "UPDATE carts SET items = ? WHERE user_id = ?",
            (json.dumps(items), user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        return get_cart(user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove from cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
