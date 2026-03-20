"""
wiki_queue.txt 에서 N개 꺼내 Wikipedia API로 본문 수집 → sources.jsonl 저장
"""
import json
import sys
import time
from pathlib import Path

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import DATA_DIR, CONFIG_FILE as _CF

QUEUE_FILE = DATA_DIR / "wiki_queue.txt"
DONE_FILE = DATA_DIR / "wiki_done.txt"
CONFIG_FILE = _CF

WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKI_API = "https://en.wikipedia.org/w/api.php"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def queue_size() -> int:
    if not QUEUE_FILE.exists():
        return 0
    with open(QUEUE_FILE, encoding="utf-8") as f:
        return sum(1 for l in f if l.strip())


def pop_from_queue(n: int) -> list[tuple[str, str]]:
    """queue 앞에서 n개 꺼내고 파일에서 삭제. [(page_id, title), ...]"""
    if not QUEUE_FILE.exists():
        return []
    with open(QUEUE_FILE, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    taken, remaining = lines[:n], lines[n:]
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(remaining) + ("\n" if remaining else ""))
    result = []
    for line in taken:
        parts = line.split("|", 1)
        if len(parts) == 2:
            result.append((parts[0], parts[1]))
    return result


def append_done(page_id: str, title: str):
    DONE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DONE_FILE, "a", encoding="utf-8") as f:
        f.write(f"{page_id}|{title}\n")


def fetch_wiki_summary(title: str) -> dict | None:
    encoded = requests.utils.quote(title.replace(" ", "_"))
    try:
        resp = requests.get(f"{WIKI_REST}/{encoded}", timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[fetcher] 오류 ({title}): {e}")
        return None


def fetch_full_content(page_id: str) -> str:
    params = {
        "action": "query",
        "pageids": page_id,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "format": "json",
    }
    try:
        resp = requests.get(WIKI_API, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        page = data["query"]["pages"].get(page_id, {})
        return page.get("extract", "")[:8000]
    except Exception as e:
        print(f"[fetcher] 본문 수집 오류 ({page_id}): {e}")
        return ""


def fetch_sources(n: int, log=print) -> int:
    """
    queue에서 n개 꺼내 Wikipedia 수집 후 sources.jsonl 저장.
    반환값: 성공적으로 저장된 수
    """
    sys.path.insert(0, str(ROOT))
    from storage import source_exists, add_source
    from crawler.build_queue import build_queue

    cfg = load_config()

    # queue 부족 시 자동 보충
    if queue_size() < n:
        log("[fetcher] 큐 소진 → build_queue 자동 호출")
        build_queue(log=log)

    items = pop_from_queue(n)
    if not items:
        log("[fetcher] 가져올 항목 없음")
        return 0

    saved = 0
    for page_id, title in items:
        log(f"[fetcher] 수집 중: {title} (id={page_id})")

        if source_exists(page_id):
            log(f"[fetcher] 이미 존재, 스킵: {title}")
            append_done(page_id, title)
            continue

        summary_data = fetch_wiki_summary(title)
        if not summary_data:
            log(f"[fetcher] 수집 실패: {title}")
            continue

        summary = summary_data.get("extract", "")[:1000]
        content = fetch_full_content(page_id)

        add_source(page_id, title, summary, content)
        append_done(page_id, title)
        saved += 1
        log(f"[fetcher] 저장 완료: {title}")
        time.sleep(0.5)

    log(f"[fetcher] {saved}/{len(items)}개 저장 완료")
    return saved


if __name__ == "__main__":
    fetch_sources(n=10)
