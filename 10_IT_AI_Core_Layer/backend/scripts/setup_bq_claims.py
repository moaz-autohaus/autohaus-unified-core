import os
import sys
import json
from google.cloud import bigquery

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.bigquery_client import BigQueryClient
from models.claims import HumanAssertion, AssertionType

def setup_claims_tables():
    bq = BigQueryClient()
    client = bq.client
    if not client:
        print("Failed to initialize BigQuery client.")
        return

    query_extraction_claims = f"""
    CREATE TABLE IF NOT EXISTS `{bq.project_id}.{bq.dataset_id}.extraction_claims`
    (
      claim_id STRING NOT NULL,
      source STRING NOT NULL,
      extractor_identity STRING NOT NULL,
      input_reference STRING NOT NULL,
      entity_type STRING NOT NULL,
      target_entity_id STRING,
      target_field STRING NOT NULL,
      extracted_value STRING NOT NULL,
      confidence FLOAT64 NOT NULL,
      source_lineage JSON NOT NULL,
      status STRING NOT NULL DEFAULT 'PENDING',
      created_at TIMESTAMP NOT NULL,
      updated_at TIMESTAMP NOT NULL
    )
    PARTITION BY DATE(created_at)
    CLUSTER BY entity_type, status, target_entity_id;
    """

    query_human_assertions = f"""
    CREATE TABLE IF NOT EXISTS `{bq.project_id}.{bq.dataset_id}.human_assertions`
    (
      assertion_id STRING NOT NULL,
      asserted_by STRING NOT NULL,
      asserted_at TIMESTAMP NOT NULL,
      assertion_type STRING NOT NULL,
      content STRING NOT NULL,
      authority STRING NOT NULL DEFAULT 'HUMAN_ASSERTED',
      evidence_required STRING,
      verified_by_document STRING,
      evidence_structure JSON,
      corroboration_score FLOAT64 DEFAULT 0.0,
      corroboration_threshold FLOAT64 DEFAULT 0.75,
      supporting_documents JSON,
      verification_status STRING NOT NULL,
      downstream_dependents JSON,
      created_at TIMESTAMP NOT NULL,
      updated_at TIMESTAMP NOT NULL
    )
    PARTITION BY DATE(created_at)
    CLUSTER BY assertion_type, verification_status, asserted_by;
    """

    query_verification_view = f"""
    CREATE OR REPLACE VIEW `{bq.project_id}.{bq.dataset_id}.pending_verification_queue`
    AS
    SELECT
      assertion_id,
      asserted_by,
      assertion_type,
      content,
      evidence_required,
      evidence_structure,
      verification_status,
      corroboration_score,
      corroboration_threshold,
      downstream_dependents,
      created_at
    FROM 
      `{bq.project_id}.{bq.dataset_id}.human_assertions`
    WHERE 
      verification_status IN (
        'PENDING_VERIFICATION',
        'PENDING_CORROBORATION'
      )
    ORDER BY created_at ASC;
    """

    print("Running DDL for extraction_claims...")
    client.query(query_extraction_claims).result()
    print("Running DDL for human_assertions...")
    client.query(query_human_assertions).result()
    print("Running DDL for pending_verification_queue view...")
    client.query(query_verification_view).result()
    
    print("Tables and view provisioned successfully.")

    a1 = HumanAssertion.from_human_input(
        content="Carbon LLC and Next Gig LLC are 50/50 owners of KAMM LLC",
        assertion_type=AssertionType.VERIFIABLE_FACT,
        asserted_by="moaz_sial",
        evidence_required="KAMM LLC Operating Agreement"
    )
    a1.downstream_dependents = ["kamm_ownership_governance", "hitl_authority_routing"]

    a2 = HumanAssertion.from_human_input(
        content="AstroLogistics LLC held the original dealer license. KAMM LLC was formed as its successor for future vehicle purchases",
        assertion_type=AssertionType.CONTEXT,
        asserted_by="moaz_sial",
        evidence_structure=[
            "KAMM LLC formation documents",
            "Iowa dealer license under KAMM LLC",
            "AstroLogistics LLC dealer license status",
            "First vehicle titled under KAMM LLC"
        ]
    )
    a2.downstream_dependents = ["entity_transition_logic", "dealer_license_boundary"]

    a3 = HumanAssertion.from_human_input(
        content="Auto-Owners TPP proposal KammLLCTPP-6041894 has been bound as active coverage. Binding confirmed by owner but binding document not yet located.",
        assertion_type=AssertionType.VERIFIABLE_FACT,
        asserted_by="moaz_sial",
        evidence_required="Auto-Owners bound policy declarations page"
    )
    a3.downstream_dependents = ["insurance_boundary_logic", "entity_coverage_validation"]

    assertions = [a1, a2, a3]
    
    existing_q = f"SELECT content FROM `{bq.project_id}.{bq.dataset_id}.human_assertions`"
    try:
        existing_rows = [row.content for row in client.query(existing_q).result()]
    except Exception as e:
        existing_rows = []
        print(f"Could not fetch existing assertions (this is fine if it is the first run): {e}")

    to_insert = []
    for a in assertions:
        if a.content not in existing_rows:
            row = json.loads(a.model_dump_json())
            # Convert python lists/dicts to json strings for BQ JSON columns
            for json_field in ['evidence_structure', 'supporting_documents', 'downstream_dependents']:
                if row.get(json_field) is not None:
                    row[json_field] = json.dumps(row[json_field])
            to_insert.append(row)

    if to_insert:
        errors = client.insert_rows_json(f"{bq.project_id}.{bq.dataset_id}.human_assertions", to_insert)
        if errors:
            print(f"Errors occurred during seeding: {errors}")
        else:
            print(f"Successfully seeded {len(to_insert)} assertions.")
    else:
        print("Assertions already seeded or no new assertions to seed.")

if __name__ == "__main__":
    setup_claims_tables()
