# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import jwt
import logging
import os
import json
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Admin Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ============ Models ============
class AdminLogin(BaseModel):
    email: str
    password: str

class AdminUser(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

class DashboardMetrics(BaseModel):
    total_users: int
    total_products: int
    total_orders: int
    total_revenue: float
    pending_orders: int
    recent_orders: List[Dict]

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None

# ============ Database Connections ============
MONGODB_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/zurimarket")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-2024")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# MongoDB client
mongo_client = None
mongo_db = None

def get_postgres_connection():
    import re
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
        if match:
            return psycopg2.connect(
                host=match.group(3),
                database=match.group(5),
                user=match.group(1),
                password=match.group(2),
                port=match.group(4)
            )
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        database=os.getenv("PGDATABASE", "zurimarket"),
        user=os.getenv("PGUSER", "zuri"),
        password=os.getenv("PGPASSWORD", "zuripass"),
        port=os.getenv("PGPORT", "5432")
    )

@app.on_event("startup")
async def startup():
    global mongo_client, mongo_db
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client[os.getenv("MONGODB_DB", "zurimarket")]
    logger.info("Admin Service started")

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()

# ============ Authentication ============
def verify_admin_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            return None
        return payload
    except:
        return None

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_admin_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return payload

# ============ Admin Auth ============
@app.post("/api/admin/login")
async def admin_login(login: AdminLogin):
    """Admin login - checks if user is admin"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT * FROM users WHERE email = %s", (login.email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Generate admin token
        token = jwt.encode({
            "sub": user["id"],
            "email": user["email"],
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=24)
        }, SECRET_KEY, algorithm=ALGORITHM)
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"]
            }
        }
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Dashboard Metrics ============
@app.get("/api/admin/dashboard")
async def get_dashboard_metrics(admin: Dict = Depends(get_admin_user)):
    """Get dashboard metrics"""
    try:
        # Get user count from PostgreSQL
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.close()
        
        # Get product count from MongoDB
        products_count = await mongo_db.products.count_documents({})
        
        # Get order metrics from PostgreSQL
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_orders
            FROM orders
        """)
        order_stats = cur.fetchone()
        cur.close()
        
        # Get recent orders
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM orders 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        recent_orders = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert order items from JSON string if needed
        for order in recent_orders:
            if isinstance(order.get("items"), str):
                try:
                    order["items"] = json.loads(order["items"])
                except:
                    pass
        
        return {
            "total_users": total_users,
            "total_products": products_count,
            "total_orders": order_stats.get("total_orders", 0),
            "total_revenue": float(order_stats.get("total_revenue", 0)),
            "pending_orders": order_stats.get("pending_orders", 0),
            "recent_orders": recent_orders
        }
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ User Management ============
@app.get("/api/admin/users")
async def get_all_users(admin: Dict = Depends(get_admin_user)):
    """Get all users (admin only)"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, email, phone, full_name, role, is_verified, is_active, created_at FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        cur.close()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/admin/users/{user_id}")
async def update_user(user_id: str, update: UserUpdate, admin: Dict = Depends(get_admin_user)):
    """Update a user (admin only)"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        updates = []
        params = []
        
        if update.role is not None:
            updates.append("role = %s")
            params.append(update.role)
        if update.is_active is not None:
            updates.append("is_active = %s")
            params.append(update.is_active)
        if update.full_name is not None:
            updates.append("full_name = %s")
            params.append(update.full_name)
        if update.phone is not None:
            updates.append("phone = %s")
            params.append(update.phone)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING *"
        cur.execute(query, params)
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"message": "User updated successfully", "user": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Product Management ============
@app.get("/api/admin/products")
async def get_all_products(admin: Dict = Depends(get_admin_user)):
    """Get all products (admin only)"""
    try:
        cursor = mongo_db.products.find().sort("created_at", -1)
        products = await cursor.to_list(length=1000)
        for product in products:
            product["_id"] = str(product["_id"])
        return products
    except Exception as e:
        logger.error(f"Get products error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/products/{product_id}")
async def delete_product(product_id: str, admin: Dict = Depends(get_admin_user)):
    """Delete a product (admin only)"""
    try:
        result = await mongo_db.products.delete_one({"_id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete product error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Order Management ============
@app.get("/api/admin/orders")
async def get_all_orders(admin: Dict = Depends(get_admin_user)):
    """Get all orders (admin only)"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        orders = cur.fetchall()
        cur.close()
        conn.close()
        
        for order in orders:
            if isinstance(order.get("items"), str):
                try:
                    order["items"] = json.loads(order["items"])
                except:
                    pass
        
        return orders
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/admin/orders/{order_id}/status")
async def update_order_status(order_id: str, status_data: Dict, admin: Dict = Depends(get_admin_user)):
    """Update order status (admin only)"""
    try:
        new_status = status_data.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="Status is required")
        
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE orders 
            SET status = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s 
            RETURNING *
        """, (new_status, order_id))
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {"message": f"Order status updated to {new_status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Analytics ============
@app.get("/api/admin/analytics/sales")
async def get_sales_analytics(admin: Dict = Depends(get_admin_user)):
    """Get sales analytics (admin only)"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Daily sales for last 30 days
        cur.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as order_count,
                SUM(total_amount) as revenue
            FROM orders 
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """)
        daily_sales = cur.fetchall()
        
        # Payment method breakdown
        cur.execute("""
            SELECT 
                payment_method,
                COUNT(*) as count,
                SUM(total_amount) as total
            FROM orders 
            GROUP BY payment_method
        """)
        payment_methods = cur.fetchall()
        
        # Order status breakdown
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM orders 
            GROUP BY status
        """)
        order_statuses = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "daily_sales": daily_sales,
            "payment_methods": payment_methods,
            "order_statuses": order_statuses
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
