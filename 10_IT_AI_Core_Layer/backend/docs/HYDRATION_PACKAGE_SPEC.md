# HYDRATION PACKAGE SPECIFICATION

This document outlines the field-level definition of the structured Context Package that the Hydration Engine will assemble prior to firing any intelligent nodes (Phase 1, Task 1.3). It represents the contract between structural data normalization and the AI processing layers.

## 1. Resolved Entities (`resolved_entities`)
* **Source:** `master_person_graph`, `inventory_master`, `logistics_jobs`
* **Query Pattern:** Probabilistic match (via `IdentityEngine` or direct ID lookup) derived from normalized input identifiers (email, phone, VIN, RO, or Job ID).
* **Required:** Optional (an input may relate to a new, unknown entity).
* **Empty/Fallback State:** `[]` (Empty list if no entities match).
* **Downstream Consumer:** 
  * `router_agent.py` to evaluate whether the query is inquiring about an existing object.
  * `gmail_intel.py` and `attachment_processor.py` to attach extracted claims to a pre-existing Master ID.
  * `iea_agent.py` to recognize if missing context is already universally known.

## 2. Active Open Questions (`open_questions`)
* **Source:** BigQuery `open_questions` table.
* **Query Pattern:** `SELECT * FROM autohaus_cil.open_questions WHERE target_id IN (@resolved_entity_ids) AND status = 'OPEN'`
* **Required:** Optional.
* **Empty/Fallback State:** `[]`
* **Downstream Consumer:**
  * `governance_agent.py` to identify if the current input is a direct answer resolving a pending `ASK` block.
  * `iea_agent.py` to avoid raising redundant clarifying questions about the same entity.

## 3. Associated Anomaly Flags (`recent_anomalies`)
* **Source:** BigQuery `drift_sweep_results` and `system_audit_ledger`
* **Query Pattern:** Lookup using `entity_id` constraints where `resolved = FALSE` or within a policy-defined time horizon (e.g., past 48 hours for logistics delays).
* **Required:** Optional.
* **Empty/Fallback State:** `[]`
* **Downstream Consumer:**
  * `router_agent.py` to elevate the internal priority of the routed payload.
  * `attention_dispatcher.py` to contextualize the urgency score if an interaction triggers on an actively anomalous entity.

## 4. Operational Policies (`applicable_policies`)
* **Source:** `policy_engine.py` (which caches from BigQuery `policy_registry`).
* **Query Pattern:** Loaded based on input domain (e.g., if input relates to logistics, load `LOGISTICS` category policies).
* **Required:** Required.
* **Empty/Fallback State:** `{}` (Empty dictionary if no specific policies override global defaults).
* **Downstream Consumer:**
  * `hitl_service.py` to determine if proposed claims exceed auto-approve limits.
  * `attention_dispatcher.py` to determine the routing threshold (e.g., SMS vs WebSocket).
  * *Future:* All intelligent nodes to govern `ASK` vs `PROCEED` thresholds.

## 5. Prior Claims & Conclusions (`recent_claims`)
* **Source:** BigQuery `extraction_claims` (Phase 2 task).
* **Query Pattern:** `SELECT * FROM autohaus_cil.extraction_claims WHERE target_entity_id IN (@resolved_entity_ids) ORDER BY created_at DESC LIMIT X`
* **Required:** Optional.
* **Empty/Fallback State:** `[]`
* **Downstream Consumer:**
  * `conflict_detector.py` to evaluate against active assertions, preventing silent logic overwrites.
  * `gmail_intel.py` to prevent redundant extraction conclusions on duplicate or chained email threads.

## 6. Active HITL Proposals (`active_hitl_proposals`)
* **Source:** BigQuery `hitl_events`.
* **Query Pattern:** `SELECT * FROM autohaus_cil.hitl_events WHERE target_id IN (@resolved_entity_ids) AND status = 'PROPOSED'`
* **Required:** Optional.
* **Empty/Fallback State:** `[]`
* **Downstream Consumer:**
  * `iea_agent.py` / `governance_agent.py` to understand if an action the human is attempting is already staging hardware approval by another actor.

## 7. Pending Human Assertions (`pending_assertions`)
* **Source:** BigQuery `human_assertions` table (Phase 2).
* **Query Pattern:** `WHERE target_entity_id IN (@resolved_entity_ids) AND verification_status IN ('PENDING_VERIFICATION', 'PENDING_CORROBORATION')`
* **Required:** Optional.
* **Empty/Fallback State:** `[]` (Log as INFO if empty: "human_assertions table pending Phase 2").
* **Downstream Consumer:**
  * `conflict_detector.py` (Phase 2) will check new document claims against this list on every ingestion to assess if documentary evidence corroborates or validates an unverified human fact.
