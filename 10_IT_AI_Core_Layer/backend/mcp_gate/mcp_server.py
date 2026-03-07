import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, HTTPException, Depends
from google.cloud import bigquery
from pydantic import BaseModel, Field

from mcp.server import Server
import mcp.types as types
from mcp.server.sse import SseServerTransport

from database.bigquery_client import BigQueryClient
from routes.inventory import get_bq_client

logger = logging.getLogger("autohaus.mcp")

# Setup MCP Server
mcp_server = Server("autohaus-cil")
sse = SseServerTransport("/mcp/messages")
mcp_router = APIRouter(prefix="", tags=["mcp"])

from mcp.server.models import InitializationOptions

@mcp_router.get("/sse")
async def mcp_sse(request: Request):
    """MCP standard Server-Sent Events endpoint."""
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="autohaus-cil",
                server_version="0.1.0",
                capabilities=mcp_server.get_capabilities(
                    notification_options=types.ServerCapabilitiesNotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

@mcp_router.post("/messages")
async def mcp_messages(request: Request):
    """MCP standard HTTP POST endpoint for client messages."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


# --- Phase 1: 5 Read Tools ---

@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_inventory_summary",
            description="Get the current status of all vehicles in global inventory.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_open_questions",
            description="Get all open governance questions and exceptions that require human resolution.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_policy_registry",
            description="View all active governance policies enforcing the CIL Membrane.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_recent_events",
            description="Retrieve the event spine logs out of the CIL layer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent events to retrieve. Default is 50."
                    }
                }
            }
        ),
        types.Tool(
            name="get_ontology",
            description="Retrieve the unified business ontology map (entities, relations, roles).",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="query_bigquery",
            description="Execute arbitrary SELECT statements against authorized CIL tables to perform specific analytical deep dives.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The exact SQL SELECT statement to execute. Only SELECT queries are permitted."
                    }
                },
                "required": ["sql"]
            }
        ),
        types.Tool(
            name="get_business_health",
            description="Provides a macro-level overview of the entire entity's health across all CIL subsystems.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="trigger_governance_review",
            description="Surfaces all pending proposals that require high-tier SOVEREIGN authorization.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="kill_switch",
            description="Hard stop mechanism for the entire autonomous pipeline. Requires a reason.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Justification for initiating the kill switch."
                    },
                    "authority": {
                        "type": "string",
                        "description": "The authority level of the caller. Must be 'SOVEREIGN' to execute."
                    }
                },
                "required": ["reason", "authority"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Execute MCP tool functions. Maps tool names to BigQuery functions."""
    if arguments is None:
        arguments = {}
        
    try:
        # Use our existing ADC/Impersonation client logic
        bq_client = get_bq_client()
        if not bq_client:
            return [types.TextContent(type="text", text="Error: BigQuery client unavailable.")]

        # Phase 1
        if name == "get_inventory_summary":
            return await _get_inventory_summary(bq_client)
        elif name == "get_open_questions":
            return await _get_open_questions(bq_client)
        elif name == "get_policy_registry":
            return await _get_policy_registry(bq_client)
        elif name == "get_recent_events":
            limit = arguments.get("limit", 50)
            return await _get_recent_events(bq_client, limit)
        elif name == "get_ontology":
            return await _get_ontology(bq_client)
            
        # Phase 2
        elif name == "query_bigquery":
            sql = arguments.get("sql")
            if not sql:
                return [types.TextContent(type="text", text="Error: Missing 'sql' parameter.")]
            return await _query_bigquery(bq_client, sql)
            
        # Phase 3/4 (Meta-Layer)
        elif name == "get_business_health":
            return await _get_business_health(bq_client)
        elif name == "trigger_governance_review":
            return await _trigger_governance_review(bq_client)
        elif name == "kill_switch":
            reason = arguments.get("reason")
            authority = arguments.get("authority")
            if not reason or not authority:
                 return [types.TextContent(type="text", text="Error: Missing 'reason' or 'authority' parameter.")]
            if authority != "SOVEREIGN":
                 return [types.TextContent(type="text", text="REJECTED: kill_switch requires SOVEREIGN authority level.")]
            return await _kill_switch(bq_client, reason)
            
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown tool '{name}'")]
            
    except Exception as e:
        logger.error(f"[MCP ERROR] Tool {name} failed: {e}")
        return [types.TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]

# Tool Implementations

async def _get_inventory_summary(client: bigquery.Client) -> list[types.TextContent]:
    query = "SELECT status, COUNT(*) as count FROM `autohaus-infrastructure.autohaus_cil.vw_live_inventory` GROUP BY status"
    results = client.query(query).result()
    summary = {row.status: row.count for row in results}
    return [types.TextContent(type="text", text=json.dumps(summary, indent=2))]

async def _get_open_questions(client: bigquery.Client) -> list[types.TextContent]:
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE status = 'OPEN' ORDER BY created_at DESC"
    results = [dict(row) for row in client.query(query).result()]
    return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

async def _get_policy_registry(client: bigquery.Client) -> list[types.TextContent]:
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.policy_registry` WHERE active = TRUE"
    results = [dict(row) for row in client.query(query).result()]
    return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

async def _get_recent_events(client: bigquery.Client, limit: int) -> list[types.TextContent]:
    safe_limit = min(max(1, limit), 500) # Boundary enforcement
    query = f"SELECT * FROM `autohaus-infrastructure.autohaus_cil.cil_events` ORDER BY timestamp DESC LIMIT {safe_limit}"
    results = [dict(row) for row in client.query(query).result()]
    return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

async def _get_ontology(client: bigquery.Client) -> list[types.TextContent]:
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.business_ontology_map` WHERE status = 'ACTIVE'"
    results = [dict(row) for row in client.query(query).result()]
    return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

async def _query_bigquery(client: bigquery.Client, sql: str) -> list[types.TextContent]:
    """Execute dynamic SQL Deep Dives strictly for analytical reads."""
    # 1. Reject writes and destructive statements
    sql_upper = sql.upper().strip()
    destructive_keywords = ["INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]
    
    if any(sql_upper.startswith(kw) or f" {kw} " in sql_upper for kw in destructive_keywords):
        return [types.TextContent(type="text", text="REJECTED: MCP Layer is READ-ONLY. Only SELECT statements are permitted. All writes must route through the CIL Membrane via FastAPI endpoints.")]
    
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        return [types.TextContent(type="text", text="REJECTED: Query must begin with SELECT or WITH.")]
        
    # 2. Whitelist constraints: enforce CIL schema limits
    whitelisted_tables = [
        "cil_events", "inventory_master", "open_questions", 
        "extraction_claims", "human_assertions", "policy_registry", "vw_live_inventory"
    ]
    # Simple verification that one of the whitelisted table names is mentioned in query
    if not any(table in sql for table in whitelisted_tables):
         return [types.TextContent(type="text", text=f"REJECTED: Query targets unauthorized or unknown tables. Whitelist: {', '.join(whitelisted_tables)}")]
         
    # 3. Execution
    try:
        results = [dict(row) for row in client.query(sql).result()]
        return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Query execution failed: {str(e)}")]

async def _get_business_health(client: bigquery.Client) -> list[types.TextContent]:
    """Macro-level overview of entity health."""
    try:
        # 1. Anomaly Status
        query_anomalies = "SELECT COUNT(*) as cnt FROM `autohaus-infrastructure.autohaus_cil.drift_sweep_results` WHERE resolved = FALSE"
        anomalies = list(client.query(query_anomalies).result())[0].cnt
        status = "NORMAL" if anomalies == 0 else "ELEVATED" if anomalies < 5 else "CRITICAL"
        
        # 2. Cash Position
        query_cash = "SELECT SUM(amount) as total FROM `autohaus-infrastructure.autohaus_cil.financial_ledger`"
        cash = list(client.query(query_cash).result())[0].total or 0
        
        # 3. Open Questions
        query_qs = "SELECT COUNT(*) as cnt FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE status = 'OPEN'"
        open_qs = list(client.query(query_qs).result())[0].cnt
        
        health = {
            "anomaly_status": status,
            "cash_position": cash,
            "open_question_count": open_qs,
            "timestamp": datetime.utcnow().isoformat()
        }
        return [types.TextContent(type="text", text=json.dumps(health, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error fetching business health: {e}")]

async def _trigger_governance_review(client: bigquery.Client) -> list[types.TextContent]:
    """Surfaces pending SOVEREIGN tier proposals."""
    query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.hitl_events` WHERE status = 'PROPOSED' AND urgency >= 8"
    try:
        results = [dict(row) for row in client.query(query).result()]
        return [types.TextContent(type="text", text=json.dumps(results, indent=2, default=str))]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error triggering governance review: {e}")]

async def _kill_switch(client: bigquery.Client, reason: str) -> list[types.TextContent]:
    """Hard stop for the autonomous pipeline."""
    try:
        # 1. Log to cil_events
        event = {
            "event_type": "HARD_STOP_ENFORCED",
            "description": f"Kill switch triggered via MCP. Reason: {reason}",
            "timestamp": datetime.utcnow().isoformat(),
            "actor": "MCP_META_LAYER"
        }
        client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event])
        
        # 2. Update policy to frozen
        policy = {
            "domain": "SYSTEM",
            "key": "FROZEN",
            "value": "true",
            "active": True,
            "version": int(datetime.utcnow().timestamp()),
            "created_at": datetime.utcnow().isoformat()
        }
        client.insert_rows_json("autohaus-infrastructure.autohaus_cil.policy_registry", [policy])
        
        # 3. Clear policy cache if engine is loaded
        try:
            from database.policy_engine import _engine
            _engine.clear_cache()
        except:
            pass
            
        return [types.TextContent(type="text", text=f"SUCCESS: SYSTEM HARD STOP INITIATED. Reason: {reason}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"FAILED to initiate kill switch: {e}")]
