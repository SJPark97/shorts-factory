"""
JSONL 파일 기반 공용 스토리지 모듈
- data/sources.jsonl  : 수집된 Wikipedia 소스
- data/scripts.jsonl  : 생성된 대본
"""
import json
from pathlib import Path
from datetime import datetime

from paths import DATA_DIR

SOURCES_FILE = DATA_DIR / "sources.jsonl"
SCRIPTS_FILE = DATA_DIR / "scripts.jsonl"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─── 범용 JSONL 헬퍼 ──────────────────────────────────────────────

def read_all(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def write_all(path: Path, records: list[dict]):
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_record(path: Path, record: dict):
    _ensure_dir()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─── Sources ──────────────────────────────────────────────────────

def get_all_sources() -> list[dict]:
    return read_all(SOURCES_FILE)


def source_exists(page_id: str) -> bool:
    return any(s["page_id"] == page_id for s in get_all_sources())


def add_source(page_id: str, title: str, summary: str, content: str) -> dict:
    record = {
        "id": _next_id(SOURCES_FILE),
        "page_id": page_id,
        "title": title,
        "summary": summary,
        "content": content,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    append_record(SOURCES_FILE, record)
    return record


def update_source_status(page_id: str, status: str):
    records = get_all_sources()
    for r in records:
        if r["page_id"] == page_id:
            r["status"] = status
    write_all(SOURCES_FILE, records)


def get_pending_sources(limit: int = 10) -> list[dict]:
    return [s for s in get_all_sources() if s.get("status") == "pending"][:limit]


# ─── Scripts ──────────────────────────────────────────────────────

def get_all_scripts() -> list[dict]:
    return read_all(SCRIPTS_FILE)


def add_script(source_id: int, channel_id: str, title: str,
               body: str, hashtags: list[str]) -> dict:
    record = {
        "id": _next_id(SCRIPTS_FILE),
        "source_id": source_id,
        "channel_id": channel_id,
        "title": title,
        "body": body,
        "hashtags": hashtags,
        "tts_path": None,
        "video_path": None,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    append_record(SCRIPTS_FILE, record)
    return record


def update_script(script_id: int, **kwargs):
    records = get_all_scripts()
    for r in records:
        if r["id"] == script_id:
            r.update(kwargs)
    write_all(SCRIPTS_FILE, records)


def get_pending_scripts(limit: int = 10) -> list[dict]:
    return [s for s in get_all_scripts() if s.get("status") == "pending"][:limit]


def get_tts_ready_scripts(limit: int = 10) -> list[dict]:
    return [s for s in get_all_scripts()
            if s.get("status") == "tts_done"][:limit]


def get_video_ready_scripts(limit: int = 10) -> list[dict]:
    return [s for s in get_all_scripts()
            if s.get("status") == "video_done"][:limit]


# ─── 내부 헬퍼 ────────────────────────────────────────────────────

def _next_id(path: Path) -> int:
    records = read_all(path)
    if not records:
        return 1
    return max(r.get("id", 0) for r in records) + 1
