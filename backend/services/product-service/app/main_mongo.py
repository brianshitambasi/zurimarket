# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import uuid
import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Product Service (MongoDB)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DB", "zurimarket")

client = None
db = None

@app.on_event("startup")
async def startup():
    global client, db
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DATABASE_NAME]
        await db.products.create_index([("slug", 1)], unique=True)
        await db.products.create_index([("category", 1)])
        await db.products.create_index([("brand", 1)])
        logger.info("MongoDB connected for Product Service")
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    if client:
        client.close()
        logger.info("MongoDB disconnected")

class ProductCreate(BaseModel):
    name: str
    description: str
    price: Dict
    category: List[str]
    brand: Optional[str] = None
    specifications: Optional[Dict] = {}
    stock_quantity: int = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Dict] = None
    category: Optional[List[str]] = None
    brand: Optional[str] = None
    specifications: Optional[Dict] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

@app.get("/")
def root():
    return {"service": "Product Service", "database": "mongodb", "status": "running"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "product-service",
        "database": "mongodb",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/products")
async def create_product(product: ProductCreate):
    try:
        logger.info(f"Creating product: {product.name}")
        slug = product.name.lower().replace(" ", "-").replace("'", "")
        
        product_dict = product.dict()
        product_dict["_id"] = str(uuid.uuid4())
        product_dict["slug"] = slug
        product_dict["created_at"] = datetime.utcnow()
        product_dict["updated_at"] = datetime.utcnow()
        product_dict["views"] = 0
        product_dict["rating_average"] = 0
        product_dict["review_count"] = 0
        product_dict["is_active"] = True
        product_dict["is_featured"] = False
        
        await db.products.insert_one(product_dict)
        logger.info(f"Product created: {product.name}")
        return product_dict
    except Exception as e:
        logger.error(f"Create product error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
async def get_products():
    try:
        cursor = db.products.find().sort("created_at", -1).limit(100)
        products = await cursor.to_list(length=100)
        for product in products:
            product["_id"] = str(product["_id"])
        return {"products": products, "total": len(products)}
    except Exception as e:
        logger.error(f"Get products error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
async def get_product(product_id: str):
    try:
        product = await db.products.find_one({"_id": product_id})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product["_id"] = str(product["_id"])
        return product
    except Exception as e:
        logger.error(f"Get product error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/products/{product_id}")
async def update_product(product_id: str, product_data: ProductUpdate):
    try:
        update_data = product_data.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await db.products.update_one(
            {"_id": product_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        product = await db.products.find_one({"_id": product_id})
        product["_id"] = str(product["_id"])
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update product error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str):
    try:
        result = await db.products.delete_one({"_id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete product error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
