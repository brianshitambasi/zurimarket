from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str
    price: Dict[str, float]
    category: List[str]
    brand: Optional[str] = None
    specifications: Dict[str, str] = {}
    images: List[str] = []
    variants: List[Dict] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Dict[str, float]] = None
    category: Optional[List[str]] = None
    brand: Optional[str] = None
    specifications: Optional[Dict[str, str]] = None
    images: Optional[List[str]] = None
    variants: Optional[List[Dict]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

class ProductResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    slug: str
    description: str
    price: Dict[str, float]
    category: List[str]
    brand: Optional[str] = None
    specifications: Dict[str, str]
    images: List[str]
    variants: List[Dict]
    seller_id: str
    rating_average: float
    review_count: int
    is_active: bool
    is_featured: bool
    views: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    limit: int
    total_pages: int
