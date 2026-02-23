import datetime
import uuid

class GovernanceException(Exception):
    """Protocol 4.5 Violation: Audit Context Missing or Invalid."""
    pass

class AuditWatcher:
    @staticmethod
    def verify_context(audit_context: dict):
        """
        Enforce Protocol 4.5: EVERY backend action must have an audit_context.
        Required keys: run_id, operator_id, timestamp
        """
        if not audit_context:
            raise GovernanceException("CRITICAL: Audit Context Missing. Operation Aborted.")
            
        required_keys = ['run_id', 'operator_id', 'timestamp']
        for key in required_keys:
            if key not in audit_context:
                raise GovernanceException(f"CRITICAL: Audit Context Incomplete. Missing '{key}'.")
        
        # Log to "GCP Observability Dashboard" (Simulated via localized logging for now)
        print(f"[AUDIT] Traceable Action | RunID: {audit_context['run_id']} | Operator: {audit_context['operator_id']} | Time: {audit_context['timestamp']}")
        return True

    @staticmethod
    def generate_id():
        return str(uuid.uuid4())
