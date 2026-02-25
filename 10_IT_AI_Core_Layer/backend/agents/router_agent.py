"""
AutoHaus C-OS v3.1 — MODULE 2: The Agentic Router (Concept Orchestrator)
=========================================================================
This module is the core "Brain" of the Digital Chief of Staff.
It receives raw human text (from chat, SMS via Twilio, or voice transcriptions)
and uses Gemini 1.5 Pro to classify the intent into a specific operational
domain and extract relevant business entities.

The RouterAgent is designed to be stateless and importable into any FastAPI
route, WebSocket handler, or scheduled worker within the CIL backend.

Active Constraints (from AUTOHAUS_SYSTEM_STATE.json v3.1.1-Alpha):
  - KAMM Scope: KAMM is purely a legal/compliance vehicle. Do NOT route
    general sales/inventory queries to KAMM. Route to INVENTORY or FINANCE.
  - MSO Model: Carbon LLC carries zero operational risk.
  - Insurance Purity: Entity identification must respect insurance boundaries.

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

import google.generativeai as genai

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.router_agent")


class IntentDomain(str, Enum):
    """The four operational domains the C-OS routes to."""
    FINANCE = "FINANCE"
    INVENTORY = "INVENTORY"
    SERVICE = "SERVICE"
    CRM = "CRM"
    LOGISTICS = "LOGISTICS"
    COMPLIANCE = "COMPLIANCE"
    UNKNOWN = "UNKNOWN"


@dataclass
class RoutedIntent:
    """Structured output from the Agentic Router."""
    intent: str
    confidence: float
    entities: dict = field(default_factory=dict)
    suggested_action: str = ""
    target_entity: str = ""
    raw_input: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# System Prompt (The "Soul" of the Chief of Staff)
# ---------------------------------------------------------------------------
ROUTER_SYSTEM_PROMPT = """You are the AutoHaus Digital Chief of Staff — an intent classification engine
for a multi-entity automotive dealership group. Your job is to analyze a human command
and return a strictly formatted JSON object.

## OPERATIONAL ENTITIES YOU MUST KNOW:
- CARBON_LLC: MSO / Digital Brain. Administrative only. Zero operational risk.
- KAMM_LLC: Dealer Compliance & Title HQ. STRICT: Iowa Dealer Law Compliance, Title Processing, Damage Disclosures ONLY. Do NOT route general sales or inventory queries here.
- AUTOHAUS_SERVICES_LLC: Service & Recon (Lane A). Mechanical work, diagnostics, detailing.
- ASTROLOGISTICS_LLC: Cosmetic Studio (Lane B). Tint, PPF, Ceramic, Vinyl Wraps.
- FLUIDITRUCK_LLC: Fleet Asset Holding. Airport Shuttle, Turo, Rentals.
- CARLUX_LLC: Logistics & Dispatch. Transport coordination, auction runs.
- MAHAD_HOLDINGS_LLC: Real Estate. Property management.

## INTENT DOMAINS:
Classify the user's command into exactly ONE of these domains:
- FINANCE: Anything related to revenue, costs, margins, invoices, billing, P&L, payroll.
- INVENTORY: Anything related to vehicles, VINs, pricing, stock levels, acquisitions, Digital Twins.
- SERVICE: Anything related to mechanical work, recon, cosmetic work, inspections, repair orders.
- CRM: Anything related to customers, leads, contacts, appointments, follow-ups, identity resolution.
- LOGISTICS: Anything related to transport, dispatch, delivery, pick-up, fleet movement.
- COMPLIANCE: Anything related to titles, damage disclosures, Iowa dealer law, insurance documents.
- UNKNOWN: If the intent cannot be confidently classified.

## ENTITY EXTRACTION RULES:
From the user's text, extract any of the following if mentioned:
- "vehicle": The make, model, or VIN of a vehicle (e.g., "BMW M4", "911 Carrera T").
- "lane": Which service lane (e.g., "A" for mechanical, "B" for cosmetic).
- "entity": Which LLC is relevant (e.g., "ASTROLOGISTICS_LLC").
- "person": Any person name mentioned (e.g., "Mohsin", "Asim").
- "time_range": Any time reference (e.g., "this month", "last week", "Q4").

## OUTPUT FORMAT (STRICT JSON, NO MARKDOWN):
{
  "intent": "FINANCE",
  "confidence": 0.95,
  "entities": {
    "lane": "A",
    "time_range": "this month"
  },
  "suggested_action": "Query BigQuery for Lane A financial aggregates for the current month.",
  "target_entity": "AUTOHAUS_SERVICES_LLC"
}

