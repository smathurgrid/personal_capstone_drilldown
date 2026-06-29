"""SAM2 segmentation — ported from branch_rohith with configurable SAM2_PATH."""

import os
import sys

import numpy as np
from PIL import Image

from backend.shared.config import settings

SAM2Service = None

if settings.SAM2_PATH and os.path.isdir(settings.SAM2_PATH):
    SAM2_PATH = settings.SAM2_PATH
    if SAM2_PATH not in sys.path:
        sys.path.append(SAM2_PATH)

    try:
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        class _SAM2Service:
            _predictor = None

            @classmethod
            def get_predictor(cls):
                if cls._predictor is None:
                    original_cwd = os.getcwd()
                    try:
                        os.chdir(SAM2_PATH)
                        checkpoint = os.path.join(SAM2_PATH, "checkpoints/sam2.1_hiera_tiny.pt")
                        model_cfg = "configs/sam2.1/sam2.1_hiera_t.yaml"
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                        sam2_model = build_sam2(model_cfg, checkpoint, device=device)
                        cls._predictor = SAM2ImagePredictor(sam2_model)
                    finally:
                        os.chdir(original_cwd)
                return cls._predictor

            @classmethod
            def segment_object(cls, image_path: str, x: float, y: float, output_mask_path: str):
                predictor = cls.get_predictor()
                image = Image.open(image_path).convert("RGB")
                image_np = np.array(image)
                predictor.set_image(image_np)
                width, height = image.size
                input_point = np.array([[x * width, y * height]])
                input_label = np.array([1])
                with torch.inference_mode():
                    masks, scores, _ = predictor.predict(
                        point_coords=input_point,
                        point_labels=input_label,
                        multimask_output=False,
                    )
                mask = masks[0]
                mask_image = Image.fromarray((mask * 255).astype(np.uint8))
                segmented_img = Image.new("RGB", image.size, (0, 0, 0))
                segmented_img.paste(image, (0, 0), mask_image)
                segmented_img.save(output_mask_path, "PNG")
                rows = np.any(mask, axis=1)
                cols = np.any(mask, axis=0)
                ymin, ymax = np.where(rows)[0][[0, -1]]
                xmin, xmax = np.where(cols)[0][[0, -1]]
                return {
                    "bbox": [int(xmin), int(ymin), int(xmax), int(ymax)],
                    "confidence": float(scores[0]),
                }

        SAM2Service = _SAM2Service
    except Exception as exc:
        print(f"WARNING: Could not load SAM2Service: {exc}")
