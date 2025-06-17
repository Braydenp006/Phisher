import csv
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.sendgrid.net"
SMTP_PORT = 587
SMTP_USER = "apikey"  # DO NOT CHANGE
SMTP_PASSWORD = "YOUR_SENDGRID_API_KEY"  # Replace this with your actual API key
FROM_ADDRESS = "payroll@newleafpayroll.ca"
TRACKING_BASE_URL = "http://192.168.1.100:8000/track?uid="  # Change to your IP or ngrok URL

with open("email_template.html", "r") as f:
    html_template = f.read()

with open("recipients.csv", newline="") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        uid = str(uuid.uuid4())
        tracking_url = f"{TRACKING_BASE_URL}{uid}"
        personalized_html = html_template.replace("{{TRACKING_URL}}", tracking_url)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Important: Payroll Discrepancy Notification"
        msg["From"] = FROM_ADDRESS
        msg["To"] = row["email"]

        part = MIMEText(personalized_html, "html")
        msg.attach(part)

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(FROM_ADDRESS, row["email"], msg.as_string())
            print(f"Sent to {row['email']}")
        except Exception as e:
            print(f"Failed to send to {row['email']}: {e}")