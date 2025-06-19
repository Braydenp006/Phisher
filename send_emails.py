import csv
import smtplib
import uuid
import os
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def generate_tracking_link(email):
    encoded_email = urllib.parse.quote(email)
    return f"https://verify.newleafpayroll.ca/track?uid={encoded_email}"

SMTP_SERVER = "smtp.sendgrid.net"
SMTP_PORT = 587
SMTP_USER = "apikey"  # DO NOT CHANGE
SMTP_PASSWORD = os.environ.get("SENDGRID_KEY")
FROM_ADDRESS = "payroll@newleafpayroll.ca"
TRACKING_BASE_URL = "https://verify.newleafpayroll.ca/track?uid="  # Change to your IP or ngrok URL



with open("email_template.html", "r") as f:
    html_template = f.read()

with open("recipients.csv", newline="") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        recipient_email = row["email"]
        tracking_url = generate_tracking_link(recipient_email)  # Use the function correctly
        
        personalized_html = html_template.replace("{{TRACKING_URL}}", tracking_url)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Important: Payroll Discrepancy Notification"
        msg["From"] = FROM_ADDRESS
        msg["To"] = recipient_email
        msg["X-MS-Exchange-Organization-PhishSimulation"] = "true"

        part = MIMEText(personalized_html, "html")
        msg.attach(part)

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(FROM_ADDRESS, recipient_email, msg.as_string())
            print(f"Sent to {recipient_email}")
        except Exception as e:
            print(f"Failed to send to {recipient_email}: {e}")
