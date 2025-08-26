import os
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# === Zapis do pliku ===
def save_posts(posts, query, date):
    safe_query = query.replace(" ", "_")
    path = f"data/{safe_query}/{date.year}/{date.month:02d}/"
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{date.day:02d}.txt")

    existing_texts = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    existing_texts.add(data["text"].strip())
                except:
                    continue

    unique_posts = [p for p in posts if p["text"].strip() not in existing_texts]
    if not unique_posts:
        print(f"Brak nowych postów: {date.date()}")
        return

    with open(file_path, "a", encoding="utf-8") as f:
        for post in unique_posts:
            f.write(json.dumps(post, ensure_ascii=False) + "\n")

    print(f"Zapisano {len(unique_posts)} postów do: {file_path}")

# === Setup Selenium ===
def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    return webdriver.Chrome(options=options)

# === Scraper Instagram ===
def scrape_instagram(query, max_posts=10):
    url = f"https://www.instagram.com/explore/tags/{query.lower()}/"
    driver = init_driver()
    driver.get(url)
    time.sleep(5)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    posts = []
    articles = soup.find_all("article")
    for article in articles:
        text = article.get_text(strip=True)
        if text:
            posts.append({
                "platform": "Instagram",
                "text": text,
                "timestamp": str(datetime.utcnow())
            })
        if len(posts) >= max_posts:
            break

    return posts

# === Scraper Facebook (tylko dla publicznych wyszukiwań) ===
def scrape_facebook(query, max_posts=10):
    url = f"https://www.facebook.com/search/posts/?q={query}"
    driver = init_driver()
    driver.get(url)
    time.sleep(6)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    posts = []
    divs = soup.find_all("div")
    for div in divs:
        text = div.get_text(strip=True)
        if text and len(text) > 50:
            posts.append({
                "platform": "Facebook",
                "text": text,
                "timestamp": str(datetime.utcnow())
            })
        if len(posts) >= max_posts:
            break

    return posts

# === MAIN ===
if __name__ == "__main__":
    topics = ["Bitcoin", "Allegro", "Ethereum", "Zabka", "XTB"]
    for query in topics:
        print(f"\n🔍 IG + FB: Szukam postów o: {query}")
        posts_ig = scrape_instagram(query, max_posts=10)
        posts_fb = scrape_facebook(query, max_posts=10)

        now = datetime.utcnow()
        save_posts(posts_ig, query, now)
        save_posts(posts_fb, query, now)
