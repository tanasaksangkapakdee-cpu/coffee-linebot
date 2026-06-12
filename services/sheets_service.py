"""
Google Sheets Service
บันทึกออเดอร์และรายจ่ายลง Google Sheets
"""

import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_ORDERS = "ออเดอร์"
SHEET_EXPENSES = "รายจ่าย"

ORDER_HEADERS = ["วันที่", "สินค้า", "จำนวน", "ชื่อลูกค้า", "หมายเหตุ", "ข้อความต้นฉบับ"]
EXPENSE_HEADERS = ["วันที่", "รายการ", "จำนวนเงิน (บาท)", "แหล่งที่มา", "หมายเหตุ"]


class SheetsService:
    def __init__(self):
        self._client = None
        self._spreadsheet = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        if not creds_json:
            raise ValueError("ไม่พบ GOOGLE_CREDENTIALS_JSON")
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self):
        if self._spreadsheet is not None:
            return self._spreadsheet
        client = self._get_client()
        sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
        if not sheet_id:
            raise ValueError("ไม่พบ GOOGLE_SHEET_ID")
        self._spreadsheet = client.open_by_key(sheet_id)
        self._ensure_worksheets()
        return self._spreadsheet

    def _ensure_worksheets(self):
        existing = [ws.title for ws in self._spreadsheet.worksheets()]
        if SHEET_ORDERS not in existing:
            ws = self._spreadsheet.add_worksheet(SHEET_ORDERS, rows=1000, cols=10)
            ws.append_row(ORDER_HEADERS)
        if SHEET_EXPENSES not in existing:
            ws = self._spreadsheet.add_worksheet(SHEET_EXPENSES, rows=1000, cols=10)
            ws.append_row(EXPENSE_HEADERS)

    def add_order(self, parsed: dict) -> int:
        ws = self._get_spreadsheet().worksheet(SHEET_ORDERS)
        row = [
            parsed.get("date", ""),
            parsed.get("product", ""),
            parsed.get("quantity", ""),
            parsed.get("customer", ""),
            "",
            parsed.get("raw", ""),
        ]
        ws.append_row(row)
        return ws.row_count

    def get_current_month_orders(self) -> list:
        ws = self._get_spreadsheet().worksheet(SHEET_ORDERS)
        records = ws.get_all_records()
        month_prefix = datetime.now().strftime("%Y-%m")
        return [r for r in records if str(r.get("วันที่", "")).startswith(month_prefix)]

    def add_expense(self, parsed: dict) -> int:
        ws = self._get_spreadsheet().worksheet(SHEET_EXPENSES)
        row = [
            parsed.get("date", ""),
            parsed.get("description", ""),
            parsed.get("amount", 0),
            parsed.get("source", "ข้อความ"),
            parsed.get("raw", "")[:100],
        ]
        ws.append_row(row)
        return ws.row_count

    def get_current_month_expenses(self) -> list:
        ws = self._get_spreadsheet().worksheet(SHEET_EXPENSES)
        records = ws.get_all_records()
        month_prefix = datetime.now().strftime("%Y-%m")
        return [r for r in records if str(r.get("วันที่", "")).startswith(month_prefix)]
