"""
AutoHaus CIL — Native Governance Open Questions Engine (Pass 7)
"""

import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel
from .policy_engine import get_policy

logger = logging.getLogger("autohaus.open_questions")

def raise_open_question(bq_client, question_type: str, priority: str, context: dict, description: str):
    """Raises an open question to the HITL/CoS layer instead of silently failing."""
    
    # Check policy for snooze/escalation defaults
    snooze_hours = int(get_policy("ESCALATION", "snooze_duration_hours") or 24)
    
    row = {
        "question_id": str(uuid.uuid4()),
        "question_type": question_type,
        "priority": priority, # HIGH, MEDIUM, LOW
        "status": "OPEN",
        "context": json.dumps(context),
        "description": description,
        "assigned_to": None,
        "escalation_target": "CEO",
        "due_by": None, # Could be set here based on max_overdue_hours
        "created_at": datetime.utcnow().isoformat(),
        "resolved_at": None,
        "resolution_event_id": None
    }
    
    # Also emit an event
    event_row = {
        "event_id": str(uuid.uuid4()),
        "event_type": "QUESTION_RAISED", 
        "timestamp": row["created_at"],
        "actor_type": "SYSTEM",
        "actor_id": "open_questions_engine",
        "actor_role": "SYSTEM",
        "target_type": "QUESTION",
        "target_id": row["question_id"],
        "payload": json.dumps(row),
        "metadata": None,
        "idempotency_key": f"qr_{row['question_id']}"
    }
    
    try:
        # BQ requires the table to exist
        q_errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.open_questions", [row])
        if q_errs: logger.error(f"[QUESTION] Insert Error: {q_errs}")
        e_errs = bq_client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
        if e_errs: logger.error(f"[QUESTION] Event Error: {e_errs}")
        
        logger.warning(f"[QUESTION] Raised: {description}")
    except Exception as e:
        logger.error(f"[QUESTION] Failed to raise open question: {e}")

class OpenQuestion(BaseModel):
    question_id: str
    content: str
    status: str
    owner_role: str
    source_type: str
    source_id: str
    dependency_list: list[str]
    lineage_pointer: dict
    resolution_answer: Optional[str] = None
    resolution_propagated: bool
    sla_hours: int
    due_at: datetime
    escalated: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

class ResolutionResult(BaseModel):
    question_id: str
    resolution_answer: str
    resolved_by: str
    resolution_time_vs_sla: str
    dependencies_released: int
    propagation_complete: bool

class OverdueQuestion(BaseModel):
    question_id: str
    content: str
    owner_role: str
    hours_overdue: float
    dependency_count: int
    escalated_at: datetime

