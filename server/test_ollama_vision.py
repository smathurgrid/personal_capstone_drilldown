import base64
import json
import requests
import os

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:9b"
# Using one of the existing png files from static
IMAGE_PATH = "server/static/d132aff11b05393d4cc087de31cc11d542b4eee3d4b0b6ccad3da0792fa6829c.png"

PROMPT = "Return a JSON object with one item: {\"granular_details\": [{\"label\": \"test\", \"point\": [500, 500]}]}. Identify one object in this image and give its coordinates."

def test():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: {IMAGE_PATH} not found")
        return

    with open(IMAGE_PATH, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "images": [img_b64],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 8192
        }
    }

    try:
        print(f"Calling Ollama {MODEL} with image {IMAGE_PATH}...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        print(f"Status Code: {response.status_code}")
        res_json = response.json()
        print(f"Full Response: {json.dumps(res_json, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
