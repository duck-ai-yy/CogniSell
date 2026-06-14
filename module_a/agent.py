import os
import base64
from dotenv import load_dotenv
load_dotenv()
from pydantic import BaseModel, Field
from typing import Optional

# Define the structured output schema
class BusinessCardInfo(BaseModel):
    name: Optional[str] = Field(description="The name of the person on the business card.")
    company: Optional[str] = Field(description="The company name.")
    title: Optional[str] = Field(description="The job title or position of the person.")
    phone: Optional[str] = Field(description="The phone number.")
    email: Optional[str] = Field(description="The email address.")
    website: Optional[str] = Field(description="The website URL if present.")
    address: Optional[str] = Field(description="The physical address.")

class BusinessCardList(BaseModel):
    cards: list[BusinessCardInfo] = Field(description="List of business cards found in the image. Return an empty list if no business cards are present.")

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

def _safe_image_path(image_path: str) -> str:
    """Validate an image path before opening to prevent file-inclusion/traversal."""
    if not image_path or not isinstance(image_path, str) or "\x00" in image_path:
        raise ValueError("Invalid image path.")
    resolved = os.path.realpath(image_path)
    base = os.environ.get("CARD_DATA_DIR")
    if base:
        base = os.path.realpath(base)
        if resolved != base and not resolved.startswith(base + os.sep):
            raise ValueError("Image path escapes the allowed data directory.")
    if os.path.splitext(resolved)[1].lower() not in _IMAGE_EXTS:
        raise ValueError("Unsupported image file type.")
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    return resolved

def encode_image(image_path):
    safe_path = _safe_image_path(image_path)
    with open(safe_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def parse_business_card_image(image_path: str) -> dict:
    """
    Uses Gemini Vision API via LangChain to parse an image directly, extracting potentially multiple business cards.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it in your .env file.")
        
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.messages import HumanMessage

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    parser = PydanticOutputParser(pydantic_object=BusinessCardList)
    
    image_base64 = encode_image(image_path)
    
    prompt = f"""Extract the relevant information for ALL business cards found in the provided image.
If there are multiple business cards, extract information for each of them.
If the image contains no business cards (e.g. it is just a blank table, notebook corner, or noise), return an empty list.

{parser.get_format_instructions()}
"""

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": f"data:image/png;base64,{image_base64}"}
        ]
    )
    
    try:
        res = llm.invoke([message])
        result = parser.parse(res.content)
        return result.model_dump()
    except Exception as e:
        print(f"Error parsing image: {e}")
        return {"error": str(e), "cards": []}
