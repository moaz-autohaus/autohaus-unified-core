# AUTOHAUS ECOSYSTEM VERSION 3.1 — INTEGRATED INTERFACE SPECIFICATION

## 1. Core Concept: The Conversational Operating System (C-OS)
The classic trap in software development is building "the everything app"—a single UI crammed with static navigation menus for Sales, Service, HR, Accounting, and Marketing. This creates brittle, slow, and confusing user interfaces.

Version 3.1 introduces a massive evolution: The **Conversational Operating System (C-OS).**

The AutoHaus interface is defined as a **Just-In-Time (JIT) Interface**. It functions as a "clean slate" where the **Digital Chief of Staff** (the Chatbot/Global Orchestrator) acts as the primary driver, dynamically generating and mounting specialized **UI Plates** based on real-time human intent and backend event triggers.

---

## 2. Interaction Hierarchy

| Layer | Responsibility | Primary Interactions |
| --- | --- | --- |
| **Human User** | Strategy & Intent | Conversational commands, one-click approvals, and data refinement. |
| **Chatbot (The Hub)** | Orchestration & Translation | Refines intent, suggests next steps, and coordinates between the UI and CIL. |
| **CIL (The Brain)** | Processing & Logic | Gemini-powered extraction, BigQuery SQL execution, and specialized agent routing. |
| **UI (The Spoke)** | Visualization & Action | Displays JIT Plates (financials, 3D twins, ledgers) as requested by the Chatbot. |

---

## 3. The "JIT Dashboard" Workflow

The Unified Command Center (UCC) does not present a static dashboard; it builds the interface around the current conversation.

*   **Human Intent**: Ahsin (CEO) issues a command via voice, mobile app, or browser:
    *   *Example*: "Show me the financials for Service Lane A, but exclude car detailing."
*   **Chatbot Coordination**: The **Global Orchestrator** receives the command and coordinates with the **Finance Agent**.
*   **Refinement**: The bot identifies potential ambiguity (e.g., "Exclude detailing from KAMM recon or retail service?") and asks for clarification.
*   **Logic Execution**: Once confirmed, the Central Intelligence Layer (CIL) executes a specific BigQuery/Sheets query to generate the curated report.
*   **UI Presentation**: The Chatbot sends a **JSON Payload** to the frontend, which instantly mounts the **Financial Plate** template, hydrated with the newly generated data directly in or alongside the chat stream.

---

## 4. Semantic Integration & Ontology Management

The Chatbot uses the CIL to link unstructured human commands to structured business assets.

*   **Contextual Linking**: The user can upload a file and issue a command such as "Add this to the blue BMW M4 that got tints last week".
*   **Ontology Resolution**: The **Digital Twin Agent** cross-references the description ("blue BMW M4") and historical context ("tints last week") with the **Identity Resolution Engine** to locate the exact VIN.
*   **Automated Filing**: The CIL then automatically renames the file according to the ecosystem standard (`ENTITY_TYPE_YYYYMMDD_DESCRIPTION`) and moves it to the correct folder in the **Google Drive Architecture** (e.g., `05_Cosmetics_AstroLogistics/M4_VIN_1234/`).

---

## 5. Proactive Discovery & Issue Resolution

The Chatbot functions as an autonomous monitor for the ecosystem.

*   **Anomaly Detection**: By analyzing centralized data, the **Compliance Agent** may detect a missing document (e.g., "No damage disclosure for VIN X") and proactively alert the CEO via the conversational window.
*   **Strategy Refinement**: The **Pricing & Inventory Optimization Agent** can detect market shifts and suggest proactive adjustments directly in the chat: "Market price for 2018 Camry is dropping; suggest price adjustment on Lot Unit 102".

---

## 6. Technical Implementation Pillars

1.  **Universal Remote**: The same "Brain" (CIL) is accessible via Replit-hosted browser dashboards (combining Chat with rich JIT Plates), mobile apps, and Twilio-based text messaging (text-only fallbacks).
2.  **Conversational Memory Vault**: Strategic commands and personal preferences are stored in an isolated vector memory container, separate from operational data, ensuring long-term context without transactional database clutter.
3.  **Entity Permissions**: While the CEO's **Sovereign Bot** has global access, staff-specific bots (for Lane A or Lane B) operate through restricted "lenses" defined by their role in **Carbon LLC** (managed via `business_ontology.json`).

---

*This document officially replaces the static dashboard "Hub-and-Spoke" model with the autonomous v3.1 Conversational Operating System (C-OS) paradigm.*
