from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "ZuriMarket Product Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    MONGODB_URL: str = "mongodb://zurimarket:zurimarket_dev_2024@localhost:27017"
    MONGODB_DB: str = "zurimarket"
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
