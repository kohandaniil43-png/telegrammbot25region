import sqlite3
import re
from flask import Flask, request, jsonify
import requests
import json
import os

# ======= НАСТРОЙКИ =======
TOKEN = "8980303731:AAGSbV7t9E49_nVsjmT4QcWALWYzHkz0_rA"
CHANNEL_ID = -1004336857767  # ВСТАВЬ СВОЙ (с минусом)!!!
ADMIN_ID = 1912704977         # ВСТАВЬ СВОЙ ID ТЕЛЕГРАМА!!!
# ==========================

app = Flask(__name__)

# --- База данных ---
conn = sqlite3.connect('bot_db.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, banned BOOLEAN)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats (total_approved INTEGER DEFAULT 0, total_rejected INTEGER DEFAULT 0)''')
cursor.execute('INSERT OR IGNORE INTO stats (total_approved, total_rejected) VALUES (0, 0)')
conn.commit()

# --- Функция отправки сообщений ---
def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=data)

# --- Проверка шаблона ---
def check_template(text):
    errors = []
    warnings = []
    if not re.search(r'\d+\s*[/\-]\s*\d+|\d+\s*руб|\d+\s*в час', text, re.IGNORECASE):
        errors.append("💰 Укажи зарплату")
    if not re.search(r'(\+7|8)\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text):
        errors.append("📱 Укажи номер телефона")
    if not re.search(r'место|адрес', text, re.IGNORECASE):
        warnings.append("📍 Укажи место (желательно)")
    if not re.search(r'часов|\d+\s*ч', text, re.IGNORECASE):
        warnings.append("⏰ Укажи время (желательно)")
    return errors, warnings

# --- Меню ---
def get_main_menu():
    return {
        "keyboard": [
            ["📝 Отправить объявление", "ℹ️ Помощь"],
            ["📊 Статистика", "👤 Мой профиль"]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# --- Обработка ВСЕХ сообщений (самая важная часть!) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"status": "ok"})
    
    message = data['message']
    user_id = message['from']['id']
    text = message.get('text', '')
    username = message['from'].get('username', 'нет юзернейма')
    
    # --- /start ---
    if text == '/start':
        cursor.execute('INSERT OR IGNORE INTO users (id, banned) VALUES (?, 0)', (user_id,))
        conn.commit()
        send_telegram(user_id, "👋 Привет! Отправь объявление с зарплатой и телефоном.", get_main_menu())
        return jsonify({"status": "ok"})
    
    # --- Проверка бана ---
    cursor.execute('SELECT banned FROM users WHERE id = ?', (user_id,))
    if cursor.fetchone() and cursor.fetchone()[0]:
        send_telegram(user_id, "🚫 Ты забанен.")
        return jsonify({"status": "ok"})
    
    # --- Кнопки меню ---
    if text == "📝 Отправить объявление":
        send_telegram(user_id, "📝 Напиши текст с зарплатой и телефоном", get_main_menu())
        return jsonify({"status": "ok"})
    if text == "ℹ️ Помощь":
        send_telegram(user_id, "🤖 Бот для вакансий\n/start - начать", get_main_menu())
        return jsonify({"status": "ok"})
    if text == "📊 Статистика":
        cursor.execute('SELECT total_approved, total_rejected FROM stats')
        appr, rej = cursor.fetchone()
        send_telegram(user_id, f"📊 Статистика\n✅ {appr}\n❌ {rej}", get_main_menu())
        return jsonify({"status": "ok"})
    if text == "👤 Мой профиль":
        send_telegram(user_id, f"👤 Профиль\n🆔 {user_id}\n👤 @{username}", get_main_menu())
        return jsonify({"status": "ok"})
    
    # --- Админ-панель (/admin) ---
    if text == '/admin' and user_id == ADMIN_ID:
        send_telegram(user_id, "⚙️ Админ-панель")
        return jsonify({"status": "ok"})
    
    # --- Модерация ---
    errors, warnings = check_template(text)
    if errors:
        cursor.execute('UPDATE stats SET total_rejected = total_rejected + 1')
        conn.commit()
        send_telegram(user_id, "❌ Ошибки:\n" + "\n".join(errors), get_main_menu())
        return jsonify({"status": "ok"})
    
    # --- Отправка в канал ---
    try:
        send_telegram(CHANNEL_ID, f"📢 ВАКАНСИЯ\n\n{text}\n\n👤 @{username}")
        cursor.execute('UPDATE stats SET total_approved = total_approved + 1')
        conn.commit()
        reply = "✅ Опубликовано!"
        if warnings:
            reply += "\n⚠️ " + "\n".join(warnings)
        send_telegram(user_id, reply, get_main_menu())
    except Exception as e:
        send_telegram(user_id, f"❌ Ошибка: {str(e)}", get_main_menu())
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
