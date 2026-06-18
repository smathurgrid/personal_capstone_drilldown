import hashlib
import os
import asyncio
import json
from app.services.ai_service import AIService
from app.utils.compositor import ImageCompositor
from app.services.depth_service import DepthService
try:
    from app.services.sam2_service import SAM2Service
except Exception as e:
    print(f"WARNING: Could not import SAM2Service: {e}")
    SAM2Service = None

STATIC_DIR = "static"

class PageService:
    @staticmethod
    def get_hash(key: str):
        return hashlib.sha256(key.encode()).hexdigest()

    def generate_page_hash(self, parent_id: str, x: float, y: float, vision_model: str, grounding_mode: str, custom_topic: str = None, drill_mode: str = "inside"):
        """Generates a robust and unified hash key for child pages with consistent coordinate rounding."""
        rx = round(x, 4)
        ry = round(y, 4)
        hash_key = f"drill_{parent_id}_{rx}_{ry}_{vision_model}_{grounding_mode}_{drill_mode}"
        if custom_topic:
            hash_key += f"_{custom_topic}"
        return self.get_hash(hash_key)

    def _get_parent_path(self, parent_id: str) -> str:
        """Resolves parent_id to its absolute local file path (supports document pages)."""
        if parent_id.startswith("doc_"):
            parts = parent_id.split("_")
            if len(parts) >= 3:
                doc_id = parts[1]
                page_part = parts[2]
                page_num = page_part[1:]
                return os.path.join(STATIC_DIR, "documents", doc_id, f"page_{page_num}.png")
        return os.path.join(STATIC_DIR, f"{parent_id}.png")

    async def _run_grounding_async(self, page_id: str, parent_path: str, x: float, y: float, grounding_mode: str):
        """
        Runs grounding phase (SAM2 segmenting or Red Ring marking) asynchronously.
        Enforces graceful degradation to Red Ring if SAM2 is unavailable or fails.
        """
        loop = asyncio.get_event_loop()
        segment_path = None
        marked_path = None
        sam_confidence = None
        final_mode = grounding_mode

        if grounding_mode == "sam2" and SAM2Service is not None:
            segment_path = os.path.join(STATIC_DIR, f"seg_{page_id}.png")
            try:
                def run_sam():
                    return SAM2Service.segment_object(parent_path, x, y, segment_path)
                sam_info = await loop.run_in_executor(None, run_sam)
                sam_confidence = sam_info['confidence']
            except Exception as e:
                print(f"SAM2 segmentation failed: {e}. Falling back to Red Ring grounding...")
                segment_path = None

        if grounding_mode == "red_ring" or segment_path is None or SAM2Service is None:
            final_mode = "red_ring"
            marked_path = os.path.join(STATIC_DIR, f"marked_{page_id}.png")
            def draw_ring():
                ImageCompositor.draw_red_ring(parent_path, x, y, marked_path)
            await loop.run_in_executor(None, draw_ring)

        return segment_path, marked_path, sam_confidence, final_mode

    async def _run_vision(self, parent_path: str, x: float, y: float, vision_model: str, grounding_path: str, custom_topic: str = None, drill_mode: str = "inside"):
        """
        Runs context identification using the chosen vision model.
        Returns a (vision_result, crop_path) tuple.
        """
        if custom_topic:
            # SEMANTIC DRILL: Use custom label text directly
            if drill_mode == "pov":
                drill_topic = f"A first-person point-of-view perspective looking outwards from the {custom_topic}, showing the complete surrounding layout, seating, or scenery as seen from this exact vantage point."
                editorial_headline = f"Perspective View: From {custom_topic}"
                explainer_paragraph = f"This layer generates a realistic first-person point-of-view perspective looking outward from the position of the {custom_topic}."
            else:
                drill_topic = f"An extreme macro close-up of {custom_topic}, focusing on its specific textures, materials, and fine details."
                editorial_headline = f"Drilling into: {custom_topic}"
                explainer_paragraph = f"This layer explores the specific details of the {custom_topic} identified in the previous scene."

            vision_result = {
                "drill_topic": drill_topic,
                "metadata": {
                    "object": custom_topic,
                    "editorial_headline": editorial_headline,
                    "explainer_paragraph": explainer_paragraph,
                    "style": "Technical continuity"
                },
                "input_prompt": f"Detail zoom of {custom_topic}" if drill_mode != "pov" else f"POV perspective of {custom_topic}",
                "raw_json": json.dumps({"object": custom_topic})
            }
            crop_path = grounding_path
        elif vision_model == "none":
            vision_result = {
                "drill_topic": "a detailed macro-zoom into the textures and components of this specific area",
                "metadata": {
                    "object": "Undefined Component",
                    "editorial_headline": "The Pure Detail",
                    "explainer_paragraph": "This is a direct visual drill-down without semantic analysis. The AI is interpreting the textures and shapes of the original image to generate a deeper layer.",
                    "style": "Visual continuity from previous page"
                },
                "input_prompt": "N/A - Vision Skipped",
                "raw_json": "{}"
            }
            crop_path = None
        else:
            vision_result, crop_path = await AIService.identify_context(
                parent_path, x, y, 
                model_key=vision_model, 
                segment_path=grounding_path,
                drill_mode=drill_mode
            )

        return vision_result, crop_path

    async def get_or_create_page(self, query: str = None, parent_id: str = None, x: float = None, y: float = None, vision_model: str = "qwen3.5", grounding_mode: str = "sam2", drill_mode: str = "inside"):
        if query:
            page_id = self.get_hash(f"initial_{query}")
            output_path = os.path.join(STATIC_DIR, f"{page_id}.png")
            depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
            
            if os.path.exists(output_path):
                if not os.path.exists(depth_path):
                    await DepthService.generate_depth_map(output_path, depth_path)
                return {
                    "id": page_id, 
                    "imageUrl": f"/static/{page_id}.png",
                    "depthUrl": f"/static/{page_id}_depth.png"
                }
            
            prompt = f"A watercolor illustration of {query}, pale palette, serif title, 16:9"
            await AIService.generate_image(prompt, output_path)
            await DepthService.generate_depth_map(output_path, depth_path)
            return {
                "id": page_id, 
                "imageUrl": f"/static/{page_id}.png",
                "depthUrl": f"/static/{page_id}_depth.png"
            }

        if parent_id and x is not None and y is not None:
            # Hash now generated via unified generate_page_hash
            page_id = self.generate_page_hash(parent_id, x, y, vision_model, grounding_mode, drill_mode=drill_mode)
            output_path = os.path.join(STATIC_DIR, f"{page_id}.png")
            json_path = os.path.join(STATIC_DIR, f"{page_id}.json")
            video_path = os.path.join(STATIC_DIR, f"trans_{page_id}.mp4")

            # Cache Hit Logic
            if os.path.exists(output_path) and os.path.exists(json_path):
                print(f"Cache Hit for page: {page_id}")
                with open(json_path, "r") as f:
                    cached_data = json.load(f)
                depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
                if not os.path.exists(depth_path):
                    await DepthService.generate_depth_map(output_path, depth_path)
                if not os.path.exists(video_path):
                    parent_path = self._get_parent_path(parent_id)
                    from app.services.video_service import VideoService
                    await asyncio.get_event_loop().run_in_executor(
                        None, VideoService.generate_zoom_transition, parent_path, output_path, x, y, video_path
                    )
                return {
                    "id": page_id,
                    "imageUrl": f"/static/{page_id}.png",
                    "depthUrl": f"/static/{page_id}_depth.png",
                    "videoUrl": f"/static/trans_{page_id}.mp4",
                    **cached_data
                }
            
            parent_path = self._get_parent_path(parent_id)
            if not os.path.exists(parent_path):
                raise FileNotFoundError(f"Parent image not found: {parent_path}")

            # 1. Unified Grounding Phase
            segment_path, marked_path, sam_confidence, final_mode = await self._run_grounding_async(
                page_id, parent_path, x, y, grounding_mode
            )

            # 2. Identify context
            grounding_path = segment_path if segment_path else marked_path
            
            if vision_model == "all":
                # Comparison mode (runs multiple models concurrently)
                models_to_test = ["gemini", "qwen3.5", "qwen", "internvl", "pixtral", "llava_next", "minicpm", "moondream", "llava", "phi4", "llama_vision"]
                
                async def run_model(m_key):
                    try:
                        res, c_path = await AIService.identify_context(
                            parent_path, x, y, 
                            model_key=m_key, 
                            segment_path=grounding_path,
                            drill_mode=drill_mode
                        )
                        return {"model": m_key, "metadata": res.get("metadata", {}), "rawJson": res.get("raw_json", "")}
                    except Exception as e:
                        return {"model": m_key, "metadata": {"error": str(e)}, "rawJson": ""}

                tasks = [run_model(m) for m in models_to_test]
                results = await asyncio.gather(*tasks)
                
                result_meta = {
                    "isComparison": True,
                    "results": results,
                    "groundingMode": final_mode
                }
                
                # Cleanup grounding images
                if marked_path and os.path.exists(marked_path):
                    os.remove(marked_path)
                if segment_path and os.path.exists(segment_path):
                    os.remove(segment_path)
                    
                return {
                    "id": page_id, 
                    "imageUrl": f"/static/{parent_id}.png",
                    **result_meta
                }

            # Normal single model execution (re-uses shared helper)
            vision_result, crop_path = await self._run_vision(
                parent_path, x, y, vision_model, grounding_path, drill_mode=drill_mode
            )
            
            drill_topic = vision_result.get("drill_topic", "a detailed sub-component")
            metadata = vision_result.get("metadata", {})
            input_prompt = vision_result.get("input_prompt", "")
            raw_json = vision_result.get("raw_json", "")

            # 3. Generate child page guided by the style reference
            ref_path = segment_path if segment_path else crop_path
            await AIService.generate_image(drill_topic, output_path, reference_image_path=ref_path)
            
            # Generate depth map
            depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
            await DepthService.generate_depth_map(output_path, depth_path)
            
            # Generate zoom transition video
            video_path = os.path.join(STATIC_DIR, f"trans_{page_id}.mp4")
            from app.services.video_service import VideoService
            await asyncio.get_event_loop().run_in_executor(
                None, VideoService.generate_zoom_transition, parent_path, output_path, x, y, video_path
            )
            
            # Prepare result object
            result_meta = {
                "context": drill_topic,
                "metadata": metadata,
                "inputPrompt": input_prompt or drill_topic,
                "rawJson": raw_json,
                "samConfidence": sam_confidence,
                "groundingMode": final_mode
            }

            # Save metadata to cache
            with open(json_path, "w") as f:
                json.dump(result_meta, f)

            # Clean up temp files
            if segment_path and os.path.exists(segment_path):
                os.remove(segment_path)
            if marked_path and os.path.exists(marked_path):
                os.remove(marked_path)
            if crop_path and os.path.exists(crop_path) and crop_path != parent_path:
                os.remove(crop_path)
                
            return {
                "id": page_id, 
                "imageUrl": f"/static/{page_id}.png",
                "depthUrl": f"/static/{page_id}_depth.png",
                "videoUrl": f"/static/trans_{page_id}.mp4",
                **result_meta
            }
        
        raise ValueError("Invalid parameters for page generation")

    async def stream_page(self, query: str = None, parent_id: str = None, x: float = None, y: float = None, vision_model: str = "qwen3.5", grounding_mode: str = "sam2", custom_topic: str = None, drill_mode: str = "inside"):
        def sse(event: str, data: dict):
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        if query:
            yield sse("generating", {"message": "Generating initial image..."})
            page_id = self.get_hash(f"initial_{query}")
            output_path = os.path.join(STATIC_DIR, f"{page_id}.png")
            depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
            if not os.path.exists(output_path):
                prompt = f"A watercolor illustration of {query}, pale palette, serif title, 16:9"
                
                gen_task = asyncio.create_task(
                    AIService.generate_image(prompt, output_path)
                )
                
                # Keep-alive heartbeat loop during initial image generation
                while not gen_task.done():
                    await asyncio.sleep(1.5)
                    yield sse("ping", {"message": "Generating initial image..."})
                    
                await gen_task
                
            if not os.path.exists(depth_path):
                yield sse("generating", {"message": "Analyzing scene depth..."})
                await DepthService.generate_depth_map(output_path, depth_path)
                
            yield sse("complete", {
                "id": page_id, 
                "imageUrl": f"/static/{page_id}.png",
                "depthUrl": f"/static/{page_id}_depth.png"
            })
            return

        if parent_id and x is not None and y is not None:
            print(f"Drill Request: parent={parent_id}, x={x}, y={y}, custom={custom_topic}, mode={drill_mode}")
            
            # Unified page_id calculation
            page_id = self.generate_page_hash(parent_id, x, y, vision_model, grounding_mode, custom_topic, drill_mode=drill_mode)
            output_path = os.path.join(STATIC_DIR, f"{page_id}.png")
            json_path = os.path.join(STATIC_DIR, f"{page_id}.json")

            if os.path.exists(output_path) and os.path.exists(json_path):
                with open(json_path, "r") as f:
                    cached_data = json.load(f)
                depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
                video_path = os.path.join(STATIC_DIR, f"trans_{page_id}.mp4")
                if not os.path.exists(depth_path):
                    yield sse("generating", {"message": "Analyzing scene depth..."})
                    await DepthService.generate_depth_map(output_path, depth_path)
                if not os.path.exists(video_path):
                    yield sse("generating", {"message": "Rendering zoom transition..."})
                    parent_path = self._get_parent_path(parent_id)
                    from app.services.video_service import VideoService
                    await asyncio.get_event_loop().run_in_executor(
                        None, VideoService.generate_zoom_transition, parent_path, output_path, x, y, video_path
                    )
                yield sse("complete", {
                    "id": page_id, 
                    "imageUrl": f"/static/{page_id}.png", 
                    "depthUrl": f"/static/{page_id}_depth.png", 
                    "videoUrl": f"/static/trans_{page_id}.mp4",
                    **cached_data
                })
                return

            parent_path = self._get_parent_path(parent_id)
            if not os.path.exists(parent_path):
                print(f"ERROR: Parent image not found: {parent_path}")
                yield sse("error", {"message": "Parent image not found. Please wait for the current image to finish loading."})
                return

            yield sse("grounding", {"message": "Isolating object..."})
            
            # 1. Unified Grounding Phase
            segment_path, marked_path, sam_confidence, final_mode = await self._run_grounding_async(
                page_id, parent_path, x, y, grounding_mode
            )
            
            yield sse("vision", {"message": "Analyzing component...", "samConfidence": sam_confidence})
            grounding_path = segment_path if segment_path else marked_path
            
            if vision_model == "all":
                yield sse("error", {"message": "Compare mode not supported in stream yet."})
                return

            # 2. Unified Vision Phase
            vision_result, crop_path = await self._run_vision(
                parent_path, x, y, vision_model, grounding_path, custom_topic, drill_mode=drill_mode
            )
            
            drill_topic = vision_result.get("drill_topic", "a detailed sub-component")
            metadata = vision_result.get("metadata", {})
            input_prompt = vision_result.get("input_prompt", "")
            raw_json = vision_result.get("raw_json", "")

            result_meta = {
                "context": drill_topic,
                "metadata": metadata,
                "inputPrompt": input_prompt or drill_topic,
                "rawJson": raw_json,
                "samConfidence": sam_confidence,
                "groundingMode": final_mode
            }
            
            # Yield metadata so UI can update instantly before image finishes
            yield sse("generating", {
                "message": "Illustrating detail...", 
                "metadata": metadata, 
                "samConfidence": sam_confidence,
                "rawJson": raw_json,
                "inputPrompt": input_prompt or drill_topic
            })

            # 3. Generate child page guided by the style reference as an asyncio task
            ref_path = segment_path if segment_path else crop_path
            print(f"Generating image for topic: {drill_topic[:50]}...")
            
            gen_task = asyncio.create_task(
                AIService.generate_image(drill_topic, output_path, reference_image_path=ref_path)
            )
            
            # Keep-alive heartbeat loop to prevent HTTP connection timeouts
            while not gen_task.done():
                await asyncio.sleep(1.5)
                yield sse("ping", {"message": "Illustrating detail (applying style continuity)..."})
                
            await gen_task
            print(f"Image generation finished: {output_path}")
            
            # Generate depth map
            yield sse("generating", {"message": "Analyzing scene depth...", **result_meta})
            depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
            await DepthService.generate_depth_map(output_path, depth_path)
            
            # Generate zoom transition video
            yield sse("generating", {"message": "Rendering zoom transition...", **result_meta})
            video_path = os.path.join(STATIC_DIR, f"trans_{page_id}.mp4")
            from app.services.video_service import VideoService
            await asyncio.get_event_loop().run_in_executor(
                None, VideoService.generate_zoom_transition, parent_path, output_path, x, y, video_path
            )
            
            with open(json_path, "w") as f:
                json.dump(result_meta, f)
            print(f"Metadata saved to: {json_path}")

            if segment_path and os.path.exists(segment_path): os.remove(segment_path)
            if marked_path and os.path.exists(marked_path): os.remove(marked_path)
            if crop_path and os.path.exists(crop_path) and crop_path != parent_path: os.remove(crop_path)
            
            print(f"Sending complete event for {page_id}")
            yield sse("complete", {
                "id": page_id, 
                "imageUrl": f"/static/{page_id}.png", 
                "depthUrl": f"/static/{page_id}_depth.png", 
                "videoUrl": f"/static/trans_{page_id}.mp4",
                **result_meta
            })
            return

        yield sse("error", {"message": "Invalid parameters for page generation"})
