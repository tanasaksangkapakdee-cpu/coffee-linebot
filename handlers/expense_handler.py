"""
Expense Handler - จดรายจ่าย
รองรับ: ข้อความอิสระ + รูปสลิป/ใบเสร็จ/กระดาษลายมือ
"""

import re
import io
import os
import json
import base64
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from services.sheets_service import SheetsService
from services.ocr_service import extract_text_from_image, parse_receipt_amount

GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")  # optional: folder to save receipts


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
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg")
        f = service.files().create(body=meta, media_body=media, fields="id").execute()
        file_id = f.get("id", "")
        # Make publicly viewable
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception:
        return ""


def handle_expense(text: str, sheets: SheetsService) -> str:
    parsed = _parse_expense_text(text)
    if parsed["amount"] is None:
        return "ไม่พบจำนวนเงิน ลองพิมพ์แบบนี้:\n  จ่ายค่าเมล็ดกาแฟ 3500 บาท"
    try:
        row_num = sheets.add_expense(parsed)
        amount_fmt = f"{parsed['amount']:,.0f}" if isinstance(parsed['amount'], (int, float)) else str(parsed['amount'])
        return (
            f"✅ บันทึกรายจ่ายแล้ว (แถว {row_num})\n"
            f"📝 รายการ: {parsed['description']}\n"
            f"💰 จำนวน: {amount_fmt} บาท\n"
            f"📅 วันที่: {parsed['date']}"
        )
    except Exception as e:
        return f"บันทึกไม่สำเร็จ: {str(e)}"


def handle_expense_image(image_bytes: bytes, sheets: SheetsService) -> str:
    try:
        raw_text = extract_text_from_image(image_bytes)
        if not raw_text:
            return "อ่านสลิปไม่ออก ลองถ่ายใหม่"
        amount, description = parse_receipt_amount(raw_text)
        if amount is None:
            return f"อ่านสลิปได้ แต่หาจำนวนเงินไม่เจอ\nข้อความ: {raw_text[:300]}"

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        filename = f"receipt_{date_str.replace(':', '-').replace(' ', '_')}.jpg"

        # Save image to Google Drive
        drive_url = _save_image_to_drive(image_bytes, filename)

        parsed = {
            "description": description or "สลิปใบเสร็จ",
            "amount": amount,
            "date": date_str,
            "source": drive_url or "สลิป/รูปภาพ",
        }
        row_num = sheets.add_expense(parsed)
        amount_fmt = f"{amount:,.0f}" if isinstance(amount, (int, float)) else str(amount)
        reply = (
            f"✅ บันทึกรายจ่ายแล้ว (แถว {row_num})\n"
            f"📝 รายการ: {parsed['description']}\n"
            f"💰 จำนวน: {amount_fmt} บาท\n"
            f"📅 วันที่: {date_str}"
        )
        if drive_url:
            reply += f"\n🖼️ รูปภาพ: {drive_url}"
        return reply
    except Exception as e:
        return f"บันทึกสลิปไม่สำเร็จ: {str(e)}"


def _parse_expense_text(text: str) -> dict:
    text = text.strip()
    for kw in ["จ่าย", "expense", "รายจ่าย", "บันทึกรายจ่าย", "ค่าใช้จ่าย"]:
        text = re.sub(rf"(?i)^{kw}\s*", "", text, count=1)

    amount = None
    description = text.strip()

    # Extract amount (number + optional บาท)
    m = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:บาท|baht|฿)?", text, re.IGNORECASE)
    if m:
        raw = m.group(1).replace(",", "")
        try:
            amount = float(raw)
        except ValueError:
            pass
        description = (text[:m.start()] + text[m.end():]).strip().strip("ค่า").strip() or "รายจ่าย"

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "description": description or "รายจ่าย",
        "amount": amount,
        "date": date_str,
        "source": "ข้อความ",
    }
