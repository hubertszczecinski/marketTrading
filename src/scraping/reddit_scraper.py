import os
import json
from datetime import datetime, timedelta, timezone
import praw

with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

reddit_config = config["reddit"]

# Konfiguracja Reddit API
reddit = praw.Reddit(
    client_id=reddit_config["client_id"],
    client_secret=reddit_config["client_secret"],
    user_agent=reddit_config["user_agent"]
)

# Subreddity finansowe i inwestycyjne
FINANCE_SUBREDDITS = [
    "stocks", "investing", "CryptoCurrency", "wallstreetbets",
    "StockMarket", "pennystocks", "options", "dividends",
    "Bitcoin", "Ethereum", "CryptoMarkets", "altcoin",
    "finance", "economics", "personalfinance", "Forex",
    "Trading", "Daytrading", "inwestowanie", "Polska"
]

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

def build_simple_query(base_terms):
    base_parts = []
    for term in base_terms:
        term_lower = term.lower()
        term_variants = list(set([
            term, term_lower, term.upper(), term.capitalize()
        ]))
        if "zabka" in term_lower:
            term_variants += ["Żabka", "żabka", "ŻABKA"]

        variants_query = " OR ".join(f'"{v}"' for v in term_variants)
        base_parts.append(f"({variants_query})")

    return " OR ".join(base_parts)


def text_contains_investment_keywords(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in INVESTMENT_KEYWORDS)

def fetch_and_save_posts(topics, days_back=90, limit_total=1000):
    now = datetime.now(timezone.utc)

    for topic in topics:
        safe_topic = topic.replace(" ", "_")
        print(f"\n🔎 Reddit | Temat: {topic}")
        query = build_simple_query([topic])
        posts = []

        for subreddit_name in FINANCE_SUBREDDITS:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                gen = subreddit.search(
                    query=query,
                    sort="new",
                    time_filter="year",
                    limit=limit_total // len(FINANCE_SUBREDDITS)
                )

                for post in gen:
                    # ⏱️ Pomijamy posty starsze niż days_back dni
                    if post.created_utc < (now - timedelta(days=days_back)).timestamp():
                        continue

                    full_text = (post.title or "") + "\n" + (post.selftext or "")

                    # Dodatkowe filtrowanie dla mniej finansowych subredditów
                    if subreddit_name not in [
                        "stocks", "CryptoCurrency", "Bitcoin", "Ethereum",
                        "CryptoMarkets", "altcoin", "inwestowanie"
                    ]:
                        if not text_contains_investment_keywords(full_text):
                            continue

                    post_date = datetime.fromtimestamp(post.created_utc, timezone.utc)
                    save_path = os.path.join("data", safe_topic, f"{post_date.year}", f"{post_date.month:02d}")
                    os.makedirs(save_path, exist_ok=True)
                    filename = f"{post_date.day:02d}.txt"

                    post_json = {
                        "platform": "Reddit",
                        "text": full_text.strip(),
                        "timestamp": post_date.isoformat(),
                        "subreddit": post.subreddit.display_name,
                        "title": post.title,
                        "url": post.url
                    }

                    with open(os.path.join(save_path, filename), "a", encoding="utf-8") as f:
                        f.write(json.dumps(post_json, ensure_ascii=False) + "\n")

                    posts.append(post_json)

            except Exception as e:
                print(f"⚠️ Błąd dla subreddit '{subreddit_name}': {e}")

        print(f"Zapisano {len(posts)} postów dla tematu: '{topic}'")

if __name__ == "__main__":
    topics = [
        "Bitcoin", "Ethereum", "Litecoin",
        "Tesla", "Apple", "Microsoft", "Amazon", "Google",
        "CD Projekt", "Allegro", "XTB", "PZU", "zabka"
    ]
    fetch_and_save_posts(topics=topics, days_back=365, limit_total=1000)
