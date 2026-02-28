import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("autohaus.intelligence.forwarded_detector")

class ForwardedDetector:
    """
    Detects and extracts metadata from forwarded emails.
    """
    
    FORWARD_PATTERNS = [
        r"---------- Forwarded message ----------",
        r"Subject: Fwd:",
        r"From: .*? <.*?>\nDate: .*?\nSubject: .*?\nTo: .*?\n", # Gmail style header
    ]

    def detect(self, subject: str, body: str) -> bool:
        if subject.lower().startswith("fwd:"):
            return True
        for pattern in self.FORWARD_PATTERNS:
            if re.search(pattern, body):
                return True
        return False

    def extract_original_metadata(self, body: str) -> Optional[Dict[str, Any]]:
        """
        Extracts original sender, date, and recipients from the forwarded header block.
        """
        # Gmail Pattern
        # ---------- Forwarded message ---------
        # From: Name <email@example.com>
        # Date: Fri, Feb 28, 2026 at 2:04 AM
        # Subject: Re: Title
        # To: Name <email@example.com>
        
        match = re.search(r"From: (.*?)\nDate: (.*?)\nSubject: (.*?)\nTo: (.*?)\n", body, re.DOTALL)
        if match:
            original_sender = match.group(1).strip()
            original_date_raw = match.group(2).strip()
            original_subject = match.group(3).strip()
            original_recipients = match.group(4).strip()
            
            # Simple date parsing logic (could be improved with dateutil)
            # source_timestamp should use this!
            
            return {
                "original_sender": original_sender,
                "original_date_raw": original_date_raw,
                "original_subject": original_subject,
                "original_recipients": original_recipients,
                "is_forwarded": True
            }
            
        return None

forwarded_detector = ForwardedDetector()
