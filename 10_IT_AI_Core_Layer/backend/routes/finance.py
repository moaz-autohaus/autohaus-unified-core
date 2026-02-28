from fastapi import APIRouter, HTTPException, Depends, Query
from google.cloud import bigquery
from typing import Optional, List
import logging

from database.bigquery_client import BigQueryClient
from finance.financial_engine import FinancialEngine

logger = logging.getLogger("autohaus.finance.router")
finance_router = APIRouter()

def get_financial_engine():
    client = BigQueryClient().client
    return FinancialEngine(client)

@finance_router.get("/aggregate")
async def get_finance_aggregate(engine: FinancialEngine = Depends(get_financial_engine)):
    """
    Returns a high-level summary of the business's financial state 
    based on the Internal Shadow Ledger.
    """
    query = """
        SELECT 
            account_name, account_code, entry_type, SUM(amount) as total
        FROM `autohaus-infrastructure.autohaus_cil.financial_ledger`
        WHERE status = 'POSTED'
        GROUP BY account_name, account_code, entry_type
    """
    try:
        results = list(engine.bq_client.query(query))
        
        # Calculate stats
        cash = 0.0
        inventory_value = 0.0
        revenue = 0.0
        expenses = 0.0
        
        for row in results:
            if row.account_code.startswith("10"): # Cash
                cash += row.total if row.entry_type == "DEBIT" else -row.total
            elif row.account_code.startswith("14"): # Inventory
                inventory_value += row.total if row.entry_type == "DEBIT" else -row.total
            elif row.account_code.startswith("4"): # Revenue
                revenue += row.total # Credits for revenue
            elif row.account_code.startswith("5"): # Expenses
                expenses += row.total
                
        return {
            "cash_on_hand": cash,
            "inventory_valuation": inventory_value,
            "total_revenue": revenue,
            "total_expenses": expenses,
            "net_profit": revenue - expenses,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Failed to fetch financial aggregate: {e}")
        raise HTTPException(status_code=500, detail="Financial query failed")

@finance_router.get("/vin/{vin_id}/pnl")
async def get_vin_pnl(vin_id: str, engine: FinancialEngine = Depends(get_financial_engine)):
    """
    Returns the exact Profit and Loss for a specific vehicle.
    """
    pnl = engine.get_vin_pnl(vin_id)
    if pnl["status"] == "error":
        raise HTTPException(status_code=500, detail=pnl["message"])
    return pnl

@finance_router.post("/journal")
async def post_manual_journal(lines: List[dict], engine: FinancialEngine = Depends(get_financial_engine)):
    """
    Enables manual journal entries to be posted to the ledger.
    """
    res = engine.post_journal_entry(lines, created_by="USER_MANUAL")
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res
