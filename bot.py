from flask import Flask, request, jsonify
import requests
import re
import sqlite3
import os

app = Flask(__name__)

# ======== ТВОИ ДАННЫЕ (ЗАМЕНИ) ========
TOKEN = "8980303731:AAGSbV7t9E49_nVsjmT4QcWALWYzHkz0_rA"
CHANNEL_ID = -1004336857767   # 👈 ЗДЕСЬ ДОЛЖЕН БЫТЬ ТВОЙ ID КАНАЛА С МИНУСОМ!
ADMIN_ID = 1912704977          # 👈 ЗДЕСЬ ТВОЙ ID ТЕЛЕГРАМА!
# ======================================

# База данных
conn = sqlite3.connect('db.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, banned INTEGER DEFAULT 0)')
conn.commit()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=data)
    except:
        pass

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"status": "ok"})
    
    msg = data['message']
    user_id = msg['from']['id']
    text = msg.get('text', '')
    username = msg['from'].get('username', 'no_username')
    
    # /start
    if text == '/start':
        cursor.execute('INSERT OR IGNORE INTO users (id, banned) VALUES (?, 0)', (user_id,))
        conn.commit()
        send_message(user_id, "👋 Привет! Бот работает. Отправь объявление с зарплатой и телефоном.")
        return jsonify({"status": "ok"})
    
    # Проверка бана
    cursor.execute('SELECT banned FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    if result and result[1] == 1:
        send_message(user_id, "🚫 Ты забанен.")
        return jsonify({"status": "ok"})
    
    # Модерация (проверка шаблона)
    errors = []
    if not re.search(r'\d+\s*[/\-]\s*\d+', text):
        errors.append("Зарплата (например, 500/1)")
    if not re.search(r'(\+7|8)\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text):
        errors.append("Номер телефона")
    
    if errors:
        send_message(user_id, "❌ Ошибка! Нет:\n" + "\n".join(errors))
        return jsonify({"status": "ok"})
    
    # Отправка в канал
    try:
        send_message(CHANNEL_ID, f"📢 ВАКАНСИЯ\n\n{text}\n\n👤 @{username}")
        send_message(user_id, "✅ Опубликовано в канале!")
    except Exception as e:
        send_message(user_id, f"❌ Ошибка канала: {str(e)}")
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
