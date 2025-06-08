import os
import pyodbc
import logging
import speech_recognition as sr
import dateparser
import csv
import threading
import hashlib
import time
import pygame
import requests  # ⬅️ для Mistral

from gtts import gTTS

# 🔐 Ключ OpenRouter
OPENROUTER_API_KEY = "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"  # ← ВСТАВ СВІЙ КЛЮЧ

# 🔹 Налаштування логів
logging.basicConfig(filename="assistant_log.txt", level=logging.INFO, format="%(asctime)s - %(message)s")

# 🔹 Кешування TTS
tts_lock = threading.Lock()
CACHE_DIR = "voice_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# 🔊 Ініціалізація pygame
pygame.mixer.init()

def speak_text(text):
    with tts_lock:
        try:
            print(f"🔊 Озвучення: {text}")
            logging.info(f"Озвучення тексту: {text}")
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            file_path = os.path.join(CACHE_DIR, f"{text_hash}.mp3")
            if not os.path.exists(file_path):
                tts = gTTS(text=text, lang='uk')
                tts.save(file_path)
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logging.error(f"❌ Помилка озвучення: {e}")
            print(f"❌ Помилка озвучення: {e}")

# 🔹 Підключення до БД
try:
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-1RPC6FA\\SQLEXPRESS;"
        "DATABASE=voice_assistant;"
        "Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
except Exception as e:
    logging.error(f"Помилка підключення до SQL Server: {e}")
    speak_text("Не вдалося підключитися до бази даних.")
    exit(1)

# 🔹 Розпізнавання голосу
def listen_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Слухаю...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language="uk-UA")
        print("🗣 Розпізнано:", text)
        return text.lower()
    except sr.UnknownValueError:
        speak_text("Не вдалося розпізнати команду.")
        return ""
    except sr.RequestError:
        speak_text("Помилка сервісу розпізнавання.")
        return ""

# 🔹 Підтвердження голосом
def confirm_input(field_name, value):
    speak_text(f"Ви сказали: {value}. Це правильно?")
    answer = listen_text()
    return "так" in answer

def get_confirmed_input(prompt_text, field_name):
    while True:
        speak_text(prompt_text)
        value = listen_text()
        if value and confirm_input(field_name, value):
            return value

# 🔹 Функції роботи з БД
def add_supplier():
    name = get_confirmed_input("Назвіть ім'я постачальника.", "ім'я")
    contact = get_confirmed_input("Назвіть контактну особу.", "контакт")
    phone = get_confirmed_input("Назвіть номер телефону.", "телефон")
    email = get_confirmed_input("Назвіть електронну пошту.", "пошта")
    try:
        cursor.execute("INSERT INTO suppliers (name, contact, phone, email) VALUES (?, ?, ?, ?)",
                       name, contact, phone, email)
        conn.commit()
        speak_text("Постачальника успішно додано.")
    except Exception as e:
        logging.error(f"Помилка додавання постачальника: {e}")
        speak_text("Сталася помилка.")

def add_product():
    name = get_confirmed_input("Назвіть назву матеріалу.", "назва")
    unit = get_confirmed_input("Назвіть одиницю вимірювання.", "одиниця")
    description = get_confirmed_input("Назвіть опис матеріалу.", "опис")
    price = get_confirmed_input("Назвіть ціну за куб.", "ціна")
    try:
        cursor.execute("INSERT INTO products (name, unit, description, price_per_cubic_meter) VALUES (?, ?, ?, ?)",
                       name, unit, description, price)
        conn.commit()
        speak_text("Матеріал успішно додано.")
    except Exception as e:
        logging.error(f"Помилка додавання матеріалу: {e}")
        speak_text("Помилка при додаванні.")

def add_supply():
    supplier = get_confirmed_input("Назвіть ID постачальника.", "ID постачальника")
    date_input = get_confirmed_input("Назвіть дату постачання.", "дата")
    delivery_date = dateparser.parse(date_input, languages=['uk'])
    product = get_confirmed_input("Назвіть ID товару.", "ID товару")
    try:
        cursor.execute("INSERT INTO deliveries (supplier_id, product_id, delivery_date) VALUES (?, ?, ?)",
                       supplier, product, delivery_date.date())
        conn.commit()
        speak_text("Постачання додано.")
    except Exception as e:
        logging.error(f"Помилка додавання постачання: {e}")
        speak_text("Сталася помилка.")

def search_supply():
    query = get_confirmed_input("Скажіть дату або назву товару.", "запит")
    parsed_date = dateparser.parse(query, languages=['uk'])
    try:
        if parsed_date:
            cursor.execute("SELECT * FROM deliveries WHERE delivery_date = ?", parsed_date.date())
        else:
            cursor.execute(
                "SELECT * FROM deliveries WHERE product_id IN (SELECT id FROM products WHERE name LIKE ?)",
                f"%{query}%")
        results = cursor.fetchall()
        if results:
            for row in results:
                speak_text(f"ID {row.id}, постачальник {row.supplier_id}, товар {row.product_id}, дата {row.delivery_date}")
        else:
            speak_text("Не знайдено постачань.")
    except Exception as e:
        logging.error(f"Помилка пошуку: {e}")
        speak_text("Помилка при пошуку.")

