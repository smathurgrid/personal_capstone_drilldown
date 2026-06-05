from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    GOOGLE_API_KEY: str
    QDRANT_PATH: str = "/Users/bsama/ai-ecommerce-drilldown/data/qdrant_storage"
    UPLOADS_DIR: str = "/Users/bsama/ai-ecommerce-drilldown/uploads"
    DEBUG_DIR: str = "/Users/bsama/ai-ecommerce-drilldown/debug"
    COLLECTION_NAME: str = "fashion_products"
    DATASET_IMAGES_DIR: str = "/Users/bsama/Downloads/fashion-dataset/images"
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"

settings = Settings()
