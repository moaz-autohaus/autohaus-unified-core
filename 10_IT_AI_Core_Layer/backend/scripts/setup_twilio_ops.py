import os
import json
import logging
import asyncio
from datetime import datetime
from database.bigquery_client import BigQueryClient
from integrations.twilio_spoke import TwilioSpoke

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_twilio_ops")

async def run_setup():
    bq = BigQueryClient()
    twilio_number = "+13193007709"
    twilio_sid = "PN21d71b7892c4fd3591d5ebd0367257bf"
    moaz_phone = "+14124991241"
    
    # 1. Update/Registry KAMM LLC
    logger.info("Registering KAMM LLC with CIL_OPS number...")
    kamm_row = {
        "entity_id": "KAMM_LLC",
        "entity_type": "COMPANY",
        "canonical_name": "KAMM LLC",
        "status": "ACTIVE",
        "anchors": json.dumps({"CIL_OPS": twilio_number}),
        "authority_level": "VERIFIED",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Check if exists
    check_query = "SELECT entity_id FROM `autohaus-infrastructure.autohaus_cil.entity_registry` WHERE entity_id = 'KAMM_LLC'"
    exists = list(bq.client.query(check_query).result())
    
    if not exists:
        errs = bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.entity_registry", [kamm_row])
        if errs: logger.error(f"Failed to insert KAMM_LLC: {errs}")
        else: logger.info("KAMM LLC registered.")
    else:
        update_query = f"""
            UPDATE `autohaus-infrastructure.autohaus_cil.entity_registry`
            SET anchors = @anchors, updated_at = CURRENT_TIMESTAMP()
            WHERE entity_id = 'KAMM_LLC'
        """
        job_config = bq.client.query(update_query, job_config=bq.client.QueryJobConfig(
            query_parameters=[bq.client.ScalarQueryParameter("anchors", "STRING", json.dumps({"CIL_OPS": twilio_number}))]
        ))
        job_config.result()
        logger.info("KAMM LLC anchors updated.")

    # 2. Update Policy Registry
    logger.info("Seeding TWILIO policies...")
    policies = [
        ("TWILIO", "CIL_OPS_NUMBER", twilio_number),
        ("TWILIO", "CIL_OPS_SID", twilio_sid),
        ("TWILIO", "CUSTOMER_NUMBER", "null"),
        ("TWILIO", "DISPATCH_NUMBER", "null"),
    ]
    
    for domain, key, val in policies:
        insert_query = f"""
            INSERT INTO `autohaus-infrastructure.autohaus_cil.policy_registry`
            (domain, key, value, created_at, created_by, active)
            VALUES ('{domain}', '{key}', '{val}', CURRENT_TIMESTAMP(), 'SYSTEM', TRUE)
        """
        bq.client.query(insert_query).result()
        logger.info(f"  + Policy {domain}.{key} = {val}")

    # 3. Log Activation Event
    logger.info("Logging activation event...")
    event_row = {
        "event_id": str(datetime.utcnow().timestamp()),
        "event_type": "TWILIO_CHANNEL_ACTIVATED",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_type": "SYSTEM",
        "actor_id": "setup_script",
        "actor_role": "SYSTEM",
        "target_type": "PHONE",
        "target_id": twilio_number,
        "payload": json.dumps({"sid": twilio_sid, "purpose": "CIL_OPS", "linked_to": "KAMM_LLC"}),
    }
    bq.client.insert_rows_json("autohaus-infrastructure.autohaus_cil.cil_events", [event_row])

    # 4. Send Test SMS
    logger.info(f"Sending test SMS to {moaz_phone}...")
    spoke = TwilioSpoke(bq)
    res = await spoke.send_sms(
        to_number=moaz_phone,
        message="AutoHaus CIL Operations Channel Active. This number is for system alerts and internal coordination.",
        purpose="CIL_OPS"
    )
    logger.info(f"SMS Result: {res}")

if __name__ == "__main__":
    asyncio.run(run_setup())
