import google.generativeai as genai
from PIL import Image
import json
import os
from ..core.config import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)

class VisionService:
    def __init__(self):
        # Preferred models in order of priority
        self.preferred_models = [
            'models/gemini-2.5-flash',
            'models/gemini-2.0-flash',
            'models/gemini-1.5-flash',
            'models/gemini-pro-vision'
        ]
        self.active_model_name = self.preferred_models[0]
        self.model = genai.GenerativeModel(self.active_model_name)
        print(f"VisionService initialized with {self.active_model_name}")

    async def _find_working_model(self):
        """Discovers the best available model for the current API key."""
        try:
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            print(f"Available models: {available}")
            for preferred in self.preferred_models:
                if preferred in available:
                    return preferred
            for m in available:
                if 'flash' in m:
                    return m
            return available[0] if available else None
        except Exception as e:
            print(f"Error listing models: {e}")
            return self.active_model_name

    async def identify_item(self, original_image_path: str, composite_image_path: str, x: float, y: float):
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

        # Ensure we have a working model
        if not self.model:
            working_name = await self._find_working_model()
            if working_name:
                self.active_model_name = working_name
                self.model = genai.GenerativeModel(self.active_model_name)

        try:
            print(f"Identifying with {self.active_model_name} at ({x}, {y})...")
            # Send both images to Gemini
            response = self.model.generate_content([prompt, original_img, composite_img])
            content = response.text
            print(f"Gemini Raw Response: {content}")
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            # Key Normalization: Align with frontend and search service
            if 'category' in data and 'masterCategory' not in data:
                data['masterCategory'] = data.pop('category')
            
            if 'boundingBox' in data:
                data['bounding_box'] = data.pop('boundingBox')
            
            return data
        except Exception as e:
            print(f"Error with {self.active_model_name}: {e}")
            # Try once to refresh and retry
            working_name = await self._find_working_model()
            if working_name and working_name != self.active_model_name:
                print(f"Switching to {working_name} and retrying...")
                self.active_model_name = working_name
                self.model = genai.GenerativeModel(self.active_model_name)
                try:
                    response = self.model.generate_content([prompt, original_img, composite_img])
                    content = response.text
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    data = json.loads(content)
                    
                    if 'category' in data and 'masterCategory' not in data:
                        data['masterCategory'] = data.pop('category')
                    if 'boundingBox' in data:
                        data['bounding_box'] = data.pop('boundingBox')
                        
                    return data
                except Exception as e2:
                    print(f"Retry failed: {e2}")
            return None

vision_service = VisionService()