def create_question(
    content: str,
    source_type: str,
    source_id: str,
    owner_role: str,
    dependency_list: list[str] = [],
    lineage_pointer: dict = {},
    conflict_outcome: str = None,
    assertion_type: str = None,
    bq_client = None
) -> OpenQuestion:
    
    computed_role = None
    if source_type == "CONFLICT":
        if conflict_outcome in ["CRITICAL", "MATERIAL", "MATERIAL_CONFLICT"]:
            computed_role = "SOVEREIGN"
        else:
            computed_role = "STANDARD"
    elif source_type == "ASSERTION":
        if assertion_type in ["VERIFIABLE_FACT", "INTENT"]:
            computed_role = "SOVEREIGN"
        else:
            computed_role = "STANDARD"
    elif source_type == "IEA":
        computed_role = "STANDARD"
    elif source_type == "MANUAL":
        computed_role = "SOVEREIGN"
    
    final_role = computed_role or owner_role
    
    sla_key = f"question_sla_hours_{source_type}"
    sla_val = get_policy("PIPELINE", sla_key)
    if sla_val is None:
        logger.warning(f"Policy PIPELINE::{sla_key} missing. Defaulting to 48.")
        if source_type == "CONFLICT":
            sla_hours = 24
        elif source_type == "ASSERTION":
            sla_hours = 72
        elif source_type == "IEA":
            sla_hours = 4
        elif source_type == "MANUAL":
            sla_hours = 48
        else:
            sla_hours = 48
    else:
        sla_hours = int(sla_val)
        
    created_at = datetime.now(timezone.utc)
    due_at = created_at + timedelta(hours=sla_hours)
    q_id = str(uuid.uuid4())
    
    q = OpenQuestion(
        question_id=q_id,
        content=content,
        status="OPEN",
        owner_role=final_role,
        source_type=source_type,
        source_id=source_id,
        dependency_list=dependency_list,
        lineage_pointer=lineage_pointer,
        resolution_answer=None,
        resolution_propagated=False,
        sla_hours=sla_hours,
        due_at=due_at,
        escalated=False,
        created_at=created_at,
        resolved_at=None,
        resolved_by=None
    )
    
    if bq_client:
        try:
            client = bq_client if hasattr(bq_client, 'query') else bq_client.client
            row = {
                "question_id": q.question_id,
                "content": q.content,
                "status": q.status,
                "owner_role": q.owner_role,
                "source_type": q.source_type,
                "source_id": q.source_id,
                "dependency_list": json.dumps(q.dependency_list),
                "lineage_pointer": json.dumps(q.lineage_pointer),
                "resolution_answer": q.resolution_answer,
                "resolution_propagated": q.resolution_propagated,
                "sla_hours": q.sla_hours,
                "due_at": q.due_at.isoformat(),
                "escalated": q.escalated,
                "created_at": q.created_at.isoformat(),
                "resolved_at": None,
                "resolved_by": None
            }
            
            event_row = {
                "event_id": str(uuid.uuid4()),
                "event_type": "OPEN_QUESTION_CREATED",
                "timestamp": created_at.isoformat(),
                "actor_type": "SYSTEM",
                "actor_id": "open_questions_engine",
                "target_type": "QUESTION",
                "target_id": q.question_id,
                "payload": json.dumps({"summary": q.content, "owner_role": q.owner_role, "due_at": q.due_at.isoformat()}),
                "idempotency_key": f"create_question_{q.question_id}"
            }
            
            client.insert_rows_json("autohaus-infrastructure.autohaus_cil.open_questions", [row])
            client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
        except Exception as e:
            logger.error(f"Failed to insert open question {q.question_id}: {e}")
            
    return q

async def resolve_question(
    question_id: str,
    resolution_answer: str,
    resolved_by: str,
    bq_client = None
) -> ResolutionResult:
    now = datetime.now(timezone.utc)
    vs_sla = "ON_TIME"
    deps = []
    
    if bq_client:
        try:
            client = bq_client if hasattr(bq_client, 'query') else bq_client.client
            from google.cloud import bigquery
            
            q = "SELECT due_at, dependency_list FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE question_id = @qid"
            jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("qid", "STRING", question_id)])
            
            rows = list(client.query(q, job_config=jc).result())
            if rows:
                due_at = rows[0].due_at
                deps = []
                if rows[0].dependency_list:
                    # In BQ it might come back as string
                    dl = rows[0].dependency_list
                    if isinstance(dl, str):
                        deps = json.loads(dl)
                    else:
                        deps = dl
                if due_at and now > due_at:
                    vs_sla = "OVERDUE"
                    
                u_q = """
                    UPDATE `autohaus-infrastructure.autohaus_cil.open_questions`
                    SET status = 'RESOLVED',
                        resolution_answer = @ans,
                        resolved_by = @rb,
                        resolved_at = CURRENT_TIMESTAMP()
                    WHERE question_id = @qid
                """
                jc_u = bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("ans", "STRING", resolution_answer),
                    bigquery.ScalarQueryParameter("rb", "STRING", resolved_by),
                    bigquery.ScalarQueryParameter("qid", "STRING", question_id)
                ])
                client.query(u_q, job_config=jc_u).result()
                
                event_row = {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "OPEN_QUESTION_RESOLVED",
                    "timestamp": now.isoformat(),
                    "actor_type": "USER",
                    "actor_id": resolved_by,
                    "target_type": "QUESTION",
                    "target_id": question_id,
                    "payload": json.dumps({
                        "question_id": question_id,
                        "resolved_by": resolved_by,
                        "resolution_answer": resolution_answer,
                        "resolution_time_vs_sla": vs_sla
                    }),
                    "idempotency_key": f"resolve_question_{question_id}"
                }
                client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
                
                await propagate_resolution(question_id, resolution_answer, deps, bq_client)
                
                return ResolutionResult(
                    question_id=question_id,
                    resolution_answer=resolution_answer,
                    resolved_by=resolved_by,
                    resolution_time_vs_sla=vs_sla,
                    dependencies_released=len(deps),
                    propagation_complete=True
                )
        except Exception as e:
            logger.error(f"Failed to resolve open question {question_id}: {e}")
            
    return ResolutionResult(
        question_id=question_id,
        resolution_answer=resolution_answer,
        resolved_by=resolved_by,
        resolution_time_vs_sla=vs_sla,
        dependencies_released=0,
        propagation_complete=False
    )

