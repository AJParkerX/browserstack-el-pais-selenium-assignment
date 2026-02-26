import argparse
import os
import re
import time
import json
import threading
import requests
from collections import Counter
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from dotenv import load_dotenv
load_dotenv()

# credentials & constants 

BROWSERSTACK_USERNAME = os.environ.get("BROWSERSTACK_USERNAME", "YOUR_BS_USERNAME")
BROWSERSTACK_ACCESS_KEY = os.environ.get("BROWSERSTACK_ACCESS_KEY", "YOUR_BS_ACCESS_KEY")
BS_HUB_URL = f"https://{BROWSERSTACK_USERNAME}:{BROWSERSTACK_ACCESS_KEY}@hub.browserstack.com/wd/hub"

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY")

IMAGES_DIR = "article_images"
TARGET_URL  = "https://elpais.com"
OPINION_URL = "https://elpais.com/opinion/"

# browser/device matrix 

BS_CAPABILITIES = [
    {
        "browserName": "Chrome",
        "browserVersion": "latest",
        "os": "Windows",
        "osVersion": "11",
        "sessionName": "Chrome Win11",
    },
    {
        "browserName": "Firefox",
        "browserVersion": "latest",
        "os": "OS X",
        "osVersion": "Ventura",
        "sessionName": "Firefox macOS",
    },
    {
        "browserName": "Edge",
        "browserVersion": "latest",
        "os": "Windows",
        "osVersion": "10",
        "sessionName": "Edge Win10",
    },
    {
        "browserName": "Chrome",
        "deviceName": "Samsung Galaxy S23",
        "osVersion": "13.0",
        "realMobile": "true",
        "sessionName": "Samsung Galaxy S23",
    },
    {
        "browserName": "Safari",
        "deviceName": "iPhone 14",
        "osVersion": "16",
        "realMobile": "true",
        "sessionName": "iPhone 14 Safari",
    },
]


# drivers

def get_local_driver():
    opts = ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=es")
    opts.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=opts)
    return driver


def get_browserstack_driver(cap: dict):
    bs_options = {
        "userName": BROWSERSTACK_USERNAME,
        "accessKey": BROWSERSTACK_ACCESS_KEY,
        "sessionName": cap.get("sessionName", "El País Test"),
        "buildName": "ElPais_Opinion_Scraper",
        "projectName": "ElPais BrowserStack Assignment",
        "debug": True,
        "consoleLogs": "info",
        "networkLogs": True,
    }

    options = ChromeOptions()
    browser = cap.get("browserName", "Chrome").lower()

    if browser == "firefox":
        options = FirefoxOptions()
        options.set_capability("bstack:options", bs_options)
        for key, value in cap.items():
            if key not in ("sessionName",):
                options.set_capability(key, value)
        driver = webdriver.Remote(command_executor=BS_HUB_URL, options=options)
        return driver

    options.set_capability("bstack:options", bs_options)
    for key, value in cap.items():
        if key not in ("sessionName",):
            options.set_capability(key, value)

    driver = webdriver.Remote(command_executor=BS_HUB_URL, options=options)
    return driver


# cookie banner 

def dismiss_consent(driver):
    selectors = [
        "button#didomi-notice-agree-button",
        "button[id*='accept']",
        "button[class*='accept']",
        "a[id*='accept']",
    ]
    for sel in selectors:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn.click()
            time.sleep(1)
            return
        except Exception:
            pass


# scraping 

def scrape_opinion_articles(driver) -> list[dict]:
    driver.get(OPINION_URL)
    dismiss_consent(driver)
    time.sleep(2)

    article_links = []
    candidates = driver.find_elements(
        By.CSS_SELECTOR,
        "article a, h2 a, h3 a, .c_t a, .headline a"
    )
    seen = set()
    for el in candidates:
        href = el.get_attribute("href") or ""
        if (href and href not in seen and "/opinion/" in href
            and href.startswith("http")
            and re.search(r'/opinion/\d{4}-\d{2}-\d{2}/', href)):
            seen.add(href)
            article_links.append(href)
        if len(article_links) == 5:
            break

    if len(article_links) < 5:
        fallback = driver.find_elements(By.CSS_SELECTOR, "main a[href*='/opinion/']")
        for el in fallback:
            href = el.get_attribute("href") or ""
            if href and href not in seen and href.startswith("http"):
                seen.add(href)
                article_links.append(href)
            if len(article_links) == 5:
                break

    articles = []
    for idx, url in enumerate(article_links[:5], 1):
        print(f"\n[{idx}/5] Fetching: {url}")
        driver.get(url)
        time.sleep(2)

        title = ""
        for sel in ["h1.a_t", "h1.article-title", "h1[class*='title']", "h1"]:
            try:
                title = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                if title:
                    break
            except Exception:
                pass

        content = ""
        for sel in [
            "div.a_c p", "div[class*='article-body'] p",
            "div[class*='content'] p", "article p"
        ]:
            paras = driver.find_elements(By.CSS_SELECTOR, sel)
            if paras:
                content = "\n".join(p.text.strip() for p in paras if p.text.strip())
                break

        image_path = None
        for sel in [
            "figure.a_ph img", "figure img", ".article-header img",
            "picture img", "img[class*='cover']", "img[class*='article']"
        ]:
            try:
                img_el = driver.find_element(By.CSS_SELECTOR, sel)
                img_src = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""
                if img_src.startswith("http"):
                    image_path = download_image(img_src, idx)
                    break
            except Exception:
                pass

        articles.append({
            "index": idx,
            "url": url,
            "title": title,
            "content": content,
            "image_path": image_path,
        })

        print(f"  Title   : {title}")
        print(f"  Content : {content[:200]}{'…' if len(content) > 200 else ''}")
        print(f"  Image   : {image_path or 'Not found'}")

    return articles


