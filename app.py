"""
Custom Caff LINE Chatbot
จัดการออเดอร์เมล็ดกาแฟ + บันทึกรายจ่าย
"""

import os
import logging
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

LINE_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

logger.info(f"LINE_ACCESS_TOKEN loaded: {bool(LINE_ACCESS_TOKEN)}")
logger.info(f"LINE_SECRET loaded: {bool(LINE_SECRET)}")

configuration = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)
sheets = SheetsService()

@app.route("/", methods=["GET"])
def health():
    return "Custom Caff Bot is running! ☕"

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    logger.info(f"Webhook received, body length: {len(body)}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("InvalidSignatureError - check LINE_CHANNEL_SECRET")
        abort(400)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    text = event.message.text.strip()
    logger.info(f"Text received: {text!r}")
    reply = None
    try:
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
        else:
            reply = "ไม่เข้าใจคำสั่ง พิมพ์ help เพื่อดูคำสั่งทั้งหมด"
    except Exception as e:
        logger.error(f"handle_text error: {e}")
        reply = f"เกิดข้อผิดพลาด: {str(e)}"
    if reply:
        _reply(event.reply_token, reply)

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            resp = line_bot_api.get_message_content(event.message.id)
            image_bytes = resp.read()
            reply = handle_expense_image(image_bytes, sheets)
        except Exception as e:
            logger.error(f"handle_image error: {e}")
            reply = f"อ่านรูปไม่ได้: {str(e)}"
    if reply:
        _reply(event.reply_token, reply)

# Keywords ทั้งภาษาไทยและอังกฤษ
ORDER_KEYWORDS = ["สั่ง", "ออเดอร์", "order", "จอง"]
EXPENSE_KEYWORDS = ["จ่าย", "ซื้อ", "ค่า", "expense", "buy", "pay"]
LIST_KEYWORDS = ["รายการ", "ดูออเดอร์", "list order", "show orders"]
REPORT_KEYWORDS = ["รายงาน", "สรุป", "report", "summary"]
HELP_KEYWORDS = ["help", "ช่วยเหลือ", "วิธีใช้", "คำสั่ง", "commands"]

def _is_order(text): return any(kw in text for kw in ORDER_KEYWORDS)
def _is_expense(text): return any(kw in text for kw in EXPENSE_KEYWORDS)
def _is_order_list(text): return any(kw in text for kw in LIST_KEYWORDS)
def _is_expense_report(text): return any(kw in text for kw in REPORT_KEYWORDS)
def _is_help(text): return any(kw in text for kw in HELP_KEYWORDS)

def _reply(reply_token, text):
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
            )
            logger.info(f"Reply sent: {text[:50]}")
    except Exception as e:
        logger.error(f"Reply error: {e}")

def _expense_report(sheets):
    rows = sheets.get_current_month_expenses()
    if not rows:
        return "ไม่มีรายจ่ายเดือนนี้"
    total = sum(float(str(r.get("amount", 0)).replace(",", "")) for r in rows)
    return f"รายจ่ายเดือนนี้รวม: {total:,.0f} บาท"

def _help_message():
    return (
        "📋 คำสั่งบอท Custom Caff:\n"
        "สั่ง <ชื่อ> <จำนวน> - บันทึกออเดอร์เมล็ดกาแฟ\n"
        "จ่าย <จำนวน> บาท <รายการ> - บันทึกรายจ่าย\n"
        "รายการ - ดูออเดอร์เดือนนี้\n"
        "สรุป - ดูรายจ่ายเดือนนี้\n"
        "ส่งรูปใบเสร็จ - บันทึกรายจ่ายจากใบเสร็จ"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
