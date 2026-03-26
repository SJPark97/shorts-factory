"""
Phase 2: sources.jsonl 에서 pending 소스 꺼내 LLM으로 대본 생성 → scripts.jsonl 저장
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import CONFIG_FILE

# 채널 스타일별 프롬프트 템플릿
STYLE_PROMPTS = {
    "dramatic": (
        "Write a dramatic, emotional YouTube Shorts script about the following historical topic. "
        "Use vivid storytelling and build tension. Make it feel like a movie narrator."
    ),
    "quiz": (
        "Write a YouTube Shorts script as a fun quiz format about the following historical topic. "
        "Start with a surprising question, reveal the answer dramatically, then give 2-3 fascinating facts."
    ),
    "timeline": (
        "Write a YouTube Shorts script as a clear timeline about the following historical topic. "
        "Use 'First... Then... Finally...' structure. Keep it fast-paced and factual."
    ),
    "default": (
        "Write an engaging YouTube Shorts script about the following historical topic. "
        "Hook the viewer in the first 3 seconds. Keep it concise and fascinating."
    ),
}

SCRIPT_FORMAT = """
Output ONLY a JSON object with this exact structure (no markdown, no extra text):
{{
  "title": "Short punchy title for the video (max 60 chars)",
  "body": "The full narration script ({duration} seconds when read aloud, ~{words} words). No stage directions.",
  "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}
"""


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _words_for_duration(seconds: int) -> int:
    """평균 낭독 속도 130 단어/분 기준"""
    return int(seconds * 130 / 60)


def generate_with_claude(api_key: str, prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def generate_with_openai(api_key: str, prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return resp.choices[0].message.content


def build_prompt(source: dict, style: str, duration_sec: int) -> str:
    style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS["default"])
    words = _words_for_duration(duration_sec)
    format_instruction = SCRIPT_FORMAT.format(duration=duration_sec, words=words)

    return (
        f"{style_instruction}\n\n"
        f"Topic: {source['title']}\n\n"
        f"Background information:\n{source['summary']}\n\n"
        f"{format_instruction}"
    )


def parse_script_response(raw: str) -> dict:
    """LLM 응답에서 JSON 파싱"""
    raw = raw.strip()
    # 마크다운 코드블록 제거
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(raw)


def generate_scripts(n: int = None, channel_id: str = "default",
                     style: str = "default", log=print) -> int:
    """
    pending 소스 n개에 대해 대본 생성 후 scripts.jsonl 저장.
    n=None 이면 config의 daily_upload_limit 사용.
    반환값: 생성된 대본 수
    """
    from storage import get_pending_sources, update_source_status, add_script

    cfg = load_config()
    if n is None:
        n = cfg["upload"].get("daily_upload_limit", 3)

    provider = cfg["api"].get("llm_provider", "claude")
    api_key = cfg["api"].get("llm_api_key", "")
    duration_sec = cfg["video"].get("target_duration_sec", 90)

    if not api_key:
        log(f"[generator] 오류: LLM API 키가 설정되지 않았습니다 (provider={provider})")
        return 0

    sources = get_pending_sources(limit=n)
    if not sources:
        log("[generator] 처리할 pending 소스 없음")
        return 0

    generated = 0
    for source in sources:
        log(f"[generator] 대본 생성 중: {source['title']}")
        prompt = build_prompt(source, style, duration_sec)

        try:
            if provider == "claude":
                raw = generate_with_claude(api_key, prompt)
            elif provider == "openai":
                raw = generate_with_openai(api_key, prompt)
            else:
                log(f"[generator] 알 수 없는 provider: {provider}")
                continue

            parsed = parse_script_response(raw)
            title = parsed.get("title", source["title"])
            body = parsed.get("body", "")
            hashtags = parsed.get("hashtags", [])

            if not body:
                log(f"[generator] 빈 대본 생성됨, 스킵: {source['title']}")
                continue

            add_script(
                source_id=source["id"],
                channel_id=channel_id,
                title=title,
                body=body,
                hashtags=hashtags,
            )
            update_source_status(source["page_id"], "done")
            generated += 1
            log(f"[generator] 저장 완료: {title}")

        except json.JSONDecodeError as e:
            log(f"[generator] JSON 파싱 오류 ({source['title']}): {e}")
        except Exception as e:
            log(f"[generator] 오류 ({source['title']}): {e}")

    log(f"[generator] {generated}/{len(sources)}개 대본 생성 완료")
    return generated


if __name__ == "__main__":
    generate_scripts()
