"""
API 호출 없이 전체 파이프라인 흐름 검증 스크립트
mock 대상: LLM, TTS, Kling API, YouTube 업로드, FFmpeg
"""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

MOCK_SCRIPT_JSON = json.dumps({
    "title": "Test Title",
    "body": "This is a test body. It has multiple sentences. Testing pipeline flow.",
    "hashtags": ["test", "history", "shorts"],
})


def make_dummy_audio(path: Path):
    """최소한의 유효한 MP3 헤더 (무음 파일)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    # ID3 태그 없는 최소 MP3 프레임 (128kbps)
    path.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 413)


def make_dummy_video(path: Path):
    """빈 바이너리 파일 (FFmpeg mock이므로 내용 불필요)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 1024)


def run():
    print("=" * 55)
    print("[TEST] API mock 파이프라인 검증 시작")
    print("=" * 55)

    # ── Phase 1: Wikipedia 수집 ────────────────────────────────
    print("\n[Phase 1] 소스 수집 (실제 Wikipedia 호출)")
    from crawler.fetcher import fetch_sources
    fetched = fetch_sources(n=1, log=print)
    print(f"[Phase 1] 완료: {fetched}개 수집\n")

    # ── Phase 2: 대본 생성 (LLM mock) ─────────────────────────
    print("[Phase 2] 대본 생성 (LLM mock)")
    with patch("script.generator.generate_with_openai", return_value=MOCK_SCRIPT_JSON), \
         patch("script.generator.generate_with_claude", return_value=MOCK_SCRIPT_JSON):
        from script.generator import generate_scripts
        scripts_done = generate_scripts(n=1, log=print)
    print(f"[Phase 2] 완료: {scripts_done}개 대본 생성\n")

    # ── Phase 3-1: TTS (mock) ─────────────────────────────────
    print("[Phase 3-1] TTS 변환 (mock)")
    def fake_tts_openai(api_key, text, voice, model, out_path):
        make_dummy_audio(out_path)

    def fake_tts_elevenlabs(api_key, text, voice_id, out_path):
        make_dummy_audio(out_path)

    with patch("video.tts.tts_openai", side_effect=fake_tts_openai), \
         patch("video.tts.tts_elevenlabs", side_effect=fake_tts_elevenlabs):
        from video.tts import run_tts_batch
        tts_done = run_tts_batch(n=scripts_done or 1, log=print)
    print(f"[Phase 3-1] 완료: {tts_done}개 TTS 변환\n")

    # ── Phase 3-2: Kling 영상 생성 (mock) ─────────────────────
    print("[Phase 3-2] Kling 영상 생성 (mock, TTS 30초 기준)")
    _task_counter = {"n": 0}

    def fake_create_task(prompt, cfg, log=print):
        _task_counter["n"] += 1
        return f"mock_task_{_task_counter['n']}"

    def fake_check_task(task_id, cfg):
        return "succeed", "http://mock.url/video.mp4"

    def fake_download_video(url, out_path, log=print):
        make_dummy_video(out_path)

    with patch("video.kling.create_video_task", side_effect=fake_create_task), \
         patch("video.kling.check_task", side_effect=fake_check_task), \
         patch("video.kling.download_video", side_effect=fake_download_video), \
         patch("video.kling.get_audio_duration", return_value=30.0):
        from video.kling import run_kling_batch
        kling_done = run_kling_batch(n=tts_done or 1, log=print)
    print(f"[Phase 3-2] 완료: {kling_done}개 영상 생성\n")

    # ── Phase 3-3: FFmpeg 합성 (mock) ─────────────────────────
    print("[Phase 3-3] FFmpeg 합성 (mock)")
    def fake_compose_video(video_path, audio_path, srt_path, out_path, log=print, **kwargs):
        make_dummy_video(out_path)

    with patch("video.composer.compose_video", side_effect=fake_compose_video), \
         patch("video.composer.get_audio_duration", return_value=10.0):
        from video.composer import run_compose_batch
        composed = run_compose_batch(n=kling_done or 1, log=print)
    print(f"[Phase 3-3] 완료: {composed}개 합성\n")

    # ── Phase 4: YouTube 업로드 스킵 ─────────────────────────
    print("[Phase 4] YouTube 업로드 → 스킵 (인증 필요)")

    print("\n" + "=" * 55)
    print(f"[TEST] 결과: 수집={fetched} | 대본={scripts_done} | "
          f"TTS={tts_done} | 영상={kling_done} | 합성={composed}")
    print("=" * 55)


if __name__ == "__main__":
    run()
