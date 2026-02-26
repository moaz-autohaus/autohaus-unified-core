
import csv
import os
import sys
import re
from datetime import datetime
from collections import defaultdict

ALLOWED_ENTITY_TYPES = {"MSO", "DEALER", "SERVICE", "COSMETIC", "FLEET", "LOGISTICS", "REAL_ESTATE"}
ALLOWED_ACCESS_LEVELS = {"SOVEREIGN", "STANDARD", "FIELD"}
ALLOWED_VENDOR_TYPES = {"AUCTION_HOUSE", "TRANSPORT_CARRIER", "PARTS_SUPPLIER", "FINANCE_COMPANY", "INSURANCE_CARRIER", "OTHER"}
ALLOWED_INVENTORY_STATUS = {"RECON", "AVAILABLE", "SERVICE", "COSMETIC", "SOLD", "IN_TRANSIT"}
ALLOWED_RELATIONSHIP_TYPES = {"CEO_OF", "OPERATES_AT", "HELD_BY", "INSURED_BY", "AUCTION_VENDOR_FOR", "TRANSPORT_VENDOR_FOR", "EMPLOYED_BY", "MANAGES", "ASSIGNED_TO"}
ALLOWED_RELATIONSHIP_STATUS = {"ACTIVE", "INACTIVE"}

