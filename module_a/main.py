import json
import os
import argparse
from dotenv import load_dotenv
from segmentation import segment_business_cards
from agent import parse_business_card_image

# Load environment variables from .env file
load_dotenv()

def _safe_output_path(output_json: str) -> str:
    """Validate an output path before writing to prevent traversal."""
    if not output_json or not isinstance(output_json, str) or "\x00" in output_json:
        raise ValueError("Invalid output path.")
    resolved = os.path.realpath(output_json)
    base = os.environ.get("CARD_DATA_DIR")
    if base:
        base = os.path.realpath(base)
        if resolved != base and not resolved.startswith(base + os.sep):
            raise ValueError("Output path escapes the allowed data directory.")
    return resolved

def process_image(image_path, output_json="results.json"):
    print(f"Processing main image: {image_path}")
    
    # Step 1: Segmentation using OpenCV
    print("Segmenting business cards...")
    try:
        cropped_image_paths = segment_business_cards(image_path)
        print(f"Found {len(cropped_image_paths)} candidates.")
    except Exception as e:
        print(f"Segmentation failed: {e}")
        return

    all_cards_info = []

        # Step 2: Extracting data with Multimodal Vision Agent
    for i, path in enumerate(cropped_image_paths):
        print(f"\nProcessing candidate {i+1}/{len(cropped_image_paths)}: {path}")
        
        print("Analyzing image with Gemini Vision Agent...")
        structured_data = parse_business_card_image(path)
        
        # Check if the model identified it as a valid business card
        if not structured_data.get("is_business_card", True):
            print("Skipped: Candidate identified as background noise/not a business card.")
            continue
            
        print("Success! Business card parsed.")
        structured_data["source_image"] = path
        structured_data.pop("is_business_card", None)
        
        # Step 3: Internet Research Enrichment
        print("Enriching data with Internet Research Agent (Tavily + Gemini)...")
        from research_agent import enrich_business_card_data
        enriched_data = enrich_business_card_data(structured_data)
        
        # Preserve source image path just in case the enrichment model drops it
        enriched_data["source_image"] = path
        
        all_cards_info.append(enriched_data)
        print(f"Enriched Info: {enriched_data}")

    # Output to JSON
    safe_output = _safe_output_path(output_json)
    with open(safe_output, 'w', encoding='utf-8') as f:
        json.dump(all_cards_info, f, indent=4, ensure_ascii=False)
        
    print(f"\nAll done! Results saved to {output_json}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process an image containing multiple business cards.")
    parser.add_argument("image_path", help="Path to the input image file")
    parser.add_argument("--output", default="results.json", help="Path to the output JSON file")
    args = parser.parse_args()
    
    if not os.path.exists(args.image_path):
        print(f"Error: Image file not found at {args.image_path}")
    else:
        process_image(args.image_path, args.output)
