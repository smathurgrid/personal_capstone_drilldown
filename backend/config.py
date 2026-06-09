import os
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

class Settings:
    OLLAMA_BASE: str = os.getenv("OLLAMA_BASE", "http://localhost:11434")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen2.5vl:7b")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "x/flux2-klein:4b-bf16")
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "ollama").lower()

settings = Settings()
