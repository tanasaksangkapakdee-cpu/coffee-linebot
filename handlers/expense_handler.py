"""
Expense Handler - จดรายจ่าย
รองรับ: ข้อความอิสระ + รูปสลิป/ใบเสร็จ
"""

import re
import io
import os
import json
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from services.sheets_service import SheetsService

TZ_BANGKOK = timezone(timedelta(hours=7))

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")


def _get_drive_service():
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    return build("drive", "v3", credentials=creds)


def _save_image_to_drive(image_bytes: bytes, filename: str) -> str:
    """Save image to Google Drive, return file URL or empty string on failure."""
    try:
        service = _get_drive_service()
        meta = {"name": filename}
        if DRIVE_FOLDER_ID:
            meta["parents"] = [DRIVE_FOLDER_ID]
        media = MediaIoBaseUpload(io.BytesIO(bytes(image_bytes)), mimetype="image/jpeg")
        f = service.files().create(body=meta, media_body=media, fields="id").execute()
        file_id = f.get("id", "")
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception as e:
        return ""


def handle_expense(text: str, sheets: SheetsService, image_url: str = None) -> str:
    parsed = _parse_expense_text(text)
    if parsed["amount"] is None:
        return "ไม่พบจำนวนเงิน ลองพิมพ์แบบนี้:\n  จ่าย 3500 ค่าเมล็ดกาแฟ"
    try:
        if image_url:
            parsed["source"] = image_url
        row_num = sheets.add_expense(parsed)
        amount_fmt = f"{parsed['amount']:,.0f}" if isinstance(parsed['amount'], (int, float)) else str(parsed['amount'])
        reply = (
            f"✅ บันทึกรายจ่ายแล้ว (แถว {row_num})\n"
            f"📝 รายการ: {parsed['description']}\n"
            f"💰 จำนวน: {amount_fmt} บาท\n"
            f"📅 วันที่: {parsed['date']}"
        )
        if image_url:
            reply += f"\n🖼️ รูปภาพ: {image_url}"
        return reply
    except Exception as e:
        return f"บันทึกไม่สำเร็จ: {str(e)}"


def _parse_expense_text(text: str) -> dict:
    text = text.strip()
    for kw in ["จ่าย", "expense", "รายจ่าย", "บันทึกรายจ่าย", "ค่าใช้จ่าย"]:
        text = re.sub(rf"(?i)^{kw}\s*", "", text, count=1)

    amount = None
    description = text.strip()

    m = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:บาท|baht|฿)?", text, re.IGNORECASE)
    if m:
        raw = m.group(1).replace(",", "")
        try:
            amount = float(raw)
        except ValueError:
            pass
        description = (text[:m.start()] + text[m.end():]).strip().strip("ค่า").strip() or "รายจ่าย"

    date_str = datetime.now(TZ_BANGKOK).strftime("%Y-%m-%d %H:%M")
    return {
        "description": description or "รายจ่าย",
        "amount": amount,
        "date": date_str,
        "source": "ข้อความ",
    }
