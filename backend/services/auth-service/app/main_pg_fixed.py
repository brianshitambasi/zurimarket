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
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Auth Service (PostgreSQL)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class UserRegister(BaseModel):
    email: str
    phone: str
    full_name: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

# Database connection - using environment variables for Render
def get_db_connection():
    # Try Render's DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        import re
        # Parse DATABASE_URL: postgresql://user:pass@host:port/dbname
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', database_url)
        if match:
            return psycopg2.connect(
                host=match.group(3),
                database=match.group(5),
                user=match.group(1),
                password=match.group(2),
                port=match.group(4)
            )
    
    # Fallback to individual env vars or defaults
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        database=os.getenv("PGDATABASE", "zurimarket"),
        user=os.getenv("PGUSER", "zuri"),
        password=os.getenv("PGPASSWORD", "zuripass"),
        port=os.getenv("PGPORT", "5432")
    )

# Create tables if they don't exist
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(20) UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'customer',
                is_verified BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("PostgreSQL tables created/verified")
    except Exception as e:
        logger.error(f"Database error: {e}")

# Initialize database on startup
init_db()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-2024")
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
    return {"service": "Auth Service", "database": "postgresql", "status": "running"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "auth-service",
        "database": "postgresql",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/auth/register")
def register(user: UserRegister):
    logger.info(f"Register attempt: {user.email}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if user exists
        cur.execute("SELECT * FROM users WHERE email = %s", (user.email,))
        existing = cur.fetchone()
        if existing:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user
        user_id = str(uuid.uuid4())
        hashed = hash_password(user.password)
        
        cur.execute("""
            INSERT INTO users (id, email, phone, full_name, hashed_password)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, email, phone, full_name, role, created_at
        """, (user_id, user.email, user.phone, user.full_name, hashed))
        
        db_user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        # Generate token
        token = create_access_token({"sub": user_id, "email": user.email, "role": "customer"})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": db_user["id"],
                "email": db_user["email"],
                "phone": db_user["phone"],
                "full_name": db_user["full_name"],
                "role": db_user["role"],
                "created_at": db_user["created_at"].isoformat() if db_user["created_at"] else None
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find user
        cur.execute("SELECT * FROM users WHERE email = %s", (user.email,))
        db_user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not verify_password(user.password, db_user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Generate token
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
                "created_at": db_user["created_at"].isoformat() if db_user["created_at"] else None
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, email, phone, full_name, role FROM users WHERE id = %s", (user_id,))
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
