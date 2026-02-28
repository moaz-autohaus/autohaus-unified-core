import json
import logging
import uuid
import re
import os
from datetime import datetime, timezone

from google.cloud import bigquery
import google.generativeai as genai

from database.open_questions import raise_open_question
from pipeline.hitl_service import propose, ActionType

logger = logging.getLogger("autohaus.governance_agent")

GOVERNANCE_CLASSIFICATION_PROMPT = """You are the AutoHaus Governance Intent Classifier.
Analyze the user's input and map it to a specific governance action.

You MUST return a JSON object in this exact format:
{
  "action": "RESOLVE_QUESTION" | "SHOW_PATTERNS" | "SHOW_TRUST" | "POLICY_CHANGE" | "POLICY_VIEW" | "CONFIRM_PROPOSAL" | "UNKNOWN",
  "parameters": {
    "question_id": "optional string, e.g. a UUID if mentioned",
    "resolution_value": "optional string, the value to set or the reference to use",
    "domain": "optional string, e.g. EXTRACTION, COMPLIANCE, ESCALATION",
    "key": "optional string, e.g. CONFIDENCE_THRESHOLD, KAMM_MUST_REVIEW_TYPES",
    "doc_type": "optional string, e.g. AUCTION_RECEIPT, VEHICLE_TITLE",
    "value": "optional mixed, e.g. 0.90 or 'BILL_OF_SALE' for policies",
    "action_type": "optional string, e.g. ADD, REMOVE, SET"
  }
}

Examples:
Input: "Change the confidence threshold for auction receipts to 0.90"
Output: {"action": "POLICY_CHANGE", "parameters": {"domain": "EXTRACTION", "key": "CONFIDENCE_THRESHOLD", "doc_type": "AUCTION_RECEIPT", "value": 0.90}}

Input: "Add BILL_OF_SALE to the KAMM review list"
Output: {"action": "POLICY_CHANGE", "parameters": {"domain": "COMPLIANCE", "key": "KAMM_MUST_REVIEW_TYPES", "action_type": "ADD", "value": "BILL_OF_SALE"}}

Input: "Show me the current policies"
Output: {"action": "POLICY_VIEW", "parameters": {}}

Input: "What's the confidence threshold for titles?"
Output: {"action": "POLICY_VIEW", "parameters": {"domain": "EXTRACTION", "key": "CONFIDENCE_THRESHOLD", "doc_type": "VEHICLE_TITLE"}}

Input: "resolve question 123e4567 to 12345"
Output: {"action": "RESOLVE_QUESTION", "parameters": {"question_id": "123e4567", "resolution_value": "12345"}}

Input: "Yes", "Confirm", "Do it"
Output: {"action": "CONFIRM_PROPOSAL", "parameters": {}}
"""

