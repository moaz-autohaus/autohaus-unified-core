#!/bin/bash

# AutoHaus Unified & Infrastructure: GitHub-to-Drive Mirroring (Protocol 4.5)
# This script bundles the local repository and mirrors it to the Master Data Drive.

PROJECT_DIR="/Users/moazsial/Documents/AutoHaus_CIL"
DRIVE_PATH="/Users/moazsial/My Drive/OBSERVATORY_ROOT/10_IT_AI_Core_Layer/01_Source_Mirroring/GitHub_CIL_Backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BUNDLE_NAME="autohaus_cil_mirror_${TIMESTAMP}.bundle"

echo "[MIRROR] Initiating Repository Bundle..."

# Create the bundle
git -C "$PROJECT_DIR" bundle create "${BUNDLE_NAME}" --all

if [ $? -eq 0 ]; then
    echo "[MIRROR] Bundle Created: ${BUNDLE_NAME}"
    
    # Ensure Drive destination exists (Simulated/Local check)
    mkdir -p "${DRIVE_PATH}"
    
    # Mirror to Drive
    cp "${BUNDLE_NAME}" "${DRIVE_PATH}/"
    
    if [ $? -eq 0 ]; then
        echo "[MIRROR] Transfer Complete. Master Data Drive Updated."
        # Cleanup local bundle
        rm "${BUNDLE_NAME}"
        
        # Log to Audit Registry (Simulated via localized echo for now)
        echo "[AUDIT] Mirror Trace | File: ${BUNDLE_NAME} | Status: Success | Time: ${TIMESTAMP}"
    else
        echo "[ERROR] Drive Transfer Failed."
        exit 1
    fi
else
    echo "[ERROR] Git Bundle Failed."
    exit 1
fi
