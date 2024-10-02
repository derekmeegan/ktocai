from google.oauth2 import service_account
import gspread
import json
import os
import streamlit as st

service_account_info = json.loads(st.secrets["GOOGLE_SHEET_CREDENTIALS"])

credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
client = gspread.authorize(credentials)
sheet = client.open_by_key(st.secrets['GOOGLE_SHEET_ID'])