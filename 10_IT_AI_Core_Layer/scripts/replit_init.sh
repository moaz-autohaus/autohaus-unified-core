#!/bin/bash
set -e

echo "========================================================="
echo "INITIALIZING AUTOHAUS UNIFIED DATA CORE [CIL BRIDGE]"
echo "========================================================="

# 1. Dependency Installation
echo "[SYSTEM] Resolving Python dependencies..."
pip install -r backend/requirements.txt

# 2. Scope & Environment Pathing
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# 3. Governance Check: Replit Secret Resolution
echo "[SECURITY] Verifying CIL Entity Identity..."
mkdir -p auth

if [ -z "$SERVICE_ACCOUNT_JSON" ]; then
    echo "[CRITICAL] SERVICE_ACCOUNT_JSON secret is missing from Replit Environment!"
    echo "Governance Rule: The Unified Build cannot boot without Carbon LLC authorization."
    echo "Result: Backend Halt. Reversal Protocol 4.5 will trigger on the frontend."
    exit 1
else
    # Hydrate the expected file for the Python SDK
    echo "$SERVICE_ACCOUNT_JSON" > auth/service_account.json
    echo "[SECURITY] Service Account contextualized for autohaus-infrastructure in auth/ directory."
fi

# 4. Boot Core Bridge
echo "[SYSTEM] Booting Unified Data Bridge..."
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
