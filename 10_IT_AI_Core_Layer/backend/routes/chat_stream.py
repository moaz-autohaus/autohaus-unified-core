"""
AutoHaus C-OS v3.1 — MODULE 3: JIT Plate Protocol (WebSocket Chat Stream)
==========================================================================
Rebuild 3 (Cloud Run Ready): 
WebSocket Transport decoupled from Orchestration using Redis Pub/Sub.

Author: AutoHaus CIL Build System
Version: 2.0.0
"""

import json
import logging
from datetime import datetime, timezone
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis
import os

from pipeline.orchestrator import route_and_process
from models.cos_response import CoSResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.chat_stream")

chat_router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
redis_client = None

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    logger.warning(f"Failed to initialize Redis client: {e}")

# ---------------------------------------------------------------------------
# Local In-Memory Fallback Broker (for dev without Redis)
# ---------------------------------------------------------------------------
class LocalBroker:
    def __init__(self):
        self.subscribers = {}
        
    async def subscribe(self, client_id: str, queue: asyncio.Queue):
        self.subscribers[client_id] = queue
        
    def unsubscribe(self, client_id: str):
        self.subscribers.pop(client_id, None)
        
    async def publish(self, client_id: str, message: dict):
        if client_id in self.subscribers:
            await self.subscribers[client_id].put(message)

local_broker = LocalBroker()


# ---------------------------------------------------------------------------
# Pub/Sub Listener Task for Each WebSocket Connection
# ---------------------------------------------------------------------------
async def redis_listener(websocket: WebSocket, client_id: str):
    """Subscribes to a client-specific channel and pushes messages to the WebSocket."""
    if redis_client:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"client:{client_id}")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    payload = json.loads(message["data"])
                    await websocket.send_json(payload)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(f"client:{client_id}")
        except Exception as e:
            logger.error(f"[{client_id}] Redis listener error: {e}")
            await pubsub.unsubscribe(f"client:{client_id}")
    else:
        # Local fallback
        queue = asyncio.Queue()
        await local_broker.subscribe(client_id, queue)
        try:
            while True:
                payload = await queue.get()
                await websocket.send_json(payload)
        except asyncio.CancelledError:
            local_broker.unsubscribe(client_id)


# ---------------------------------------------------------------------------
# FastAPI WebSocket Router
# ---------------------------------------------------------------------------
@chat_router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    Stateless WebSocket Endpoint.
    Only handles transport. Orchestration is offloaded to background task / worker.
    """
    await websocket.accept()
    
    client_id = f"client_{id(websocket)}"
    logger.info(f"[{client_id}] WebSocket client connected.")

    # Spin up a listener task for this specific client
    listener_task = asyncio.create_task(redis_listener(websocket, client_id))

    # Send Welcome Greeting asynchronously
    from agents.governance_agent import GovernanceAgent
    gov_agent = GovernanceAgent()
    greeting_msg = gov_agent.generate_session_greeting()
    
    welcome_response = CoSResponse(
        type="SYSTEM",
        message=greeting_msg,
        connected_clients=1, # Cannot rely on global active count in multi-instance
        authority_state="SOVEREIGN",
        legacy_sync=False,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    await websocket.send_json(welcome_response.model_dump())

    USER_ACCESS_MAP = {
        "AHSIN_CEO": "SOVEREIGN",
        "ASIM_SALES": "STANDARD",
        "MOHSIN_OPS": "STANDARD",
        "MOAZ_LOGISTICS": "FIELD",
    }
    
    access = "FIELD"

    try:
        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
                incoming_user_id = data.get("user_id", "")
                if incoming_user_id:
                    access = USER_ACCESS_MAP.get(incoming_user_id, "FIELD")
                    logger.info(f"[{client_id}] Access set to {access} for {incoming_user_id}")
                
                if data.get("type") == "identify":
                    continue
                user_message = data.get("message", data.get("text", "")).strip()
            except json.JSONDecodeError:
                user_message = raw_data.strip()

            if not user_message:
                error_response = CoSResponse(
                    type="ERROR",
                    message="Empty command received. Please provide an instruction."
                )
                await websocket.send_json(error_response.model_dump())
                continue

            # Dispatch strictly to orchestration (Fire and forget)
            # Route and process decoupled from connection management
            asyncio.create_task(route_and_process(user_message, client_id, access))

    except WebSocketDisconnect:
        logger.info(f"[{client_id}] WebSocket closed cleanly.")
    except Exception as e:
        logger.error(f"[{client_id}] WebSocket closed with error: {e}")
    finally:
        listener_task.cancel()
