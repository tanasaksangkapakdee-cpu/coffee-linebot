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
        customer = f"คุณ{parsed['customer']}" if parsed['customer'] else "-"
        return (
            f"✅ บันทึกออเดอร์แล้ว (แถว {row_num}) 📦\n"
            f" สินค้า: {parsed['product']} ⚖️\n"
            f" จำนวน: {parsed['quantity']} 👤\n"
            f" ชื่อ: {customer} 📅 วันที่: {parsed['date']}"
        )
    except Exception as e:
        return f"บันทึกไม่สำเร็จ: {str(e)}"


def handle_order_list(sheets: SheetsService) -> str:
    try:
        orders = sheets.get_orders()
        if not orders:
            return "ยังไม่มีออเดอร์"
        lines = ["📋 รายการออเดอร์:"]
        for o in orders[-10:]:
            lines.append(f"• {o.get('date','')} | {o.get('product','')} {o.get('quantity','')} | {o.get('customer','')}")
        return "\n".join(lines)
    except Exception as e:
        return f"ดึงข้อมูลไม่สำเร็จ: {str(e)}"


def _parse_order(text: str) -> dict:
    text = text.strip()
    for kw in ["สั่ง", "order", "สั่งซื้อ", "จดออเดอร์", "บันทึกออเดอร์"]:
        text = re.sub(rf"(?i)^{kw}\s*", "", text, count=1)

    product = ""
    quantity = ""
    customer = ""

    m = re.search(r"(?:ชื่อ|name|ลูกค้า)\s*[:]?\s*([\w\s]+?)(?:\s|$)", text, re.IGNORECASE)
    if m:
        customer = m.group(1).strip().lstrip("คุณ")
        text = text[:m.start()] + text[m.end():]

    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|กก|กิโล|ถุง|แพ็ค)?", text, re.IGNORECASE)
    if m:
        qty_num = m.group(1)
        qty_unit = m.group(2) or "kg"
        quantity = f"{qty_num} {qty_unit}"
        text = text[:m.start()] + text[m.end():]

    product = text.strip().strip(",").strip()
    if not product:
        for bean in KNOWN_BEANS:
            if bean in text.lower():
                product = bean.title()
                break

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    return {
        "product": product,
        "quantity": quantity or "1 kg",
        "customer": customer,
        "date": date_str,
    }
