
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from database import Session, Order
from config import BOT_TOKEN, ADMIN_ID
import os

app = Flask(__name__)
orders = {}
app_bot = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [["Оформить заказ", "Статус заказа"]]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("Добро пожаловать в курьерскую службу!", reply_markup=markup)

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text

    if text == "Оформить заказ":
        orders[chat_id] = {"step": "name"}
        await update.message.reply_text("Введите ваше имя:")
    elif text == "Статус заказа":
        orders[chat_id] = {"step": "check_status"}
        await update.message.reply_text("Введите ID заказа:")
    elif chat_id in orders:
        step = orders[chat_id]["step"]
        if step == "name":
            orders[chat_id]["name"] = text
            orders[chat_id]["step"] = "phone"
            await update.message.reply_text("Введите номер телефона:")
        elif step == "phone":
            orders[chat_id]["phone"] = text
            orders[chat_id]["step"] = "from"
            await update.message.reply_text("Введите адрес отправления:")
        elif step == "from":
            orders[chat_id]["from"] = text
            orders[chat_id]["step"] = "to"
            await update.message.reply_text("Введите адрес получения:")
        elif step == "to":
            orders[chat_id]["to"] = text
            session = Session()
            order = Order(
                name=orders[chat_id]["name"],
                phone=orders[chat_id]["phone"],
                from_address=orders[chat_id]["from"],
                to_address=text
            )
            session.add(order)
            session.commit()
            await update.message.reply_text(f"Ваш заказ оформлен! ID: {order.id}")
            session.close()
            del orders[chat_id]
        elif step == "check_status":
            session = Session()
            order = session.query(Order).filter_by(id=text).first()
            if order:
                await update.message.reply_text(f"Статус заказа: {order.status}")
            else:
                await update.message.reply_text("Заказ не найден.")
            session.close()
            del orders[chat_id]
    elif text == "/admin" and update.message.from_user.id == ADMIN_ID:
        session = Session()
        all_orders = session.query(Order).all()
        for o in all_orders:
            await update.message.reply_text(f"ID: {o.id}, {o.name} ({o.status})")
        session.close()
    elif text.startswith("/setstatus") and update.message.from_user.id == ADMIN_ID:
        parts = text.split()
        if len(parts) == 3:
            order_id, new_status = parts[1], parts[2]
            session = Session()
            order = session.query(Order).filter_by(id=order_id).first()
            if order:
                order.status = new_status
                session.commit()
                await update.message.reply_text(f"Статус заказа {order_id} обновлен.")
            else:
                await update.message.reply_text("Заказ не найден.")
            session.close()

app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), app_bot.bot)
    app_bot.update_queue.put(update)
    return 'ok'

if __name__ == '__main__':
    app_bot.run_polling()
