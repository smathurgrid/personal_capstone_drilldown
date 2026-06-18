import torch
import numpy as np
from PIL import Image, ImageDraw
import os
import sys

# Add SAM2 path to sys.path to allow imports, allowing environment override for portability
SAM2_PATH = os.getenv("SAM2_PATH", "/Users/trohith/Documents/CAPSATONE PROJECT/sam2-test/sam2")
if SAM2_PATH not in sys.path:
    sys.path.append(SAM2_PATH)

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

class SAM2Service:
    _instance = None
    _predictor = None

    @classmethod
    def get_predictor(cls):
        if cls._predictor is None:
            import os
            # Ensure we are in the SAM2 directory context for hydra to find configs
            original_cwd = os.getcwd()
            try:
                os.chdir(SAM2_PATH)
                checkpoint = os.path.join(SAM2_PATH, "checkpoints/sam2.1_hiera_tiny.pt")
                model_cfg = "configs/sam2.1/sam2.1_hiera_t.yaml"
                
                device = "cpu"
                print(f"Loading SAM2 from {checkpoint} and {model_cfg} on device: {device}...")
                
                sam2_model = build_sam2(model_cfg, checkpoint, device=device)
                cls._predictor = SAM2ImagePredictor(sam2_model)
                print("SAM2 Predictor loaded successfully.")
            finally:
                os.chdir(original_cwd)
        return cls._predictor

    @classmethod
    def segment_object(cls, image_path: str, x: float, y: float, output_mask_path: str):
        """
        Uses SAM2 to generate a mask for the object at (x, y).
        Saves the segmented object (with black background) to output_mask_path.
        """
        predictor = cls.get_predictor()
        
        # Load and set image
        image = Image.open(image_path).convert("RGB")
        image_np = np.array(image)
        predictor.set_image(image_np)
        
        # Click point
        width, height = image.size
        input_point = np.array([[x * width, y * height]])
        input_label = np.array([1]) # 1 for foreground
        
        # Predict
        with torch.inference_mode(), torch.autocast(device_type="cuda" if torch.cuda.is_available() else "cpu", enabled=False):
            masks, scores, logits = predictor.predict(
                point_coords=input_point,
                point_labels=input_label,
                multimask_output=False,
            )
        
        # Process the mask (masks[0] is the best one)
        mask = masks[0] # Boolean array
        
        # Create an image from the mask
        mask_image = Image.fromarray((mask * 255).astype(np.uint8))
        
        # Create the segmented image (black background)
        segmented_img = Image.new("RGB", image.size, (0, 0, 0))
        segmented_img.paste(image, (0, 0), mask_image)
        
        segmented_img.save(output_mask_path, "PNG")
        
        # Return the bounding box of the mask for better cropping later
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        ymin, ymax = np.where(rows)[0][[0, -1]]
        xmin, xmax = np.where(cols)[0][[0, -1]]
        
        return {
            "bbox": [int(xmin), int(ymin), int(xmax), int(ymax)],
            "confidence": float(scores[0])
        }
