from flask import Flask, request, send_file, render_template_string
import csv
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

LOG_FILE = "logs/clicks.csv"
LANDING_PAGE = "landing_page.html"
GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU" 
# Google Sheets logging using environment variable
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

def append_to_google_sheet(row):
    sheet.append_row(row)

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    timestamp = datetime.now().isoformat()
    ip = request.remote_addr
    user_agent = request.user_agent.string

    row = [timestamp, uid, ip, user_agent]

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)

    append_to_google_sheet(row)

    return send_file(LANDING_PAGE)

@app.route("/")
def index():
    return send_file(LANDING_PAGE)

@app.route("/done")
def done():
    return render_template_string("""
        <html>
        <head>
            <title>You've Been Phished!</title>
            <style>
                body {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    background-color: #f2f2f2;
                    font-family: Arial, sans-serif;
                    text-align: center;
                }
                .message {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0px 0px 15px rgba(0, 0, 0, 0.1);
                }
                .emoji {
                    font-size: 64px;
                }
            </style>
        </head>
        <body>
            <div class="message">
                <div class="emoji">😄</div>
                <h1>You have Been Scammed!</h1>
                <p>Fortunately, it was just a test by your own company to raise awareness. Stay sharp!</p>
            </div>
        </body>
        </html>
    """)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
