"""
AutoHaus C-OS v3.1 — MODULE 5: Anomaly Monitor (The Sovereign Guardian)
========================================================================
An autonomous background worker that continuously audits the CIL's
operational state against defined SOPs and CEO-mandated thresholds.

This script is designed to run as a Cloud Run Job on a 15-minute cron
schedule, or be invoked manually for ad-hoc audits.

Audit Checks:
  1. THE GOLDEN RULE — Flag VINs 'Inbound' > 60 min without 'Quote_Sent'.
  2. ENTITY DRIFT     — Flag 'Green Tag' vehicles with no intercompany invoice.
  3. MARGIN ALERT     — Flag transport costs exceeding the $500 threshold.

Dispatch:
  When anomalies are found, a PRIORITY ALERT SMS is sent to the CEO via
  Twilio, and if the UCC dashboard is open, a JIT Plate is pushed.

MSO Purity Constraint:
  This monitor REPORTS risks. It does NOT execute financial transactions.
  Any remediation requires a human-in-the-loop Approval JIT Plate.

Author: AutoHaus CIL Build System
Version: 1.0.0
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from google.cloud import bigquery
import google.auth
from dotenv import load_dotenv

# Load environment
load_dotenv(os.path.expanduser("~/Documents/AutoHaus_CIL/10_IT_AI_Core_Layer/auth/.env"))

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autohaus.anomaly_monitor")

PROJECT_ID = "autohaus-infrastructure"
DATASET_ID = "autohaus_cil"
LEDGER_TABLE = f"{PROJECT_ID}.{DATASET_ID}.system_audit_ledger"
INVENTORY_TABLE = f"{PROJECT_ID}.{DATASET_ID}.inventory_master"

# Twilio Config
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
CEO_PHONE_NUMBER = os.environ.get("CEO_PHONE_NUMBER", "")

from database.policy_engine import get_policy

# Thresholds (derived from AUTOHAUS_SYSTEM_STATE.json + Sovereign Memory SOPs)
# Dynamically loaded via Policy Engine
def get_golden_rule_minutes():
    val = get_policy("ANOMALY", "golden_rule_minutes")
    if val is None:
        raise ValueError("Missing ANOMALY.golden_rule_minutes in policy registry. No fallbacks allowed.")
    return int(val)

def get_transport_cost_ceiling():
    val = get_policy("ANOMALY", "transport_cost_ceiling")
    if val is None:
        raise ValueError("Missing ANOMALY.transport_cost_ceiling in policy registry. No fallbacks allowed.")
    return float(val)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class Anomaly:
    """A detected anomaly requiring CEO attention."""
    check_name: str
    severity: str          # CRITICAL, WARNING, INFO
    description: str
    affected_entity: str
    affected_vin: str = ""
    affected_amount: float = 0.0
    detected_at: str = ""

    def to_alert_text(self) -> str:
        """Format as a concise SMS-friendly alert."""
        vin_str = f" | VIN: {self.affected_vin}" if self.affected_vin else ""
        amt_str = f" | ${self.affected_amount:,.2f}" if self.affected_amount > 0 else ""
        return (
            f"🚨 [{self.severity}] {self.check_name}\n"
            f"{self.description}{vin_str}{amt_str}\n"
            f"Entity: {self.affected_entity}"
        )


# ---------------------------------------------------------------------------
# BigQuery Client
# ---------------------------------------------------------------------------
def _get_bq_client() -> Optional[bigquery.Client]:
    """Create an authenticated BigQuery client with service account impersonation."""
    try:
        credentials, project = google.auth.default(
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/bigquery",
            ]
        )
        if hasattr(credentials, "with_subject"):
            credentials = credentials.with_subject("moaz@autohausia.com")
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    except Exception as e:
        logger.error(f"BigQuery client initialization failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Audit Check 1: THE GOLDEN RULE
# ---------------------------------------------------------------------------
def check_golden_rule(client: bigquery.Client) -> list[Anomaly]:
    """
    Flag any VIN that has been 'Inbound' for more than 60 minutes
    without a corresponding 'Quote_Sent' status in the audit ledger.
    """
    anomalies = []
    golden_rule_minutes = get_golden_rule_minutes()
    threshold_time = (
        datetime.now(timezone.utc) - timedelta(minutes=golden_rule_minutes)
    ).isoformat()

    query = f"""
        WITH inbound_vins AS (
            SELECT
                entity_id AS vin,
                MIN(timestamp) AS inbound_time,
                MAX(CASE WHEN action LIKE '%Quote%' OR action LIKE '%quote%'
                         THEN timestamp END) AS quote_time
            FROM `{LEDGER_TABLE}`
            WHERE action LIKE '%Inbound%' OR action LIKE '%inbound%'
            GROUP BY entity_id
        )
        SELECT vin, inbound_time
        FROM inbound_vins
        WHERE quote_time IS NULL
          AND inbound_time < @threshold
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("threshold", "TIMESTAMP", threshold_time),
        ]
    )

    try:
        results = list(client.query(query, job_config=job_config))
        for row in results:
            anomalies.append(Anomaly(
                check_name="THE GOLDEN RULE",
                severity="CRITICAL",
                description=f"VIN sitting Inbound >{golden_rule_minutes}min with no quote sent.",
                affected_entity="AUTOHAUS_SERVICES_LLC",
                affected_vin=str(row.get("vin", "UNKNOWN")),
                detected_at=datetime.now(timezone.utc).isoformat(),
            ))
        logger.info(f"[CHECK 1] Golden Rule: {len(anomalies)} violations found.")
    except Exception as e:
        logger.error(f"[CHECK 1] Golden Rule query failed: {e}")

    return anomalies


