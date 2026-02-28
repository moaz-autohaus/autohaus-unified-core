import asyncio
import logging
import json
import os
import sys
from google.cloud import bigquery
from google.oauth2 import service_account

# Fix paths for module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance.financial_engine import FinancialEngine
from finance.financial_dispatcher import FinancialDispatcher

# Initialize BigQuery
KEY_PATH = "/Users/moazsial/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/backend/auth/replit-sa-key.json"
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project="autohaus-infrastructure")

async def test_financial_ledger():
    print("\n--- 💸 TESTING INTERNAL SHADOW LEDGER 💸 ---")
    engine = FinancialEngine(client)
    dispatcher = FinancialDispatcher(client)
    
    # 1. Simulate an Auction Receipt Extraction Result
    test_vin = "WBA93HM0XP1TEST01"
    doc_id = "test_doc_auction_001"
    fields = {
        "vin": {"value": test_vin},
        "purchase_price": {"value": 15000.00},
        "buy_fee": {"value": 650.00}
    }
    
    print(f"\n[STEP 1] Dispatching Auction Receipt for VIN {test_vin}...")
    # This would normally create a HITL proposal. For the test, we'll bypass and post directly to engine as well.
    res = await dispatcher.propose_entries_from_doc(doc_id, "AUCTION_RECEIPT", fields)
    print(f"✅ Dispatcher created HITL proposal: {res.get('hitl_event_id')}")
    
    # 2. Simulate Posting to Ledger (Manually)
    lines = [
        {
            "account_code": "1400",
            "account_name": "Inventory",
            "entry_type": "DEBIT",
            "amount": 15650.00,
            "entity_id": test_vin,
            "description": "Auction Purchase via Test Script"
        },
        {
            "account_code": "1000",
            "account_name": "Cash",
            "entry_type": "CREDIT",
            "amount": 15650.00,
            "entity_id": None,
            "description": "Payment for VIN " + test_vin
        }
    ]
    
    print("\n[STEP 2] Committing Journal Entry to Immutable Ledger...")
    post_res = engine.post_journal_entry(lines, created_by="TEST_RUNNER")
    print(f"✅ Ledger Posted: {post_res.get('transaction_id')}")
    
    # 3. Simulate a Recon Expense (e.g. Tires)
    recon_lines = [
        {"account_code": "5200","account_name": "Recon","entry_type": "DEBIT","amount": 400.00,"entity_id": test_vin,"description": "New Tires"},
        {"account_code": "1000","account_name": "Cash","entry_type": "CREDIT","amount": 400.00,"entity_id": None,"description": "Payment for tires"}
    ]
    engine.post_journal_entry(recon_lines, created_by="TEST_RUNNER")
    
    # 4. Query P&L
    print(f"\n[STEP 3] Calculating Unit Economics for VIN {test_vin}...")
    pnl = engine.get_vin_pnl(test_vin)
    print(json.dumps(pnl, indent=2))
    
    print("\n--- ✅ TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_financial_ledger())
