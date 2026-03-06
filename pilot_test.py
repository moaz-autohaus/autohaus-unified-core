import asyncio
import os
import sys

# Setup path purely for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '10_IT_AI_Core_Layer', 'backend'))

from services.attachment_processor import attachment_processor
from models.claims import ClaimSource
from datetime import datetime, timezone
import json

async def test_pilot():
    pdf_path = "10_IT_AI_Core_Layer/attached_assets/Test.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    print("Running extraction...")
    data = await attachment_processor._extract_tier0_metrics(
        file_bytes=file_bytes,
        filename="Test.pdf",
        sender="UI_UPLOAD",
        subject="UI_UPLOAD"
    )
    print("Extraction successful. Data returned:")
    print(json.dumps(data, indent=2))

    if data:
        lineage = {
            "model": "gemini-2.5-flash",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        from services.attachment_processor import unpack_to_claims
        claims = unpack_to_claims(
            raw_response=data,
            source=ClaimSource.ATTACHMENT,
            extractor_identity="attachment_processor._extract_tier0_metrics",
            input_reference="test_123",
            source_lineage=lineage
        )
        print(f"\nUnpacked to {len(claims)} claims:")
        if claims:
            for c in claims:
                print(c.target_field, "->", c.extracted_value)

if __name__ == "__main__":
    asyncio.run(test_pilot())
