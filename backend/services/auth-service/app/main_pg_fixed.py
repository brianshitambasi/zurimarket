# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
import bcrypt
import jwt
import logging
import os
import sqlite3
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Auth Service (SQLite)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRegister(BaseModel):
    email: str
    phone: str
    full_name: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

# SQLite Database
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
        conn.commit()
        cur.close()
        conn.close()
        logger.info("SQLite tables created/verified")
    except Exception as e:
        logger.error(f"Database init error: {e}")

init_db()

SECRET_KEY = os.getenv("SECRET_KEY", "KBKBIUH9Y896875657446@#@#LK")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
security = HTTPBearer()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.get("/")
def root():
    return {"service": "Auth Service", "database": "sqlite", "status": "running"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "auth-service",
        "database": "sqlite",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/auth/register")
def register(user: UserRegister):
    logger.info(f"Register attempt: {user.email}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user exists
        cur.execute("SELECT * FROM users WHERE email = ?", (user.email,))
        existing = cur.fetchone()
        if existing:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Email already registered")
        
        user_id = str(uuid.uuid4())
        hashed = hash_password(user.password)
        
        cur.execute("""
            INSERT INTO users (id, email, phone, full_name, hashed_password)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, user.email, user.phone, user.full_name, hashed))
        
        conn.commit()
        cur.close()
        conn.close()
        
        token = create_access_token({"sub": user_id, "email": user.email, "role": "customer"})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "role": "customer",
                "created_at": datetime.utcnow().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login")
def login(user: UserLogin):
    logger.info(f"Login attempt: {user.email}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM users WHERE email = ?", (user.email,))
        db_user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not verify_password(user.password, db_user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"sub": db_user["id"], "email": user.email, "role": db_user["role"]})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": db_user["id"],
                "email": db_user["email"],
                "phone": db_user["phone"],
                "full_name": db_user["full_name"],
                "role": db_user["role"],
                "created_at": db_user["created_at"] or datetime.utcnow().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/me")
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, phone, full_name, role FROM users WHERE id = ?", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user["id"],
            "email": user["email"],
            "phone": user["phone"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
