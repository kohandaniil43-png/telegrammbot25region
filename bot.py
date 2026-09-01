import sqlite3
import re
from flask import Flask, request, jsonify
import requests
import json

# ======= НАСТРОЙКИ (ЗАМЕНИ ЭТИ 3 СТРОЧКИ) =======
TOKEN = "8980303731:AAGSbV7t9E49_nVsjmT4QcWALWYzHkz0_rA"
CHANNEL_ID = -1004336857767
ADMIN_ID = 1912704977
# =================================================

app = Flask(__name__)

conn = sqlite3.connect('bot_db.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, banned BOOLEAN)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats (total_approved INTEGER DEFAULT 0, total_rejected INTEGER DEFAULT 0)''')
cursor.execute('INSERT OR IGNORE INTO stats (total_approved, total_rejected) VALUES (0, 0)')
conn.commit()

def send_telegram(chat_id, text, reply_markup=None, parse_mode='HTML'):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=data)

def edit_telegram(chat_id, message_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=data)

def check_template(text):
    errors = []
    warnings = []
    if not re.search(r'\d+\s*[/\-]\s*\d+|\d+\s*руб|\d+\s*в час', text, re.IGNORECASE):
        errors.append("💰 Укажи зарплату (например: 500/1)")
    if not re.search(r'(\+7|8)\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text):
        errors.append("📱 Укажи номер телефона")
    if not re.search(r'место|адрес|метро', text, re.IGNORECASE):
        warnings.append("📍 Укажи место работы (желательно)")
    if not re.search(r'часов|\d+\s*ч|время', text, re.IGNORECASE):
        warnings.append("⏰ Укажи время (желательно)")
    return errors, warnings

def get_main_menu():
    return {
        "keyboard": [
            ["📝 Отправить объявление", "ℹ️ Помощь"],
            ["📊 Статистика", "👤 Мой профиль"]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def admin_inline_buttons():
    return {
        "inline_keyboard": [
            [{"text": "📊 Статистика", "callback_data": "admin_stats"}],
            [{"text": "👥 Забаненные", "callback_data": "admin_banned"}],
            [{"text": "✍️ Написать юзеру", "callback_data": "admin_write"}],
            [{"text": "🔨 Забанить", "callback_data": "admin_ban"}],
            [{"text": "🔓 Разбанить", "callback_data": "admin_unban"}],
            [{"text": "📢 Рассылка", "callback_data": "admin_mailing"}]
        ]
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"status": "ok"})
    
    if 'callback_query' in data:
        callback = data['callback_query']
        user_id = callback['from']['id']
        message_id = callback['message']['message_id']
        chat_id = callback['message']['chat']['id']
        action = callback['data']
        if user_id != ADMIN_ID:
            send_telegram(user_id, "⛔ Нет прав!")
            return jsonify({"status": "ok"})
        if action == "admin_stats":
            cursor.execute('SELECT total_approved, total_rejected FROM stats')
            appr, rej = cursor.fetchone()
            text = f"📊 Статистика\n✅ {appr}\n❌ {rej}"
            edit_telegram(chat_id, message_id, text, admin_inline_buttons())
        elif action == "admin_banned":
            cursor.execute('SELECT id FROM users WHERE banned = 1')
            banned = cursor.fetchall()
            text = "🚫 Забаненные:\n" + "\n".join([str(b[0]) for b in banned]) if banned else "✅ Нет"
            edit_telegram(chat_id, message_id, text, admin_inline_buttons())
        elif action == "admin_write":
            edit_telegram(chat_id, message_id, "Введи: ID текст", admin_inline_buttons())
        elif action == "admin_ban":
            edit_telegram(chat_id, message_id, "Введи ID для бана:", admin_inline_buttons())
        elif action == "admin_unban":
            edit_telegram(chat_id, message_id, "Введи ID для разбана:", admin_inline_buttons())
        elif action == "admin_mailing":
            edit_telegram(chat_id, message_id, "Введи текст рассылки:", admin_inline_buttons())
        return jsonify({"status": "ok"})
    
    if 'message' not in data:
        return jsonify({"status": "ok"})
    
    message = data['message']
    user_id = message['from']['id']
    text = message.get('text', '')
    username = message['from'].get('username', 'нет юзернейма')
    
    if text == '/start':
        cursor.execute('INSERT OR IGNORE INTO users (id, banned) VALUES (?, 0)', (user_id,))
        conn.commit()
        send_telegram(user_id, "👋 Привет! Отправь объявление с зарплатой и телефоном", get_main_menu())
        return jsonify({"status": "ok"})
    
    cursor.execute('SELECT banned FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        send_telegram(user_id, "🚫 Ты забанен.", get_main_menu())
        return jsonify({"status": "ok"})
    
    if text in ["📝 Отправить объявление", "ℹ️ Помощь", "📊 Статистика", "👤 Мой профиль"]:
        if text == "📝 Отправить объявление":
            send_telegram(user_id, "📝 Напиши текст с зарплатой и телефоном", get_main_menu())
        elif text == "ℹ️ Помощь":
            send_telegram(user_id, "🤖 Бот для вакансий\n/start - начать\n/admin - админ-панель", get_main_menu())
        elif text == "📊 Статистика":
            cursor.execute('SELECT total_approved, total_rejected FROM stats')
            appr, rej = cursor.fetchone()
            send_telegram(user_id, f"📊 Статистика\n✅ {appr}\n❌ {rej}", get_main_menu())
        elif text == "👤 Мой профиль":
            send_telegram(user_id, f"👤 Профиль\n🆔 {user_id}\n👤 @{username}", get_main_menu())
        return jsonify({"status": "ok"})
    
    if text == '/admin' and user_id == ADMIN_ID:
        send_telegram(user_id, "⚙️ Админ-панель", admin_inline_buttons())
        return jsonify({"status": "ok"})
    
    if user_id == ADMIN_ID:
        if text.startswith('/ban '):
            target = int(text.split()[1])
            cursor.execute('UPDATE users SET banned = 1 WHERE id = ?', (target,))
            conn.commit()
            send_telegram(user_id, f"✅ {target} забанен", get_main_menu())
            return jsonify({"status": "ok"})
        if text.startswith('/unban '):
            target = int(text.split()[1])
            cursor.execute('UPDATE users SET banned = 0 WHERE id = ?', (target,))
            conn.commit()
            send_telegram(user_id, f"✅ {target} разбанен", get_main_menu())
            return jsonify({"status": "ok"})
        if text.startswith('/msg '):
            parts = text.split(maxsplit=2)
            if len(parts) == 3:
                try:
                    send_telegram(int(parts[1]), f"📩 От админа:\n{parts[2]}")
                    send_telegram(user_id, "✅ Отправлено", get_main_menu())
                except:
                    send_telegram(user_id, "❌ Ошибка", get_main_menu())
            return jsonify({"status": "ok"})
        if text.startswith('/mail '):
            mail_text = text[6:]
            cursor.execute('SELECT id FROM users')
            users = cursor.fetchall()
            count = 0
            for user in users:
                try:
                    send_telegram(user[0], f"📢 Рассылка\n\n{mail_text}")
                    count += 1
                except:
                    pass
            send_telegram(user_id, f"✅ Отправлено {count} пользователям", get_main_menu())
            return jsonify({"status": "ok"})
    
    errors, warnings = check_template(text)
    if errors:
        cursor.execute('UPDATE stats SET total_rejected = total_rejected + 1')
        conn.commit()
        send_telegram(user_id, "❌ Ошибки:\n" + "\n".join(errors), get_main_menu())
        return jsonify({"status": "ok"})
    
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
    app.run(host='0.0.0.0', port=8080)