def edit_supply():
    id_text = get_confirmed_input("Назвіть ID постачання, яке потрібно змінити.", "ID")
    try:
        supply_id = int(id_text)
        cursor.execute("SELECT * FROM deliveries WHERE id = ?", supply_id)
        row = cursor.fetchone()
        if not row:
            speak_text("Постачання не знайдено.")
            return
        field = get_confirmed_input("Що змінити: постачальник, товар чи дата?", "поле")
        if "постачальник" in field:
            new_value = get_confirmed_input("Назвіть новий ID постачальника.", "новий постачальник")
            cursor.execute("UPDATE deliveries SET supplier_id = ? WHERE id = ?", new_value, supply_id)
        elif "товар" in field:
            new_value = get_confirmed_input("Назвіть новий ID товару.", "новий товар")
            cursor.execute("UPDATE deliveries SET product_id = ? WHERE id = ?", new_value, supply_id)
        elif "дата" in field:
            new_date_input = get_confirmed_input("Назвіть нову дату.", "нова дата")
            new_date = dateparser.parse(new_date_input, languages=['uk'])
            cursor.execute("UPDATE deliveries SET delivery_date = ? WHERE id = ?", new_date.date(), supply_id)
        else:
            speak_text("Поле не розпізнано.")
            return
        conn.commit()
        speak_text("Постачання оновлено.")
    except Exception as e:
        logging.error(f"Помилка редагування: {e}")
        speak_text("Сталася помилка при редагуванні.")

def delete_supply():
    id_text = get_confirmed_input("Назвіть ID постачання для видалення.", "ID")
    try:
        supply_id = int(id_text)
        cursor.execute("DELETE FROM deliveries WHERE id = ?", supply_id)
        conn.commit()
        speak_text("Постачання видалено.")
    except Exception as e:
        logging.error(f"Помилка видалення: {e}")
        speak_text("Помилка при видаленні.")

def export_to_csv():
    try:
        cursor.execute("SELECT * FROM deliveries")
        rows = cursor.fetchall()
        with open("deliveries_export.csv", mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([desc[0] for desc in cursor.description])
            for row in rows:
                writer.writerow(row)
        speak_text("Експорт завершено.")
    except Exception as e:
        logging.error(f"Помилка експорту: {e}")
        speak_text("Помилка при експорті.")

def show_help():
    help_text = (
        "Ось короткий список  команд: "
        "1. Додай постачальника. "
        "2. Додай матеріал. "
        "3. Додай постачання. "
        "4. Знайди постачання. "
        "5. Редагуй постачання. "
        "6. Видали постачання. "
        "7. Експортуй постачання. "
        "8. Допомога. "
        "9. Чат."
        "10. Вийти."
    )
    speak_text(help_text)

# 🔹 Mistral (OpenRouter)
def ask_openrouter(user_input):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistralai/mistral-7b-instruct",  # 🟡 Заміна назви моделі
        "messages": [
            {"role": "system", "content": "Ти розумний голосовий помічник українською мовою."},
            {"role": "user", "content": user_input}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code != 200:
            # 🔴 Лог конкретної помилки
            logging.error(f"OpenRouter API error {response.status_code}: {response.text}")
            print(f"🔴 Відповідь API: {response.status_code}, {response.text}")
            return "Не вдалося звернутися до ШІ помічника."
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"❌ Виняток при запиті до OpenRouter: {e}")
        print(f"❌ Exception: {e}")
        return "Не вдалося звернутися до ШІ помічника."



# 🔹 Обробка команд
def process_command(command):
    print("📥 Команда:", command)
    if "постачальника" in command and "додай" in command:
        add_supplier()
    elif "матеріал" in command:
        add_product()
    elif "постачання" in command and "додай" in command:
        add_supply()
    elif "знайди" in command or "пошук" in command:
        search_supply()
    elif "редагуй" in command:
        edit_supply()
    elif "видали" in command:
        delete_supply()
    elif "експортуй" in command:
        export_to_csv()
    elif "допомога" in command:
        show_help()
    elif "вийти" in command or "завершити" in command:
        speak_text("До побачення!")
        conn.close()
        exit()
    elif command.startswith("чат"):
        query = command.replace("чат", "").strip()
        if not query:
            speak_text("Що саме запитати в ШІ?")
            query = listen_text()
        if query:
            reply = ask_openrouter(query)
            speak_text(reply)
    else:
        speak_text("Команду не розпізнано.")
# 🔹 Основний цикл
def listen_for_command():
    speak_text("Доброго дня! Скажіть 'Алекс', щоб дати команду.")
    while True:
        text = listen_text()
        if any(kw in text for kw in ["алекс", "але", "олекс", "алекса", "помічник"]):
            speak_text("Слухаю.")
            command = listen_text()
            if command:
                process_command(command)
        else:
            print("⏳ Чекаю активації...")

# 🔹 Запуск
if __name__ == "__main__":
    listen_for_command()
