import os
import json
import requests
import telebot

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TOKEN)
MEMORY_FILE = 'memory.json'

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except: return {"coins": [], "news": []}
    return {"coins": [], "news": []}

def save_memory(data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_easy_earn(memory):
    print("=== ЗАПУСК ПЕРЕВІРКИ API EASY EARN ===")
    url = "https://api2.bybit.com/v2/public/marketing/easy-earn/product-list?page=1&pageSize=50"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        found = 0
        if 'result' in data and 'list' in data['result']:
            for item in data['result']['list']:
                # Дивимось на APR (тут воно в десяткових дробах, наприклад 0.20 = 20%)
                apr = float(item.get('apr', 0)) * 100
                coin = item.get('currency', 'UNKNOWN')
                
                if apr > 100:
                    found += 1
                    coin_id = f"{coin}_{apr}"
                    if coin_id not in memory["coins"]:
                        memory["coins"].append(coin_id)
                        msg = f"🔥 **Знайдено новий стейкінг > 100%!**\n\n🪙 Монета: {coin}\n📈 APR: {apr}%\n🔗 https://www.bybit.com/uk-UA/earn/easy-earn/"
                        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
        print(f"[УСПІХ] Знайдено пулів > 100%: {found}")
    except Exception as e:
        print(f"[ПОМИЛКА] API: {e}")

if __name__ == '__main__':
    current_memory = load_memory()
    check_easy_earn(current_memory)
    save_memory(current_memory)
    print("=== РОБОТУ ЗАВЕРШЕНО ===")
