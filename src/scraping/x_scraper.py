import os
import json
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from twikit import Client

# Słowa kluczowe związane z inwestowaniem
INVESTMENT_KEYWORDS = [
    "akcje", "giełda", "inwestor", "inwestycja", "notowania",
    "kurs", "spółka", "fundusz", "dividenda", "dividend",
    "ticker", "share", "stock", "earnings", "IPO",
    "wykres", "trading", "broker", "forex", "crypto",
    "bitcoin", "ethereum", "altcoin",
    "price", "market", "buy", "sell", "hold",
    "portfolio", "wallet", "exchange", "mining", "blockchain",
    "cena", "rynek", "kupić", "sprzedać", "trzymać",
    "portfel", "portfel kryptowalut", "giełda kryptowalut", "kopanie", "blockchain"
]


def contains_investment_keywords(text):
    text = text.lower()
    return any(kw in text for kw in INVESTMENT_KEYWORDS)


def save_posts(posts, topic, date):
    safe_query = topic.replace(" ", "_")
    path = os.path.join("data", safe_query, f"{date.year}", f"{date.month:02d}")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{date.day:02d}.txt")

    existing = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    existing.add(json.loads(line)["text"].strip())
                except:
                    pass

    new_posts = [p for p in posts if p["text"].strip() not in existing]

    if not new_posts:
        print(f"📭 Brak nowych wpisów do zapisania dla {topic} ({date.date()})")
        return

    with open(file_path, "a", encoding="utf-8") as f:
        for post in new_posts:
            f.write(json.dumps(post, ensure_ascii=False) + "\n")

    print(f"💾 Zapisano {len(new_posts)} wpisów dla {topic}: {file_path}")


def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Plik {config_path} nie istnieje. Utwórz plik z kluczem 'twitter' zawierającym 'x_username', 'x_password', 'x_client_id', 'x_client_secret' i opcjonalnie 'cookies'.")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    twitter_config = config.get("twitter", {})
    required_keys = ["x_username", "x_password", "x_client_id", "x_client_secret"]
    for key in required_keys:
        if key not in twitter_config:
            raise KeyError(f"Brak klucza '{key}' w pliku config.json w sekcji 'twitter'.")

    return (
        twitter_config["x_username"],
        twitter_config["x_password"],
        twitter_config.get("cookies", []),
        twitter_config["x_client_id"],
        twitter_config["x_client_secret"]
    )


def login_to_x_selenium(driver, username, password, cookies=None):
    driver.get("https://x.com/login")
    print("🔒 Próba logowania do X (Selenium)...")
    try:
        if cookies:
            print("🍪 Próba użycia ciasteczek do logowania...")
            driver.get("https://x.com")
            for cookie in cookies:
                driver.add_cookie(cookie)
            driver.refresh()
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='SearchBox_Search_Input']"))
                )
                print("🔒 Zalogowano pomyślnie za pomocą ciasteczek!")
                return
            except:
                print("⚠️ Ciasteczka nie działały, próbuję standardowego logowania...")
                driver.get("https://x.com/login")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
        )
        username_field = driver.find_element(By.CSS_SELECTOR, "input[autocomplete='username']")
        username_field.send_keys(username)
        print("🔑 Wprowadzono nazwę użytkownika")

        next_button = driver.find_element(By.CSS_SELECTOR,
                                          "button[role='button'] span, button[data-testid='LoginForm_Login_Button']")
        next_button.click()
        print("➡️ Kliknięto 'Next'")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='current-password']"))
        )
        password_field = driver.find_element(By.CSS_SELECTOR, "input[autocomplete='current-password']")
        password_field.send_keys(password)
        print("🔑 Wprowadzono hasło")

        login_button = driver.find_element(By.CSS_SELECTOR,
                                           "button[role='button'] span, button[data-testid='LoginForm_Login_Button']")
        login_button.click()
        print("➡️ Kliknięto 'Log in'")

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='verification_code']"))
            )
            verification_code = input("🔐 Wprowadź kod weryfikacyjny (2FA): ")
            verification_field = driver.find_element(By.CSS_SELECTOR, "input[name='verification_code']")
            verification_field.send_keys(verification_code)
            verify_button = driver.find_element(By.CSS_SELECTOR,
                                                "button[data-testid='ocfVerifyButton'], button[role='button']")
            verify_button.click()
            print("➡️ Kliknięto 'Verify'")
        except:
            print("ℹ️ Brak dodatkowego kroku weryfikacji")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='SearchBox_Search_Input']"))
        )
        print("🔒 Zalogowano pomyślnie!")
    except Exception as e:
        print(f"⚠️ Błąd podczas logowania (Selenium): {str(e)}")
        raise


