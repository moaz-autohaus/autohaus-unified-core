import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any

from database.bigquery_client import BigQueryClient

logger = logging.getLogger("autohaus.finance")

class FinancialEngine:
    """
    Core double-entry bookkeeping engine for AutoHaus CIL.
    Ensures that every financial event has balancing debits and credits 
    before committing to the immutable ledger.
    """
    def __init__(self, bq_client=None):
        self.bq_client = bq_client or BigQueryClient().client

    def post_journal_entry(self, lines: List[Dict[str, Any]], created_by: str = "SYSTEM", source_doc_id: str = None) -> dict:
        """
        Takes a list of proposed journal lines and commits them if they balance correctly.
        Expected line shape:
        {
           "account_code": "1400",
           "account_name": "Inventory",
           "entry_type": "DEBIT",
           "amount": 10500.00,
           "entity_id": "ent_AHSIN_VIN_001",
           "description": "Auction purchase + fee"
        }
        """
        if not lines:
            return {"status": "error", "message": "No lines provided."}

        # 0. Global Compliance Freeze Check
        from database.policy_engine import get_policy
        if get_policy("SYSTEM", "FROZEN"):
            logger.warning(f"[SECURITY] Ledger post blocked: System is FROZEN.")
            return {"status": "error", "message": "Ledger is currently frozen for security/compliance."}

        # 1. Verification Phase
        total_debit = 0.0
        total_credit = 0.0

        for line in lines:
            amt = float(line.get("amount", 0.0))
            if amt < 0:
                return {"status": "error", "message": f"Amounts must be absolute positive values. Found {amt}."}

            if line["entry_type"] == "DEBIT":
                total_debit += amt
            elif line["entry_type"] == "CREDIT":
                total_credit += amt
            else:
                return {"status": "error", "message": f"Invalid entry_type: {line['entry_type']}"}

        # 2. Strict Balance Check
        # We use a tiny float tolerance just in case of weird division issues
        if abs(total_debit - total_credit) > 0.001:
            logger.error(f"[LEDGER REJECTED] Unbalanced entry: Debits={total_debit}, Credits={total_credit}")
            return {
                "status": "error", 
                "message": f"Journal entry must balance. Debits: {total_debit}, Credits: {total_credit}"
            }

        # 3. Preparation 
        transaction_id = f"tx_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        rows_to_insert = []

        for line in lines:
            rows_to_insert.append({
                "entry_id": f"je_{uuid.uuid4().hex[:12]}",
                "transaction_id": transaction_id,
                "transaction_date": now,
                "account_code": line["account_code"],
                "account_name": line.get("account_name", "Unknown Account"),
                "entry_type": line["entry_type"],
                "amount": float(line["amount"]),
                "entity_id": line.get("entity_id"),
                "description": line.get("description"),
                "created_by": created_by,
                "status": "POSTED",
                "source_document_id": source_doc_id
            })

        # 4. Commit to BigQuery immutable ledger
        if self.bq_client:
            errors = self.bq_client.insert_rows_json(
                "autohaus-infrastructure.autohaus_cil.financial_ledger", 
                rows_to_insert
            )
            if errors:
                logger.error(f"[LEDGER CRITICAL] BigQuery insertion failed for {transaction_id}: {errors}")
                return {"status": "error", "message": "Database insertion failed", "details": errors}

        logger.info(f"[LEDGER POSTED] Transaction {transaction_id} committed. Value: ${total_debit:,.2f}")
        return {
            "status": "success",
            "transaction_id": transaction_id,
            "lines_posted": len(rows_to_insert),
            "total_value": total_debit
        }

    def get_vin_pnl(self, vin_entity_id: str) -> dict:
        """
        Calculates the real-time exact profit/loss of a specific vehicle
        by summing all ledger actions tied to it.
        """
        query = """
            SELECT 
                account_code, account_name, entry_type, SUM(amount) as total
            FROM `autohaus-infrastructure.autohaus_cil.financial_ledger`
            WHERE entity_id = @vin_id AND status = 'POSTED'
            GROUP BY account_code, account_name, entry_type
        """
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("vin_id", "STRING", vin_entity_id)]
        )
        
        try:
            results = list(self.bq_client.query(query, job_config=job_config))
            
            # Simple summarization
            cost_basis = 0.0
            recon_costs = 0.0
            revenue = 0.0
            
            for row in results:
                # E.g. Account 1400 = Inventory (Cost Basis), 5200 = Recon
                if row.account_code.startswith("14") and row.entry_type == "DEBIT":
                    cost_basis += row.total
                elif row.account_code.startswith("5") and row.entry_type == "DEBIT":
                    recon_costs += row.total
                elif row.account_code.startswith("4") and row.entry_type == "CREDIT":
                    revenue += row.total

            return {
                "entity_id": vin_entity_id,
                "cost_basis": cost_basis,
                "recon_costs": recon_costs,
                "revenue": revenue,
                "gross_profit": revenue - cost_basis - recon_costs,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Failed to fetch VIN P&L for {vin_entity_id}: {e}")
            return {"status": "error", "message": "Query failed"}
