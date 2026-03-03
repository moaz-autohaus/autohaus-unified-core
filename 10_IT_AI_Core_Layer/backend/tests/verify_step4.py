
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from membrane.translation_engine import TranslationEngine

def verify_step4():
    print("=== Phase 3 Step 4 Verification Hook ===")
    
    engine = TranslationEngine()
    
    # 1. Test Conflict Translation
    print("\nTest 1: Translating MATERIAL_CONFLICT_DETECTED...")
    payload1 = {
        "target_id": "VEH_9923",
        "existing_value": "$65,000",
        "extracted_value": "$68,500",
        "variance_description": "Price mismatch on buyer order"
    }
    
    plate1 = engine.translate_to_plate("MATERIAL_CONFLICT_DETECTED", payload1)
    
    assert plate1 is not None, "Plate should not be None"
    assert plate1.plate_type == "CONFLICT_PLATE"
    assert plate1.display_data["existing"] == "$65,000"
    assert plate1.display_data["proposed"] == "$68,500"
    
    # Check for 'RESOLVE_CONFLICT' variant in actions labels or actions identifiers
    actions = [a["action"] for a in plate1.available_actions]
    assert any("RESOLVE_CONFLICT" in a for a in actions), f"Expected resolve actions, got {actions}"
    print(f"✅ CONFLICT_PLATE translated successfully with data: {plate1.display_data}")
    
    # 2. Test Lead Translation
    print("\nTest 2: Translating NEW_LEAD...")
    payload2 = {
        "person_id": "PER_001",
        "name": "John Doe",
        "source": "TrueCar",
        "interest_summary": "Inquiry on Porsche 911",
        "contact_method": "SMS"
    }
    
    plate2 = engine.translate_to_plate("NEW_LEAD", payload2)
    assert plate2.plate_type == "LEAD_PLATE"
    assert plate2.display_data["name"] == "John Doe"
    print(f"✅ LEAD_PLATE translated successfully")

    # 3. Test Enforcement Error Translation
    print("\nTest 3: Translating ENFORCEMENT_STOP...")
    payload3 = {
        "target_id": "CARBON_LLC",
        "action_attempted": "POLICY_WRITE",
        "reason": "Role 'FIELD' lacks explicit permission"
    }
    
    plate3 = engine.translate_to_plate("ENFORCEMENT_STOP", payload3)
    assert plate3.plate_type == "ERROR_MODAL"
    assert "Operation Blocked" in plate3.display_title
    print(f"✅ ERROR_MODAL translated successfully")

    print("\n=== Verification Hook PASSED ===")

if __name__ == "__main__":
    verify_step4()
