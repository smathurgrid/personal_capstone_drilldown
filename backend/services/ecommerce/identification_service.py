"""Gemini-based fashion item identification for ecommerce."""

import json

from PIL import Image

from backend.shared.config import Settings


def _configure_genai(api_key: str):
    import google.generativeai as genai

    if api_key:
        genai.configure(api_key=api_key)
    return genai


class IdentificationService:
    def __init__(self, app_settings: Settings) -> None:
        self._settings = app_settings
        self.preferred_models = [
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
            "models/gemini-pro-vision",
        ]
        self.active_model_name = self.preferred_models[0]
        self.model = None
        if app_settings.GOOGLE_API_KEY:
            self.model = _configure_genai(app_settings.GOOGLE_API_KEY).GenerativeModel(
                self.active_model_name
            )

    async def _find_working_model(self):
        try:
            genai = _configure_genai(self._settings.GOOGLE_API_KEY)
            available = [
                m.name
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            for preferred in self.preferred_models:
                if preferred in available:
                    return preferred
            for model_name in available:
                if "flash" in model_name:
                    return model_name
            return available[0] if available else None
        except Exception as exc:
            print(f"Error listing models: {exc}")
            return self.active_model_name

    @staticmethod
    def _parse_vision_response(content: str) -> dict:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json.loads(content)
        if "category" in data and "masterCategory" not in data:
            data["masterCategory"] = data.pop("category")
        if "boundingBox" in data:
            data["bounding_box"] = data.pop("boundingBox")
        return data

    async def _generate_identification(self, prompt: str, original_img, composite_img):
        response = self.model.generate_content([prompt, original_img, composite_img])
        return self._parse_vision_response(response.text)

    async def identify_item(
        self, original_image_path: str, composite_image_path: str, x: float, y: float
    ):
        if not self._settings.GOOGLE_API_KEY:
            return None

        if not self.model:
            self.model = _configure_genai(self._settings.GOOGLE_API_KEY).GenerativeModel(
                self.active_model_name
            )

        original_img = Image.open(original_image_path)
        composite_img = Image.open(composite_image_path)
        width, height = original_img.size

        prompt = f"""
        Identify the fashion item indicated by the red marker.

        Use both the full original image and the composite image where a red marker has been placed at normalized coordinates (x={x:.2f}, y={y:.2f}).

        The red marker is the user's intended target.

        Return the result as a JSON object with the following fields:
        {{
            "masterCategory": "e.g., Apparel, Accessories, Footwear",
            "articleType": "Choose from: Tshirts, Shirts, Casual Shoes, Watches, Sports Shoes, Kurtas, Tops, Handbags, Heels, Sunglasses, Wallets, Flip Flops, Sandals, Briefs, Belts, Backpacks, Socks, Formal Shoes, Jeans, Shorts, Trousers, Flats, Bra, Dresses, Sarees, Earrings",
            "color": "e.g., Black, White, Blue, Brown, Grey, Red, Green, Pink, Navy Blue, Purple, Silver, Gold, Beige, Olive, Maroon",
            "material": "estimate material",
            "pattern": "e.g., solid, striped, floral",
            "fit": "e.g., slim fit, oversized",
            "style": "e.g., formal, casual, streetwear",
            "gender": "Men, Women, Boys, Girls, Unisex",
            "description": "a short descriptive phrase",
            "confidence": 0.0-1.0,
            "boundingBox": {{ "x1": int, "y1": int, "x2": int, "y2": int }}
        }}

        The boundingBox MUST be in absolute pixel coordinates of the original image ({width}x{height}).
        Ensure the JSON is valid and only return the JSON.
        """

        try:
            return await self._generate_identification(prompt, original_img, composite_img)
        except Exception as exc:
            print(f"Vision identify error: {exc}")
            working_name = await self._find_working_model()
            if working_name and working_name != self.active_model_name:
                self.active_model_name = working_name
                self.model = _configure_genai(self._settings.GOOGLE_API_KEY).GenerativeModel(
                    self.active_model_name
                )
                try:
                    return await self._generate_identification(prompt, original_img, composite_img)
                except Exception as exc2:
                    print(f"Vision retry failed: {exc2}")
            return None
