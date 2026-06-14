import os
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()

def load_text_file(filepath: str) -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def load_lead_profile(results_json_path: str, company: str, recipient: str = None) -> dict:
    """
    Search results.json for a matching company and/or recipient name.
    """
    if not os.path.exists(results_json_path):
        raise FileNotFoundError(f"Lead data file not found: {results_json_path}")
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        leads = json.load(f)
        
    # Standardize input for searching
    company_lower = company.lower() if company else ""
    recipient_lower = recipient.lower() if recipient else ""
    
    # Try precise match first
    for lead in leads:
        lead_company = lead.get("company", "").lower()
        lead_name = lead.get("name", "").lower()
        
        if recipient_lower and company_lower:
            if recipient_lower in lead_name and company_lower in lead_company:
                return lead
        elif company_lower:
            if company_lower in lead_company:
                return lead
        elif recipient_lower:
            if recipient_lower in lead_name:
                return lead
                
    # Fallback to loose match (just company or just recipient)
    for lead in leads:
        if company_lower and company_lower in lead.get("company", "").lower():
            return lead
        if recipient_lower and recipient_lower in lead.get("name", "").lower():
            return lead
            
    return None

def write_cold_email(product_doc_path: str, company: str, recipient: str = None, lead_profile: dict = None, results_json_path: str = None) -> str:
    """
    Generates a highly personalized cold email based on company product docs 
    and target lead's enriched profile details.
    """
    # 1. Load our product technical doc
    product_doc = load_text_file(product_doc_path)
    
    # 2. Find and load the lead's enriched profile
    if not lead_profile and results_json_path:
        lead_profile = load_lead_profile(results_json_path, company, recipient)
    
    if not lead_profile:
        print(f"Warning: No matching lead profile found for Company: '{company}', Recipient: '{recipient}' in results.json.")
        print("Falling back to writing a general cold email based on the company name.")
        lead_profile = {
            "name": recipient or "Prospect",
            "company": company,
            "title": "Decision Maker",
            "company_website": None,
            "company_news_events": [],
            "other_crm_info": f"{company} is a leading company in their industry."
        }

    # 3. Instantiate Gemini LLM
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    
    # 4. Formulate email generation prompt
    prompt = PromptTemplate(
        template="""You are an expert Enterprise B2B Sales Executive at our company, Antigravity AI.
Your goal is to write a highly professional, hyper-personalized cold outreach email to a potential customer.

To do this, you must synthesize:
1. Our own product technical documentation (features, tiers, value proposition).
2. The target prospect's enriched profile, specifically looking at their role, company news, and context we found online.

---

### OUR PRODUCT SPECIFICATIONS:
{product_doc}

---

### PROSPECT ENRICHED CRM PROFILE:
{lead_profile}

---

### EMAIL DRAFTING GUIDELINES:
- **Subject Line**: Create a highly compelling, relevant, non-spammy subject line. Mentioning their company's latest news, or a shared mutual objective, or something specific works best.
- **The Hook**: Open with a personalized hook referencing the actual news, events, or background we found in their CRM profile (under 'company_news_events' or 'other_crm_info'). Do not use generic statements. Show that we actually understand what they and their company are currently focused on.
- **The Core Pitch**: Connect their current focus/news seamlessly to how our product ("Antigravity AI CRM") can solve their operational pain points, streamline their pipelines, or unlock new value. Refer to features mentioned in our specifications.
- **Value Proposition**: Briefly show how we can help (e.g., automated scans, real-time web-scraping intelligence, or personalized automated writing). Align our plan tiers (Growth vs. Enterprise) if appropriate.
- **Call to Action (CTA)**: Include a clear, soft, and respectful CTA (e.g., "Would you be open to a brief 10-minute chat next Tuesday to see how this works?", "I'd love to share a custom trial environment with you").
- **Tone**: Professional, consultative, respectful, and authoritative. Avoid being overly pushy or excessively enthusiastic. No robotic greetings.
- **Format**: Output ONLY the email. Use Markdown for layout. Include Subject Line at the top.

Let's write the professional cold email:""",
        input_variables=["product_doc", "lead_profile"]
    )
    
    chain = prompt | llm
    
    try:
        response = chain.invoke({
            "product_doc": product_doc,
            "lead_profile": json.dumps(lead_profile, indent=4, ensure_ascii=False)
        })
        return response.content
    except Exception as e:
        return f"Error drafting email: {e}"
