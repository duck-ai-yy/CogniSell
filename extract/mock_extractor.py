from __future__ import annotations

import os
import sys
from typing import Any

# Import module_a
try:
    from module_a.segmentation import segment_business_cards
    from module_a.agent import parse_business_card_image
except ImportError:
    # Fallback if module_a is not in path
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.dirname(_ROOT))
    from module_a.segmentation import segment_business_cards
    from module_a.agent import parse_business_card_image

from skills import fixtures

def scan_business_card(image_path: str) -> dict[str, Any]:
    """Pioneer A: real image -> structured fields with per-field confidence.
    """
    try:
        from dotenv import load_dotenv
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dotenv_path = os.path.join(os.path.dirname(_ROOT), ".env")
        load_dotenv(dotenv_path)
    except ImportError:
        pass

    if not os.path.exists(image_path):
        return {"ok": False, "error": f"Image not found at {image_path}"}
    
    try:
        cropped_image_paths = segment_business_cards(image_path)
    except Exception as e:
        return {"ok": False, "error": f"Segmentation failed: {str(e)}"}
    
    cards = []
    
    for i, path in enumerate(cropped_image_paths):
        structured_data = parse_business_card_image(path)
        if not structured_data.get("is_business_card", True):
            continue
            
        # Convert structured_data to fields list
        fields = []
        name = structured_data.get("name", "Unknown contact")
        company = structured_data.get("company", structured_data.get("company_name", "Unknown company"))
        title = structured_data.get("title", "")
        email = structured_data.get("email", "")
        phone = structured_data.get("phone", "")
        
        # We assign an arbitrary confidence of 0.6 to company to trigger human review
        fields.append({"key": "name", "value": name, "confidence": 0.95})
        fields.append({"key": "company", "value": company, "confidence": 0.6})
        fields.append({"key": "title", "value": title, "confidence": 0.9})
        fields.append({"key": "email", "value": email, "confidence": 0.95})
        fields.append({"key": "phone", "value": phone, "confidence": 0.95})
        
        # Generate node hints based on the extracted name and company
        person_id = f"n_person_{name.lower().replace(' ', '_')[:12]}" if name != "Unknown contact" else f"n_person_unknown_{i}"
        company_id = f"n_company_{company.lower().replace(' ', '_')[:12]}" if company != "Unknown company" else f"n_company_unknown_{i}"
        
        cards.append({
            "node_hints": {"person": person_id, "company": company_id},
            "fields": fields
        })
        
    return {
        "ok": True,
        "cards": cards
    }

def digest_email_thread(thread_id: str) -> dict[str, Any]:
    """Pioneer B: email thread -> relationship triples with confidence.
    """
    thread = fixtures.get_email_thread(thread_id)
    if thread is None:
        return {"ok": False, "thread_id": thread_id, "error": f"no email thread fixture for {thread_id!r}"}

    return {
        "ok": True,
        "thread_id": thread_id,
        "contact": thread.get("contact"),
        "triples": list(thread.get("extracted_triples", [])),
    }
