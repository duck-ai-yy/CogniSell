import json
import requests
import re

class PCBQuotingAgent:
    """
    A self-contained intelligent agent for the PCB manufacturing industry.
    It combines GLiNER2 perception, a deterministic pricing brain, and Gemma 4 conversational capabilities.
    """
    
    def __init__(self, pioneer_api_key: str, gliner_model_id: str):
        self.api_key = pioneer_api_key
        self.gliner_model_id = gliner_model_id
        
    def _extract_parameters(self, email_text: str) -> dict:
        """Perception: Extracts raw parameters using fine-tuned GLiNER2."""
        payload = {
            "model_id": self.gliner_model_id,
            "text": email_text,
            "schema": {
                "structures": {
                    "pcb_order": {
                        "fields": [
                            {"name": "Layers", "dtype": "str"},
                            {"name": "Material", "dtype": "str"},
                            {"name": "Copper_Thickness", "dtype": "str"},
                            {"name": "Surface_Finish", "dtype": "str"},
                            {"name": "Quantity", "dtype": "str"},
                            {"name": "Board_Thickness", "dtype": "str"},
                            {"name": "Min_Trace_Spacing", "dtype": "str"},
                            {"name": "Solder_Mask_Color", "dtype": "str"},
                            {"name": "Lead_Time", "dtype": "str"},
                            {"name": "Incoterm", "dtype": "str"}
                        ]
                    }
                }
            },
            "threshold": 0.5
        }
        
        try:
            response = requests.post(
                "https://api.pioneer.ai/inference",
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            if response.status_code == 503:
                return {"_error": "Model warming up (503)."}
            result = response.json()
            raw_output = result.get("result", {}).get("data", {}).get("pcb_order", [{}])[0]
            raw_params = {k: v['text'] for k, v in raw_output.items()}
            return raw_params
        except Exception as e:
            print("Extraction Error:", e)
            return {"_error": str(e)}

    @staticmethod
    def _normalize_parameters(raw_params: dict) -> dict:
        """Brain part 1: Translates multilingual chaos into structured engineering constants."""
        normalized = {}
        
        qty_str = raw_params.get("Quantity", "100")
        nums = re.findall(r'\d+', qty_str.replace(',', ''))
        normalized["Quantity"] = int(nums[0]) if nums else 100
        
        layer_str = raw_params.get("Layers", "2")
        nums = re.findall(r'\d+', layer_str)
        normalized["Layers"] = int(nums[0]) if nums else 2
        if any(x in layer_str.lower() for x in ['单面', 'einseitig', '片面', 'single']):
            normalized["Layers"] = 1
            
        mat_str = raw_params.get("Material", "FR-4").lower()
        if any(x in mat_str for x in ['铝', 'aluminum', 'alu', 'アルミ']):
            normalized["Material"] = "Aluminum"
        elif any(x in mat_str for x in ['rogers', '罗杰斯', 'ロジャース']):
            normalized["Material"] = "Rogers"
        else:
            normalized["Material"] = "FR-4"
            
        cu_str = raw_params.get("Copper_Thickness", "1oz").lower()
        if any(x in cu_str for x in ['2oz', '2 oz', '70um', '70µm']):
            normalized["Copper_Thickness"] = "2oz"
        elif any(x in cu_str for x in ['3oz', '105']):
            normalized["Copper_Thickness"] = "3oz"
        elif any(x in cu_str for x in ['0.5', '半', '18']):
            normalized["Copper_Thickness"] = "0.5oz"
        else:
            normalized["Copper_Thickness"] = "1oz"
            
        finish_str = raw_params.get("Surface_Finish", "HASL").lower()
        if any(x in finish_str for x in ['enig', '金', 'gold']):
            normalized["Surface_Finish"] = "ENIG"
        elif 'osp' in finish_str:
            normalized["Surface_Finish"] = "OSP"
        else:
            normalized["Surface_Finish"] = "HASL"
            
        lt_str = raw_params.get("Lead_Time", "Standard").lower()
        if any(x in lt_str for x in ['48', '24', 'rush', '急', 'eilauftrag', '特急', 'asap']):
            normalized["Lead_Time"] = "Rush"
        else:
            normalized["Lead_Time"] = "Standard"
            
        normalized["Board_Thickness"] = raw_params.get("Board_Thickness", "1.6mm")
        normalized["Solder_Mask_Color"] = raw_params.get("Solder_Mask_Color", "Green")
        normalized["Min_Trace_Spacing"] = raw_params.get("Min_Trace_Spacing", "4mil")
        normalized["Incoterm"] = raw_params.get("Incoterm", "FOB").upper()
        
        return normalized

    @staticmethod
    def _calculate_price(normalized_params: dict) -> dict:
        """Brain part 2: Deterministic pricing rules."""
        qty = normalized_params["Quantity"]
        layers = normalized_params["Layers"]
        material = normalized_params["Material"]
        copper = normalized_params["Copper_Thickness"]
        finish = normalized_params["Surface_Finish"]
        lead_time = normalized_params["Lead_Time"]
        
        base_setup_fee = 50.0
        
        mat_cost = 0.5
        if material == "Aluminum": mat_cost = 1.0
        if material == "Rogers": mat_cost = 3.5
        
        layer_multiplier = 1.0
        if layers == 4: layer_multiplier = 2.0
        elif layers == 6: layer_multiplier = 3.5
        elif layers >= 8: layer_multiplier = 5.0
        
        copper_cost = 0.0
        if copper == "2oz": copper_cost = 0.5
        elif copper == "3oz": copper_cost = 1.2
        
        finish_cost = 0.0
        if finish == "ENIG": finish_cost = 0.8
        
        unit_price = (mat_cost * layer_multiplier) + copper_cost + finish_cost
        rush_fee = 150.0 if lead_time == "Rush" else 0.0
        total_price = base_setup_fee + rush_fee + (unit_price * qty)
        
        return {
            "unit_price_usd": round(unit_price, 2),
            "setup_fee_usd": base_setup_fee,
            "rush_fee_usd": rush_fee,
            "total_price_usd": round(total_price, 2)
        }

    def _draft_quote_email_with_gemma(self, email_text: str, normalized_params: dict, pricing: dict) -> str:
        """Action: Uses Gemma 4 to draft a professional quote response."""
        # For Hackathon demo purposes, this fakes the API call to Gemma 4 and directly outputs the prompt result.
        # In a real setup, you would pass 'system_prompt' and 'user_prompt' to your Gemma endpoint.
        
        gemma_response = f"""Subject: Re: PCB Quote Request - {normalized_params['Quantity']}pcs {normalized_params['Layers']}-Layer {normalized_params['Material']}

Hi there,

Thank you for reaching out to CogniSell with your PCB manufacturing request. I have reviewed your specifications and we can certainly accommodate your requirements, including the {normalized_params['Min_Trace_Spacing']} trace spacing and {normalized_params['Material']} material.

Here is the breakdown of your quote:
- Specifications: {normalized_params['Layers']}-Layer, {normalized_params['Material']}, {normalized_params['Copper_Thickness']} Copper, {normalized_params['Surface_Finish']} Finish, {normalized_params['Solder_Mask_Color']} Solder Mask.
- Unit Price: ${pricing['unit_price_usd']:.2f}
- Engineering Setup Fee: ${pricing['setup_fee_usd']:.2f}
- Expedite/Rush Fee: ${pricing['rush_fee_usd']:.2f}

**Total Estimated Price: ${pricing['total_price_usd']:.2f} (via {normalized_params['Incoterm']})**

Please note that due to the fixed engineering setup fee, ordering a higher quantity can significantly reduce your price per unit. Let me know if you would like me to quote for a larger volume.

If you approve this quote, please send over the final Gerber files and we will initiate production immediately.

Best regards,
CogniSell AI Agent
"""
        return gemma_response

    def handle_inbound_rfq(self, email_text: str) -> dict:
        """Main Pipeline 1: Handle messy inbound RFQ emails."""
        raw_params = self._extract_parameters(email_text)
        
        if "_error" in raw_params:
            return {"error": raw_params["_error"]}
            
        normalized = self._normalize_parameters(raw_params)
        pricing = self._calculate_price(normalized)
        reply_email = self._draft_quote_email_with_gemma(email_text, normalized, pricing)
        
        return {
            "raw_extracted": raw_params,
            "normalized_specs": normalized,
            "pricing": pricing,
            "gemma_reply": reply_email
        }

    def draft_outbound_cold_email(self, lead_data: dict) -> dict:
        """
        Main Pipeline 2: Outbound Sales
        Drafts a proactive cold email based on enriched company data.
        """
        company = lead_data.get("company", "the company")
        pain_points = lead_data.get("pain_points", "supply chain reliability")
        
        # Here we simulate Gemma 4 generating a cold pitch
        cold_email = f"""Subject: Scaling PCB Manufacturing for {company}

Hi Team at {company},

I've been following your recent developments and noticed you might be dealing with challenges around {pain_points}. 

At CogniSell, we specialize in high-precision, rapid-turnaround PCB manufacturing (including advanced High-TG and Rogers materials). We have helped similar hardware teams reduce their prototype-to-production lead times by 30%.

Would you be open to a quick chat next week to see if we can help optimize your next hardware iteration? Alternatively, if you have a Gerber file ready, feel free to reply directly to this email and our AI will generate an instant quote for you.

Best regards,
CogniSell Proactive Agent
"""
        return {
            "target_company": company,
            "cold_email_content": cold_email
        }
