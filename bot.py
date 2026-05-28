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
    print("=== ЗАПУСК ПЕРЕВІРКИ EASY EARN ===")
    driver = get_browser()
    try:
        driver.get("https://www.bybit.com/uk-UA/earn/easy-earn/")
        time.sleep(8) 

        # ЕМУЛЯЦІЯ СКРОЛІНГУ: прокручуємо вниз і вгору для активації лінивого завантаження карток
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(4)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Вирізаємо технічні приховані блоки
        for tech in soup(["script", "style", "noscript", "textarea", "svg", "form", "head"]):
            tech.decompose()
        
        percent_strings = soup.find_all(string=lambda t: t and "%" in t)
        print(f"[ДЕБАГ] Видимих елементів із знаком '%' знайдено: {len(percent_strings)}")
        
        found_items = []

        for s in percent_strings:
            parent_box = s.parent
            if not parent_box:
                continue
            
            # СКЛЕЮВАННЯ ТЕГІВ: беремо текст батька та дідуся, щоб з'єднати розділені цифри та значок %
            combined_text = parent_box.get_text(separator=" ")
            if parent_box.parent:
                combined_text += " " + parent_box.parent.get_text(separator=" ")
                
            clean_str = " ".join(combined_text.split())
            
            # Шукаємо числа біля відсотка
            pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', clean_str)
            if not pct_matches:
                continue

            for m in pct_matches:
                try:
                    pct = float(m)
                    
                    if pct > 100:
                        current_element = s
                        coin_name = "Невідома монета"
                        duration = "Гнучкий / Фіксований"
                        
                        # Підіймаємося вгору по структурі картки для збору контексту
                        for _ in range(7):
                            if not current_element.parent:
                                break
                            current_element = current_element.parent
                            parent_text = " ".join(current_element.get_text(separator=" ").split())
                            
                            # Визначаємо тикер монети
                            if coin_name == "Невідома монета":
                                uppercase_words = re.findall(r'\b([A-Z]{3,6})\b', parent_text)
                                exclude = {
                                    'APR', 'BYBIT', 'EARN', 'NEW', 'VIP', 'ROI', 'UTC', 'PROMO', 
                                    'CRAZY', 'USER', 'ALL', 'THURSDAY', 'BOOST', 'DAY', 'USD', 'EUR'
                                }
                                valid_coins = [w for w in uppercase_words if w not in exclude]
                                if valid_coins:
                                    coin_name = valid_coins[0]
                            
                            # Визначаємо тривалість
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
                        
                        # РЕЗЕРВНИЙ ЗАХИСТ: Якщо регулярний вираз пропустив назву, перевіряємо по списку відомих монет
                        if coin_name == "Невідома монета":
                            # Отримуємо фінальний повний текст картки/блоку
                            full_block_text = " ".join(current_element.get_text(separator=" ").split())
                            for kc in ['USDT', 'XUSD', 'USDC', 'BTC', 'ETH', 'MNT', 'AERO', 'SOL']:
                                if kc in full_block_text:
                                    coin_name = kc
                                    break
                        
                        found_items.append({
                            'coin': coin_name,
                            'pct': pct,
                            'duration': duration
                        })
                except ValueError:
                    continue

        # Фільтрація дублікатів
        unique_coins = {}
        for item in found_items:
            coin_id = f"{item['coin']}_{item['pct']}"
            unique_coins[coin_id] = item

        print(f"[ДЕБАГ] Після очищення знайдено реальних пулів > 100%: {len(unique_coins)}")

        # Надсилання сповіщень
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
