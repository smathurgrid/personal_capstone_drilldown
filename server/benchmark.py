import time
import requests
import json
import base64
import os
import math
import re
from PIL import Image
from io import BytesIO

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:9b"
DEFAULT_IMAGE = "static/d132aff11b05393d4cc087de31cc11d542b4eee3d4b0b6ccad3da0792fa6829c.png"

GOLDEN_DATA = {
    "Man reading book": [0.65, 0.50],
    "Coffee cup": [0.82, 0.95],
    "Laptop": [0.28, 0.50]
}

class VLM_Benchmarker:
    def __init__(self, model=MODEL, url=OLLAMA_URL):
        self.model = model
        self.url = url
        self.prompt = (
            "TASK: Forensic Scene Analysis.\n"
            "Identify 5 sub-components in 'granular_details'.\n"
            "Each MUST have: 'label' (name), and 'point' [x, y] coordinates.\n"
            "OUTPUT: Return ONLY a raw JSON object."
        )

    def prepare_image(self, image_path, max_size=768):
        if not os.path.exists(image_path): return None
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def extract_json(self, text):
        text = text.strip()
        # Find first [ or { and last ] or }
        start = min([i for i in [text.find('['), text.find('{')] if i != -1] or [0])
        end = max([i for i in [text.rfind(']'), text.rfind('}')] if i != -1] or [len(text)])
        return text[start:end+1]

    def sanitize_data(self, data):
        """Ultra-robust sanitizer for boxes and lists."""
        details = []
        if isinstance(data, list):
            details = data
        elif isinstance(data, dict):
            for key in ["granular_details", "details", "objects", "items"]:
                if key in data and isinstance(data[key], list):
                    details = data[key]; break
            if not details: details = data.get("granular_details", [])

        clean_details = []
        for item in details:
            if not isinstance(item, dict): continue
            label = item.get("label", item.get("component", "Unknown"))
            
            # Find point or bbox
            raw_p = item.get("point", item.get("center_point", item.get("bbox_2d", item.get("box", [0.5, 0.5]))))
            
            # Handle 4-number bbox: [y1, x1, y2, x2]
            if isinstance(raw_p, list) and len(raw_p) == 4:
                y1, x1, y2, x2 = raw_p
                point = [(x1+x2)/2.0, (y1+y2)/2.0] # Center of box
            elif isinstance(raw_p, list) and len(raw_p) >= 2:
                point = raw_p[:2]
            else:
                point = [0.5, 0.5]

            # Normalize 1000-grid to 0.0-1.0
            point = [v/1000.0 if v > 2.0 else v for v in point]
            clean_details.append({"label": label, "point": point})
            
        return {"granular_details": clean_details}

    def run_test(self, image_path):
        print(f"\n🚀 STARTING ADVANCED BENCHMARK: {self.model}")
        img_b64 = self.prepare_image(image_path)
        payload = {"model": self.model, "prompt": self.prompt, "images": [img_b64], "stream": False, "options": {"temperature": 0.0}}

        start_time = time.time()
        try:
            response = requests.post(self.url, json=payload, timeout=300)
            duration = time.time() - start_time
            raw_text = response.json().get("response", "")
            
            clean_json = self.extract_json(raw_text)
            data = json.loads(clean_json)
            
            clean_data = self.sanitize_data(data)
            self.print_scorecard(clean_data, duration)
        except Exception as e:
            print(f"❌ Test Failed: {e}")
            if 'raw_text' in locals(): print(f"Raw response head: {raw_text[:200]}...")

    def print_scorecard(self, data, duration):
        details = data.get("granular_details", [])
        print("\n" + "="*70)
        print(f"⏱️  Time: {duration:.2f}s | 📊 Count: {len(details)} objects")
        print("-" * 70)
        print(f"{'Detected Component':<35} | {'Coord':<15} | {'Precision'}")
        print("-" * 70)
        for item in details:
            label = item.get("label", "Unknown")
            point = item.get("point", [0,0])
            status = "N/A"
            for g_label, g_point in GOLDEN_DATA.items():
                if g_label.lower() in label.lower() or label.lower() in g_label.lower():
                    # Distance math
                    dist = math.sqrt((point[0]-g_point[0])**2 + (point[1]-g_point[1])**2)
                    status = f"{max(0, 100 - (dist * 100)):.1f}% Match"
                    break
            print(f"{label[:35]:<35} | {str([round(p,2) for p in point]):<15} | {status}")
        print("="*70)

if __name__ == "__main__":
    VLM_Benchmarker().run_test(DEFAULT_IMAGE)
