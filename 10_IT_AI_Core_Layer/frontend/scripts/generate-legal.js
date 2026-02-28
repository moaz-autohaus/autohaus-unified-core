import { writeFileSync } from 'fs';

const privacy = `<!DOCTYPE html><html><head><title>Privacy Policy - KAMM LLC</title></head><body>
<h1>Privacy Policy</h1>
<p>KAMM LLC operates an internal business management system. No mobile information will be shared with third parties/affiliates for marketing/promotional purposes. All other categories exclude text messaging originator opt-in data and consent; this information will not be shared with any third parties.</p>
</body></html>`;

const terms = `<!DOCTYPE html><html><head><title>Terms of Service - KAMM LLC</title></head><body>
<h1>Terms of Service</h1>
<p>By using this service you agree to receive SMS messages for operational purposes. Message and data rates may apply. Message frequency varies. Text STOP to opt out. Text HELP for help.</p>
</body></html>`;

writeFileSync('../../dist/privacy.html', privacy);
writeFileSync('../../dist/terms.html', terms);
console.log('Legal pages generated.');
