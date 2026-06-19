import asyncio
import os
import io
import base64
import json
import requests
import re
import traceback
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv("server/.env")

class AIService:
    # --- GOOGLE CONFIGURATION (For Image Gen) ---
    google_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    IMAGE_MODEL_GOOGLE = "imagen-4.0-fast-generate-001"

    # --- LOCAL OLLAMA CONFIGURATION (For Vision) ---
    OLLAMA_URL = "http://localhost:11434/api"
    VISION_MODEL_LOCAL = "qwen3.5:9b"

    # --- PROMPTS (Upgraded with Forensic Illustrative Logic) ---
    STRUCTURED_PROMPT = (
        "SYSTEM PERSONA: You are an expert Technical Forensic Analyst and Master Illustrator. "
        "You specialize in identifying complex internal structures for educational textbooks.\n\n"
        "TASK: Analyze the technical sub-component at the specified location. Identify its material composition, "
        "mechanical function, and internal layers. Keep the surrounding scene in mind for context.\n\n"
        "FIELDS TO FILL:\n"
        "1. 'object': Specific, granular technical name of the part.\n"
        "2. 'materials': List specific technical materials and textures (e.g., 'brushed aerospace aluminum', 'translucent polymer').\n"
        "3. 'style': The design aesthetic (e.g., 'Bauhaus functionalism', 'Organic bionics').\n"
        "4. 'editorial_headline': A short, captivating technical title (max 6 words).\n"
        "5. 'explainer_paragraph': 2-3 elegantly written sentences of deep technical context explaining the function or history of this detail.\n"
        "6. 'drill_topic': A MASTER IMAGE PROMPT for the next layer. It MUST describe an EXTREME MACRO CLOSE-UP or CROSS-SECTION CUTAWAY. "
        "Describe forensic textures, soft cinematic lighting, and internal mechanical/biological details in great depth. "
        "Aesthetic: 'clean technical illustration, muted watercolor palette on cream paper, architectural diagram style'. "
        "CRITICAL: Explicitly forbid text. The prompt must produce a PURELY VISUAL image with ZERO labels or annotations.\n\n"
        "OUTPUT: Return ONLY a raw JSON object matching this schema exactly. No conversation."
    )

    GLOBAL_DETECTION_PROMPT = (
        "TASK: Forensic Scene Analysis.\n"
        "1. Create a technical 'editorial_headline' for the scene.\n"
        "2. Write a 2-sentence 'explainer_paragraph' summarizing the technology shown.\n"
        "3. Identify 8-12 major sub-components in 'granular_details'. Each MUST have: 'label' (name), 'description' (technical purpose), and 'point' [x, y].\n"
        "OUTPUT: Return ONLY a raw JSON object with these 3 root keys."
    )

    @classmethod
    def _extract_json(cls, text: str):
        """Advanced JSON repair and extraction."""
        if not text: return "{}"
        text = text.strip()
        print(f"\n--- [AI RAW START] ---\n{text[:1000]}...\n--- [AI RAW END] ---\n")
        
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match: text = json_match.group(1).strip()
            
        start = text.find('{')
        if start == -1: return "{}"
        
        extracted = text[start:]
        bracket_count = 0
        end_index = -1
        in_string = False
        escape = False
        
        for i, char in enumerate(extracted):
            if char == '"' and not escape: in_string = not in_string
            if not in_string:
                if char == '{': bracket_count += 1
                elif char == '}': 
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_index = i + 1; break
            if char == '\\': escape = True
            else: escape = False
            
        if end_index != -1: return extracted[:end_index]
        
        if extracted.count('"') % 2 != 0: extracted += '"'
        open_braces = extracted.count('{')
        close_braces = extracted.count('}')
        if open_braces > close_braces: extracted += '}' * (open_braces - close_braces)
        return extracted

    @classmethod
    def _sanitize_coordinates(cls, data):
        """
        Total Metadata Normalizer:
        Ensures arrows and tabs are perfectly synced, and string values are robustly flattened.
        """
        if isinstance(data, list):
            data = {"granular_details": data}

        if not isinstance(data, dict): return {"granular_details": []}
        
        # 1. Normalize Root Metadata
        for k_h in ["headline", "title", "subject", "topic"]:
            if k_h in data and "editorial_headline" not in data: data["editorial_headline"] = data[k_h]
        for k_e in ["description", "explainer", "summary", "context"]:
            if k_e in data and "explainer_paragraph" not in data: data["explainer_paragraph"] = data[k_e]
        if "name" in data and "object" not in data: data["object"] = data["name"]

        # Ensure editorial_headline is a flat string to prevent React rendering crashes
        eh = data.get("editorial_headline")
        if isinstance(eh, dict):
            data["editorial_headline"] = eh.get("text", eh.get("headline", eh.get("title", next(iter(eh.values())) if eh else "")))
        elif isinstance(eh, list):
            data["editorial_headline"] = " ".join(str(x) for x in eh)
        elif eh is not None:
            data["editorial_headline"] = str(eh)

        # Ensure explainer_paragraph is a flat string to prevent React rendering crashes
        ep = data.get("explainer_paragraph")
        if isinstance(ep, dict):
            if "text" in ep:
                data["explainer_paragraph"] = ep["text"]
            else:
                data["explainer_paragraph"] = " ".join(str(v) for v in ep.values() if isinstance(v, str))
        elif isinstance(ep, list):
            data["explainer_paragraph"] = " ".join(str(x) for x in ep)
        elif ep is not None:
            data["explainer_paragraph"] = str(ep)

        if "editorial_headline" not in data or not data["editorial_headline"]: 
            data["editorial_headline"] = "Technical Component Analysis"
        if "explainer_paragraph" not in data or not data["explainer_paragraph"]: 
            data["explainer_paragraph"] = "System-level forensic scan of the region."

        # 2. Support Keyed Objects
        details = []
        if not any(k in data for k in ["granular_details", "details", "objects", "components", "items"]):
            potential_details = []
            for k, v in data.items():
                if isinstance(v, dict) and any(pk in v for pk in ["label", "point", "center_point", "bbox_2d", "component"]):
                    potential_details.append(v)
            if potential_details: details = potential_details

        if not details:
            for key in ["granular_details", "details", "objects", "components", "items"]:
                if key in data and isinstance(data[key], list):
                    details = data[key]; break
        
        if not details: details = data.get("granular_details", [])
        data["granular_details"] = details

        # 3. Process each Point
        for detail in details:
            if not isinstance(detail, dict): continue
            
            # Map Label (Fixing the "Technical Detail" name bug)
            if "label" not in detail:
                detail["label"] = detail.get("component", detail.get("name", detail.get("object", "Technical Detail")))
            
            # Map Description
            if "description" not in detail:
                detail["description"] = detail.get("text", detail.get("explainer", detail.get("purpose", "")))

            # Coordinate normalization
            if "bbox_2d" in detail and isinstance(detail["bbox_2d"], list) and len(detail["bbox_2d"]) == 4:
                y1, x1, y2, x2 = detail["bbox_2d"]
                detail["point"] = [(x1 + x2) / 2.0, (y1 + y2) / 2.0]
            if "point" not in detail:
                for k_p in ["centerPoint", "center_point", "center", "location"]:
                    if k_p in detail: detail["point"] = detail[k_p]; break
            
            point = detail.get("point")
            if isinstance(point, list) and len(point) >= 2:
                normalized = []
                for val in [float(point[0]), float(point[1])]:
                    if val > 2.0: normalized.append(round(val / 1000.0, 4))
                    else: normalized.append(round(val, 4))
                detail["point"] = normalized
            else:
                detail["point"] = [0.5, 0.5]
        return data

    @classmethod
    def _prepare_vision_image(cls, image_path: str, max_size: int = 768):
        """Shrink image for faster local Ollama processing."""
        with Image.open(image_path) as img:
            if img.mode != "RGB": img = img.convert("RGB")
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    @classmethod
    async def describe_style_reference(cls, image_path: str) -> str:
        """Analyze reference image to extract detailed style, colors, materials, and textures for continuity."""
        if not image_path or not os.path.exists(image_path):
            return ""
        
        print(f"ANALYZING STYLE REFERENCE: {image_path}...")
        prompt = (
            "Describe the visual style, color palette, artistic medium, lighting, textures, "
            "and materials in this image. Keep it concise (under 50 words). Focus only on "
            "visual aesthetic elements to guide an image generator to maintain perfect visual "
            "continuity. Do not mention any text, labels, or annotations."
        )
        try:
            loop = asyncio.get_event_loop()
            def run_gemini():
                with Image.open(image_path) as img:
                    response = cls.google_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[img, prompt]
                    )
                    return response.text
            desc = await loop.run_in_executor(None, run_gemini)
            print(f"STYLE GUIDE GENERATED: {desc.strip()[:100]}...")
            return desc
        except Exception as e:
            print(f"Failed to describe style reference: {e}")
            return ""

    @classmethod
    async def generate_image(cls, prompt: str, output_path: str, reference_image_path: str = None, drill_mode: str = "inside"):
        """Fast image generation via Google Imagen, guided by an optional style reference image."""
        print(f"DRAWING: Google Imagen (mode={drill_mode})...")
        
        # Safeguard: If prompt is a structured list or dict returned by the VLM, extract the raw text prompt string
        if isinstance(prompt, list):
            print(f"Unwrapping structured list prompt: {prompt}")
            if len(prompt) > 0:
                item = prompt[0]
                if isinstance(item, dict):
                    prompt = item.get("prompt", item.get("drill_topic", item.get("description", str(item))))
                else:
                    prompt = str(item)
            else:
                prompt = "technical detail"
        elif isinstance(prompt, dict):
            print(f"Unwrapping structured dict prompt: {prompt}")
            prompt = prompt.get("prompt", prompt.get("drill_topic", prompt.get("description", str(prompt))))
            
        print(f"Generating image for pure prompt string: {prompt[:100]}...")
        
        style_desc = ""
        if reference_image_path and os.path.exists(reference_image_path):
            try:
                style_desc = await cls.describe_style_reference(reference_image_path)
            except Exception as e:
                print(f"Failed to get style guide: {e}")

        if drill_mode == "pov":
            enhanced_prompt = (
                f"A realistic first-person point-of-view (POV) perspective photograph looking OUTWARD from the clicked object. "
                f"The immediate foreground or framing of the image should subtly show parts of the clicked object or its immediate housing/structure to establish the perspective. "
                f"View details: {prompt}."
            )
            if style_desc:
                enhanced_prompt += (
                    f" CRITICAL: To maintain perfect visual continuity, the image MUST use the exact same color palette, "
                    f"texture design, materials, and overall aesthetic described here: {style_desc.strip()}."
                )
        else:
            enhanced_prompt = f"A delicate illustration of {prompt}. technical editorial style."
            if style_desc:
                enhanced_prompt += f" Maintain high visual continuity and style matching with: {style_desc.strip()}."
            
        try:
            def run():
                res = cls.google_client.models.generate_images(
                    model=cls.IMAGE_MODEL_GOOGLE, prompt=enhanced_prompt,
                    config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio='16:9', output_mime_type='image/png')
                )
                return res.generated_images[0].image.image_bytes
            img_bytes = await asyncio.get_event_loop().run_in_executor(None, run)
            with open(output_path, "wb") as f: f.write(img_bytes)
            return output_path
        except Exception as e:
            print(f"Imagen generation failed, creating fallback gray placeholder: {e}")
            Image.new('RGB', (1024, 576), color='gray').save(output_path)
            return output_path

    @classmethod
    async def auto_analyze(cls, image_path: str, model_key: str = "qwen3.5"):
        """Scene Analysis using the specified model key (Gemini 2.5 Pro or local Ollama)."""
        loop = asyncio.get_event_loop()
        
        if model_key == "gemini":
            print(f"SCANNING: Gemini 2.5 Pro (Multimodal Reasoning)...")
            try:
                def run_gemini():
                    with Image.open(image_path) as img:
                        response = cls.google_client.models.generate_content(
                            model="gemini-2.5-pro",
                            contents=[img, cls.GLOBAL_DETECTION_PROMPT]
                        )
                        return response.text
                raw_text = await loop.run_in_executor(None, run_gemini)
                json_text = cls._extract_json(raw_text)
                data = json.loads(json_text)
                result = cls._sanitize_coordinates(data)
                return {"metadata": result, "rawJson": json.dumps(result, indent=2)}
            except Exception as e:
                print(f"Gemini scan failed, falling back to local model: {e}")
                # Fallback to local
                model_key = "qwen3.5"

        # Local Ollama Execution
        print(f"SCANNING: Local model '{model_key}' (with fallback)...")
        # Map model keys
        model_map = {
            "qwen3.5": "qwen3.5:9b",
            "qwen": "qwen3.5:9b",
            "internvl": "internvl2",
            "pixtral": "pixtral",
            "llava_next": "llava-next",
            "minicpm": "minicpm-v",
            "moondream": "moondream",
            "llava": "llava",
            "phi4": "phi4",
            "llama_vision": "llama3.2-vision",
        }
        target_model = model_map.get(model_key, cls.VISION_MODEL_LOCAL)
        
        last_parsed_result = None
        for attempt in range(2):
            try:
                img_b64 = cls._prepare_vision_image(image_path)
                payload = {
                    "model": target_model, 
                    "prompt": cls.GLOBAL_DETECTION_PROMPT, 
                    "images": [img_b64], 
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,
                        "num_ctx": 8192
                    }
                }
                
                def run_ollama():
                    try:
                        res = requests.post(f"{cls.OLLAMA_URL}/generate", json=payload, timeout=300)
                        if res.status_code == 200:
                            res_json = res.json()
                            if "error" not in res_json:
                                return res_json.get("response", "") or res_json.get("thinking", "")
                    except Exception as err:
                        print(f"Ollama request error: {err}")
                    
                    # Fallback on first failure
                    if payload["model"] != cls.VISION_MODEL_LOCAL:
                        print(f"Model '{target_model}' unavailable. Falling back to local Qwen3.5...")
                        payload["model"] = cls.VISION_MODEL_LOCAL
                        res = requests.post(f"{cls.OLLAMA_URL}/generate", json=payload, timeout=300)
                        if res.status_code == 200:
                            res_json = res.json()
                            return res_json.get("response", "") or res_json.get("thinking", "")
                    return ""

                raw_text = await loop.run_in_executor(None, run_ollama)
                json_text = cls._extract_json(raw_text)
                data = json.loads(json_text)
                result = cls._sanitize_coordinates(data)
                
                if result.get("granular_details"):
                    return {"metadata": result, "rawJson": json.dumps(result, indent=2)}
                
                last_parsed_result = result
                print(f"Attempt {attempt+1} empty details list. Retrying...")
            except Exception as e:
                traceback.print_exc()
                if attempt == 1: 
                    return {"metadata": {"editorial_headline": "Error", "granular_details": []}, "rawJson": str(e)}
                    
        if last_parsed_result:
            print("Returning successfully parsed scene metadata even though granular details list was empty.")
            return {"metadata": last_parsed_result, "rawJson": json.dumps(last_parsed_result, indent=2)}
            
        return {"metadata": {"editorial_headline": "Empty Scan", "granular_details": []}, "rawJson": "{}"}

    @classmethod
    async def identify_context(cls, image_path: str, x: float, y: float, model_key: str = "qwen3.5", segment_path: str = None, drill_mode: str = "inside"):
        """Detail Identification using the specified model key (Gemini 2.5 Pro or local Ollama)."""
        loop = asyncio.get_event_loop()
        process_path = segment_path if segment_path and os.path.exists(segment_path) else image_path
        
        # Prepare dynamic prompt based on drill_mode
        prompt_to_use = cls.STRUCTURED_PROMPT
        if drill_mode == "pov":
            prompt_to_use = prompt_to_use.replace(
                "Describe forensic textures, soft cinematic lighting, and internal mechanical/biological details in great depth. Aesthetic: 'clean technical illustration, muted watercolor palette on cream paper, architectural diagram style'. CRITICAL: Explicitly forbid text. The prompt must produce a PURELY VISUAL image with ZERO labels or annotations.",
                "Describe a first-person point-of-view perspective looking outwards from this component's physical coordinates towards its surrounding room, stadium stage, movie screen, or overall environment. What does someone see when looking OUTWARD from exactly this location? Aesthetic: photorealistic, wide-angle camera shot, cinematic natural lighting, highly detailed. CRITICAL: Explicitly forbid text. The prompt must produce a PURELY VISUAL image with ZERO labels or annotations."
            ).replace(
                "It MUST describe an EXTREME MACRO CLOSE-UP or CROSS-SECTION CUTAWAY.",
                "It MUST describe a FIRST-PERSON POINT-OF-VIEW (POV) OUTWARD PERSPECTIVE looking towards the surrounding room/scenery/stage/screen."
            ).replace(
                "Aesthetic: 'clean technical illustration, muted watercolor palette on cream paper, architectural diagram style'.",
                "Aesthetic: 'photorealistic wide-angle photograph, natural environment detail'."
            )

        if model_key == "gemini":
            print(f"IDENTIFYING: Gemini 2.5 Pro at [{x}, {y}] with mode={drill_mode}...")
            try:
                def run_gemini():
                    with Image.open(process_path) as img:
                        response = cls.google_client.models.generate_content(
                            model="gemini-2.5-pro",
                            contents=[img, prompt_to_use]
                        )
                        return response.text
                raw_text = await loop.run_in_executor(None, run_gemini)
                json_text = cls._extract_json(raw_text)
                data = json.loads(json_text)
                result = cls._sanitize_coordinates(data)
                
                drill_topic = result.get("drill_topic")
                if not drill_topic:
                    if drill_mode == "pov":
                        drill_topic = f"A first-person point-of-view perspective looking outwards from {result.get('object', 'detail')}, photorealistic wide-angle view, showing the surroundings."
                    else:
                        drill_topic = f"An extreme macro close-up of {result.get('object', 'detail')}, technical style."
                
                return {
                    "drill_topic": drill_topic, 
                    "raw_json": json.dumps(result, indent=2),
                    "rawJson": json.dumps(result, indent=2),
                    "metadata": result
                }, process_path
            except Exception as e:
                print(f"Gemini identification failed, falling back to local: {e}")
                model_key = "qwen3.5"

        # Local Ollama Execution
        print(f"IDENTIFYING: Local model '{model_key}' at [{x}, {y}] with mode={drill_mode}...")
        model_map = {
            "qwen3.5": "qwen3.5:9b",
            "qwen": "qwen3.5:9b",
            "internvl": "internvl2",
            "pixtral": "pixtral",
            "llava_next": "llava-next",
            "minicpm": "minicpm-v",
            "moondream": "moondream",
            "llava": "llava",
            "phi4": "phi4",
            "llama_vision": "llama3.2-vision",
        }
        target_model = model_map.get(model_key, cls.VISION_MODEL_LOCAL)
        
        try:
            img_b64 = cls._prepare_vision_image(process_path, max_size=800)
            payload = {
                "model": target_model, 
                "prompt": prompt_to_use, 
                "images": [img_b64], 
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_ctx": 8192
                }
            }
            
            def run_ollama():
                try:
                    res = requests.post(f"{cls.OLLAMA_URL}/generate", json=payload, timeout=300)
                    if res.status_code == 200:
                        res_json = res.json()
                        if "error" not in res_json:
                            return res_json.get("response", "") or res_json.get("thinking", "")
                except Exception as err:
                    print(f"Ollama request error: {err}")
                
                # Fallback on failure
                if payload["model"] != cls.VISION_MODEL_LOCAL:
                    print(f"Model '{target_model}' failed or not found. Falling back to local Qwen3.5...")
                    payload["model"] = cls.VISION_MODEL_LOCAL
                    res = requests.post(f"{cls.OLLAMA_URL}/generate", json=payload, timeout=300)
                    if res.status_code == 200:
                        res_json = res.json()
                        return res_json.get("response", "") or res_json.get("thinking", "")
                return ""

            raw_text = await loop.run_in_executor(None, run_ollama)
            json_text = cls._extract_json(raw_text)
            data = json.loads(json_text)
            result = cls._sanitize_coordinates(data)
            
            drill_topic = result.get("drill_topic")
            if not drill_topic:
                if drill_mode == "pov":
                    drill_topic = f"A first-person point-of-view perspective looking outwards from {result.get('object', 'detail')}, photorealistic wide-angle view, showing the surroundings."
                else:
                    drill_topic = f"An extreme macro close-up of {result.get('object', 'detail')}, technical style."
            
            return {
                "drill_topic": drill_topic, 
                "raw_json": json.dumps(result, indent=2),
                "rawJson": json.dumps(result, indent=2),
                "metadata": result
            }, process_path
        except Exception as e:
            traceback.print_exc()
            return {"drill_topic": "detail", "metadata": {"object": "Error"}, "rawJson": str(e)}, process_path
        except Exception as e:
            traceback.print_exc()
            return {"drill_topic": "detail", "metadata": {"object": "Error"}, "rawJson": str(e)}, process_path
