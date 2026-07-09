from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ZuriMarket Product Service",
    description="Product Management Microservice",
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

# In-memory database
products_db = []
categories_db = []
reviews_db = []

# ============= Models =============
class Price(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = "KES"

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    price: Price  # Now price is an object with amount and currency
    category: List[str]
    brand: Optional[str] = None
    specifications: Optional[Dict[str, str]] = {}
    images: Optional[List[str]] = []
    variants: Optional[List[Dict]] = []
    tags: Optional[List[str]] = []
    stock_quantity: int = 0
    is_active: bool = True
    is_featured: bool = False

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Price] = None
    category: Optional[List[str]] = None
    brand: Optional[str] = None
    specifications: Optional[Dict[str, str]] = None
    images: Optional[List[str]] = None
    variants: Optional[List[Dict]] = None
    tags: Optional[List[str]] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

class ProductResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    slug: str
    description: str
    price: Dict[str, Any]  # {"amount": 150000, "currency": "KES"}
    category: List[str]
    brand: Optional[str] = None
    specifications: Dict[str, str]
    images: List[str]
    variants: List[Dict]
    tags: List[str]
    seller_id: Optional[str] = None
    stock_quantity: int
    rating_average: float = 0
    review_count: int = 0
    is_active: bool = True
    is_featured: bool = False
    views: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    image: Optional[str] = None

class CategoryResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    image: Optional[str] = None
    created_at: datetime

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: str = Field(..., min_length=3, max_length=100)
    comment: str = Field(..., min_length=10)
    images: Optional[List[str]] = []

class ReviewResponse(BaseModel):
    id: str = Field(alias="_id")
    product_id: str
    user_id: str
    user_name: str
    rating: int
    title: str
    comment: str
    images: List[str]
    helpful_count: int = 0
    verified_purchase: bool = False
    created_at: datetime

# ============= Helper Functions =============
def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from name"""
    import re
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
    return slug

# ============= Health Check =============
@app.get("/")
def root():
    return {
        "service": "ZuriMarket Product Service",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "product-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============= Product Endpoints =============
@app.get("/api/products")
def get_products(
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """Get all products with filtering and pagination"""
    filtered = products_db.copy()
    
    # Apply filters
    if category:
        filtered = [p for p in filtered if category in p.get('category', [])]
    if brand:
        filtered = [p for p in filtered if p.get('brand') == brand]
    if min_price is not None:
        filtered = [p for p in filtered if p.get('price', {}).get('amount', 0) >= min_price]
    if max_price is not None:
        filtered = [p for p in filtered if p.get('price', {}).get('amount', 0) <= max_price]
    if search:
        search_lower = search.lower()
        filtered = [p for p in filtered if search_lower in p.get('name', '').lower() or 
                    search_lower in p.get('description', '').lower()]
    
    # Sort
    reverse = sort_order == "desc"
    filtered.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    
    # Paginate
    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    paginated = filtered[start:end]
    
    return {
        "products": paginated,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }

@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    """Get a single product by ID"""
    for product in products_db:
        if product.get("_id") == product_id:
            # Increment view count
            product["views"] = product.get("views", 0) + 1
            return product
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Product not found"
    )

@app.post("/api/products")
def create_product(product: ProductCreate):
    """Create a new product"""
    logger.info(f"Creating product: {product.name}")
    
    product_dict = product.dict()
    product_dict["_id"] = str(uuid.uuid4())
    product_dict["slug"] = generate_slug(product.name)
    product_dict["seller_id"] = None
    product_dict["rating_average"] = 0
    product_dict["review_count"] = 0
    product_dict["views"] = 0
    product_dict["created_at"] = datetime.utcnow()
    product_dict["updated_at"] = datetime.utcnow()
    
    products_db.append(product_dict)
    logger.info(f"Product created: {product.name} (ID: {product_dict['_id']})")
    
    return product_dict

@app.put("/api/products/{product_id}")
def update_product(product_id: str, product_data: ProductUpdate):
    """Update a product"""
    for i, product in enumerate(products_db):
        if product.get("_id") == product_id:
            # Update fields
            update_data = product_data.dict(exclude_unset=True)
            for key, value in update_data.items():
                if key == "price" and value:
                    product[key] = value.dict() if hasattr(value, 'dict') else value
                else:
                    product[key] = value
            product["updated_at"] = datetime.utcnow()
            products_db[i] = product
            
            # If name changed, update slug
            if "name" in update_data:
                product["slug"] = generate_slug(product["name"])
            
            logger.info(f"Product updated: {product['name']}")
            return product
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Product not found"
    )

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    """Delete a product"""
    for i, product in enumerate(products_db):
        if product.get("_id") == product_id:
            products_db.pop(i)
            logger.info(f"Product deleted: {product_id}")
            return {"message": "Product deleted successfully"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Product not found"
    )

# ============= Category Endpoints =============
@app.get("/api/categories")
def get_categories():
    """Get all categories"""
    return categories_db

@app.post("/api/categories")
def create_category(category: CategoryCreate):
    """Create a new category"""
    category_dict = category.dict()
    category_dict["_id"] = str(uuid.uuid4())
    category_dict["slug"] = generate_slug(category.name)
    category_dict["created_at"] = datetime.utcnow()
    
    categories_db.append(category_dict)
    return category_dict

# ============= Review Endpoints =============
@app.get("/api/products/{product_id}/reviews")
def get_product_reviews(product_id: str):
    """Get reviews for a product"""
    product_reviews = [r for r in reviews_db if r.get("product_id") == product_id]
    return product_reviews

@app.post("/api/products/{product_id}/reviews")
def create_review(product_id: str, review: ReviewCreate):
    """Create a review for a product"""
    # Check if product exists
    product_exists = any(p.get("_id") == product_id for p in products_db)
    if not product_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    review_dict = review.dict()
    review_dict["_id"] = str(uuid.uuid4())
    review_dict["product_id"] = product_id
    review_dict["user_id"] = "temp_user"
    review_dict["user_name"] = "Anonymous User"
    review_dict["helpful_count"] = 0
    review_dict["verified_purchase"] = False
    review_dict["created_at"] = datetime.utcnow()
    
    reviews_db.append(review_dict)
    
    # Update product rating
    product_reviews = [r for r in reviews_db if r.get("product_id") == product_id]
    if product_reviews:
        avg_rating = sum(r.get("rating", 0) for r in product_reviews) / len(product_reviews)
        for product in products_db:
            if product.get("_id") == product_id:
                product["rating_average"] = round(avg_rating, 1)
                product["review_count"] = len(product_reviews)
                break
    
    return review_dict

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
