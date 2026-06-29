import asyncio
import json
import httpx
import argparse
import shutil
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

API_BASE = "http://127.0.0.1:8000/api/explainer"

# Load the API key from .env file
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

evaluator_model = None

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    preferred_models = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
        "models/gemini-pro-vision"
    ]
    
    active_model_name = preferred_models[2] # Default fallback
    try:
        available = [
            m.name
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        for preferred in preferred_models:
            if preferred in available:
                active_model_name = preferred
                break
        print(f"🤖 Configured Gemini Evaluator using model: {active_model_name}")
        evaluator_model = genai.GenerativeModel(active_model_name)
    except Exception as e:
        print(f"⚠️ Failed to list/bind Gemini models, falling back: {e}")
        evaluator_model = genai.GenerativeModel("models/gemini-1.5-flash")
else:
    print("⚠️ WARNING: GOOGLE_API_KEY not found in .env. Gemini Evaluation will be skipped.")

async def evaluate_image_with_gemini(parent_path: Path, child_path: Path, target_name: str) -> dict:
    if not evaluator_model:
        return {"score": 0, "feedback": "Skipped (No API Key)", "correction": "N/A"}
    
    print(f"🤖 Sending parent and child images to Gemini for visual consistency & depth evaluation...")
    try:
        # Load both parent and generated child images via PIL
        parent_img = Image.open(parent_path)
        child_img = Image.open(child_path)
        
        prompt = f"""
        You are an expert AI visual QA tester analyzing a recursive visual microscope drill-down sequence.
        
        INPUTS:
        1. Parent Image (Image 1): The wider view. The user focused on the region '{target_name}' in this image.
        2. Generated Child Image (Image 2): The deep internal view of what is inside or beneath '{target_name}'.
        
        CRITICAL ASSESSMENT:
        Is Image 2 actually a detailed, zoomed-in, internal cross-section or microscopic view of '{target_name}'?
        If Image 2 simply looks like the exact same object from the same camera angle, or is a generic copy/crop with no inner anatomical, mechanical, or structural detail, you must give it a VERY LOW score (less than 5).
        If Image 2 reveals genuine inside layers, fibers, cells, machinery, or microscopic structures that are logically inside '{target_name}', give it a HIGH score (7 or more).
        
        EVALUATION CRITERIA:
        1. Contextual Match: Does the generated child (Image 2) align with the visual style, color palette, lighting, material texture, and concept of the focused target '{target_name}' from the parent image (Image 1)?
        2. Depth: Is it actually an internal cross-section, microscopic cutaway, or deep drill-down of '{target_name}' (showing what's inside, not just the outside)?
        3. Score: Rate the quality and depth out of 10.
        4. Corrections: If the score is less than 7, provide 1 clear, specific "correction" instruction on exactly what inner structural details (e.g. "show microscopic muscle fibers, capillaries, and blood cells", "show paper fibers and ink grains") should be drawn to make it a real drill-down.
        
        Return your response strictly in the following JSON format:
        {{
            "score": <number between 1 and 10>,
            "feedback": "<1-2 short sentences summarizing visual style, color, and concept consistency>",
            "correction": "<Specific corrective suggestion to guide Flux on what internal components to generate>"
        }}
        """
        
        # Pass both images together to the multimodal model
        response = evaluator_model.generate_content([prompt, parent_img, child_img])
        response_text = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(response_text)
        return result
    except Exception as e:
        return {"score": 0, "feedback": f"Gemini Evaluation Failed: {str(e)}", "correction": f"Verify prompt details for {target_name}"}

async def run_recursive_test(image_path: str, max_depth: int):
    root_path = Path(image_path)
    if not root_path.exists():
        print(f"❌ Error: Image not found at {root_path}")
        return

    session_dir = Path("data/test_images") / f"{root_path.stem}_drills"
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=======================================================")
    print(f"🚀 Starting Self-Correcting Recursive Drill microscope Test")
    print(f"   Root Image: {root_path.name}")
    print(f"   Requested Depth Target: {max_depth} layers")
    print(f"   Results Folder: {session_dir}/")
    print(f"=======================================================\n")

    current_image_path = root_path
    evaluations = []
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        for depth in range(1, max_depth + 1):
            print(f"\n-------------------------------------------------------")
            print(f"🔬 [LAYER {depth}/{max_depth}] Drilling deeper...")
            print(f"-------------------------------------------------------\n")

            # STEP 1: UPLOAD CURRENT LAYER IMAGE
            print(f"[{depth}.1] Uploading image to API...")
            with open(current_image_path, "rb") as f:
                files = {"file": (current_image_path.name, f, "image/jpeg")}
                resp = await client.post(f"{API_BASE}/vision/upload", files=files)
            
            if not resp.is_success:
                print(f"❌ Layer {depth} Upload failed: {resp.text}")
                break
                
            page_data = resp.json()
            current_page_id = page_data["id"]
            print(f"✅ Upload successful! Page ID: {current_page_id}")

            # STEP 2: ANALYZE IMAGE (Extract Hotspots)
            print(f"\n[{depth}.2] Triggering Vision Analysis (qwen3.5:9b)...")
            resp = await client.post(
                f"{API_BASE}/vision/analyze",
                json={"pageId": current_page_id, "visionModel": "qwen3.5", "scanMode": "global"}
            )
            
            if not resp.is_success:
                print(f"❌ Layer {depth} Analysis failed: {resp.text}")
                break
                
            analysis_data = resp.json()
            metadata = analysis_data.get("metadata", {})
            hotspots = metadata.get("granular_details", [])
            
            if not hotspots:
                print("⚠️ No labels detected on this layer. Ending microscope exploration early.")
                break
                
            print(f"✅ Analysis complete! Found {len(hotspots)} AI hotspots.")
            
            # STEP 3: AUTO-SELECT A TARGET HOTSPOT
            target = hotspots[0]
            x, y = target.get("point", [0.5, 0.5])
            x_pct, y_pct = x * 100, y * 100
            target_name = target.get("label", "Unknown Component")
            
            print(f"\n[{depth}.3] Auto-selecting focus: '{target_name}' at [X:{x_pct:.1f}%, Y:{y_pct:.1f}%]")

            # PROGRESSIVE ANCESTRY PROMPT ACCUMULATION
            if depth == 1:
                custom_prompt = f"Detailed architectural cross-section cutaway showing the physical internal layers and materials inside the {target_name}"
            else:
                previous_target = evaluations[-1]["target"] if evaluations else "previous layer"
                custom_prompt = f"Extremely magnified, high-resolution microscopic close-up view deep inside the {target_name}, drilling down and zooming in from the previous {previous_target} structure"
            
            # GEMINI SELF-CORRECTION LOOP (MAX RETRIES = 3)
            max_retries = 3
            final_eval = None
            clean_target_name = "".join(c if c.isalnum() else "_" for c in target_name)
            saved_filename = f"{depth:02d}_drill_{clean_target_name}.png"
            local_save_path = session_dir / saved_filename
            
            for attempt in range(1, max_retries + 1):
                print(f"\n[{depth}.4.Attempt {attempt}/{max_retries}] Initiating drill-down stream (x/flux2-klein:4b-bf16)...")
                
                # STEP 4: ISOLATE & TRIGGER STREAM
                payload = {
                    "parentId": current_page_id,
                    "x": x,
                    "y": y,
                    "drillMode": "inside",
                    "visionModel": "qwen3.5",
                    "groundingMode": "red_ring",
                    "cacheBust": f"{asyncio.get_event_loop().time()}_attempt_{attempt}" # Force unique session per attempt!
                }
                
                print("⏳ Waiting for visual isolation & metadata analysis...")
                confirm_payload_data = None
                
                async with client.stream("POST", f"{API_BASE}/vision/stream-page", json=payload) as stream:
                    async for line in stream.aiter_lines():
                        line = line.strip()
                        if not line: continue
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if "expiresAt" in data and "pageId" in data:
                                    confirm_payload_data = data
                                    break
                            except:
                                pass

                if not confirm_payload_data:
                    print(f"❌ Failed to receive grounding confirmation for Layer {depth} (Attempt {attempt}).")
                    break

                child_page_id = confirm_payload_data["pageId"]
                print(f"  → Obtained valid session child ID: {child_page_id}")

                print(f"\n[{depth}.5.Attempt {attempt}/{max_retries}] Triggering Flux with Prompt: \"{custom_prompt}\"")
                
                confirm_resp = await client.post(
                    f"{API_BASE}/vision/confirm-drill",
                    json={
                        "pageId": child_page_id, # Pass the fresh unique page ID from stream!
                        "parentId": current_page_id,
                        "x": x,
                        "y": y,
                        "drillTopic": target_name,
                        "drillMode": "inside",
                        "customPrompt": custom_prompt
                    }
                )
                
                if confirm_resp.status_code != 200:
                    print(f"❌ Flux generation failed: {confirm_resp.text}")
                    break
                    
                final_data = confirm_resp.json()
                child_image_url = final_data.get("imageUrl")
                
                # Download generated image copies
                static_url = f"http://127.0.0.1:8000{child_image_url}"
                try:
                    img_resp = await client.get(static_url)
                    if img_resp.status_code == 200:
                        with open(local_save_path, "wb") as f_save:
                            f_save.write(img_resp.content)
                        print(f"💾 Saved layer {depth} (Attempt {attempt}) successfully!")
                    else:
                        raise Exception(f"HTTP {img_resp.status_code}")
                except Exception as e:
                    print(f"⚠️ Failed to download/save local image copy: {e}")
                    break

                # EVALUATE WITH GEMINI
                print(f"\n[{depth}.6.Attempt {attempt}/{max_retries}] Gemini Context Evaluation")
                eval_result = await evaluate_image_with_gemini(current_image_path, local_save_path, target_name)
                score = eval_result.get("score", 0)
                feedback = eval_result.get("feedback", "")
                correction = eval_result.get("correction", "")
                
                print(f"⭐ Score: {score}/10")
                print(f"📝 Feedback: {feedback}")
                
                final_eval = {
                    "depth": depth,
                    "target": target_name,
                    "file": saved_filename,
                    "score": score,
                    "feedback": feedback,
                    "correction": correction,
                    "attempts_needed": attempt
                }
                
                if score >= 7:
                    print(f"🎉 Perfect Score achieved ({score}/10) on attempt {attempt}! Saving and moving to next depth.")
                    break
                else:
                    if attempt < max_retries:
                        print(f"⚠️ Score is low ({score}/10). Gemini Corrective Feedback: \"{correction}\"")
                        print("🤖 Incorporating feedback and re-generating with Flux...")
                        # Append the Gemini correction directly to the EXISTING progressive custom_prompt!
                        custom_prompt = f"{custom_prompt}. STRICT QA DIRECTION: {correction}"
                    else:
                        print(f"⚠️ Reached max retries ({max_retries}). Saving best attempt ({score}/10).")

            if final_eval:
                evaluations.append(final_eval)
            
            # SET CURRENT LAYER COPY AS INPUT FOR NEXT DEPTH
            current_image_path = local_save_path

        print(f"\n=======================================================")
        print(f"🏆 MICROSCOPE DRILL TEST COMPLETED")
        print(f"   Max Depth Explored: {depth} layers")
        print(f"=======================================================\n")
        
        if evaluations:
            print("📋 FINAL GEMINI SELF-CORRECTING QA REPORT:")
            total_score = 0
            for ev in evaluations:
                print(f"  Layer {ev['depth']} | Target: {ev['target']} | Score: {ev['score']}/10 (Attempts: {ev['attempts_needed']})")
                print(f"  ├ Feedback: {ev['feedback']}")
                print(f"  └ Correction Suggestion: {ev['correction']}\n")
                total_score += float(ev.get("score", 0))
            
            avg_score = total_score / len(evaluations)
            print(f"📈 AVERAGE PIPELINE ACCURACY: {avg_score:.1f}/10")
        
        print(f"All images archived inside: {session_dir}/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Self-Correcting Recursive AI Drill-Down Tester with Gemini QA")
    parser.add_argument("--image", type=str, required=True, help="Path to test image")
    parser.add_argument("--depth", type=int, default=3, help="Recursion depth target (default: 3)")
    args = parser.parse_args()
    
    asyncio.run(run_recursive_test(args.image, args.depth))
