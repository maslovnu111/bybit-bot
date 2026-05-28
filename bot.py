import os
import json
import time
import re
import telebot
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Зчитуємо секретні токени з налаштувань GitHub
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TOKEN)
MEMORY_FILE = 'memory.json'

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {"coins": [], "news": []}
    return {"coins": [], "news": []}

def save_memory(data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def check_easy_earn(memory):
    print("Перевірка Easy Earn...")
    driver = get_browser()
    try:
        driver.get("https://www.bybit.com/uk-UA/earn/easy-earn/")
        time.sleep(12) # Даємо сторінці трохи більше часу на завантаження скриптів таблиць

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        found_items = []
        
        # Скануємо всі інформаційні блоки (рядки таблиць tr та блоки карток div)
        for tag in soup.find_all(['tr', 'div']):
            text = tag.get_text(separator=" ").strip()
            text = " ".join(text.split()) # Очищаємо від зайвих пробілів та переносів
            
            # Пропускаємо глобальні великі блоки сайту або занадто малі тексти
            if len(text) > 350 or len(text) < 10:
                continue
            
            # Шукаємо всі згадки відсотків за допомогою Regex (наприклад: 555.00% або 777.00%)
            pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', text)
            if pct_matches:
                # Перетворюємо знайдені текстові відсотки на дробові числа
                pct_floats = [float(m) for m in pct_matches]
                highest_pct = max(pct_floats) # Беремо найбільший відсоток з блоку
                
                # Нова умова: перевіряємо, чи відсоток більший за 100%
                if highest_pct > 100:
                    # Шукаємо тикер монети (від 3 до 6 великих літер, наприклад: USDT, XUSD, AERO)
                    coin_match = re.search(r'\b([A-Z]{3,6})\b', text)
                    coin_name = coin_match.group(1) if coin_match else "Знайдено"
                    
                    # Намагаємось красиво витягнути тривалість
                    duration = "Не вказано"
                    if "дн" in text.lower() or "d" in text.lower():
                        dur_match = re.search(r'(\d+\s*(?:Дн\.|D|днів|дня))', text, re.IGNORECASE)
                        if dur_match:
                            duration = dur_match.group(1)
                    elif "безстроковий" in text.lower():
                        duration = "Безстроковий"
                    elif "фіксований" in text.lower():
                        duration = "Фіксований"
                        
                    found_items.append({
                        'coin': coin_name,
                        'pct': highest_pct,
                        'duration': duration,
                        'full_text': text
                    })
        
        # Фільтруємо дублікати (оскільки великі div блоки включають у себе менші div)
        unique_coins = {}
        for item in found_items:
            # Створюємо СТАБІЛЬНИЙ ідентифікатор монети без врахування таймера зворотного відліку
            coin_id = f"{item['coin']}_{item['pct']}"
            if coin_id not in unique_coins:
                unique_coins[coin_id] = item
            else:
                # Якщо монета вже є, залишаємо варіант з коротшим описом (він зазвичай точніший)
                if len(item['full_text']) < len(unique_coins[coin_id]['full_text']):
                    unique_coins[coin_id] = item
        
        # Надсилаємо сповіщення в Telegram
        for coin_id, item in unique_coins.items():
            if coin_id not in memory["coins"]:
                memory["coins"].append(coin_id)
                
                msg = f"🔥 **Знайдено новий стейкінг > 100%!**\n\n" \
                      f"🪙 Монета: **{item['coin']}**\n" \
                      f"📈 Макс. відсоток: **{item['pct']}% APR**\n" \
                      f"⏳ Тривалість: {item['duration']}\n\n" \
                      f"🔗 Посилання: https://www.bybit.com/uk-UA/earn/easy-earn/"
                
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                print(f"Надіслано сповіщення про монету: {coin_id}")
                
    except Exception as e:
        print(f"Помилка Easy Earn: {e}")
    finally:
        driver.quit()

def check_announcements(memory):
    print("Перевірка новин...")
    driver = get_browser()
    try:
        driver.get("https://announcements.bybit.com/uk-UA/?category=&page=1")
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all('a')
        
        for link in links:
            title = link.get_text(strip=True)
            href = link.get('href')
            
            if 'apr' in title.lower():
                if title not in memory["news"]:
                    memory["news"].append(title)
                    
                    full_link = href if href.startswith('http') else f"https://announcements.bybit.com{href}"
                    msg = f"📰 **Нова новина з APR!**\n\n{title}\n\nЧитати: {full_link}"
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                    print(f"Надіслано сповіщення про новину: {title}")
    except Exception as e:
        print(f"Помилка новин: {e}")
    finally:
        driver.quit()

if __name__ == '__main__':
    current_memory = load_memory()
    
    check_easy_earn(current_memory)
    check_announcements(current_memory)
    
    save_memory(current_memory)
    print("Роботу завершено, пам'ять оновлено.")
