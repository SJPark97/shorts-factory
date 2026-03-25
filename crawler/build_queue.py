"""
1회성 초기 작업: Wikipedia 역사 카테고리 재귀 탐색 → wiki_queue.txt 생성
"""
import json
import sys
import time
from pathlib import Path

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import APP_DIR, DATA_DIR, CONFIG_FILE as _CF

QUEUE_FILE = DATA_DIR / "wiki_queue.txt"
DONE_FILE = DATA_DIR / "wiki_done.txt"
CONFIG_FILE = _CF

WIKI_API = "https://en.wikipedia.org/w/api.php"
DEFAULT_CATEGORIES = [
    "History_by_period",
    "Wars",
    "Ancient_civilizations",
    "Empires",
]


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_done_set() -> set:
    if not DONE_FILE.exists():
        return set()
    with open(DONE_FILE, encoding="utf-8") as f:
        return {line.split("|")[0].strip() for line in f if line.strip()}


def load_queue_set() -> set:
    if not QUEUE_FILE.exists():
        return set()
    with open(QUEUE_FILE, encoding="utf-8") as f:
        return {line.split("|")[0].strip() for line in f if line.strip()}


HEADERS = {"User-Agent": "ShortsBot/1.0 (educational project; python-requests)"}


def get_category_members(category: str, cmtype: str = "page|subcat") -> list[dict]:
    """Wikipedia API로 카테고리 멤버 가져오기"""
    members = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": 500,
        "cmtype": cmtype,
        "format": "json",
    }
    while True:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        members.extend(data["query"]["categorymembers"])
        if "continue" not in data:
            break
        params["cmcontinue"] = data["continue"]["cmcontinue"]
        time.sleep(0.5)
    return members


def crawl_category(category: str, depth: int, max_depth: int,
                   done_set: set, queue_set: set,
                   new_pages: list, log=print, limit: int = 100):
    if depth > max_depth:
        return
    if len(new_pages) >= limit:
        return

    log(f"[build_queue] 탐색 중: {category} (깊이 {depth})")
    try:
        members = get_category_members(category)
    except Exception as e:
        log(f"[build_queue] 오류: {category} → {e}")
        return

    for m in members:
        if len(new_pages) >= limit:
            break
        ns = m.get("ns", 0)
        page_id = str(m["pageid"]) if "pageid" in m else None

        if ns == 0 and page_id:  # 일반 문서
            if page_id not in done_set and page_id not in queue_set:
                title = m["title"].replace("|", " ")
                new_pages.append(f"{page_id}|{title}")
                queue_set.add(page_id)

        elif ns == 14:  # 하위 카테고리
            subcat = m["title"].replace("Category:", "")
            crawl_category(subcat, depth + 1, max_depth,
                           done_set, queue_set, new_pages, log, limit)
        time.sleep(0.1)


def build_queue(categories: list[str] | None = None,
                max_depth: int | None = None,
                refill_size: int | None = None,
                log=print) -> int:
    """
    Wikipedia 카테고리 재귀 탐색 후 wiki_queue.txt 에 추가.
    반환값: 새로 추가된 문서 수
    """
    cfg = load_config()
    if categories is None:
        categories = cfg["crawl"].get("categories", DEFAULT_CATEGORIES)
    if max_depth is None:
        max_depth = cfg["crawl"].get("recursion_depth", 3)
    if refill_size is None:
        refill_size = cfg["crawl"].get("queue_refill_size", 100)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    done_set = load_done_set()
    queue_set = load_queue_set()
    new_pages: list[str] = []

    for cat in categories:
        if len(new_pages) >= refill_size:
            break
        crawl_category(cat, depth=1, max_depth=max_depth,
                       done_set=done_set, queue_set=queue_set,
                       new_pages=new_pages, log=log,
                       limit=refill_size)

    if new_pages:
        with open(QUEUE_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(new_pages) + "\n")
        log(f"[build_queue] {len(new_pages)}개 문서 추가됨 → {QUEUE_FILE}")
    else:
        log("[build_queue] 새로 추가할 문서 없음")

    return len(new_pages)


if __name__ == "__main__":
    count = build_queue()
    print(f"완료: {count}개 추가")