# ---------------------------------------------------------------------------
# Audit Check 2: ENTITY DRIFT
# ---------------------------------------------------------------------------
def check_entity_drift(client: bigquery.Client) -> list[Anomaly]:
    """
    Flag vehicles marked 'Green Tag' (ready for sale) that have no record
    of an intercompany invoice from AutoHaus Services to KAMM LLC.
    This catches vehicles being sold without proper compliance handoff.
    """
    anomalies = []

    query = f"""
        WITH green_tagged AS (
            SELECT entity_id AS vin
            FROM `{LEDGER_TABLE}`
            WHERE action LIKE '%Green Tag%' OR action LIKE '%green_tag%'
              OR action LIKE '%Frontline Ready%'
        ),
        invoiced_to_kamm AS (
            SELECT entity_id AS vin
            FROM `{LEDGER_TABLE}`
            WHERE (action LIKE '%Intercompany Invoice%' OR action LIKE '%KAMM%')
              AND (action LIKE '%Title%' OR action LIKE '%Compliance%'
                   OR action LIKE '%invoice%')
        )
        SELECT g.vin
        FROM green_tagged g
        LEFT JOIN invoiced_to_kamm i ON g.vin = i.vin
        WHERE i.vin IS NULL
    """

    try:
        results = list(client.query(query))
        for row in results:
            anomalies.append(Anomaly(
                check_name="ENTITY DRIFT",
                severity="WARNING",
                description="Green Tag vehicle has no intercompany invoice to KAMM for compliance.",
                affected_entity="KAMM_LLC",
                affected_vin=str(row.get("vin", "UNKNOWN")),
                detected_at=datetime.now(timezone.utc).isoformat(),
            ))
        logger.info(f"[CHECK 2] Entity Drift: {len(anomalies)} violations found.")
    except Exception as e:
        logger.error(f"[CHECK 2] Entity Drift query failed: {e}")

    return anomalies


