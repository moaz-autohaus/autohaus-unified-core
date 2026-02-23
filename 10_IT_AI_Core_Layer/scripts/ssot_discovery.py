from google.cloud import bigquery
import google.auth
import sys

def discover_ssot():
    print("[DISCOVERY] Initiating BigQuery SSOT Scan...")
    try:
        credentials, default_project = google.auth.default()
        print(f"[AUTH] Active Project: {default_project}")
        
        client = bigquery.Client(credentials=credentials)
        projects = [p.project_id for p in client.list_projects()]
        print(f"[AUTH] Accessible Projects: {projects}")
        
        target_dataset = "autohaus_cil"
        found = False
        
        for project in projects:
            print(f"[SCAN] Checking Project: {project}")
            p_client = bigquery.Client(credentials=credentials, project=project)
            
            # Check all common locations
            locations = [None, 'US', 'EU', 'us-central1', 'me-central1']
            for loc in locations:
                try:
                    datasets = p_client.list_datasets(location=loc)
                    for ds in datasets:
                        print(f"  - Found Dataset: {ds.dataset_id} in {loc or 'default'}")
                        if ds.dataset_id == target_dataset:
                            print(f"\n[SIGHT RESTORED] Found {target_dataset} in Project: {project} | Location: {loc or 'default'}")
                            print("[TABLES]:")
                            tables = p_client.list_tables(ds.reference)
                            for t in tables:
                                print(f"    - {t.table_id}")
                            found = True
                            return True
                except Exception:
                    continue
                    
        if not found:
            print(f"[ERROR] {target_dataset} not found in any accessible projects/locations.")
            return False
            
    except Exception as e:
        print(f"[CRITICAL] Discovery Failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = discover_ssot()
    if not success:
        sys.exit(1)