def fetch_comments_selenium(driver, tweet_url, parent_tweet_text):
    comments = []
    try:
        print(f"💬 Otwieram stronę tweeta: {tweet_url}")
        driver.get(tweet_url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "article"))
        )

        previous_comment_count = 0
        for i in range(20):
            soup = BeautifulSoup(driver.page_source, "html.parser")
            current_comment_count = len(soup.find_all("article", attrs={"role": "article"}))
            print(f"🔄 Scroll komentarzy {i + 1}/20 dla tweeta, komentarzy: {current_comment_count}")

            if current_comment_count == previous_comment_count and i > 0:
                print(f"ℹ️ Brak nowych komentarzy po scrollu {i + 1}, przerywam")
                break
            previous_comment_count = current_comment_count

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2 + (0.1 * current_comment_count))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        comment_articles = soup.find_all("article", attrs={"role": "article"})
        for article in comment_articles:
            comment_div = article.find("div", attrs={"data-testid": "tweetText"})
            if comment_div:
                text = comment_div.get_text(separator=" ", strip=True)
                if text and contains_investment_keywords(text):
                    comments.append({
                        "platform": "X-Selenium-Comment",
                        "text": text,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "parent_tweet": parent_tweet_text[:50]
                    })
                    print(f"💬 Komentarz: {text[:50]}... Matches keywords: True")
        print(f"💬 Znaleziono {len(comments)} komentarzy dla tweeta")
    except Exception as e:
        print(f"⚠️ Błąd podczas pobierania komentarzy dla {tweet_url}: {str(e)}")
    return comments


