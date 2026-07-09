# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import uuid
import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Cart Service (MongoDB)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DB", "zurimarket")

# Global client
client = None
db = None

@app.on_event("startup")
async def startup():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    # Create TTL index for cart expiration
    await db.carts.create_index("expires_at", expireAfterSeconds=0)
    await db.carts.create_index("user_id", unique=True)
    logger.info("✅ MongoDB connected for Cart Service!")

@app.on_event("shutdown")
async def shutdown():
    if client:
        client.close()
        logger.info("✅ MongoDB disconnected!")

# Models
class CartItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    image: Optional[str] = None
    variant: Optional[Dict] = None

class CartUpdate(BaseModel):
    items: List[CartItem]

@app.get("/")
def root():
    return {"service": "Cart Service", "database": "mongodb", "status": "running"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "cart-service",
        "database": "mongodb",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/cart/{user_id}")
async def get_cart(user_id: str):
    try:
        cart = await db.carts.find_one({"user_id": user_id})
        if not cart:
            return {
                "user_id": user_id,
                "items": [],
                "total": 0,
                "item_count": 0
            }
        
        cart["_id"] = str(cart["_id"])
        total = sum(item.get("total_price", 0) for item in cart.get("items", []))
        
        return {
            "user_id": user_id,
            "items": cart.get("items", []),
            "total": total,
            "item_count": len(cart.get("items", [])),
            "expires_at": cart.get("expires_at")
        }
    except Exception as e:
        logger.error(f"❌ Get cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cart/{user_id}")
async def add_to_cart(user_id: str, item: CartItem):
    try:
        # Get existing cart
        cart = await db.carts.find_one({"user_id": user_id})
        current_time = datetime.utcnow()
        
        if not cart:
            # Create new cart
            new_cart = {
                "user_id": user_id,
                "items": [item.dict()],
                "expires_at": (current_time + timedelta(days=7)).isoformat()
            }
            await db.carts.insert_one(new_cart)
            logger.info(f"✅ New cart created for user: {user_id}")
        else:
            # Update existing cart
            items = cart.get("items", [])
            
            # Check if product exists, update quantity
            product_found = False
            for existing_item in items:
                if existing_item.get("product_id") == item.product_id:
                    existing_item["quantity"] += item.quantity
                    existing_item["total_price"] = existing_item["quantity"] * existing_item["unit_price"]
                    product_found = True
                    break
            
            if not product_found:
                items.append(item.dict())
            
            await db.carts.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "items": items,
                        "expires_at": (current_time + timedelta(days=7)).isoformat()
                    }
                }
            )
            logger.info(f"✅ Cart updated for user: {user_id}")
        
        return await get_cart(user_id)
        
    except Exception as e:
        logger.error(f"❌ Add to cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/cart/{user_id}")
async def update_cart(user_id: str, cart_update: CartUpdate):
    try:
        cart = await db.carts.find_one({"user_id": user_id})
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found")
        
        items = [item.dict() for item in cart_update.items]
        total = sum(item.get("total_price", 0) for item in items)
        
        await db.carts.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "items": items,
                    "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
                }
            }
        )
        logger.info(f"✅ Cart updated for user: {user_id}")
        return await get_cart(user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Update cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/cart/{user_id}/items/{product_id}")
async def remove_from_cart(user_id: str, product_id: str):
    try:
        cart = await db.carts.find_one({"user_id": user_id})
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found")
        
        items = [item for item in cart.get("items", []) if item.get("product_id") != product_id]
        
        await db.carts.update_one(
            {"user_id": user_id},
            {"$set": {"items": items}}
        )
        logger.info(f"✅ Item removed from cart for user: {user_id}")
        return await get_cart(user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Remove from cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/cart/{user_id}")
async def clear_cart(user_id: str):
    try:
        cart = await db.carts.find_one({"user_id": user_id})
        if not cart:
            raise HTTPException(status_code=404, detail="Cart not found")
        
        await db.carts.update_one(
            {"user_id": user_id},
            {"$set": {"items": []}}
        )
        logger.info(f"✅ Cart cleared for user: {user_id}")
        return {"message": "Cart cleared", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Clear cart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
