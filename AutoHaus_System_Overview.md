# AutoHaus Unified Data Core: System Overview

## Executive Summary
The AutoHaus Unified Data Core is a state-of-the-art intelligent infrastructure designed to automate the full lifecycle of a vehicle from auction acquisition to public retail listing. The system eliminates manual data entry, integrates rigorous quality control checks, and ensures our "Speed to Market" metrics are strictly enforced.

By leveraging Google Cloud's AI and data capabilities alongside a secure, gated web portal, the system requires minimal human overhead while guaranteeing high accuracy and accountability.

---

## The Workflow: From Auction to Showroom

1. **Document Intake (The Intelligence Layer)**
   When a vehicle is acquired at auction, the buyer simply drops the PDF receipt or invoice into an automated Google Drive folder. 
   The **Intelligence & Automation Layer** immediately detects the new file, extracts critical vehicle data (Make, Model, VIN, Purchase Price, and Trims), and securely stores it in our cloud data warehouse.

2. **The Staging Area (Governance Gatekeeper)**
   To protect the business from mispriced or incorrectly mapped AI extractions, the extracted data is automatically flagged as `Pending Governance`. It is stored safely but remains invisible to the public Web Interface.

3. **Audit & Promotion (Human-in-the-Loop)**
   The system administrator logs into a secure internal dashboard to view a stack of pending inventory alongside original PDFs. With one click of the "Approve" button, the vehicle is promoted.
   The **Audit & Validation Engine** intercepts this click, creates a permanent cryptographic record of who approved the data, and successfully changes the status of the vehicle to `LIVE`. 

4. **Public Display (The Web Interface)**
   Within milliseconds of human approval, the public-facing AutoHaus Web Interface instantly pulls the new vehicle into the available inventory display for customers to see.

---

## Core Operational Commitments

### 1. The 60-Minute Service Standard (SLA)
Time kills deals. Our architecture actively enforces a 60-minute Service Level Agreement (SLA) from the exact second an auction PDF is detected. 
The system runs continuous timers on all vehicles trapped in the Staging/Governance queue. If a vehicle approaches its 60-minute limit without being validated and promoted by a human operator, the system will trigger escalating alerts to ensure we never fall behind our "Speed to Market" goals.

### 2. The Single Source of Truth
Every system, agent, and website reads from the exact same master table. We call this the "Digital Twin." There are no conflicting spreadsheets. The vehicle representation in the structured cloud warehouse is the definitive record of the asset.

### 3. Absolute Security
The public website is completely decoupled from the data warehouse. It operates as a "Stateless" portal. A customer (or bad actor) on the website has absolutely zero physical path to edit, scrape, or manipulate the core database. All writing privileges are securely locked behind the internal Audit & Validation Engine, protecting the integrity of the business at all times.
