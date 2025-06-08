import os
import uuid
import re
import pyodbc
from datetime import datetime
from gtts import gTTS
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler,
    ConversationHandler, filters
)
from openai import OpenAI

# --- Налаштування ---
DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-1RPC6FA\\SQLEXPRESS;"
    "DATABASE=voice_assistant;"
    "Trusted_Connection=yes;"
)
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL = "mistralai/mistral-7b-instruct"

# --- Стан розмов ---
(
    SUPPLIER_NAME, SUPPLIER_PHONE, SUPPLIER_EMAIL,
    ASK_PRODUCT_NAME, ASK_PRODUCT_ID_FOR_DELETE,
    ASK_PRODUCT_ID_FOR_EDIT, ASK_NEW_PRODUCT_NAME
) = range(7)

ADD_SUPPLIER_ID, ADD_PRODUCT_NAME, ADD_QUANTITY, ADD_DATE = range(7, 11)

# --- TTS ---
def save_tts(text: str) -> str:
    filename = f"tts_{uuid.uuid4().hex}.mp3"
    gTTS(text=text, lang='uk').save(filename)
    return filename

async def send_tts(update: Update, text: str):
    filename = save_tts(text)
    with open(filename, "rb") as audio:
        await update.message.reply_voice(voice=InputFile(audio))
    os.remove(filename)

# --- GPT-відповідь ---
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def get_ai_response(prompt: str) -> str:
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "Ти україномовний помічник."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# --- Email-валідація ---
def is_valid_email(email: str) -> bool:
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

# --- Привітання ---
def get_greeting(name: str) -> str:
    hour = datetime.now().hour
    if hour < 12:
        time_greeting = "Доброго ранку"
    elif hour < 18:
        time_greeting = "Доброго дня"
    else:
        time_greeting = "Доброго вечора"
    return f"{time_greeting}, {name}! Я голосовий бот-помічник. Ось що я вмію. Список команд вже на екрані."

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name or "користувачу"
    greeting = get_greeting(user_name)
    msg = (
        "Привіт! Я голосовий бот-помічник для обліку постачань. Ось що я вмію:\n\n"
        "📦 /addsupplier — додати постачальника\n"
        "📦 /addproduct — додати продукт\n"
        "🚚 /adddelivery — додати поставку\n\n"
        "📋 /viewsuppliers — список постачальників\n"
        "📋 /viewproducts — список продуктів\n"
        "📋 /viewdeliveries — список поставок\n\n"
        "❌ /deletesupplier — видалити постачальника\n"
        "❌ /deleteproduct — видалити продукт\n"
        "❌ /deletedelivery — видалити поставку\n\n"
        "✏️ /editsupplier — редагувати постачальника\n"
        "✏️ /editproduct — редагувати продукт\n"
        "✏️ /editdelivery — редагувати поставку\n\n"
        "🧠 /ask — поставити будь-яке питання GPT"
    )
    await update.message.reply_text(msg)
    await send_tts(update, greeting)

# --- /ask ---
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args)
    if not question:
        await update.message.reply_text("❓ Напишіть запитання після команди /ask")
        return
    try:
        reply = get_ai_response(question)
        await update.message.reply_text(reply)
        await send_tts(update, reply)
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

# --- Додавання постачальника ---
async def start_add_supplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть назву постачальника:")
    return SUPPLIER_NAME

async def supplier_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["supplier_name"] = update.message.text
    await update.message.reply_text("Введіть номер телефону:")
    return SUPPLIER_PHONE

async def supplier_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["supplier_phone"] = update.message.text
    await update.message.reply_text("Введіть email:")
    return SUPPLIER_EMAIL

