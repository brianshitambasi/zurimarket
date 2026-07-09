from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
from datetime import datetime
import jwt
from passlib.context import CryptContext

# Initialize FastAPI
app = FastAPI(
    title="ZuriMarket Auth Service",
    description="Authentication Service for ZuriMarket",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Secret key (in production, use environment variable)
SECRET_KEY = "your-super-secret-key-change-in-production-2024"
ALGORITHM = "HS256"

# In-memory database (for development)
users_db = {}
products_db = []

# Models
class UserCreate(BaseModel):
    email: EmailStr
    phone: str
    full_name: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    phone: str
    full_name: str
    role: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse

class ProductCreate(BaseModel):
    name: str
    description: str
    price: dict
    category: list
    brand: Optional[str] = None
    specifications: dict = {}

# Helper functions
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Health Check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# Root
@app.get("/")
async def root():
    return {
        "message": "Welcome to ZuriMarket Auth Service",
        "docs": "/docs",
        "health": "/health"
    }

# Register
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    # Check if user exists
    if user_data.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "phone": user_data.phone,
        "full_name": user_data.full_name,
        "hashed_password": get_password_hash(user_data.password),
        "role": "customer",
        "is_verified": False,
        "created_at": datetime.utcnow()
    }
    
    users_db[user_data.email] = user
    
    # Generate tokens
    access_token = create_access_token({
        "sub": user_id,
        "email": user_data.email,
        "role": "customer"
    })
    
    refresh_token = create_access_token({
        "sub": user_id,
        "type": "refresh"
    })
    
    # Return user data (without password)
    user_response = UserResponse(
        id=user_id,
        email=user_data.email,
        phone=user_data.phone,
        full_name=user_data.full_name,
        role="customer",
        created_at=user["created_at"]
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_response
    )

# Login
@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    # Find user
    user = users_db.get(credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Generate tokens
    access_token = create_access_token({
        "sub": user["id"],
        "email": credentials.email,
        "role": user["role"]
    })
    
    refresh_token = create_access_token({
        "sub": user["id"],
        "type": "refresh"
    })
    
    # Return user data
    user_response = UserResponse(
        id=user["id"],
        email=credentials.email,
        phone=user["phone"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=user["created_at"]
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_response
    )

# Get current user
@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user(authorization: str = None):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        # Find user by id
        for user in users_db.values():
            if user["id"] == user_id:
                return UserResponse(
                    id=user["id"],
                    email=user["email"],
                    phone=user["phone"],
                    full_name=user["full_name"],
                    role=user["role"],
                    created_at=user["created_at"]
                )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Products endpoints (simplified)
@app.get("/api/products")
async def get_products():
    return {"products": products_db, "total": len(products_db)}

@app.post("/api/products")
async def create_product(product: ProductCreate, authorization: str = None):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    product_dict = product.dict()
    product_dict["_id"] = str(uuid.uuid4())
    product_dict["created_at"] = datetime.utcnow().isoformat()
    products_db.append(product_dict)
    
    return product_dict

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
