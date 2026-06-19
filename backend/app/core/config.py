from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    HF_TOKEN: str = ""
    SERPAPI_KEY: str = ""
    EBAY_API_KEY: str = ""
    ETSY_API_KEY: str = ""
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_VISION_MODEL: str = "qwen2.5vl:7b"
    UPLOADS_DIR: str = "/Users/bsama/ai-ecommerce-drilldown/uploads"
    DEBUG_DIR: str = "/Users/bsama/ai-ecommerce-drilldown/debug"
    REDIS_URL: str = "redis://localhost:6379"

    @property
    def SHOPPING_PROVIDERS(self) -> dict[str, bool]:
        return {
            "serpapi": True,
            "ebay": bool(self.EBAY_API_KEY),
            "etsy": bool(self.ETSY_API_KEY),
        }

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
