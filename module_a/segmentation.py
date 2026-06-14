import cv2
import numpy as np
import os

def segment_business_cards(image_path, output_dir="output_crops"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image from {image_path}")
        
    original = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Lower Canny thresholds to capture low-contrast card edges
    edged = cv2.Canny(blurred, 10, 100)
    
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        bbox_area = w * h
        aspect_ratio = w / float(h)
        
        # Check bounding box area and aspect ratio
        if bbox_area > 40000 and (0.3 < aspect_ratio < 3.0):
            candidates.append((x, y, w, h, bbox_area))
            
    # Sort candidates by area descending
    candidates = sorted(candidates, key=lambda val: val[4], reverse=True)
    
    # Deduplicate overlapping bounding boxes (if intersection > 60%)
    final_boxes = []
    for cand in candidates:
        x, y, w, h, area = cand
        overlap = False
        for fbox in final_boxes:
            fx, fy, fw, fh = fbox
            # Intersection
            ix1 = max(x, fx)
            iy1 = max(y, fy)
            ix2 = min(x+w, fx+fw)
            iy2 = min(y+h, fy+fh)
            
            iw = max(0, ix2 - ix1)
            ih = max(0, iy2 - iy1)
            iarea = iw * ih
            
            if iarea > 0:
                if (iarea / float(w*h) > 0.6) or (iarea / float(fw*fh) > 0.6):
                    overlap = True
                    break
        if not overlap:
            final_boxes.append((x, y, w, h))
            
    cropped_images = []
    for idx, box in enumerate(final_boxes):
        x, y, w, h = box
        cropped = original[y:y+h, x:x+w]
        output_path = os.path.join(output_dir, f"card_{idx}.png")
        cv2.imwrite(output_path, cropped)
        cropped_images.append(output_path)
            
    return cropped_images
