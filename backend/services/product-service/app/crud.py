from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import re

from . import schemas

async def get_products(
    db: AsyncIOMotorDatabase,
    filters: Dict[str, Any],
    sort_by: str,
    sort_order: str,
    page: int,
    limit: int
):
    query = filters.copy()
    
    # Text search
    if "$text" in query:
        search = query.pop("$text")
        query["$text"] = search
    
    # Build sort
    sort_direction = -1 if sort_order == "desc" else 1
    sort = [(sort_by, sort_direction)]
    
    # Get total count
    total = await db.products.count_documents(query)
    
    # Get products
    cursor = db.products.find(query).sort(sort).skip((page - 1) * limit).limit(limit)
    products = await cursor.to_list(length=limit)
    
    # Convert ObjectId to string
    for product in products:
        product["_id"] = str(product["_id"])
    
    return products, total

async def get_product(db: AsyncIOMotorDatabase, product_id: str):
    try:
        product = await db.products.find_one({"_id": ObjectId(product_id)})
        if product:
            product["_id"] = str(product["_id"])
        return product
    except:
        return None

async def create_product(
    db: AsyncIOMotorDatabase,
    product_data: schemas.ProductCreate,
    seller_id: str
):
    # Generate slug
    slug = re.sub(r'[^a-z0-9]+', '-', product_data.name.lower()).strip('-')
    
    product_dict = product_data.dict()
    product_dict.update({
        "slug": slug,
        "seller_id": seller_id,
        "rating_average": 0,
        "review_count": 0,
        "is_active": True,
        "is_featured": False,
        "views": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    result = await db.products.insert_one(product_dict)
    product_dict["_id"] = str(result.inserted_id)
    return product_dict

async def update_product(
    db: AsyncIOMotorDatabase,
    product_id: str,
    product_data: schemas.ProductUpdate
):
    update_data = product_data.dict(exclude_unset=True)
    if not update_data:
        return None
    
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.products.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        return None
    
    return await get_product(db, product_id)

async def delete_product(db: AsyncIOMotorDatabase, product_id: str):
    result = await db.products.delete_one({"_id": ObjectId(product_id)})
    return result.deleted_count > 0
