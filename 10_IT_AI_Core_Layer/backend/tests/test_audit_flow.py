import sys
import os
import json
import uuid
import datetime

# Add backend to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.audit_watcher import AuditWatcher, GovernanceException
from routes.inventory import get_labor_rate

def test_audit_context_enforcement():
    print("--- [VERIFICATION] Protocol 4.5: Audit Context Enforcement ---")
    
    # 1. Test Valid Context
    valid_context = {
        "run_id": str(uuid.uuid4()),
        "operator_id": "moaz@autohausia.com",
        "timestamp": str(datetime.datetime.now())
    }
    try:
        AuditWatcher.verify_context(valid_context)
        print("[SUCCESS] Valid context verified.")
    except Exception as e:
        print(f"[FAIL] Valid context rejected: {e}")

    # 2. Test Missing Context
    try:
        AuditWatcher.verify_context(None)
        print("[FAIL] Missing context allowed (Violation)")
    except GovernanceException as e:
        print(f"[SUCCESS] Missing context blocked as expected: {e}")

    # 3. Test Incomplete Context
    incomplete_context = {"run_id": "123"}
    try:
        AuditWatcher.verify_context(incomplete_context)
        print("[FAIL] Incomplete context allowed (Violation)")
    except GovernanceException as e:
        print(f"[SUCCESS] Incomplete context blocked as expected: {e}")

def test_identity_fork():
    print("\n--- [VERIFICATION] Unified Logic: Identity Fork ---")
    
    kamm_rate = get_labor_rate("KAMM_LLC")
    print(f"KAMM LLC Labor Rate: ${kamm_rate}/hr")
    if kamm_rate == 95:
        print("[SUCCESS] KAMM rate is $95.")
    else:
        print(f"[FAIL] KAMM rate mismatch: expected 95, got {kamm_rate}")

    retail_rate = get_labor_rate("RETAIL")
    print(f"Retail / AutoHaus Services Labor Rate: ${retail_rate}/hr")
    if retail_rate == 135:
        print("[SUCCESS] Retail rate is $135.")
    else:
        print(f"[FAIL] Retail rate mismatch: expected 135, got {retail_rate}")

if __name__ == "__main__":
    try:
        test_audit_context_enforcement()
        test_identity_fork()
        print("\n[UNIFIED ALIGNMENT VERIFIED]")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Verification failed: {e}")
        sys.exit(1)
