# SECRETS_MANIFEST.example.md

This document outlines the required environment variables and secrets for the AutoHaus Unified Core system. 
**NEVER commit actual secret values to this file.**

## 1. GCP Configuration
- **`GCP_SERVICE_ACCOUNT_JSON`**: The full JSON content of the GCP Service Account key with BigQuery and Drive permissions.
- **`GOOGLE_APPLICATION_CREDENTIALS`**: (Optional) Path to the service account JSON file if running locally.

## 2. AI & Intelligence
- **`GEMINI_API_KEY`**: API key for Google Gemini (Google AI Studio or Vertex AI).

## 3. Communication (Twilio)
- **`TWILIO_ACCOUNT_SID`**: Your Twilio Account SID.
- **`TWILIO_AUTH_TOKEN`**: Your Twilio Auth Token.
- **`TWILIO_PHONE_NUMBER`**: The primary CIL phone number (E.164 format, e.g., +13193007709).
- **`TWILIO_PHONE_PN_SID`**: (Optional) The SID for the primary phone number (starts with PN).

## 4. Integration & State
- **`GITHUB_PAT`**: GitHub Personal Access Token for repository synchronization.
- **`SESSION_SECRET`**: A cryptographically random string for securing FastAPI sessions.
- **`SECURITY_ACCESS_KEY_HASH`**: BCrypt hash of the external security access key for the `/api/security/` pipeline.
- **`PUBLIC_URL`**: The live Replit URL or production domain (required for Google Drive push webhooks).

## 5. Deployment
- **`GITHUB_WEBHOOK_SECRET`**: Secret for validating GitHub auto-deploy webhooks.
