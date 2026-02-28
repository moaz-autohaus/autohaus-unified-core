from fastapi import APIRouter
from fastapi.responses import HTMLResponse

legal_router = APIRouter()

PRIVACY_POLICY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy - KAMM LLC</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        h1 { border-bottom: 2px solid #333; padding-bottom: 10px; }
        .clause { background: #f9f9f9; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0; font-weight: 500; }
        footer { margin-top: 50px; font-size: 0.8em; color: #777; }
    </style>
</head>
<body>
    <h1>Privacy Policy</h1>
    <p><strong>Effective Date:</strong> February 28, 2026</p>
    <p>KAMM LLC ("we," "us," or "our") operates the AutoHaus Unified Core system. We are committed to protecting the privacy of our users and customers.</p>
    
    <h2>1. Information We Collect</h2>
    <p>We collect mobile phone numbers and communication metadata solely for the purpose of operational notifications, compliance alerts, and providing requested services related to vehicle logistics and paperwork.</p>

    <h2>2. Disclosure of Information</h2>
    <div class="clause">
        No mobile information will be shared with third parties/affiliates for marketing/promotional purposes.
    </div>
    <p>All other the above categories exclude text messaging originator opt-in data and consent; this information will not be shared with any third parties.</p>

    <h2>3. Data Protection</h2>
    <p>We use industry-standard encryption and security protocols to ensure that your personal information is stored securely and protected from unauthorized access.</p>

    <h2>4. Contact Us</h2>
    <p>If you have any questions regarding this Privacy Policy, please contact us at support@autohausia.com.</p>

    <footer>
        &copy; 2026 KAMM LLC. All Rights Reserved.
    </footer>
</body>
</html>
"""

TERMS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms of Service - KAMM LLC</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; }
        h1 { border-bottom: 2px solid #333; padding-bottom: 10px; }
        .highlight { background: #fff3cd; padding: 2px 5px; border-radius: 3px; font-weight: bold; }
        footer { margin-top: 50px; font-size: 0.8em; color: #777; }
    </style>
</head>
<body>
    <h1>Terms and Conditions</h1>
    <p><strong>Effective Date:</strong> February 28, 2026</p>
    <p>By interacting with KAMM LLC mobile services, you agree to the following terms and conditions:</p>

    <h2>1. Program Description</h2>
    <p>KAMM LLC provides automated and manual alerts regarding vehicle processing, title status, and compliance requirements. These messages are sent to provide transparency in the vehicle acquisition and logistics pipeline.</p>

    <h2>2. Message Frequency</h2>
    <p>Message frequency varies based on user interaction and active logistics files.</p>

    <h2>3. Cost and Rates</h2>
    <p><span class="highlight">Message and data rates may apply.</span> Please contact your wireless provider for details regarding your specific plan's SMS rates.</p>

    <h2>4. Opt-Out and Help</h2>
    <p><span class="highlight">You can opt-out by texting STOP.</span> To stop receiving messages from KAMM LLC, reply with the keyword STOP. You will receive a final confirmation message, and no further messages will be sent unless you re-initiate contact.</p>
    <p>For assistance, reply with the keyword <strong>HELP</strong> or email support@autohausia.com.</p>

    <h2>5. Liability</h2>
    <p>Carriers are not liable for delayed or undelivered messages.</p>

    <footer>
        &copy; 2026 KAMM LLC. All Rights Reserved.
    </footer>
</body>
</html>
"""

@legal_router.get("/privacy", response_class=HTMLResponse)
async def get_privacy_policy():
    return PRIVACY_POLICY_HTML

@legal_router.get("/terms", response_class=HTMLResponse)
async def get_terms_of_service():
    return TERMS_HTML