async def supplier_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text
    if not is_valid_email(email):
        await update.message.reply_text("❌ Невірний email. Спробуйте ще раз:")
        return SUPPLIER_EMAIL

    context.user_data["supplier_email"] = email
    try:
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO suppliers (name, phone, email) VALUES (?, ?, ?)",
                context.user_data["supplier_name"],
                context.user_data["supplier_phone"],
                email
            )
            conn.commit()
        msg = "✅ Постачальника додано."
        await update.message.reply_text(msg)
        await send_tts(update, msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")
    return ConversationHandler.END

# --- Перегляд постачальників ---
async def view_suppliers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SupplierID, name, phone, email FROM suppliers")
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    msg = f"ID: {row[0]}\nНазва: {row[1]}\nТелефон: {row[2]}\nEmail: {row[3]}"
                    await update.message.reply_text(msg)
            else:
                await update.message.reply_text("❌ Постачальників не знайдено.")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

# --- Видалення постачальника ---
async def delete_supplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if not args:
            await update.message.reply_text("⚠️ Вкажіть ID постачальника після команди. Приклад: /deletesupplier 3")
            return
        supplier_id = int(args[0])
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM suppliers WHERE SupplierID = ?", supplier_id)
            conn.commit()
        msg = "🗑️ Постачальника видалено."
        await update.message.reply_text(msg)
        await send_tts(update, msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

# --- Продукти ---
async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введи назву продукту:")
    return ASK_PRODUCT_NAME

async def save_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name = update.message.text.strip()
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Products (Name) VALUES (?)", name)
            conn.commit()
        await update.message.reply_text("✅ Продукт додано!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Помилка: {str(e)}")
    return ConversationHandler.END

async def view_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ProductID, Name FROM Products")
            rows = cursor.fetchall()
            if not rows:
                await update.message.reply_text("Продуктів не знайдено.")
                return
            msg = "📋 Продукти:\n"
            for row in rows:
                msg += f"ID: {row[0]}, Назва: {row[1]}\n"
            await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Помилка: {str(e)}")

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введи ID продукту для видалення:")
    return ASK_PRODUCT_ID_FOR_DELETE

async def confirm_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        product_id = int(update.message.text)
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Products WHERE ProductID = ?", product_id)
            conn.commit()
        await update.message.reply_text("❌ Продукт видалено.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Помилка: {str(e)}")
    return ConversationHandler.END

async def edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введи ID продукту для редагування:")
    return ASK_PRODUCT_ID_FOR_EDIT

async def ask_new_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_id'] = int(update.message.text)
    await update.message.reply_text("Введи нову назву продукту:")
    return ASK_NEW_PRODUCT_NAME

async def save_edited_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_name = update.message.text.strip()
        product_id = context.user_data['product_id']
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Products SET Name = ? WHERE ProductID = ?", new_name, product_id)
            conn.commit()
        await update.message.reply_text("✅ Продукт оновлено.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Помилка: {str(e)}")
    return ConversationHandler.END

# --- Поставки ---
async def add_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ID постачальника:")
    return ADD_SUPPLIER_ID

async def ask_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["supplier_id"] = update.message.text
    await update.message.reply_text("Введіть назву продукту:")
    return ADD_PRODUCT_NAME

async def ask_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["product_name"] = update.message.text
    await update.message.reply_text("Введіть кількість:")
    return ADD_QUANTITY

async def ask_delivery_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quantity"] = update.message.text
    await update.message.reply_text("Введіть дату доставки (рррр-мм-дд):")
    return ADD_DATE

async def save_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["delivery_date"] = update.message.text
    try:
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO deliveries (SupplierID, ProductName, Quantity, DeliveryDate) VALUES (?, ?, ?, ?)",
                context.user_data["supplier_id"],
                context.user_data["product_name"],
                context.user_data["quantity"],
                context.user_data["delivery_date"]
            )
            conn.commit()
        await update.message.reply_text("✅ Поставка додана.")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")
    return ConversationHandler.END

async def view_deliveries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, supplier_id, product_name, quantity, delivery_date FROM deliveries")
            rows = cursor.fetchall()
            if not rows:
                await update.message.reply_text("Поставок не знайдено.")
                return
            for row in rows:
                msg = (
                    f"ID поставки: {row[0]}\n"
                    f"ID постачальника: {row[1]}\n"
                    f"Назва продукту: {row[2]}\n"
                    f"Кількість: {row[3]}\n"
                    f"Дата доставки: {row[4]}"
                )
                await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

async def delete_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if not args:
            await update.message.reply_text("Вкажіть ID поставки після команди. Приклад: /deletedelivery 2")
            return
        delivery_id = int(args[0])
        with pyodbc.connect(DB_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM deliveries WHERE delivery_id = ?", delivery_id)
            conn.commit()
        await update.message.reply_text("🗑️ Поставка видалена.")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")

# --- Відміна ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Дія скасована.")
    return ConversationHandler.END

# --- Основний запуск ---
if __name__ == '__main__':
    app = ApplicationBuilder().token("7678185832:AAH9RQ0Al4IA4uc0K_RjZGhgX6gal9CzwfQ").build()

    # Команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("viewsuppliers", view_suppliers))
    app.add_handler(CommandHandler("deletesupplier", delete_supplier))

    # Постачальники - додавання
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addsupplier", start_add_supplier)],
        states={
            SUPPLIER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplier_name)],
            SUPPLIER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplier_phone)],
            SUPPLIER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplier_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Продукти
    app.add_handler(CommandHandler("viewproducts", view_products))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addproduct", add_product)],
        states={
            ASK_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("deleteproduct", delete_product)],
        states={
            ASK_PRODUCT_ID_FOR_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("editproduct", edit_product)],
        states={
            ASK_PRODUCT_ID_FOR_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_new_product_name)],
            ASK_NEW_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_product)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Поставки
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("adddelivery", add_delivery)],
        states={
            ADD_SUPPLIER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_product_name)],
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_quantity)],
            ADD_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_delivery_date)],
            ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_delivery)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(CommandHandler("viewdeliveries", view_deliveries))
    app.add_handler(CommandHandler("deletedelivery", delete_delivery))
    

    print("✅ Бот запущено...")
    app.run_polling()
