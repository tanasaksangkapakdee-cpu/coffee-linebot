"""
Order Handler — จดออเดอร์เมล็ดกาแฟ
รองรับรูปแบบอิสระ เช่น "สั่ง Ethiopia 1kg ชื่อ คุณบอล"
"""

import re
from datetime import datetime
from services.sheets_service import SheetsService


KNOWN_BEANS = [
    "ethiopia", "kenya", "colombia", "brazil", "guatemala",
    "panama", "yirgacheffe", "sumatra", "costa rica", "honduras",
    "rwanda", "burundi", "peru", "java", "vietnam",
    "เอธิโอเปีย", "เคนยา", "โคลอมเบีย", "บราซิล",
]


def handle_order(text: str, sheets: SheetsService) -> str:
    parsed = _parse_order(text)
    if not parsed["product"]:
        return "ไม่เข้าใจออเดอร์ ลองพิมพ์แบบนี้:\n  สั่ง Ethiopia 1kg"
    try:
        row_num = sheets.add_order(parsed)
        return f"บันทึกออเดอร์แล้ว (แถว {row_num})"
    except Exception as e:
        return f"บันทึกไม่สำเร็จ: {str(e)}"


def handle_order_list(sheets: SheetsService) -> str:
    try:
        orders = sheets.get_current_month_orders()
        if not orders:
            return "ยังไม่มีออเดอร์ในเดือนนี้"
        lines = [f"ออเดอร์เดือนนี้ ({len(orders)} รายการ)\n"]
        for i, o in enumerate(orders, 1):
            lines.append(f"{i}. {o.get('วันที่','')} | {o.get('สินค้า','')} {o.get('จำนวน','')} | {o.get('ชื่อลูกค้า','')}")
        return "\n".join(lines)
    except Exception as e:
        return f"ดึงข้อมูลไม่สำเร็จ: {str(e)}"


def _parse_order(text: str) -> dict:
    result = {
        "product": "",
        "quantity": "",
        "unit": "",
        "customer": "",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "raw": text,
    }
    clean = re.sub(r"^(สั่ง|ออเดอร์|order|จอง)\s*", "", text, flags=re.IGNORECASE).strip()
    customer_match = re.search(r"(ชื่อ|ของ|name)\s*[:：]?\s*(.+?)$", clean, re.IGNORECASE)
    if customer_match:
        result["customer"] = customer_match.group(2).strip()
        clean = clean[: customer_match.start()].strip()
    qty_match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|กก\.?|กิโล|กรัม|ถุง|ก\.?)", clean, re.IGNORECASE)
    if qty_match:
        result["quantity"] = qty_match.group(1)
        result["unit"] = qty_match.group(2)
        clean = (clean[: qty_match.start()] + clean[qty_match.end():]).strip()
    product = clean.strip(" ,.-")
    result["product"] = product if product else ""
    if result["quantity"]:
        result["quantity"] = f"{result['quantity']} {result['unit']}".strip()
    return result
