from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Auth Service", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SECRET_KEY = "your-secret-key-change-in-production-2024"
ALGORITHM = "HS256"

# In-memory database
users_db = {}
products_db = []

# Models
class UserCreate(BaseModel):
    email: str
    phone: str
    full_name: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ProductCreate(BaseModel):
    name: str
    description: str
    price: dict
    category: List[str]
    brand: Optional[str] = None
    specifications: Optional[dict] = {}

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[dict] = None
    category: Optional[List[str]] = None
    brand: Optional[str] = None
    specifications: Optional[dict] = None

# Helper functions
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# Routes
@app.get("/")
def root():
    return {
        "message": "ZuriMarket Auth Service",
        "status": "running",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/auth/register")
def register(user: UserCreate):
    try:
        logger.info(f"Register attempt: {user.email}")
        
        # Check if user exists
        if user.email in users_db:
            logger.warning(f"Email already registered: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(user.password)
        
        users_db[user.email] = {
            "id": user_id,
            "email": user.email,
            "phone": user.phone,
            "full_name": user.full_name,
            "password": hashed_password,
            "role": "customer",
            "is_verified": False,
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"User registered successfully: {user.email}")
        
        # Generate token
        token = create_token({
            "sub": user_id,
            "email": user.email,
            "role": "customer"
        })
        
        return {
            "access_token": token,
            "refresh_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "role": "customer",
                "created_at": users_db[user.email]["created_at"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/auth/login")
def login(credentials: UserLogin):
    try:
        logger.info(f"Login attempt: {credentials.email}")
        
        # Find user
        user = users_db.get(credentials.email)
        if not user:
            logger.warning(f"User not found: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(credentials.password, user["password"]):
            logger.warning(f"Invalid password for: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        logger.info(f"Login successful: {credentials.email}")
        
        # Generate token
        token = create_token({
            "sub": user["id"],
            "email": credentials.email,
            "role": user["role"]
        })
        
        return {
            "access_token": token,
            "refresh_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "phone": user["phone"],
                "full_name": user["full_name"],
                "role": user["role"],
                "created_at": user["created_at"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@app.get("/api/auth/me")
def get_current_user(authorization: str = None):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    try:
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        email = payload.get("email")
        user = users_db.get(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "id": user["id"],
            "email": user["email"],
            "phone": user["phone"],
            "full_name": user["full_name"],
            "role": user["role"],
            "created_at": user["created_at"]
        }
    except IndexError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

@app.post("/api/auth/logout")
def logout():
    return {"message": "Successfully logged out"}

# Product endpoints (simplified)
@app.get("/api/products")
def get_products():
    return {"products": products_db, "total": len(products_db)}

@app.post("/api/products")
def create_product(product: ProductCreate):
    product_dict = product.dict()
    product_dict["_id"] = str(uuid.uuid4())
    product_dict["created_at"] = datetime.utcnow().isoformat()
    product_dict["updated_at"] = datetime.utcnow().isoformat()
    products_db.append(product_dict)
    return product_dict

@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    for product in products_db:
        if product["_id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Product not found")

@app.put("/api/products/{product_id}")
def update_product(product_id: str, product_data: ProductUpdate):
    for product in products_db:
        if product["_id"] == product_id:
            update_data = product_data.dict(exclude_unset=True)
            product.update(update_data)
            product["updated_at"] = datetime.utcnow().isoformat()
            return product
    raise HTTPException(status_code=404, detail="Product not found")

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    for i, product in enumerate(products_db):
        if product["_id"] == product_id:
            products_db.pop(i)
            return {"message": "Product deleted successfully"}
    raise HTTPException(status_code=404, detail="Product not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
