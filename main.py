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


def run_video_pipeline(n: int, log=print):
    """
    영상 제작 파이프라인 (Phase 1~3-3).
    중단된 상태가 있으면 해당 단계부터 재개.
    업로드는 포함하지 않음 — 채널별로 별도 실행.
    """
    from storage import get_pending_scripts, get_tts_ready_scripts, get_video_ready_scripts

    log("=" * 50)
    log(f"[main] 영상 제작 시작 | 목표: {n}개")
    log("=" * 50)

    fetched = total_scripts = tts_done = kling_done = composed = 0

    # ── Phase 3-3: 합성 대기 중인 것 먼저 처리 ───────────────────────
    video_ready = get_video_ready_scripts(limit=n)
    if video_ready:
        log(f"\n[재개] video_ready {len(video_ready)}개 — 합성부터 시작")
        from video.composer import run_compose_batch
        composed += run_compose_batch(n=len(video_ready), log=log)
        log(f"[Phase 3-3] 완료: {composed}개 합성")

    # ── Phase 3-2: 클립 생성 대기 중인 것 처리 ───────────────────────
    tts_ready = get_tts_ready_scripts(limit=n)
    if tts_ready:
        log(f"\n[재개] tts_done {len(tts_ready)}개 — 클립 생성부터 시작")
        from video.kling import run_kling_batch
        kling_done += run_kling_batch(n=len(tts_ready), log=log)
        log(f"[Phase 3-2] 완료: {kling_done}개 영상 생성")
        from video.composer import run_compose_batch
        composed += run_compose_batch(n=kling_done, log=log)
        log(f"[Phase 3-3] 완료: {composed}개 합성")

    # ── Phase 3-1: TTS 대기 중인 것 처리 ─────────────────────────────
    pending = get_pending_scripts(limit=n)
    if pending:
        log(f"\n[재개] pending {len(pending)}개 — TTS부터 시작")
        from video.tts import run_tts_batch
        tts_done += run_tts_batch(n=len(pending), log=log)
        log(f"[Phase 3-1] 완료: {tts_done}개 TTS 변환")
        from video.kling import run_kling_batch
        kling_done += run_kling_batch(n=tts_done, log=log)
        log(f"[Phase 3-2] 완료: {kling_done}개 영상 생성")
        from video.composer import run_compose_batch
        composed += run_compose_batch(n=kling_done, log=log)
        log(f"[Phase 3-3] 완료: {composed}개 합성")

    # ── 목표 수량만큼 채워야 하면 처음부터 ───────────────────────────
    remaining = n - composed
    if remaining > 0:
        log(f"\n[Phase 1] Wikipedia 소스 수집 ({remaining}개 필요)")
        from crawler.fetcher import fetch_sources
        fetched = fetch_sources(n=remaining, log=log)
        log(f"[Phase 1] 완료: {fetched}개 수집")

        log("\n[Phase 2] 대본 생성")
        from script.generator import generate_scripts
        total_scripts = generate_scripts(n=remaining, log=log)
        log(f"[Phase 2] 완료: {total_scripts}개 대본 생성")

        log("\n[Phase 3-1] TTS 변환")
        from video.tts import run_tts_batch
        new_tts = run_tts_batch(n=total_scripts or remaining, log=log)
        tts_done += new_tts
        log(f"[Phase 3-1] 완료: {new_tts}개 TTS 변환")

        log("\n[Phase 3-2] Kling 영상 생성")
        from video.kling import run_kling_batch
        new_kling = run_kling_batch(n=new_tts or remaining, log=log)
        kling_done += new_kling
        log(f"[Phase 3-2] 완료: {new_kling}개 영상 생성")

        log("\n[Phase 3-3] FFmpeg 합성")
        from video.composer import run_compose_batch
        new_composed = run_compose_batch(n=new_kling or remaining, log=log)
        composed += new_composed
        log(f"[Phase 3-3] 완료: {new_composed}개 합성")

    log("\n" + "=" * 50)
    log(f"[main] 영상 제작 완료")
    log(f"  수집: {fetched} | 대본: {total_scripts} | TTS: {tts_done}"
        f" | 영상: {kling_done} | 합성: {composed}")
    log("=" * 50)
    return composed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=3, help="제작할 영상 수")
    args = parser.parse_args()
    run_video_pipeline(n=args.n)
