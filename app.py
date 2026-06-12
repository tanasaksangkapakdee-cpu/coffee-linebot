"""
Custom Caff LINE Chatbot
จัดการออเดอร์เมล็ดกาแฟ + บันทึกรายจ่าย
"""

import os
import re
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
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            resp = line_bot_api.get_message_content(event.message.id)
            image_bytes = resp.read()
            reply = handle_expense_image(image_bytes, sheets)
        except Exception as e:
            reply = f"cannot read image: {str(e)}"
        if reply:
            _reply(event.reply_token, reply)


ORDER_KEYWORDS   = ["order", "coffee order"]
EXPENSE_KEYWORDS = ["expense", "buy", "pay"]
LIST_KEYWORDS    = ["list order", "show orders"]
REPORT_KEYWORDS  = ["report", "summary"]
HELP_KEYWORDS    = ["help", "commands"]

def _is_order(text): return any(kw in text for kw in ORDER_KEYWORDS)
def _is_expense(text): return any(kw in text for kw in EXPENSE_KEYWORDS)
def _is_order_list(text): return any(kw in text.lower() for kw in LIST_KEYWORDS)
def _is_expense_report(text): return any(kw in text for kw in REPORT_KEYWORDS)
def _is_help(text): return any(kw in text.lower() for kw in HELP_KEYWORDS)

def _reply(reply_token, text):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)]))

def _expense_report(sheets):
    rows = sheets.get_current_month_expenses()
    if not rows: return "No expenses this month"
    total = sum(float(str(r.get("amount", 0)).replace(",", "")) for r in rows)
    return f"Total: {total:,.0f} baht"

def _help_message():
    return "Commands: order <item> <qty> | expense <amount> | list order | report"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
