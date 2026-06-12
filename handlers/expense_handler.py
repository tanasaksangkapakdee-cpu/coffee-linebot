"""
Expense Handler - จดรายจ่าย
รองรับ: ข้อความอิสระ + รูปสลิป (OCR)
"""

import re
import io
from datetime import datetime
from services.sheets_service import SheetsService
from services.ocr_service import extract_text_from_image, parse_receipt_amount


def handle_expense(text: str, sheets: SheetsService) -> str:
    parsed = _parse_expense_text(text)
    if parsed["amount"] is None:
        return "ไม่พบจำนวนเงิน ลองพิมพ์แบบนี้:\n  จ่ายค่าเมล็ดกาแฟ 3500 บาท"
    try:
        row_num = sheets.add_expense(parsed)
        return f"บันทึกรายจ่ายแล้ว (แถว {row_num})"
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
        parsed = {
            "description": description or "สลิปใบเสร็จ",
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "สลิป/รูปภาพ",
            "raw": raw_text[:500],
        }
        row_num = sheets.add_expense(parsed)
        return f"สแกนสลิปและบันทึกแล้ว (แถว {row_num})"
    except Exception as e:
        return f"ประมวลผลสลิปไม่สำเร็จ: {str(e)}"


def _parse_expense_text(text: str) -> dict:
    result = {
        "description": "",
        "amount": None,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "ข้อความ",
        "raw": text,
    }
    amount_match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?:บาท|฿|thb|baht)?", text, re.IGNORECASE)
    if amount_match:
        amount_str = amount_match.group(1).replace(",", "")
        result["amount"] = float(amount_str)
    desc = re.sub(r"^(จ่าย|ซื้อ|ค่า|รายจ่าย|expense|จ่ายเงิน)\s*", "", text, flags=re.IGNORECASE)
    desc = re.sub(r"\s*\d[\d,]*(?:\.\d+)?\s*(?:บาท|฿|thb|baht)?", "", desc, flags=re.IGNORECASE)
    desc = desc.strip(" ,.-")
    result["description"] = desc if desc else text[:50]
    return result