# image download

def download_image(url: str, idx: int) -> str | None:
    os.makedirs(IMAGES_DIR, exist_ok=True)
    ext = url.split("?")[0].rsplit(".", 1)[-1] if "." in url else "jpg"
    ext = ext if ext in ("jpg", "jpeg", "png", "webp", "gif") else "jpg"
    path = os.path.join(IMAGES_DIR, f"article_{idx}.{ext}")
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        return path
    except Exception as e:
        print(f"  [WARN] Image download failed: {e}")
        return None


# translation

def translate_title(spanish_title: str) -> str:
    if RAPIDAPI_KEY == "YOUR_RAPIDAPI_KEY":
        print("  [WARN] No RAPIDAPI_KEY set – returning mock translation.")
        return f"[TRANSLATED] {spanish_title}"

    url = "https://deep-translate1.p.rapidapi.com/language/translate/v2"
    payload = {"q": spanish_title, "source": "es", "target": "en"}
    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "deep-translate1.p.rapidapi.com",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        result = resp.json()["data"]["translations"]["translatedText"]
        return result[0] if isinstance(result, list) else result
    except Exception as e:
        print(f"  [WARN] Translation failed: {e}")
        return spanish_title


# word frequency 

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "its", "as", "by", "from", "that", "this",
    "are", "was", "be", "has", "have", "had", "not", "no", "he", "she",
    "they", "we", "i", "you", "his", "her", "their", "our", "my",
}

def analyze_headers(translated_titles: list[str]) -> dict[str, int]:
    word_counts: Counter = Counter()
    for title in translated_titles:
        words = re.findall(r"[a-zA-Z']+", title.lower())
        words = [w.strip("'") for w in words if w not in STOPWORDS and len(w) > 2]
        word_counts.update(words)
    repeated = {word: count for word, count in word_counts.items() if count > 2}
    return repeated


# main test flow

def run_test(driver, session_label: str = "local"):
    print(f"\n{'='*60}")
    print(f"  SESSION: {session_label}")
    print(f"{'='*60}")

    try:
        driver.get(TARGET_URL)
        dismiss_consent(driver)
        lang = driver.find_element(By.TAG_NAME, "html").get_attribute("lang") or ""
        print(f"\n[1] Page language attribute: '{lang}'")
        assert "es" in lang.lower(), f"Expected Spanish page, got lang='{lang}'"

        print("\n[2] Scraping Opinion section …")
        articles = scrape_opinion_articles(driver)

        print("\n[3] Translating titles …")
        translated_titles = []
        for art in articles:
            translated = translate_title(art["title"])
            art["translated_title"] = translated
            translated_titles.append(translated)
            print(f"  ES: {art['title']}")
            print(f"  EN: {translated}\n")

        print("\n[4] Repeated words across translated headers (count > 2):")
        repeated = analyze_headers(translated_titles)
        if repeated:
            for word, count in sorted(repeated.items(), key=lambda x: -x[1]):
                print(f"  '{word}' → {count}x")
        else:
            print("  No words repeated more than twice.")

        summary = {
            "session": session_label,
            "page_lang": lang,
            "articles": [
                {
                    "index": a["index"],
                    "title_es": a["title"],
                    "title_en": a.get("translated_title", ""),
                    "url": a["url"],
                    "image_saved": a["image_path"],
                    "content_preview": a["content"][:300],
                }
                for a in articles
            ],
            "repeated_words": repeated,
        }
        print(f"\n[SUMMARY]\n{json.dumps(summary, ensure_ascii=False, indent=2)}")

        try:
            driver.execute_script(
                'browserstack_executor: {"action": "setSessionStatus",'
                '"arguments": {"status":"passed","reason":"All steps completed"}}'
            )
        except Exception:
            pass

    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        try:
            driver.execute_script(
                f'browserstack_executor: {{"action": "setSessionStatus",'
                f'"arguments": {{"status":"failed","reason":"{str(exc)[:100]}"}}}}'
            )
        except Exception:
            pass
        raise
    finally:
        driver.quit()


# browserstack parallel runner

def run_browserstack_thread(cap: dict):
    label = cap.get("sessionName", "BS Session")
    print(f"\n[BS] Starting thread: {label}")
    driver = get_browserstack_driver(cap)
    run_test(driver, session_label=label)


def run_browserstack_parallel():
    threads = []
    for cap in BS_CAPABILITIES:
        t = threading.Thread(target=run_browserstack_thread, args=(cap,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\n✅  All BrowserStack parallel sessions completed.")


# entry point

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="El País BrowserStack Test")
    parser.add_argument("--local", action="store_true", help="Run locally with Chrome")
    parser.add_argument("--browserstack", action="store_true", help="Run on BrowserStack")
    args = parser.parse_args()

    if args.local or (not args.local and not args.browserstack):
        driver = get_local_driver()
        run_test(driver, session_label="Local Chrome")

    if args.browserstack:
        run_browserstack_parallel()
