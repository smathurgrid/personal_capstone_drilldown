import os
import cv2
import numpy as np
from PIL import Image

class VideoService:
    @classmethod
    def generate_zoom_transition(cls, parent_path: str, child_path: str, x: float, y: float, output_path: str):
        """
        Generates a 1.5-second, 30fps MP4 video zooming into (x, y) coordinates of the parent image
        and smoothly cross-fading into the child image.
        """
        print(f"COMPILING LOCAL TRANSITION: {parent_path} -> {child_path} at ({x}, {y})")
        
        try:
            # 1. Load images using OpenCV
            parent_img = cv2.imread(parent_path)
            child_img = cv2.imread(child_path)
            
            if parent_img is None or child_img is None:
                raise FileNotFoundError("Parent or child image could not be loaded.")
            
            h, w, c = parent_img.shape
            
            # Ensure child image matches parent dimensions
            if child_img.shape != parent_img.shape:
                child_img = cv2.resize(child_img, (w, h))
                
            # 2. Configure video writer
            # We use 'avc1' fourcc which compiles a standard H.264 MP4 file compatible with all standard HTML5 browsers
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            fps = 30
            num_frames = 45 # 1.5 seconds at 30fps
            
            out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
            if not out.isOpened():
                raise IOError(f"Could not open VideoWriter for path: {output_path}")
                
            # 3. Generate transition frames
            max_scale = 3.2 # Soft, gentle zoom scale factor
            
            for i in range(num_frames):
                t = i / (num_frames - 1)
                
                # Ease-in-out cubic curve for organic camera acceleration
                t_eased = 3 * (t ** 2) - 2 * (t ** 3)
                
                # Interpolate scale and pan center
                scale = 1.0 + (max_scale - 1.0) * t_eased
                
                # Lerp the focus point from the screen center (0.5, 0.5) to the clicked coordinate (x, y)
                cx = 0.5 + (x - 0.5) * t_eased
                cy = 0.5 + (y - 0.5) * t_eased
                
                # Convert normalized coordinates to pixel center
                px = int(cx * w)
                py = int(cy * h)
                
                # Calculate cropping box boundaries
                crop_w = int(w / scale)
                crop_h = int(h / scale)
                
                x1 = max(0, px - crop_w // 2)
                y1 = max(0, py - crop_h // 2)
                
                x2 = min(w, x1 + crop_w)
                y2 = min(h, y1 + crop_h)
                
                # Handle edge alignment adjustments
                if x2 - x1 < crop_w:
                    x1 = max(0, x2 - crop_w)
                if y2 - y1 < crop_h:
                    y1 = max(0, y2 - crop_h)
                    
                # Extract and resize the zoomed parent crop
                cropped = parent_img[y1:y2, x1:x2]
                zoomed_parent = cv2.resize(cropped, (w, h))
                
                # Calculate cross-fade blend opacity (alpha)
                # We start the cross-fade early at 15% of progress to create a soft, gradual lens dissolve
                alpha = 0.0
                if t_eased >= 0.15:
                    alpha = (t_eased - 0.15) / 0.85
                    
                # Blend the zoomed parent frame and the child image
                blended_frame = cv2.addWeighted(zoomed_parent, 1.0 - alpha, child_img, alpha, 0)
                
                out.write(blended_frame)
                
            out.release()
            print(f"Cinematic zoom transition successfully saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"Failed to generate zoom transition video: {e}")
            import traceback
            traceback.print_exc()
            return False
