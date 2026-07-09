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
import sqlite3
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ZuriMarket Admin Service",
    description="Admin Dashboard and Analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None

# ============ SQLite Database ============
def get_db_connection():
    conn = sqlite3.connect('zurimarket.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'customer',
                is_verified INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
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
        
        # ===== CREATE ADMIN USER IF NOT EXISTS =====
        # Check if admin exists
        cur.execute("SELECT * FROM users WHERE email = 'admin@zurimarket.com'")
        if not cur.fetchone():
            admin_id = str(uuid.uuid4())
            password = bcrypt.hashpw('Admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute('''
                INSERT INTO users (id, email, phone, full_name, hashed_password, role)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_id, 'admin@zurimarket.com', '+254712345679', 'Admin User', password, 'admin'))
            logger.info("✅ Admin user created automatically!")
        else:
            logger.info("✅ Admin user already exists")
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("SQLite tables created/verified")
    except Exception as e:
        logger.error(f"Database init error: {e}")

init_db()

# ============ MongoDB ============
mongo_client = None
mongo_db = None

@app.on_event("startup")
async def startup():
    global mongo_client, mongo_db
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db = os.getenv("MONGODB_DB", "zurimarket")
    try:
        mongo_client = AsyncIOMotorClient(mongodb_uri)
        mongo_db = mongo_client[mongodb_db]
        logger.info("MongoDB connected for Admin Service")
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}")

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
        logger.info("MongoDB disconnected")

# ============ Auth ============
SECRET_KEY = os.getenv("SECRET_KEY", "KBKBIUH9Y896875657446@#@#LK")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            return None
        return payload
    except:
        return None

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return payload

# ============ Routes ============
@app.get("/")
async def root():
    return {
        "service": "ZuriMarket Admin Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "admin-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/admin/login")
async def admin_login(login: AdminLogin):
    logger.info(f"Admin login attempt: {login.email}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM users WHERE email = ?", (login.email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user:
            logger.warning(f"User not found: {login.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if user["role"] != "admin":
            logger.warning(f"User is not admin: {login.email}")
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        if not verify_password(login.password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({
            "sub": user["id"],
            "email": user["email"],
            "role": "admin"
        })
        
        logger.info(f"Admin login successful: {login.email}")
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/dashboard")
async def get_dashboard_metrics(admin: Dict = Depends(get_admin_user)):
    """Get dashboard metrics"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_orders,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_orders
            FROM orders
        """)
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        products_count = 0
        if mongo_db:
            try:
                products_count = await mongo_db.products.count_documents({})
            except:
                pass
        
        return {
            "total_users": total_users,
            "total_products": products_count,
            "total_orders": result[0] or 0,
            "total_revenue": float(result[1] or 0),
            "pending_orders": result[2] or 0
        }
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/users")
async def get_all_users(admin: Dict = Depends(get_admin_user)):
    """Get all users (admin only)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, phone, full_name, role, is_verified, is_active, created_at FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(user) for user in users]
    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/orders")
async def get_all_orders(admin: Dict = Depends(get_admin_user)):
    """Get all orders (admin only)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        orders = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(order) for order in orders]
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/products")
async def get_all_products(admin: Dict = Depends(get_admin_user)):
    """Get all products (admin only)"""
    if not mongo_db:
        raise HTTPException(status_code=503, detail="MongoDB not available")
    
    try:
        cursor = mongo_db.products.find().sort("created_at", -1)
        products = await cursor.to_list(length=1000)
        for product in products:
            product["_id"] = str(product["_id"])
        return products
    except Exception as e:
        logger.error(f"Get products error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
