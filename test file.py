import os
import ssl
import certifi
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# ✅ Patch SSL globally to use certifi's trusted CA bundle
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context

# Make sure you set these environment variables in PowerShell first:
# $env:SMTP_FROM="your_email@example.com"
# $env:SENDGRID_API_KEY="your_sendgrid_api_key"

FROM_EMAIL = os.environ.get("SMTP_FROM")
API_KEY = os.environ.get("SENDGRID_API_KEY")

if not FROM_EMAIL or not API_KEY:
    raise Exception("❌ Please set the SMTP_FROM and SENDGRID_API_KEY environment variables in PowerShell!")

message = Mail(
    from_email=FROM_EMAIL,
    to_emails="aryansonsurkar87@gmail.com",
    subject="Draco Test Email",
    plain_text_content="If you got this, SendGrid SSL is fixed!"
)

try:
    sg = SendGridAPIClient(API_KEY)
    response = sg.send(message)
    print("✅ Email sent successfully! Status:", response.status_code)
except Exception as e:
    print("❌ Error sending email:", e)