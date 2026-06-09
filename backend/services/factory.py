from .vision import BaseVisionService, OllamaVisionService, MockVisionService
from .image import BaseImageService, OllamaImageService, MockImageService
from ..config import settings

def get_vision_service() -> BaseVisionService:
    if settings.MODEL_PROVIDER == "mock":
        return MockVisionService()
    # default to ollama
    return OllamaVisionService()

def get_image_service() -> BaseImageService:
    if settings.MODEL_PROVIDER == "mock":
        return MockImageService()
    return OllamaImageService()
