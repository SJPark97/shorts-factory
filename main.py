"""
메인 파이프라인 오케스트레이션
실행 순서: 크롤링 → 대본 생성 → TTS → Kling 영상 → FFmpeg 합성 → YouTube 업로드
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "config.json"
sys.path.insert(0, str(ROOT))


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(log=print):
    cfg = load_config()
    n = cfg["upload"].get("daily_upload_limit", 3)
    channels = cfg.get("channels", [])
    active_channels = [c for c in channels if c.get("active", True)]
    if not active_channels:
        active_channels = [{"id": "default", "style": "default"}]

    log("=" * 50)
    log(f"[main] 파이프라인 시작 | 일일 업로드: {n}개 | 채널 수: {len(active_channels)}")
    log("=" * 50)

    # ── Phase 1: Wikipedia 수집 ─────────────────────────────────────
    log("\n[Phase 1] Wikipedia 소스 수집")
    from crawler.fetcher import fetch_sources
    fetched = fetch_sources(n=n, log=log)
    log(f"[Phase 1] 완료: {fetched}개 수집")

    # ── Phase 2: 대본 생성 (채널별) ────────────────────────────────
    log("\n[Phase 2] 대본 생성")
    from script.generator import generate_scripts
    total_scripts = 0
    for channel in active_channels:
        ch_id = channel.get("id", "default")
        style = channel.get("style", "default")
        log(f"[Phase 2] 채널={ch_id}, 스타일={style}")
        count = generate_scripts(n=n, channel_id=ch_id, style=style, log=log)
        total_scripts += count
    log(f"[Phase 2] 완료: {total_scripts}개 대본 생성")

    # ── Phase 3-1: TTS 변환 ────────────────────────────────────────
    log("\n[Phase 3-1] TTS 변환")
    from video.tts import run_tts_batch
    tts_done = run_tts_batch(n=total_scripts or n, log=log)
    log(f"[Phase 3-1] 완료: {tts_done}개 TTS 변환")

    # ── Phase 3-2: Kling 영상 생성 ────────────────────────────────
    log("\n[Phase 3-2] Kling 영상 생성")
    from video.kling import run_kling_batch
    kling_done = run_kling_batch(n=tts_done or n, log=log)
    log(f"[Phase 3-2] 완료: {kling_done}개 영상 생성")

    # ── Phase 3-3: FFmpeg 합성 ─────────────────────────────────────
    log("\n[Phase 3-3] FFmpeg 합성")
    from video.composer import run_compose_batch
    composed = run_compose_batch(n=kling_done or n, log=log)
    log(f"[Phase 3-3] 완료: {composed}개 합성")

    # ── Phase 4: YouTube 업로드 ────────────────────────────────────
    log("\n[Phase 4] YouTube 업로드")
    from uploader.youtube import run_upload_batch
    uploaded = run_upload_batch(n=composed or n, log=log)
    log(f"[Phase 4] 완료: {uploaded}개 업로드")

    log("\n" + "=" * 50)
    log(f"[main] 파이프라인 완료")
    log(f"  수집: {fetched} | 대본: {total_scripts} | TTS: {tts_done}"
        f" | 영상: {kling_done} | 합성: {composed} | 업로드: {uploaded}")
    log("=" * 50)


if __name__ == "__main__":
    run_pipeline()