class GovernanceAgent:
    def __init__(self, bq_client=None, api_key=None, model_name="gemini-2.5-flash"):
        if not bq_client:
            try:
                from database.bigquery_client import BigQueryClient
                bq_wrapper = BigQueryClient()
                self.bq_client = bq_wrapper.client
            except Exception as e:
                logger.warning(f"[GOVERNANCE] BigQuery client init failed: {e}")
                self.bq_client = None
        else:
            self.bq_client = bq_client

        # Gemini setup for LLM intent parsing
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if resolved_key:
            genai.configure(api_key=resolved_key)
            self._model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=GOVERNANCE_CLASSIFICATION_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                )
            )
        else:
            logger.warning("[GOVERNANCE] GEMINI_API_KEY not set. LLM parsing will fail to regex.")
            self._model = None

    def _parse_intent_with_llm(self, user_input: str) -> dict:
        if not self._model:
            return {"action": "UNKNOWN", "parameters": {}}
            
        try:
            response = self._model.generate_content(user_input)
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                raw_text = raw_text.rsplit("```", 1)[0]
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"[GOVERNANCE] LLM Parse error: {e}")
            return {"action": "UNKNOWN", "parameters": {}}

    def generate_session_greeting(self) -> str:
        """
        Dynamically query the views and open_questions table to render a quick string.
        """
        if not self.bq_client:
            return "AutoHaus C-OS v3.1 — Digital Chief of Staff connected. (Governance metrics unavailable)."
        try:
            # 1. Active Open Questions
            q_query = "SELECT priority, COUNT(*) as c FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE status = 'OPEN' GROUP BY priority"
            open_qs = list(self.bq_client.query(q_query).result())
            high_q = sum(row.c for row in open_qs if row.priority == 'HIGH')
            med_q = sum(row.c for row in open_qs if row.priority == 'MEDIUM')

            # 2. Overdue items
            overdue_query = "SELECT COUNT(*) as c FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE status = 'OPEN' AND CURRENT_TIMESTAMP() > sla_deadline"
            overdue_res = list(self.bq_client.query(overdue_query).result())
            overdue_count = overdue_res[0].c if overdue_res else 0

            # 3. Active truth projection conflicts
            conf_query = "SELECT COUNT(*) as c FROM `autohaus-infrastructure.autohaus_cil.entity_facts` WHERE status = 'CONFLICTING_CLAIM'"
            conf_res = list(self.bq_client.query(conf_query).result())
            conf_count = conf_res[0].c if conf_res else 0

            # 4. Question debt trend
            debt_query = "SELECT priority, status, count FROM `autohaus-infrastructure.autohaus_cil.question_debt_summary`"
            debt_res = list(self.bq_client.query(debt_query).result())
            total_resolved = sum(row.count for row in debt_res if row.status == 'RESOLVED')
            
            greeting = f"AutoHaus C-OS v3.1 — Digital Chief of Staff. Welcome back, Chief.\n\n"
            greeting += f"Governance State of the Union:\n"
            greeting += f"- 🔴 {high_q} High-Priority Open Questions ({overdue_count} Overdue)\n"
            greeting += f"- 🟡 {med_q} Medium-Priority Questions\n"
            greeting += f"- ⚔️ {conf_count} Active Entity Truth Conflicts\n"
            greeting += f"- 📈 Question Debt Trend: {total_resolved} total resolved."
            
            return greeting
            
        except Exception as e:
            logger.error(f"Failed to generate greeting: {e}")
            return "AutoHaus C-OS v3.1 — Digital Chief of Staff connected. (Governance metrics unavailable)."

    def evaluate_governance_command(self, user_input: str, actor_id: str, actor_role: str) -> dict:
        """
        Parses the user input and performs governance operations if it's a resolution.
        """
        user_input_lower = user_input.lower()
        
        # 0. Try fast-path regex for explicit question resolution
        action = "UNKNOWN"
        params = {}
        
        match = re.search(r"resolve[ \w]+([a-f0-9\-]{36})[ \w]*to[ ]+([\w]+)", user_input_lower)
        if match:
            action = "RESOLVE_QUESTION"
            params = {"question_id": match.group(1), "resolution_value": match.group(2)}
        else:
            # Fallback to LLM intent classification (Primary for natural language)
            parsed = self._parse_intent_with_llm(user_input)
            action = parsed.get("action", "UNKNOWN")
            params = parsed.get("parameters", {})
        
        # 1. Check for conversational resolution
        if action == "RESOLVE_QUESTION":
            question_id = params.get("question_id")
            resolution_value = params.get("resolution_value")
            
            if not question_id:
                # If LLM didn't catch an ID, try to find the most recent open question
                q_query = "SELECT question_id FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE status = 'OPEN' ORDER BY created_at DESC LIMIT 1"
                res = list(self.bq_client.query(q_query).result())
                if res:
                    question_id = res[0].question_id
                else:
                    return {"message": "I understand you want to resolve a question, but I couldn't find an active question to apply this to.", "plate": "GOVERNANCE_DASHBOARD"}
                
            # Fetch question details to know the target document/entity
            q_query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.open_questions` WHERE question_id = @qid"
            job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("qid", "STRING", question_id)])
            res = list(self.bq_client.query(q_query, job_config=job_config).result())
            
            if res:
                q_row = res[0]
                context = json.loads(q_row.context) if isinstance(q_row.context, str) else q_row.context
                
                if q_row.question_type == "CONFIDENCE_SLA":
                    # Field override
                    payload = {
                        "field_name": context.get("field_name"),
                        "new_value": resolution_value,
                        "reason": f"Conversational resolution of {question_id}"
                    }
                    target_id = context.get("document_id")
                    
                    r = propose(self.bq_client, actor_id, actor_role, "FIELD_OVERRIDE", "DOCUMENT", target_id, payload)
                    if r["status"] in ("PROPOSED", "VALIDATED", "APPLIED"):
                        # Close the question
                        self.bq_client.query(f"UPDATE `autohaus-infrastructure.autohaus_cil.open_questions` SET status = 'RESOLVED', updated_at = CURRENT_TIMESTAMP() WHERE question_id = '{question_id}'").result()
                        return {"message": f"Successfully proposed/applied field override for {context.get('field_name')} -> {resolution_value}. HITL Event: {r.get('hitl_event_id')}", "plate": "GOVERNANCE_DASHBOARD"}
                    else:
                        return {"message": f"Failed to propose override: {r.get('reason')}", "plate": "GOVERNANCE_DASHBOARD"}

        # 2. Correction Patterns Summary
        if action == "SHOW_PATTERNS" or "pattern" in user_input_lower or "correction" in user_input_lower or "tuning" in user_input_lower:
            try:
                p_query = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.correction_patterns` LIMIT 5"
                patterns = list(self.bq_client.query(p_query).result())
                msg = "Top Correction Patterns:\n"
                for p in patterns:
                    msg += f"- Field '{p.field_name}': System said '{p.system_value}', Human corrected to '{p.human_value}' ({p.correction_count} times)\n"
                msg += "\n*Suggestion*: Consider adding a policy mapping for these recurring corrections."
                return {"message": msg, "plate": "GOVERNANCE_DASHBOARD", "dataset": [dict(p) for p in patterns]}
            except Exception as e:
                return {"message": f"Error fetching patterns: {e}", "plate": "GOVERNANCE_DASHBOARD"}
                
        # 3. Entity Trust Summary
        if action == "SHOW_TRUST" or "trust" in user_input_lower or "lineage" in user_input_lower or "entity facts" in user_input_lower:
             return {"message": "Opening Entity Trust Explorer. Querying `entity_trust_summary`...", "plate": "ENTITY_TRUST"}

        # 5. Policy Change
        if action == "POLICY_CHANGE":
            from database.policy_engine import get_policy
            domain = params.get("domain", "EXTRACTION")
            key = params.get("key", "UNKNOWN_KEY")
            doc_type = params.get("doc_type")
            new_value = params.get("value")
            
            # Fetch current (before)
            current_val = get_policy(domain, key, doc_type=doc_type)
            
            # Structure impact
            diff_msg = f"Current value: {current_val}\nProposed value: {new_value}"
            impact_msg = f"This updates global pipeline rules for {key}."
            if key == "CONFIDENCE_THRESHOLD":
                if isinstance(new_value, (int, float)) and isinstance(current_val, (int, float)):
                    if new_value > current_val:
                        impact_msg += " This means MORE documents will route to human review."
                    else:
                        impact_msg += " This means FEWER documents will route to human review."
            elif isinstance(current_val, list) and new_value:
                if new_value not in current_val:
                    impact_msg += f" This adds {new_value} to the list."
            
            payload = {
                "policy_domain": domain,
                "policy_key": key,
                "applies_to_doc_type": doc_type,
                "new_value": new_value,
                "reason": f"Conversational Policy Update to {new_value}"
            }
            
            r = propose(self.bq_client, actor_id, actor_role, "POLICY_CHANGE", "POLICY", f"{domain}_{key}", payload)
            
            if r["status"] == "PROPOSED":
                msg = f"I'll update the {domain} '{key}' policy for {doc_type or 'all documents'}.\n\n{diff_msg}\n\n{impact_msg}\n\nConfirm?"
                return {"message": msg, "plate": "GOVERNANCE_DASHBOARD", "hitl_event_id": r["hitl_event_id"]}
            elif r["status"] == "REJECTED":
                return {"message": r.get("reason", "Policy change rejected."), "plate": "GOVERNANCE_DASHBOARD"}
            else:
                return {"message": f"Successfully updated policy {domain}.{key} to {new_value}.", "plate": "GOVERNANCE_DASHBOARD"}
        
        # 6. Policy View
        if action == "POLICY_VIEW":
            domain = params.get("domain")
            if domain:
                q = f"SELECT * FROM `autohaus-infrastructure.autohaus_cil.policy_registry` WHERE active = TRUE AND domain = '{domain}'"
            else:
                q = "SELECT * FROM `autohaus-infrastructure.autohaus_cil.policy_registry` WHERE active = TRUE"
            try:
                policies = list(self.bq_client.query(q).result())
                msg = "Active Policies:\n"
                for p in policies:
                    msg += f"- {p.domain}.{p.key}: {p.value} (DocType: {p.applies_to_doc_type or 'Global'})\n"
                return {"message": msg, "plate": "GOVERNANCE_DASHBOARD", "dataset": [dict(p) for p in policies]}
            except Exception as e:
                return {"message": f"Error fetching policies: {e}", "plate": "GOVERNANCE_DASHBOARD"}

        # 7. Confirm Proposal Context Action
        if action == "CONFIRM_PROPOSAL" or user_input_lower in ["yes", "confirm", "approve", "do it", "yep", "yeah"]:
            q = """
                SELECT hitl_event_id, target_id, action_type, payload FROM `autohaus-infrastructure.autohaus_cil.hitl_events`
                WHERE actor_user_id = @actor AND status = 'PROPOSED'
                ORDER BY created_at DESC LIMIT 1
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("actor", "STRING", actor_id)]
            )
            res = list(self.bq_client.query(q, job_config=job_config).result())
            if res:
                hitl_id = res[0].hitl_event_id
                action_type = res[0].action_type
                from pipeline.hitl_service import validate, apply
                v_res = validate(self.bq_client, hitl_id)
                if v_res["status"] == "VALIDATED":
                    a_res = apply(self.bq_client, hitl_id)
                    if a_res.get("status") == "ERROR":
                        return {"message": f"Failed to apply: {a_res.get('reason')}", "plate": "GOVERNANCE_DASHBOARD"}
                    
                    if action_type == "POLICY_CHANGE":
                        pl = json.loads(res[0].payload) if isinstance(res[0].payload, str) else res[0].payload
                        return {"message": f"Done. Policy '{pl.get('policy_key')}' updated to {pl.get('new_value')}. Effective immediately.", "plate": "GOVERNANCE_DASHBOARD"}
                    else:
                        return {"message": "Done. Action applied. Effective immediately.", "plate": "GOVERNANCE_DASHBOARD"}
                else:
                    return {"message": f"Validation failed: {json.dumps(v_res.get('checks'))}", "plate": "GOVERNANCE_DASHBOARD"}
            else:
                return {"message": "Nothing to confirm.", "plate": "GOVERNANCE_DASHBOARD"}

        return {"message": "Understood. The Governance layer tracks this operation.", "plate": "GOVERNANCE_DASHBOARD"}