def fetch_tweets_hybrid(query, max_scrolls=100, max_retries=3, max_wait_time=300):
    tweets = []
    driver = None
    try:
        # Wczytaj dane logowania z config.json
        x_username, x_password, cookies, x_client_id, x_client_secret = load_config()

        # Inicjalizacja Twikit
        client = Client('en-US')
        print("🔒 Logowanie do X (Twikit)...")
        client.login(auth_info_1=x_username, auth_info_2=x_password)
        print("🔒 Zalogowano pomyślnie (Twikit)!")

        # Wyszukiwanie tweetów za pomocą Twikit
        date_ranges = [
            ("2025-01-01", "2025-02-01"),
            ("2025-02-01", "2025-03-01"),
            ("2025-03-01", "2025-04-01"),
            ("2025-04-01", "2025-05-01"),
            ("2025-05-01", "2025-06-01"),
            ("2025-06-01", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        ]

        for start_date, end_date in date_ranges:
            print(f"📅 Wyszukiwanie Twikit dla zakresu: {start_date} do {end_date}")
            search_query = f"{query} since:{start_date} until:{end_date} -is:retweet"
            try:
                twikit_tweets = client.search_tweet(query=search_query, product='Latest', count=1000)
                for tweet in twikit_tweets:
                    if contains_investment_keywords(tweet.text):
                        tweets.append({
                            "platform": "X-Twikit",
                            "text": tweet.text,
                            "timestamp": tweet.created_at,
                            "tweet_id": tweet.id
                        })
                        print(
                            f"📝 Tweet (Twikit): {tweet.text[:50]}... Matches keywords: True (Created: {tweet.created_at})")
            except Exception as e:
                print(f"⚠️ Błąd Twikit dla {query} w zakresie {start_date} - {end_date}: {str(e)}")
                continue

        # Inicjalizacja Selenium dla komentarzy
        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--memory-pressure-level=none")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-images")
        options.add_argument("--blink-settings=imagesEnabled=false")

        for attempt in range(1, max_retries + 1):
            try:
                driver_path = ChromeDriverManager(chrome_type=ChromeType.GOOGLE,
                                                  driver_version="138.0.7204.94").install()
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=options)
                print(f"🌐 Inicjalizacja przeglądarki dla {query} (próba {attempt}/{max_retries})")
                login_to_x_selenium(driver, x_username, x_password, cookies)
                break
            except Exception as e:
                print(f"⚠️ Błąd podczas inicjalizacji Selenium dla {query} (próba {attempt}/{max_retries}): {str(e)}")
                if driver:
                    driver.quit()
                    driver = None
                if attempt == max_retries:
                    print(f"❌ Nie udało się zainicjalizować Selenium dla {query}")
                    return tweets

        # Pobierz komentarze dla tweetów z Twikit
        for tweet in tweets[:50]:  # Ogranicz do 50 tweetów, aby uniknąć przeciążenia
            if tweet["platform"] == "X-Twikit":
                tweet_url = f"https://x.com/i/status/{tweet['tweet_id']}"
                comments = fetch_comments_selenium(driver, tweet_url, tweet["text"])
                tweets.extend(comments)

        # Dodatkowe wyszukiwanie Selenium dla tweetów
        for start_date, end_date in date_ranges:
            print(f"📅 Wyszukiwanie Selenium dla zakresu: {start_date} do {end_date}")
            search_query = f"{query} since:{start_date} until:{end_date}"
            search_url = f"https://x.com/search?q={search_query}&f=live"
            print(f"🌐 Ładowanie strony: {search_url}")
            driver.get(search_url)

            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
                print(f"✅ Strona załadowana dla {query}")
            except Exception as e:
                print(f"⚠️ Błąd podczas ładowania strony dla {query}: {str(e)}")
                continue

            start_time = time.time()
            previous_article_count = 0
            for i in range(max_scrolls):
                soup = BeautifulSoup(driver.page_source, "html.parser")
                current_article_count = len(soup.find_all("article", attrs={"role": "article"}))
                print(f"🔄 Scroll {i + 1}/{max_scrolls} dla {query}, artykułów: {current_article_count}")

                if current_article_count == previous_article_count and i > 0:
                    print(f"ℹ️ Brak nowych artykułów po scrollu {i + 1}, przerywam")
                    break
                previous_article_count = current_article_count

                articles = soup.find_all("article", attrs={"role": "article"})
                for article in articles:
                    tweet_div = article.find("div", attrs={"data-testid": "tweetText"})
                    if tweet_div:
                        text = tweet_div.get_text(separator=" ", strip=True)
                        if contains_investment_keywords(text):
                            tweets.append({
                                "platform": "X-Selenium",
                                "text": text,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            print(f"📝 Tweet (Selenium): {text[:50]}... Matches keywords: True")

                            link_element = article.find("a", href=True)
                            if link_element and "/status/" in link_element["href"]:
                                tweet_url = f"https://x.com{link_element['href']}"
                                comments = fetch_comments_selenium(driver, tweet_url, text)
                                tweets.extend(comments)

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2 + (0.05 * current_article_count))
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "article"))
                    )
                except:
                    print(f"⚠️ Błąd podczas scrollowania dla {query} na scrollu {i + 1}")
                    break

                if time.time() - start_time > max_wait_time:
                    print(f"⏰ Przekroczono maksymalny czas oczekiwania ({max_wait_time}s) dla {query}")
                    break

        return tweets
    except Exception as e:
        print(f"❌ Błąd ogólny dla {query}: {str(e)}")
        return tweets
    finally:
        if driver:
            driver.quit()
            print("🌐 Zamknięto przeglądarkę Selenium")


def fetch_all_posts_hybrid(topics):
    print()
    for topic in topics:
        print(f"🔍 Pobieram tweety i komentarze dla: {topic}")
        tweets = fetch_tweets_hybrid(topic)
        save_posts(tweets, topic, datetime.now(timezone.utc))
        print(f"📄 Znaleziono {len(tweets)} wpisów (tweety + komentarze) dla {topic}")


if __name__ == "__main__":
    topics = ["Bitcoin"]  # Testuj z jednym tematem
    fetch_all_posts_hybrid(topics)