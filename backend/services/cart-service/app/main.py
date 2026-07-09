from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from datetime import datetime, timedelta
import logging

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

# In-memory database (with TTL)
carts_db = {}

class CartItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    total_price: float
    image: Optional[str] = None
    variant: Optional[Dict] = None

class CartCreate(BaseModel):
    user_id: str
    items: List[CartItem]

class CartUpdate(BaseModel):
    items: List[CartItem]

@app.get("/")
def root():
    return {"service": "Cart Service", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "cart-service", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/cart/{user_id}")
def get_cart(user_id: str):
    cart = carts_db.get(user_id)
    if not cart:
        return {"user_id": user_id, "items": [], "total": 0, "item_count": 0}
    
    total = sum(item.get("total_price", 0) for item in cart.get("items", []))
    return {
        "user_id": user_id,
        "items": cart.get("items", []),
        "total": total,
        "item_count": len(cart.get("items", [])),
        "expires_at": cart.get("expires_at")
    }

@app.post("/api/cart/{user_id}")
def add_to_cart(user_id: str, item: CartItem):
    if user_id not in carts_db:
        carts_db[user_id] = {
            "items": [],
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
    
    # Check if item exists, update quantity
    for existing in carts_db[user_id]["items"]:
        if existing.get("product_id") == item.product_id:
            existing["quantity"] += item.quantity
            existing["total_price"] = existing["quantity"] * existing["unit_price"]
            return get_cart(user_id)
    
    carts_db[user_id]["items"].append(item.dict())
    return get_cart(user_id)

@app.put("/api/cart/{user_id}")
def update_cart(user_id: str, cart_update: CartUpdate):
    if user_id not in carts_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    carts_db[user_id]["items"] = [item.dict() for item in cart_update.items]
    carts_db[user_id]["expires_at"] = (datetime.utcnow() + timedelta(days=7)).isoformat()
    return get_cart(user_id)

@app.delete("/api/cart/{user_id}/items/{product_id}")
def remove_from_cart(user_id: str, product_id: str):
    if user_id not in carts_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    carts_db[user_id]["items"] = [i for i in carts_db[user_id]["items"] if i.get("product_id") != product_id]
    return get_cart(user_id)

@app.delete("/api/cart/{user_id}")
def clear_cart(user_id: str):
    if user_id in carts_db:
        carts_db[user_id]["items"] = []
    return {"message": "Cart cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