class Tier0Validator:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.errors = []
        self.entity_names = set()
        self.personnel_names = set()
        self.vendor_names = set()
        self.vin_names = set()
        
        self.files = {
            'entities': 'tier0_entities.csv',
            'personnel': 'tier0_personnel.csv',
            'vendors': 'tier0_vendors.csv',
            'inventory': 'tier0_inventory.csv',
            'insurance': 'tier0_insurance.csv',
            'relationships': 'tier0_relationships.csv'
        }

    def log_error(self, layer, row_idx, field, reason):
        self.errors.append(f"LAYER {layer} | Row {row_idx} | Field '{field}' | Error: {reason}")

    def validate_entities(self):
        path = os.path.join(self.folder_path, self.files['entities'])
        if not os.path.exists(path):
            self.errors.append(f"Missing required file: {self.files['entities']}")
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for idx, row in enumerate(reader, start=2):
                # Required fields
                req = ['legal_name', 'role', 'entity_type', 'insurance_carrier', 'insurance_policy_type', 'operational_status']
                for field in req:
                    if not row.get(field):
                        self.log_error(1, idx, field, "Missing required field")
                
                name = row.get('legal_name', '').strip()
                if name in self.entity_names:
                    self.log_error(1, idx, 'legal_name', f"Duplicate entity name: {name}")
                if name:
                    self.entity_names.add(name)
                
                e_type = row.get('entity_type', '').strip()
                if e_type and e_type not in ALLOWED_ENTITY_TYPES:
                    self.log_error(1, idx, 'entity_type', f"Invalid type. Must be one of {ALLOWED_ENTITY_TYPES}")
                
                count += 1
            print(f"LAYER 1 (Entities): {count} processed")
        return True

    def validate_personnel(self):
        path = os.path.join(self.folder_path, self.files['personnel'])
        if not os.path.exists(path):
            self.errors.append(f"Missing required file: {self.files['personnel']}")
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for idx, row in enumerate(reader, start=2):
                req = ['full_name', 'role', 'access_level', 'primary_entity']
                for field in req:
                    if not row.get(field):
                        self.log_error(2, idx, field, "Missing required field")
                
                name = row.get('full_name', '').strip()
                if name: self.personnel_names.add(name)
                
                access = row.get('access_level', '').strip()
                if access and access not in ALLOWED_ACCESS_LEVELS:
                    self.log_error(2, idx, 'access_level', f"Invalid level. Must be one of {ALLOWED_ACCESS_LEVELS}")
                
                entity = row.get('primary_entity', '').strip()
                if entity and entity not in self.entity_names:
                    self.log_error(2, idx, 'primary_entity', f"Entity '{entity}' not found in entities list")
                
                # Secondary entities validation
                secondary = row.get('secondary_entities', '').strip()
                if secondary:
                    for s_ent in [s.strip() for s in secondary.split(',')]:
                        if s_ent and s_ent not in self.entity_names:
                            self.log_error(2, idx, 'secondary_entities', f"Secondary entity '{s_ent}' not found in entities list")
                
                count += 1
            print(f"LAYER 2 (Personnel): {count} processed")
        return True

    def validate_vendors(self):
        path = os.path.join(self.folder_path, self.files['vendors'])
        if not os.path.exists(path):
            self.errors.append(f"Missing required file: {self.files['vendors']}")
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for idx, row in enumerate(reader, start=2):
                req = ['canonical_name', 'vendor_type']
                for field in req:
                    if not row.get(field):
                        self.log_error(3, idx, field, "Missing required field")
                
                name = row.get('canonical_name', '').strip()
                if name in self.vendor_names:
                    self.log_error(3, idx, 'canonical_name', f"Duplicate vendor name: {name}")
                if name:
                    self.vendor_names.add(name)
                
                v_type = row.get('vendor_type', '').strip()
                if v_type and v_type not in ALLOWED_VENDOR_TYPES:
                    self.log_error(3, idx, 'vendor_type', f"Invalid type. Must be one of {ALLOWED_VENDOR_TYPES}")
                
                count += 1
            print(f"LAYER 3 (Vendors): {count} processed")
        return True

    def validate_inventory(self):
        path = os.path.join(self.folder_path, self.files['inventory'])
        if not os.path.exists(path):
            self.errors.append(f"Missing required file: {self.files['inventory']}")
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for idx, row in enumerate(reader, start=2):
                req = ['vin', 'year', 'make', 'model', 'purchase_price', 'current_entity', 'current_status']
                for field in req:
                    if not row.get(field):
                        self.log_error(4, idx, field, "Missing required field")
                
                vin = row.get('vin', '').strip()
                if vin:
                    if not re.match(r'^[A-Z0-9]{17}$', vin):
                        self.log_error(4, idx, 'vin', f"Invalid VIN format. Must be 17 alphanumeric chars: {vin}")
                    if vin in self.vin_names:
                        self.log_error(4, idx, 'vin', f"Duplicate VIN: {vin}")
                    self.vin_names.add(vin)
                
                year = row.get('year', '').strip()
                if year and not (year.isdigit() and len(year) == 4):
                    self.log_error(4, idx, 'year', f"Invalid year: {year}")
                
                price = row.get('purchase_price', '').strip()
                try:
                    if price: float(price)
                except ValueError:
                    self.log_error(4, idx, 'purchase_price', f"Must be numeric: {price}")
                
                entity = row.get('current_entity', '').strip()
                if entity and entity not in self.entity_names:
                    self.log_error(4, idx, 'current_entity', f"Entity '{entity}' not found in entities list")
                
                status = row.get('current_status', '').strip()
                if status and status not in ALLOWED_INVENTORY_STATUS:
                    self.log_error(4, idx, 'current_status', f"Invalid status. Must be one of {ALLOWED_INVENTORY_STATUS}")
                
                source = row.get('purchase_source', '').strip()
                if source and source not in self.vendor_names:
                    self.log_error(4, idx, 'purchase_source', f"Vendor '{source}' not found in vendors list")
                
                count += 1
            print(f"LAYER 4 (Inventory): {count} processed")
        return True

    def validate_insurance(self):
        path = os.path.join(self.folder_path, self.files['insurance'])
        if not os.path.exists(path):
            self.errors.append(f"Missing required file: {self.files['insurance']}")
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for idx, row in enumerate(reader, start=2):
                req = ['policy_number', 'carrier', 'coverage_type', 'covered_entity', 'effective_date', 'expiration_date']
                for field in req:
                    if not row.get(field):
                        self.log_error(5, idx, field, "Missing required field")
                
                entity = row.get('covered_entity', '').strip()
                if entity and entity not in self.entity_names:
                    self.log_error(5, idx, 'covered_entity', f"Entity '{entity}' not found in entities list")
                
                # Date logic
                eff = row.get('effective_date', '').strip()
                exp = row.get('expiration_date', '').strip()
                try:
                    deff = datetime.strptime(eff, '%Y-%m-%d')
                    dexp = datetime.strptime(exp, '%Y-%m-%d')
                    if dexp < deff:
                        self.log_error(5, idx, 'expiration_date', f"Expiration date {exp} is before effective date {eff}")
                except ValueError:
                    if eff or exp:
                        self.log_error(5, idx, 'dates', "Dates must be in YYYY-MM-DD format")
                
                count += 1
            print(f"LAYER 5 (Insurance): {count} processed")
        return True

    def validate_relationships(self):
        path = os.path.join(self.folder_path, self.files['relationships'])
        if not os.path.exists(path):
            self.errors.append(f"Missing required file: {self.files['relationships']}")
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            all_known_names = self.entity_names | self.personnel_names | self.vendor_names | self.vin_names
            
            for idx, row in enumerate(reader, start=2):
                req = ['entity_a', 'relationship_type', 'entity_b', 'status']
                for field in req:
                    if not row.get(field):
                        self.log_error(6, idx, field, "Missing required field")
                
                rel = row.get('relationship_type', '').strip()
                if rel and rel not in ALLOWED_RELATIONSHIP_TYPES:
                    self.log_error(6, idx, 'relationship_type', f"Invalid type. Must be one of {ALLOWED_RELATIONSHIP_TYPES}")
                
                stat = row.get('status', '').strip()
                if stat and stat not in ALLOWED_RELATIONSHIP_STATUS:
                    self.log_error(6, idx, 'status', "Must be ACTIVE or INACTIVE")
                
                ent_a = row.get('entity_a', '').strip()
                ent_b = row.get('entity_b', '').strip()
                
                if ent_a and ent_a not in all_known_names:
                    self.log_error(6, idx, 'entity_a', f"Source entity '{ent_a}' not found in any master list")
                if ent_b and ent_b not in all_known_names:
                    self.log_error(6, idx, 'entity_b', f"Target entity '{ent_b}' not found in any master list")
                
                count += 1
            print(f"LAYER 6 (Relationships): {count} processed")
        return True

    def run(self):
        print(f"--- Tier 0 Sheet Validation Starting (Source: {self.folder_path}) ---")
        
        # Sequentially collect known names
        success = self.validate_entities()
        if success: success = self.validate_personnel()
        if success: success = self.validate_vendors()
        if success: success = self.validate_inventory()
        if success: success = self.validate_insurance()
        if success: success = self.validate_relationships()
        
        if self.errors:
            print("\n❌ VALIDATION FAILED!")
            for err in self.errors:
                print(f"  {err}")
            sys.exit(1)
        else:
            print("\n✅ VALIDATION PASSED — ready for seed_tier0.py")
            # Create a hidden flag file
            with open(os.path.join(self.folder_path, ".validated"), "w") as f:
                f.write(datetime.now().isoformat())
            sys.exit(0)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    validator = Tier0Validator(path)
    validator.run()
