import os
import asyncio
from PIL import Image

class DepthService:
    _pipe = None
    _downloading = False

    @classmethod
    def get_pipeline(cls):
        if cls._pipe is not None:
            return cls._pipe
            
        # Lazily check and load locally
        from transformers import pipeline
        try:
            # Check if model is already locally cached
            cls._pipe = pipeline("depth-estimation", model="Intel/dpt-hybrid-midas", local_files_only=True)
            print("Loaded locally cached depth-estimation model successfully.")
            return cls._pipe
        except Exception:
            # Model is not cached, trigger a non-blocking background download
            if not cls._downloading:
                cls._downloading = True
                print("Model not cached locally. Triggering background download...")
                asyncio.create_task(cls._bg_download_model())
            return None

    @classmethod
    async def _bg_download_model(cls):
        try:
            from transformers import pipeline
            print("Starting background download of 'Intel/dpt-hybrid-midas'...")
            loop = asyncio.get_event_loop()
            
            # Run the blocking huggingface download in a worker thread
            def download():
                return pipeline("depth-estimation", model="Intel/dpt-hybrid-midas")
                
            cls._pipe = await loop.run_in_executor(None, download)
            print("Background model download finished! High-fidelity AI depth mapping is now active.")
        except Exception as e:
            print(f"Failed to download model in the background: {e}")
        finally:
            cls._downloading = False

    @classmethod
    def _sync_generate_depth_map(cls, image_path: str, output_path: str):
        """Synchronous part of depth generation that runs inside the executor."""
        try:
            pipe = cls.get_pipeline()
            if pipe is None:
                # If pipeline is downloading, use the fast grayscale fallback instantly
                print(f"Pipeline still downloading/unavailable. Using grayscale fallback instantly for: {image_path}")
                cls._generate_fallback_depth(image_path, output_path)
                return True

            # Open image via PIL
            img = Image.open(image_path)
            print(f"Estimating depth map for: {image_path}")
            result = pipe(img)
            
            if "depth" in result:
                depth_img = result["depth"]
                depth_img.save(output_path)
                print(f"Depth map successfully saved to: {output_path}")
                return True
            else:
                raise ValueError("No depth map found in pipeline result.")
        except Exception as e:
            print(f"Error generating depth map via HuggingFace: {e}. Falling back to grayscale depth map.")
            cls._generate_fallback_depth(image_path, output_path)
            return False

    @classmethod
    def _generate_fallback_depth(cls, image_path: str, output_path: str):
        """Generates a fallback depth map by converting original image to grayscale."""
        try:
            if os.path.exists(image_path):
                with Image.open(image_path) as img:
                    fallback_img = img.convert("L")
                    fallback_img.save(output_path)
                    print(f"Saved fallback grayscale depth map to: {output_path}")
            else:
                fallback_img = Image.new("L", (512, 512), 128)
                fallback_img.save(output_path)
                print(f"Source image not found. Saved dummy grey depth map to: {output_path}")
        except Exception as fallback_err:
            print(f"Failed to generate fallback depth map: {fallback_err}")

    @classmethod
    async def generate_depth_map(cls, image_path: str, output_path: str):
        """Asynchronously estimates depth map wrapping synchronous execution in an executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, cls._sync_generate_depth_map, image_path, output_path)