RULES:
1. Always return valid JSON. Never wrap in markdown code fences.
2. Confidence must be a float between 0.0 and 1.0.
3. If the command is ambiguous, set confidence below 0.7 and add "ambiguity_note" to entities.
4. KAMM_LLC should ONLY be the target_entity for title/compliance/disclosure actions.
5. For general "sales" or "inventory" queries, target_entity should be determined by context, NOT defaulted to KAMM.
"""


# ---------------------------------------------------------------------------
# RouterAgent Class
# ---------------------------------------------------------------------------
class RouterAgent:
    """
    The Agentic Router for the AutoHaus Conversational Operating System.

    Usage:
        router = RouterAgent()
        result = router.classify("Show me the financials for Lane A")
        print(result.to_json())
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the RouterAgent with Gemini credentials.





        Args:
            api_key:    Google AI API key. Falls back to GEMINI_API_KEY env var.
            model_name: The Gemini model to use for classification.
        """
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Provide it via the constructor or set the GEMINI_API_KEY environment variable."
            )

        genai.configure(api_key=resolved_key)
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=ROUTER_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.1,       # Near-deterministic for classification
                top_p=0.95,
                max_output_tokens=512, # Classification payloads are small
                response_mime_type="application/json",
            ),
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        logger.info(f"RouterAgent initialized with model: {model_name}")

    def classify(self, user_input: str) -> RoutedIntent:
        """
        Classify a natural language command into an operational domain.

        Args:
            user_input: The raw text from the CEO, advisor, or Twilio webhook.

        Returns:
            A RoutedIntent dataclass containing the classified intent,
            confidence score, extracted entities, and suggested action.
        """
        if not user_input or not user_input.strip():
            logger.warning("Empty input received. Returning UNKNOWN intent.")
            return RoutedIntent(
                intent=IntentDomain.UNKNOWN.value,
                confidence=0.0,
                raw_input=user_input,
                suggested_action="No actionable input received.",
            )

        try:
            logger.info(f"Classifying input: '{user_input[:80]}...'")
            response = self._model.generate_content(user_input)

            # Parse the JSON from Gemini's response
            raw_text = response.text.strip()

            # Strip markdown fences if Gemini wraps them despite instructions
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]  # Remove first line
                raw_text = raw_text.rsplit("```", 1)[0] # Remove last fence

            parsed = json.loads(raw_text)

            result = RoutedIntent(
                intent=parsed.get("intent", IntentDomain.UNKNOWN.value),
                confidence=float(parsed.get("confidence", 0.0)),
                entities=parsed.get("entities", {}),
                suggested_action=parsed.get("suggested_action", ""),
                target_entity=parsed.get("target_entity", ""),
                raw_input=user_input,
            )

            logger.info(
                f"Classification result: intent={result.intent}, "
                f"confidence={result.confidence}, "
                f"target={result.target_entity}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini returned invalid JSON: {e}")
            return RoutedIntent(
                intent=IntentDomain.UNKNOWN.value,
                confidence=0.0,
                raw_input=user_input,
                suggested_action=f"JSON parse error: {e}",
                entities={"error": "gemini_json_decode_failure"},
            )
        except Exception as e:
            logger.error(f"RouterAgent classification failed: {e}")
            return RoutedIntent(
                intent=IntentDomain.UNKNOWN.value,
                confidence=0.0,
                raw_input=user_input,
                suggested_action=f"System error: {e}",
                entities={"error": str(type(e).__name__)},
            )


# ---------------------------------------------------------------------------
# Local Test Harness (__main__)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("  AutoHaus C-OS v3.1 — Agentic Router Test Harness")
    print("=" * 70)

    # Initialize the router (reads GEMINI_API_KEY from environment)
    router = RouterAgent()

    # Test cases derived from real AutoHaus operational scenarios
    test_commands = [
        "Show me the financials for Service Lane A, but exclude detailing.",
        "Schedule an inspection for the BMW M4 in Lane A.",
        "What's the status of the blue 911 Carrera T?",
        "Did John Smith ever get his tint done at AstroLogistics?",
        "Book a transport from Chicago to Des Moines for VIN WBA12345.",
        "I need the title paperwork for the 2024 Camry we just sold.",
        "How much did we spend on recon for Lane B last month?",
    ]

    for i, cmd in enumerate(test_commands, 1):
        print(f"\n--- TEST {i} ---")
        print(f"INPUT:  {cmd}")
        result = router.classify(cmd)
        print(f"OUTPUT: {result.to_json()}")
        print()
