import os
import json
import time
import telebot
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Зчитуємо секретні токени, які ми сховаємо в налаштуваннях GitHub
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

bot = telebot.TeleBot(TOKEN)
MEMORY_FILE = 'memory.json'

# Функція для завантаження історії з файлу memory.json
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"coins": [], "news": []}

# Функція для збереження історії у файл
def save_memory(data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Налаштування браузера для роботи на серверах GitHub (обов'язково Headless)
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
        time.sleep(10) # Чекаємо завантаження сторінки

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        elements = soup.find_all(string=lambda t: t and "%" in t)
        
        for el in elements:
            try:
                clean_text = el.replace('%', '').replace('+', '').strip()
                percentage = float(clean_text)
                
                if percentage > 50:
                    parent = el.parent.parent.parent
                    text_content = parent.get_text(separator=" ").strip()
                    coin_id = f"{text_content}_{percentage}"
                    
                    # Перевіряємо, чи є ця монета в пам'яті
                    if coin_id not in memory["coins"]:
                        memory["coins"].append(coin_id) # Додаємо в пам'ять
                        
                        msg = f"🔥 **Знайдено новий стейкінг > 50%!**\nВідсоток: {percentage}%\nДеталі: {text_content}\nhttps://www.bybit.com/uk-UA/earn/easy-earn/"
                        bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                        print(f"Надіслано сповіщення про монету: {coin_id}")
            except ValueError:
                continue
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
                    memory["news"].append(title) # Додаємо в пам'ять
                    
                    full_link = href if href.startswith('http') else f"https://announcements.bybit.com{href}"
                    msg = f"📰 **Нова новина з APR!**\n\n{title}\n\nЧитати: {full_link}"
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                    print(f"Надіслано сповіщення про новину: {title}")
    except Exception as e:
        print(f"Помилка новин: {e}")
    finally:
        driver.quit()

if __name__ == '__main__':
    # Головний запуск програми
    current_memory = load_memory()
    
    check_easy_earn(current_memory)
    check_announcements(current_memory)
    
    save_memory(current_memory)
    print("Роботу завершено, пам'ять оновлено.")
