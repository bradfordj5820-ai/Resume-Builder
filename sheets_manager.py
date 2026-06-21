import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Setup authentication
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# Open your spreadsheet by name
sheet = client.open("Job_Application_Tracker").sheet1

def log_job_application(company, position, status):
    """
    Status should be 'Applied' or 'Not a Fit'
    """
    row = [
        datetime.now().strftime('%Y-%m-%d'),
        company,
        position,
        status
    ]
    sheet.append_row(row)
    return True
