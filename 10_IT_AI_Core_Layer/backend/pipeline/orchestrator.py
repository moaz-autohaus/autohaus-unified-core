import json
import logging
from datetime import datetime, timezone
import asyncio

import redis.asyncio as redis
import os

from memory.vector_vault import VectorVault
from agents.iea_agent import InputEnrichmentAgent
from agents.governance_agent import GovernanceAgent
from agents.router_agent import RouterAgent
from agents.attention_dispatcher import AttentionDispatcher
from models.cos_response import CoSResponse, UIStrategyModel

logger = logging.getLogger("autohaus.orchestrator")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    logger.warning(f"Failed to initialize Redis client: {e}. Falling back to in-memory broker if available.")
    redis_client = None

# ---------------------------------------------------------------------------
# Plate Mapping: Intent Domain -> React UI Component
# ---------------------------------------------------------------------------
PLATE_MAP = {
    "FINANCE":    "FINANCE_CHART",
    "INVENTORY":  "INVENTORY_TABLE",
    "SERVICE":    "CHAT_RESPONSE",
    "CRM":        "CHAT_RESPONSE",
    "LOGISTICS":  "LIVE_DISPATCH",
    "COMPLIANCE": "ANOMALY_ALERT",
    "GOVERNANCE": "GOVERNANCE_DASHBOARD",
    "UNKNOWN":    "CHAT_RESPONSE",
}

# Lazy-initialized RouterAgent
_router = None

def _get_router():
    global _router
    if _router is None:
        _router = RouterAgent()
    return _router

def _resolve_skin(urgency_score: int, target_entity: str) -> dict:
    if urgency_score >= 8:
        return {"skin": "FIELD_DIAGNOSTIC", "urgency": urgency_score, "vibration": True, "overlay": "porsche-red-pulse"}
    elif target_entity in ("CLIENT", "EXTERNAL", "WEB_LEAD"):
        return {"skin": "CLIENT_HANDSHAKE", "urgency": urgency_score, "vibration": False, "overlay": None}
    elif urgency_score <= 2:
        return {"skin": "GHOST", "urgency": urgency_score, "vibration": False, "overlay": None}
    else:
        return {"skin": "SUPER_ADMIN", "urgency": urgency_score, "vibration": False, "overlay": None}


async def route_and_process(text_data: str, client_id: str, access: str):
    """
    Core CIL Orchestration pipeline.
    Runs completely decoupled from the WebSocket transport layer.
    """
    logger.info(f"[{client_id}] Orchestrating input: {text_data[:60]}...")
    
    try:
        # 1. Sovereign Memory context injection
        vault = VectorVault()
        memory_context = vault.build_context_injection(text_data, top_k=3)

        enriched_input = text_data
        if memory_context:
            logger.info(f"[{client_id}] Injected historical context.")
            enriched_input = f"{text_data}\n\n{memory_context}"

        # 2. Intelligent Membrane: IEA Enrichment
        iea = InputEnrichmentAgent()
        iea_result = await iea.evaluate(enriched_input)

        if iea_result.status == "INCOMPLETE":
            logger.warning(f"[{client_id}] Membrane caught incomplete input.")
            res = CoSResponse(
                type="MOUNT_PLATE",
                plate_id="CHAT_RESPONSE",
                intent="CLARIFICATION_REQUIRED",
                confidence=1.0,
                entities=iea_result.extracted_entities,
                target_entity="CARBON_LLC",
                suggested_action=iea_result.clarifying_question,
                strategy=UIStrategyModel(**_resolve_skin(5, "CARBON_LLC")),
                timestamp=datetime.now(timezone.utc).isoformat(),
                dataset=[]
            )
            await _publish_to_client(client_id, res.model_dump())
            return

        # 3. Classify structured input via RouterAgent
        router = _get_router()
        routed_intent = await router.classify(enriched_input)

        # 4. Determine Urgency via Attention Dispatcher
        dispatcher = AttentionDispatcher()
        attention_result = await dispatcher.evaluate_event(enriched_input)
        urgency_score = attention_result.urgency_score

        # 4.5. Governance
        if routed_intent.intent == "GOVERNANCE":
            gov_agent = GovernanceAgent()
            gov_res = await gov_agent.evaluate_governance_command(text_data, client_id, "SYSTEM")
            
            plate_payload = CoSResponse(
                type="MOUNT_PLATE",
                plate_id=gov_res.get("plate", "GOVERNANCE_DASHBOARD"),
                intent="GOVERNANCE",
                confidence=1.0,
                entities=routed_intent.entities,
                target_entity=routed_intent.target_entity,
                suggested_action=gov_res.get("message", "Governance action executed"),
                strategy=UIStrategyModel(**_resolve_skin(urgency_score, "CARBON_LLC")),
                timestamp=datetime.now(timezone.utc).isoformat(),
                dataset=gov_res.get("dataset", [])
            )
        else:
            # 5. Standard JIT Plate JSON payload
            plate_id = PLATE_MAP.get(routed_intent.intent, "CHAT_RESPONSE")
            if routed_intent.confidence < 0.7 and routed_intent.intent != "UNKNOWN":
                plate_id = "AMBIGUITY_RESOLUTION"
                
            strategy = UIStrategyModel(**_resolve_skin(urgency_score, routed_intent.target_entity))
            plate_payload = CoSResponse(
                type="MOUNT_PLATE",
                plate_id=plate_id,
                intent=routed_intent.intent,
                confidence=routed_intent.confidence,
                entities=routed_intent.entities,
                target_entity=routed_intent.target_entity,
                suggested_action=routed_intent.suggested_action,
                strategy=strategy,
                timestamp=datetime.now(timezone.utc).isoformat(),
                dataset=[]
            )

        # 6. Publish back to the transport layer via Redis
        await _publish_to_client(client_id, plate_payload.model_dump())
        
    except Exception as e:
        logger.error(f"[{client_id}] Orchestration failed: {e}")
        err = CoSResponse(
            type="ERROR",
            message="Internal orchestration failure."
        )
        await _publish_to_client(client_id, err.model_dump())


async def _publish_to_client(client_id: str, message: dict):
    """Publish a processed payload to the specific client's Redis channel."""
    if redis_client:
        await redis_client.publish(f"client:{client_id}", json.dumps(message))
    else:
        # In-memory local broker fallback (only if redis is completely unavailable)
        logger.error("Redis client not available to publish. Falling back to local broker.")
        from routes.chat_stream import local_broker
        await local_broker.publish(client_id, message)