async def propagate_resolution(
    question_id: str,
    resolution_answer: str,
    dependency_list: list[str],
    bq_client = None
) -> None:
    if not bq_client or not dependency_list:
        return
        
    client = bq_client if hasattr(bq_client, 'query') else bq_client.client
    now = datetime.now(timezone.utc).isoformat()
    events = []
    
    for op_id in dependency_list:
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "DEPENDENCY_RELEASED",
            "timestamp": now,
            "actor_type": "SYSTEM",
            "actor_id": "open_questions_engine",
            "target_type": "OPERATION",
            "target_id": op_id,
            "payload": json.dumps({
                "question_id": question_id,
                "operation_id": op_id,
                "resolution_answer": resolution_answer
            }),
            "idempotency_key": f"dep_release_{question_id}_{op_id}"
        })
        
    if events:
        try:
            client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", events)
        except Exception as e:
            logger.error(f"Failed to insert DEPENDENCY_RELEASED events: {e}")
            
    try:
        from google.cloud import bigquery
        u_q = """
            UPDATE `autohaus-infrastructure.autohaus_cil.open_questions`
            SET resolution_propagated = True
            WHERE question_id = @qid
        """
        jc = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("qid", "STRING", question_id)
        ])
        client.query(u_q, job_config=jc).result()
    except Exception as e:
        logger.error(f"Failed to set resolution_propagated=True for {question_id}: {e}")

async def check_overdue_questions(
    bq_client = None
) -> list[OverdueQuestion]:
    if not bq_client: return []
    
    client = bq_client if hasattr(bq_client, 'query') else bq_client.client
    
    q = """
        SELECT question_id, content, owner_role, due_at, dependency_list
        FROM `autohaus-infrastructure.autohaus_cil.open_questions`
        WHERE status = 'OPEN'
          AND due_at < CURRENT_TIMESTAMP()
          AND escalated = False
    """
    
    try:
        rows = list(client.query(q).result())
    except Exception as e:
        logger.error(f"Failed to query overdue questions: {e}")
        return []
        
    now = datetime.now(timezone.utc)
    overdue_list = []
    
    for row in rows:
        q_id = row.question_id
        content = row.content
        owner_role = row.owner_role
        due_at = row.due_at
        
        deps = []
        if row.dependency_list:
            if isinstance(row.dependency_list, str):
                deps = json.loads(row.dependency_list)
            else:
                deps = row.dependency_list
        
        hours_overdue = (now - due_at).total_seconds() / 3600.0 if due_at else 0.0
        
        try:
            from google.cloud import bigquery
            u_q = "UPDATE `autohaus-infrastructure.autohaus_cil.open_questions` SET escalated = True WHERE question_id = @qid"
            jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("qid", "STRING", q_id)])
            client.query(u_q, job_config=jc).result()
            
            event_row = {
                "event_id": str(uuid.uuid4()),
                "event_type": "QUESTION_OVERDUE",
                "timestamp": now.isoformat(),
                "actor_type": "SYSTEM",
                "actor_id": "open_questions_engine",
                "target_type": "QUESTION",
                "target_id": q_id,
                "payload": json.dumps({
                    "question_id": q_id,
                    "owner_role": owner_role,
                    "hours_overdue": hours_overdue,
                    "dependency_count": len(deps)
                }),
                "idempotency_key": f"overdue_{q_id}"
            }
            client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])
            
            if owner_role == "SOVEREIGN":
                # Will route to SMS if significance score >= policy threshold in Phase 3
                logger.info(f"Trigger attention_dispatcher for SOVEREIGN overdue question: {q_id}")
                
            overdue_list.append(OverdueQuestion(
                question_id=q_id,
                content=content,
                owner_role=owner_role,
                hours_overdue=hours_overdue,
                dependency_count=len(deps),
                escalated_at=now
            ))
        except Exception as e:
            logger.error(f"Failed to process overdue question {q_id}: {e}")
            
    return overdue_list
