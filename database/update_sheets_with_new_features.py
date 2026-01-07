"""
Update Google Sheets with new features and data
This script adds new columns and updates existing data in the Cabin_N sheet
"""
import sys
import os
import io

# Fix Unicode encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gspread

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def get_credentials():
    """Get Google credentials"""
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    
    token_path = data_dir / "token_api.json"
    
    creds = None
    
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes=REQUIRED_SCOPES)
        except Exception:
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        
        if not creds or not creds.valid:
            candidates = [
                BASE_DIR / "data" / "credentials.json",
                BASE_DIR / "credentials.json",
            ]
            cred_file = next((p for p in candidates if p.exists()), None)
            if not cred_file:
                raise FileNotFoundError(
                    "Missing credentials.json. Put it in data/credentials.json or in the project root."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), scopes=REQUIRED_SCOPES)
            try:
                creds = flow.run_local_server(port=0, prompt="consent")
            except TypeError:
                creds = flow.run_local_server(port=0)
        
        token_path.write_text(creds.to_json(), encoding="utf-8")
    
    return creds

def update_sheets():
    """Update Google Sheets with new features"""
    print("=" * 60)
    print("Updating Google Sheets with New Features")
    print("=" * 60)
    
    creds = get_credentials()
    gc = gspread.authorize(creds)
    
    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        print("[ERROR] SHEET_ID not found in .env")
        return
    
    try:
        sh = gc.open_by_key(sheet_id.strip())
        ws = sh.worksheet("Cabin_N")  # Use the worksheet name from the URL
        
        # Get current headers
        headers = ws.row_values(1)
        print(f"\nCurrent headers: {headers}")
        
        # New columns to add (if not exist)
        new_columns = {
            'AD': 'description',  # Description of the cabin
            'AE': 'notes',  # Additional notes
            'AF': 'images_urls',  # Comma-separated image URLs
            'AG': 'business_facts',  # JSON string of business facts
            'AH': 'faq_count',  # Number of approved FAQs
            'AI': 'last_updated',  # Last update timestamp
        }
        
        # Check which columns need to be added
        columns_to_add = []
        for col_letter, col_name in new_columns.items():
            col_index = ord(col_letter) - ord('A') + 1
            if col_index > len(headers):
                columns_to_add.append((col_letter, col_name))
        
        if columns_to_add:
            print(f"\nAdding {len(columns_to_add)} new columns...")
            # Add headers for new columns
            for col_letter, col_name in columns_to_add:
                col_index = ord(col_letter) - ord('A') + 1
                ws.update_cell(1, col_index, col_name)
                print(f"  [OK] Added column {col_letter}: {col_name}")
        else:
            print("\n[OK] All columns already exist")
        
        # Update existing rows with new data format
        print("\nUpdating existing rows...")
        all_records = ws.get_all_records()
        
        for idx, record in enumerate(all_records, start=2):  # Start from row 2 (skip header)
            cabin_id = record.get('cabin_id', '')
            if not cabin_id:
                continue
            
            updates = {}
            
            # Ensure address fields are properly formatted
            street = record.get('Street name + number', '')
            city = record.get('City', '')
            postal = record.get('Postal code', '')
            
            if street or city:
                # Update address format if needed
                pass  # Address is already in separate columns
            
            # Add any other updates here
            
            if updates:
                for col_name, value in updates.items():
                    if col_name in headers:
                        col_index = headers.index(col_name) + 1
                        ws.update_cell(idx, col_index, value)
                        print(f"  [OK] Updated {cabin_id}: {col_name}")
        
        print("\n" + "=" * 60)
        print("Update complete!")
        print("=" * 60)
        print("\nNew columns added:")
        for col_letter, col_name in new_columns.items():
            print(f"  {col_letter}: {col_name}")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to update sheets: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    update_sheets()


