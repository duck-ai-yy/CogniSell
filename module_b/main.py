import os
import argparse
from email_agent import write_cold_email

def main():
    parser = argparse.ArgumentParser(description="Generate a highly personalized cold sales email using CRM enriched lead profiles.")
    parser.add_argument("--company", required=True, help="Name of the target company")
    parser.add_argument("--recipient", default=None, help="Name of the target recipient")
    parser.add_argument("--product-doc", default="module_b/our_product_doc.md", help="Path to our product tech/marketing documentation")
    parser.add_argument("--results", default="results.json", help="Path to the JSON file containing enriched CRM leads")
    parser.add_argument("--output", default=None, help="Path to save the generated email (markdown)")
    
    args = parser.parse_args()
    
    print(f"Drafting personalized cold outreach email for {args.recipient or 'Decision Maker'} at {args.company}...")
    
    try:
        email_draft = write_cold_email(
            product_doc_path=args.product_doc,
            results_json_path=args.results,
            company=args.company,
            recipient=args.recipient
        )
        
        print("\n" + "="*40 + " GENERATED EMAIL " + "="*40)
        print(email_draft)
        print("="*97 + "\n")
        
        # Save output if path is provided or default to a standard filename
        output_path = args.output
        if not output_path:
            clean_company = "".join(c for c in args.company if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_').lower()
            output_path = f"module_b/outreach_{clean_company}.md"
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(email_draft)
            
        print(f"Email draft successfully saved to: {output_path}")
        
    except Exception as e:
        print(f"Error executing email generation pipeline: {e}")

if __name__ == "__main__":
    main()
