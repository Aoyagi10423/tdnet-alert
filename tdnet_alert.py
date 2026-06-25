import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

BASE_URL = "https://www.release.tdnet.info/inbs/"

WATCH_RULES = {
    "業績予想修正": [
        "業績予想の修正",
        "業績予想及び配当予想の修正",
        "業績予想と実績値との差異",
    ],
    "自己株式取得": [
        "自己株式取得",
        "自己株式の取得",
    ],
    "TOB・公開買付け": [
        "公開買付け",
        "公開買付",
        "TOB",
        "ＭＢＯ",
        "MBO",
    ],
}

EXCLUDE_KEYWORDS = [
    "自己株式の取得状況および取得終了に関するお知らせ",
    "自己株式の取得状況及び取得終了に関するお知らせ",
]


def classify(title):
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return None

    for category, keywords in WATCH_RULES.items():
        if any(k in title for k in keywords):
            return category

    return None


def fetch_tdnet_today():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d")
    url = f"{BASE_URL}I_list_001_{today}.html"

    print(f"取得URL: {url}")

    res = requests.get(url, timeout=15)
    res.raise_for_status()
    res.encoding = "utf-8"

    soup = BeautifulSoup(res.text, "html.parser")
    docs = []

    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 4:
            continue

        disclosed_time = cells[0]
        code = cells[1]
        company = cells[2]
        title = cells[3]

        print(f"取得タイトル: {code} {company} {title}")

        category = classify(title)
        if not category:
            continue

        link = row.find("a", href=re.compile(r"\.pdf$"))
        if not link:
            continue

        href = link.get("href", "")
        pdf_url = BASE_URL + href.lstrip("./")

        docs.append({
            "category": category,
            "time": disclosed_time,
            "code": code,
            "company": company,
            "title": title,
            "pdf_url": pdf_url,
        })

    return docs


def notify_slack(doc):
    text = f"""【TDnet検知：{doc["category"]}】
{doc["title"]}

コード：{doc["code"]}
会社名：{doc["company"]}
開示時刻：{doc["time"]}
PDF：{doc["pdf_url"]}"""

    res = requests.post(WEBHOOK_URL, json={"text": text}, timeout=15)
    res.raise_for_status()


def main():
    docs = fetch_tdnet_today()

    new_count = 0
    for doc in docs:
        notify_slack(doc)
        new_count += 1
        print("通知:", doc["category"], doc["code"], doc["company"], doc["title"])

    print(f"完了：通知 {new_count} 件")


if __name__ == "__main__":
    main()
