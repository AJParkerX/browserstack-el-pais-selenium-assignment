# El País Opinion Scraper

Scrapes the first 5 articles from the El País Opinion section, translates the titles to English, and runs the whole thing across 5 browsers/devices on BrowserStack in parallel.

---

## Requirements

```
pip install -r requirements.txt
```

You'll also need ChromeDriver installed locally and matching your Chrome version.

---

## Setup

Create a `.env` file in the project folder:

```
BROWSERSTACK_USERNAME=your_username
BROWSERSTACK_ACCESS_KEY=your_access_key
RAPIDAPI_KEY=your_rapidapi_key
```

BrowserStack credentials are on your [Automate dashboard](https://automate.browserstack.com).

For the translation API, sign up at [RapidAPI](https://rapidapi.com/gatzuma/api/deep-translate1) and subscribe to the Deep Translate free tier (500 requests/day).

---

## Running

Local:
```bash
python elpais_scrapper.py --local
```

BrowserStack (5 parallel sessions):
```bash
python elpais_scrapper.py --browserstack
```

Both:
```bash
python elpais_scrapper.py --local --browserstack
```

---

## What it does

1. Opens El País and checks the page language is Spanish
2. Navigates to the Opinion section and scrapes the first 5 articles — title, body text, and cover image
3. Saves cover images to an `article_images/` folder
4. Translates each title from Spanish to English via the RapidAPI Deep Translate API
5. Counts any words that appear more than twice across all translated titles

---

## Browser matrix

| Browser | OS / Device |
|---------|-------------|
| Chrome latest | Windows 11 |
| Firefox latest | macOS Ventura |
| Edge latest | Windows 10 |
| Chrome (real device) | Samsung Galaxy S23 |
| Safari (real device) | iPhone 14 |

---