# ---------------------------------------------------------------------------
# Audit Check 3: MARGIN ALERT (Transport Cost Ceiling)
# ---------------------------------------------------------------------------
def check_margin_alert(client: bigquery.Client) -> list[Anomaly]:
    """
    Flag any transport action in the ledger where the cost exceeds the
    CEO-mandated $500 threshold (sourced from Sovereign Memory SOP:
    "Never pay more than $500 for transport from Chicago to Des Moines").
    """
    anomalies = []

    transport_cost_ceiling = get_transport_cost_ceiling()

    query = f"""
        SELECT
            entity_id AS vin,
            action,
            CAST(JSON_VALUE(metadata, '$.cost') AS FLOAT64) AS transport_cost,
            timestamp
        FROM `{LEDGER_TABLE}`
        WHERE (action LIKE '%Transport%' OR action LIKE '%transport%'
               OR action LIKE '%Logistics%' OR action LIKE '%logistics%')
          AND JSON_VALUE(metadata, '$.cost') IS NOT NULL
          AND CAST(JSON_VALUE(metadata, '$.cost') AS FLOAT64) > @threshold
        ORDER BY timestamp DESC
        LIMIT 20
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("threshold", "FLOAT64", transport_cost_ceiling),
        ]
    )

    try:
        results = list(client.query(query, job_config=job_config))
        for row in results:
            cost = row.get("transport_cost", 0.0)
            anomalies.append(Anomaly(
                check_name="MARGIN ALERT",
                severity="WARNING",
                description=f"Transport cost ${cost:,.2f} exceeds ${transport_cost_ceiling} ceiling.",
                affected_entity="CARLUX_LLC",
                affected_vin=str(row.get("vin", "UNKNOWN")),
                affected_amount=float(cost),
                detected_at=datetime.now(timezone.utc).isoformat(),
            ))
        logger.info(f"[CHECK 3] Margin Alert: {len(anomalies)} violations found.")
    except Exception as e:
        logger.error(f"[CHECK 3] Margin Alert query failed: {e}")

    return anomalies


# ---------------------------------------------------------------------------
# Alert Dispatcher (Twilio SMS)
# ---------------------------------------------------------------------------
def dispatch_alerts(anomalies: list[Anomaly]):
    """
    Send a consolidated PRIORITY ALERT SMS to the CEO.

    MSO Purity: This function REPORTS only. It does NOT execute
    financial transactions or state changes. Remediation requires
    human-in-the-loop approval via an Approval JIT Plate.
    """
    if not anomalies:
        logger.info("[DISPATCH] No anomalies detected. System healthy. ✅")
        return

    # Build consolidated alert message
    header = (
        f"🛡️ AUTOHAUS SOVEREIGN GUARDIAN\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Anomalies Detected: {len(anomalies)}\n"
        f"{'─' * 30}\n"
    )

    alert_bodies = []
    for i, a in enumerate(anomalies, 1):
        alert_bodies.append(f"{i}. {a.to_alert_text()}")

    footer = (
        f"\n{'─' * 30}\n"
        f"⚠️ MSO PURITY: Report only. "
        f"No financial actions taken.\n"
        f"— Carbon LLC / C-OS v3.1"
    )

    full_message = header + "\n\n".join(alert_bodies) + footer

    # Truncate for SMS limit (1600 chars for Twilio)
    if len(full_message) > 1500:
        full_message = full_message[:1490] + "\n... [TRUNCATED]"

    # Attempt Twilio dispatch
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and CEO_PHONE_NUMBER:
        try:
            from twilio.rest import Client as TwilioClient

            twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            message = twilio_client.messages.create(
                body=full_message,
                from_=TWILIO_PHONE_NUMBER,
                to=CEO_PHONE_NUMBER,
            )
            logger.info(f"[DISPATCH] SMS sent to CEO: SID {message.sid}")
        except ImportError:
            logger.warning("[DISPATCH] Twilio SDK not installed. Printing alert to console.")
            print(full_message)
        except Exception as e:
            logger.error(f"[DISPATCH] Twilio SMS failed: {e}")
            print(full_message)
    else:
        logger.warning("[DISPATCH] Twilio credentials not configured. Console output only.")
        print(full_message)


# ---------------------------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------------------------
def run_audit():
    """
    Execute the full 3-check audit cycle.

    This function is the entry point for Cloud Run Jobs (cron) or manual runs.
    """
    logger.info("=" * 60)
    logger.info("  AUTOHAUS SOVEREIGN GUARDIAN — Audit Cycle Starting")
    logger.info("=" * 60)

    client = _get_bq_client()
    if not client:
        logger.critical("Cannot initialize BigQuery client. Aborting audit.")
        sys.exit(1)

    all_anomalies: list[Anomaly] = []

    # Run all 3 checks
    logger.info("[AUDIT] Running Check 1: The Golden Rule...")
    all_anomalies.extend(check_golden_rule(client))

    logger.info("[AUDIT] Running Check 2: Entity Drift...")
    all_anomalies.extend(check_entity_drift(client))

    logger.info("[AUDIT] Running Check 3: Margin Alert...")
    all_anomalies.extend(check_margin_alert(client))

    # Summary
    critical_count = sum(1 for a in all_anomalies if a.severity == "CRITICAL")
    warning_count = sum(1 for a in all_anomalies if a.severity == "WARNING")

    logger.info(
        f"[AUDIT COMPLETE] "
        f"Total: {len(all_anomalies)} | "
        f"Critical: {critical_count} | "
        f"Warnings: {warning_count}"
    )

    # Dispatch alerts
    dispatch_alerts(all_anomalies)

    logger.info("=" * 60)
    logger.info("  SOVEREIGN GUARDIAN — Audit Cycle Complete")
    logger.info("=" * 60)

    return all_anomalies


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_audit()
