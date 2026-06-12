"""
Custom Caff LINE Chatbot
จัดการออเดอร์เมล็ดกาแฟ + บันทึกรายจ่าย
"""

import os
import traceback
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, ImageMessageContent
)

from handlers.order_handler import handle_order, handle_order_list
from handlers.expense_handler import handle_expense, handle_expense_image
from services.sheets_service import SheetsService

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

configuration = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)
sheets = SheetsService()


@app.route("/", methods=["GET"])
def health():
    return "Custom Caff Bot is running! coffee"


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    text = event.message.text.strip()
    reply = None
    if _is_order(text):
        reply = handle_order(text, sheets)
    elif _is_expense(text):
        reply = handle_expense(text, sheets)
    elif _is_order_list(text):
        reply = handle_order_list(sheets)
    elif _is_expense_report(text):
        reply = _expense_report(sheets)
    elif _is_help(text):
        reply = _help_message()
    if reply:
        _reply(event.reply_token, reply)


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    try:
        from linebot.v3.messaging import MessagingApiBlob
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            image_bytes = blob_api.get_message_content(message_id=event.message.id)
            reply = handle_expense_image(image_bytes, sheets)
    except Exception as e:
        app.logger.error(f"handle_image error: {traceback.format_exc()}")
        reply = f"อ่านรูปไม่ได้: {str(e)}"
    if reply:
        _reply(event.reply_token, reply)


ORDER_PREFIXES   = ["สั่ง", "สั่งซื้อ", "จดออเดอร์", "order"]
EXPENSE_PREFIXES = ["จ่าย", "รายจ่าย", "บันทึกรายจ่าย", "ค่าใช้จ่าย", "expense"]
LIST_KEYWORDS    = ["รายการ", "ดูออเดอร์", "list order", "ออเดอร์เดือนนี้"]
REPORT_KEYWORDS  = ["สุป", "สรุป", "ดูรายจ่าย", "report", "summary", "รายจ่ายเดือนนี้"]
HELP_KEYWORDS    = ["help", "ช่วย", "คำสั่ง", "วิธีใช้", "เมนู"]


def _is_order(text):
    return any(text.startswith(kw) for kw in ORDER_PREFIXES)

def _is_expense(text):
    return any(text.startswith(kw) for kw in EXPENSE_PREFIXES)

def _is_order_list(text):
    return any(kw in text for kw in LIST_KEYWORDS)

def _is_expense_report(text):
    return any(kw in text for kw in REPORT_KEYWORDS)

def _is_help(text):
    return any(kw in text for kw in HELP_KEYWORDS)


def _reply(reply_token, text):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
        )


def _expense_report(sheets):
    try:
        rows = sheets.get_current_month_expenses()
        if not rows:
            return "📊 รายจ่ายเดือนนี้: ยังไม่มีรายการ"
        total = 0
        lines = ["📊 สรุปรายจ่ายเดือนนี้:"]
        for r in rows[-10:]:
            amt_raw = str(r.get("จำนวนเงิน (บาท)", 0)).replace(",", "")
            try:
                amt = float(amt_raw)
                total += amt
                lines.append(f"• {r.get('รายการ', '-')} — {amt:,.0f} บาท")
            except ValueError:
                pass
        lines.append(f"\n💰 รวม: {total:,.0f} บาท")
        return "\n".join(lines)
    except Exception as e:
        return f"ดึงข้อมูลไม่สำเร็จ: {str(e)}"


def _help_message():
    return (
        "🟦 คำสั่งบอท Custom Caff:\n"
        "สั่ง <ชื่อ> <จำนวน> – บันทึกออเดอร์เมล็ดกาแฟ\n"
        "จ่าย <จำนวน> บาท <รายการ> – บันทึกรายจ่าย\n"
        "รายการ – ดูออเดอร์เดือนนี้\n"
        "สุป – ดูรายจ่ายเดือนนี้\n"
        "ส่งรูป – บันทึกรายจ่ายจากสลิป/ใบเสร็จ"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
