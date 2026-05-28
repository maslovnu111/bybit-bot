import os
import json
import time
import re
import telebot
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

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
    # МАГІЧНА КУЛЯ: Новий режим headless, який не розпізнається Cloudflare/Akamai
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Вимикаємо прапорці автоматизації
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Ми ПРИБРАЛИ жорсткий User-Agent, щоб --headless=new згенерував свій, ідеально валідний!
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Глибока інжекція (CDP) залишається для страховки
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """
    })
    return driver

def check_easy_earn(memory):
    print("=== ЗАПУСК ПЕРЕВІРКИ EASY EARN ===")
    driver = get_browser()
    try:
        driver.get("https://www.bybit.com/uk-UA/earn/easy-earn/")
        print("[ДЕБАГ] Очікуємо 12 секунд для первинного завантаження та проходження перевірки Cloudflare...")
        time.sleep(12) 

        # ФІЗИЧНА ІМІТАЦІЯ КЛАВІАТУРИ: Натискаємо Page Down, щоб Bybit повірив, що це людина
        print("[ДЕБАГ] Імітуємо натискання клавіші Page Down...")
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            for i in range(6):
                body.send_keys(Keys.PAGE_DOWN)
                time.sleep(2) # Пауза між натисканнями
                print(f"[ДЕБАГ] Скрол {i+1}/6 виконано")
        except Exception as e:
            print(f"[ДЕБАГ] Не вдалося використати клавіатуру, помилка: {e}")
        
        # Повертаємось трохи вгору, щоб переконатись, що таблиця в зоні видимості
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        for tech in soup(["script", "style", "noscript", "textarea", "svg", "form", "head"]):
            tech.decompose()
        
        percent_strings = soup.find_all(string=lambda t: t and "%" in t)
        print(f"[ДЕБАГ] Видимих елементів із знаком '%' знайдено: {len(percent_strings)}")
        
        found_items = []

        for s in percent_strings:
            parent_box = s.parent
            if not parent_box:
                continue
            
            combined_text = parent_box.get_text(separator=" ")
            if parent_box.parent:
                combined_text += " " + parent_box.parent.get_text(separator=" ")
                
            clean_str = " ".join(combined_text.split())
            
            pct_matches = re.findall(r'(\d+(?:[.,]\d+)?)\s*%', clean_str)
            if not pct_matches:
                continue

            for m in pct_matches:
                try:
                    clean_num = m.replace(',', '.')
                    pct = float(clean_num)
                    
                    if pct > 0:
                        print(f"[ДЕБАГ] Знайдено відсоток {pct}% у тексті: '{clean_str[:60]}...'")
                    
                    if pct > 100:
                        current_element = s
                        coin_name = "Шукаємо..."
                        duration = "Гнучкий / Фіксований"
                        
                        for _ in range(12): # Збільшив глибину пошуку картки
                            if not current_element.parent:
                                break
                            current_element = current_element.parent
                            parent_text = " ".join(current_element.get_text(separator=" ").split())
                            
                            if coin_name == "Шукаємо...":
                                uppercase_words = re.findall(r'\b([A-Z]{2,6})\b', parent_text)
                                exclude = {
                                    'APR', 'BYBIT', 'EARN', 'NEW', 'VIP', 'ROI', 'UTC', 'PROMO', 
                                    'CRAZY', 'USER', 'ALL', 'THURSDAY', 'BOOST', 'DAY', 'USD', 'EUR', 'MAX'
                                }
                                valid_coins = [w for w in uppercase_words if w not in exclude]
                                if valid_coins:
                                    coin_name = valid_coins[0]
                            
                            if duration == "Гнучкий / Фіксований":
                                if "безстроковий" in parent_text.lower() and "фіксований" in parent_text.lower():
                                    duration = "Гнучкий / Фіксований"
                                elif "безстроковий" in parent_text.lower() or "гнучк" in parent_text.lower():
                                    duration = "Гнучкий"
                                elif "фіксований" in parent_text.lower():
                                    duration = "Фіксований"
                                elif "дн" in parent_text.lower() or "d" in parent_text.lower():
                                    dur_match = re.search(r'(\d+\s*(?:Дн\.|D|днів|дня|Дн))', parent_text, re.IGNORECASE)
                                    if dur_match:
                                        duration = dur_match.group(1)
                        
                        if coin_name == "Шукаємо...":
                            coin_name = "Невідома монета"
                            
                        found_items.append({
                            'coin': coin_name,
                            'pct': pct,
                            'duration': duration
                        })
                except ValueError:
                    continue

        unique_coins = {}
        for item in found_items:
            coin_id = f"{item['coin']}_{item['pct']}"
            unique_coins[coin_id] = item

        print(f"[ДЕБАГ] Після очищення знайдено реальних пулів > 100%: {len(unique_coins)}")

        for coin_id, item in unique_coins.items():
            if coin_id not in memory["coins"]:
                memory["coins"].append(coin_id)
                
                msg = f"🔥 **Знайдено новий стейкінг > 100%!**\n\n" \
                      f"🪙 Монета: **{item['coin']}**\n" \
                      f"📈 Макс. відсоток: **{item['pct']}% APR**\n" \
                      f"⏳ Тривалість: {item['duration']}\n\n" \
                      f"🔗 Посилання: https://www.bybit.com/uk-UA/earn/easy-earn/"
                
                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                print(f"[УСПІХ] Надіслано сповіщення про монету: {coin_id}")
                
    except Exception as e:
        print(f"[ПОМИЛКА] В Easy Earn: {e}")
    finally:
        driver.quit()

def check_announcements(memory):
    print("=== ЗАПУСК ПЕРЕВІРКИ НОВИН ===")
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
                    print(f"[УСПІХ] Надіслано сповіщення про новину: {title}")
    except Exception as e:
        print(f"[ПОМИЛКА] В новинах: {e}")
    finally:
        driver.quit()

if __name__ == '__main__':
    current_memory = load_memory()
    check_easy_earn(current_memory)
    check_announcements(current_memory)
    save_memory(current_memory)
    print("=== РОБОТУ ЗАВЕРШЕНО ===")
