"""
OCR Service — อ่านข้อความจากรูปสลิปใบเสร็จ
ใช้ pytesseract (ฟรี, รองรับภาษาไทย)
"""

import re
import io
from PIL import Image
import pytesseract


def extract_text_from_image(image_bytes: bytes) -> str:
    """
    รับ bytes ของภาพ → คืนข้อความที่อ่านได้
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))

        # ปรับขนาดถ้าเล็กเกินไป
        w, h = image.size
        if w < 800:
            scale = 800 / w
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # OCR ทั้งไทยและอังกฤษ
        text = pytesseract.image_to_string(image, lang="tha+eng")
        return text.strip()

    except Exception as e:
        raise RuntimeError(f"OCR ล้มเหลว: {str(e)}")


def parse_receipt_amount(raw_text: str):
    """
    หาจำนวนเงินรวมจากข้อความ OCR ของสลิป
    คืนค่า (amount: float | None, description: str)
    """
    lines = raw_text.split("\n")
    amount = None
    description = "สลิปใบเสร็จ"

    # คำที่บ่งบอกว่าเป็นยอดรวม
    TOTAL_KEYWORDS = [
        "รวม", "total", "ยอดรวม", "ยอดสุทธิ", "net", "grand total",
        "รวมทั้งสิ้น", "amount", "ชำระ", "จ่าย", "เงินสด", "โอน"
    ]

    # หาบรรทัดที่มีคำบ่งบอกยอดรวม + ตัวเลข
    best_amount = None
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in TOTAL_KEYWORDS):
            nums = re.findall(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?", line)
            if nums:
                try:
                    val = float(nums[-1].replace(",", ""))
                    if val > 0 and (best_amount is None or val > best_amount):
                        best_amount = val
                except ValueError:
                    pass

    # ถ้าไม่เจอยอดรวม → เอาตัวเลขที่ใหญ่ที่สุดในสลิป
    if best_amount is None:
        all_nums = re.findall(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?", raw_text)
        values = []
        for n in all_nums:
            try:
                v = float(n.replace(",", ""))
                if 1 <= v <= 999999:
                    values.append(v)
            except ValueError:
                pass
        if values:
            best_amount = max(values)

    amount = best_amount

    # หาคำอธิบายจากบรรทัดแรกของสลิป
    for line in lines:
        line = line.strip()
        if len(line) > 3 and not re.match(r"^[\d\s,./:-]+$", line):
            description = line[:60]
            break

    return amount, description
