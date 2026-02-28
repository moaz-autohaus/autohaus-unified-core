import os
import json
import logging
import re
from typing import Dict, Any, Tuple

logger = logging.getLogger("autohaus.classifier")

class EmailClassifier:
    """
    Triage for incoming emails using Gemini Flash.
    Determines if an email should be ignored (spam/promo) or ingested (invoice/lead).
    """

    def _build_prompt(self, sender: str, subject: str, body: str) -> str:
        return f"""You are an intelligent triage agent for AutoHaus, an auto dealership. 
Your job is to classify an incoming email to decide if it is operational business or junk.

Classification Tags:
1. "AUCTION_CONFIRMATION": Copart, IAA, Manheim, OVE, any auction purchase or sale notice.
2. "AUCTION_REPORT": Monthly statements, summaries from auction platforms.
3. "DMS_REPORT": DealerCenter or DMS monthly/weekly reports.
4. "VENDOR_INVOICE": Parts, tools, supplies invoices (LKQ, NAPA, Matco, etc.).
5. "TRANSPORT_CONFIRMATION": Carrier pickup/delivery confirmations.
6. "INSURANCE_CORRESPONDENCE": Policy notices, claims, or carrier communication.
7. "FLOOR_PLAN_NOTICE": Lender communications about inventory financing.
8. "CUSTOMER_COMMUNICATION": Customer inquiries, leads, or complaints.
9. "FINANCIAL_STATEMENT": Bank/CC statements, payment confirmations.
10. "GOVERNMENT_CORRESPONDENCE": DMV, DOT, IRS, or state authority communication.
11. "SERVICE_VENDOR": Communications from service tool/equipment vendors.
12. "MARKETING": Promotional, newsletters, junk sales.
13. "PERSONAL": Non-business-related personal correspondence.
14. "TURO_CALIFORNIA": Specifically tagged Turo-related logistics.
15. "UNCLASSIFIED": Does not fit any category.

INPUT:
Sender: {sender}
Subject: {subject}
Body: {body[:3000]}

Respond with ONLY a JSON object in this exact format:
{{
  "category": "INVOICE_RECEIPT | LEAD_INQUIRY | OPERATIONAL | NEWS_PROMO | SPAM",
  "priority": "HIGH | NORMAL | LOW",
  "action_required": true/false,
  "reasoning": "short explanation"
}}
"""

    async def classify_email(self, sender: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Calls Gemini to classify the email.
        """
        import google.generativeai as genai
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("[CLASSIFIER] No GEMINI_API_KEY found.")
            return {"category": "OPERATIONAL", "priority": "NORMAL"}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-flash-latest")
        
        prompt = self._build_prompt(sender, subject, body)
        
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean JSON
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            
            return json.loads(text)
        except Exception as e:
            logger.error(f"[CLASSIFIER] Classification failed: {e}")
            return {"category": "OPERATIONAL", "priority": "NORMAL", "reasoning": "Fallback due to error"}
