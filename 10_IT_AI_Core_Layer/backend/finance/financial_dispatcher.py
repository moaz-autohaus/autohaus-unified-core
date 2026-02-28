import logging
import json
from typing import Dict, Any, List
from google.cloud import bigquery

from .financial_engine import FinancialEngine

logger = logging.getLogger("autohaus.finance.dispatcher")

class FinancialDispatcher:
    """
    Observes finished document extractions and translates specific business 
    documents (Invoices, Receipts) into balanced Ledger Entry proposals.
    """
    def __init__(self, bq_client=None):
        self.bq_client = bq_client
        self.engine = FinancialEngine(bq_client)

    async def propose_entries_from_doc(self, document_id: str, doc_type: str, fields: Dict[str, Any]) -> dict:
        """
        Maps doc types (e.g. AUCTION_RECEIPT) to chart of account rules.
        """
        logger.info(f"[FINANCE] Dispatching document {document_id} ({doc_type}) to ledger proposals")
        
        proposals = []

        if doc_type == "AUCTION_RECEIPT":
            proposals = self._map_auction_receipt(document_id, fields)
        elif doc_type == "VENDOR_INVOICE":
            proposals = self._map_vendor_invoice(document_id, fields)
        
        if not proposals:
            return {"status": "skipped", "reason": "No financial mapping for this doc type"}

        # We don't POST yet. We CREATE A HITL PROPOSAL.
        # This keeps it in the Sandbox.
        from pipeline.hitl_service import propose
        
        res = propose(
            bq_client=self.bq_client,
            actor_user_id="SYSTEM_FINANCE",
            actor_role="SYSTEM",
            action_type="FINANCIAL_JOURNAL_PROPOSAL",
            target_type="DOCUMENT",
            target_id=document_id,
            payload={"lines": proposals},
            reason=f"Auto-generated proposal from {doc_type} extraction",
            source="FINANCE_DISPATCHER"
        )
        
        return res

    def _map_auction_receipt(self, document_id: str, fields: Dict[str, Any]) -> List[dict]:
        """
        Auction Receipt -> 
        DEBIT: 1400 Inventory (Purchase Price + Buy Fee)
        CREDIT: 1000 Cash / Floorplan
        """
        vin = fields.get("vin", {}).get("value")
        buy_price = float(fields.get("purchase_price", {}).get("value") or 0.0)
        buy_fee = float(fields.get("buy_fee", {}).get("value") or 0.0)
        total = buy_price + buy_fee
        
        if total <= 0: return []

        return [
            {
                "account_code": "1400",
                "account_name": "Inventory - Vehicles",
                "entry_type": "DEBIT",
                "amount": total,
                "entity_id": vin,
                "description": f"Auction Purchase: {vin}"
            },
            {
                "account_code": "1000",
                "account_name": "Cash",
                "entry_type": "CREDIT",
                "amount": total,
                "entity_id": None,
                "description": f"Payment for VIN {vin}"
            }
        ]

    def _map_vendor_invoice(self, document_id: str, fields: Dict[str, Any]) -> List[dict]:
        """
        Vendor Invoice (e.g. Parts/Service) ->
        DEBIT: 5200 Recon Expense
        CREDIT: 2000 Accounts Payable
        """
        vin = fields.get("vin", {}).get("value")
        amount = float(fields.get("total_amount", {}).get("value") or 0.0)
        
        if amount <= 0: return []

        return [
            {
                "account_code": "5200",
                "account_name": "Reconditioning Expense",
                "entry_type": "DEBIT",
                "amount": amount,
                "entity_id": vin,
                "description": f"Parts/Service Invoice for {vin}"
            },
            {
                "account_code": "2001",
                "account_name": "Accounts Payable",
                "entry_type": "CREDIT",
                "amount": amount,
                "entity_id": None,
                "description": f"Invoice from Vendor"
            }
        ]
