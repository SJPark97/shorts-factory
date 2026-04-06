"""
Phase 3-2: Kling AI API로 영상 생성
https://api.klingai.com
"""
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import CONFIG_FILE, OUTPUT_DIR

VIDEO_DIR = OUTPUT_DIR / "video"

KLING_BASE = "https://api.klingai.com"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _make_jwt(api_key: str, api_secret: str) -> str:
    """Kling AI JWT 토큰 생성 (HS256)"""
    import base64
    import hmac
    import time as _time

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    now = int(_time.time())
    payload = base64.urlsafe_b64encode(
        json.dumps({"iss": api_key, "exp": now + 1800, "nbf": now - 5}).encode()
    ).rstrip(b"=").decode()

    sig_input = f"{header}.{payload}".encode()
    sig = hmac.new(api_secret.encode(), sig_input, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"{header}.{payload}.{signature}"


def _headers(cfg: dict) -> dict:
    api_key = cfg["api"].get("kling_api_key", "")
    api_secret = cfg["api"].get("kling_api_secret", "")
    token = _make_jwt(api_key, api_secret)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def create_video_task(prompt: str, cfg: dict, log=print) -> str | None:
    """Kling AI 영상 생성 태스크 생성. 반환값: task_id (429 시 backoff 재시도)"""
    model = cfg["video"].get("kling_model", "kling-v1")
    aspect_ratio = cfg["video"].get("kling_aspect_ratio", "9:16")
    duration = cfg["video"].get("kling_duration", 5)

    payload = {
        "model_name": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": str(duration),
        "cfg_scale": 0.5,
        "mode": "std",
    }

    backoff = 30
    for attempt in range(5):
        resp = requests.post(
            f"{KLING_BASE}/v1/videos/text2video",
            headers=_headers(cfg),
            json=payload,
            timeout=30,
        )
        if resp.status_code == 429:
            log(f"[kling] 429 rate limit, {backoff}초 후 재시도 ({attempt + 1}/5)")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue
        resp.raise_for_status()
        break
    else:
        raise RuntimeError("Kling API 429: rate limit 초과, 재시도 실패")

    data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"Kling API 오류: {data.get('message')}")

    return data["data"]["task_id"]


def poll_task(task_id: str, cfg: dict,
              timeout: int = 300, interval: int = 10, log=print) -> str | None:
    """태스크 완료 대기. 반환값: 영상 URL"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{KLING_BASE}/v1/videos/text2video/{task_id}",
            headers=_headers(cfg),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Kling 폴링 오류: {data.get('message')}")

        status = data["data"]["task_status"]
        log(f"[kling] 태스크 상태: {status}")

        if status == "succeed":
            works = data["data"].get("task_result", {}).get("videos", [])
            if works:
                return works[0]["url"]
            raise RuntimeError("영상 URL 없음")

        if status == "failed":
            raise RuntimeError(f"Kling 태스크 실패: {data['data'].get('task_status_msg')}")

        time.sleep(interval)

    raise TimeoutError(f"Kling 태스크 타임아웃 ({timeout}초)")


def download_video(url: str, out_path: Path, log=print):
    log(f"[kling] 영상 다운로드 중: {out_path.name}")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def split_scenes(body: str) -> list[str]:
    """대본 본문을 문장 단위로 분할"""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    return sentences


def build_scene_prompt(title: str, sentence: str) -> str:
    """씬별 Kling 영상 프롬프트 생성"""
    return (
        f"Cinematic short video about: {title}. "
        f"{sentence}. "
        "9:16 vertical format, dramatic lighting, high quality, no text overlay."
    )


def check_task(task_id: str, cfg: dict) -> tuple[str, str | None]:
    """태스크 상태 단건 조회. 반환값: (status, video_url or None)"""
    resp = requests.get(
        f"{KLING_BASE}/v1/videos/text2video/{task_id}",
        headers=_headers(cfg),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Kling 폴링 오류: {data.get('message')}")
    status = data["data"]["task_status"]
    if status == "succeed":
        videos = data["data"].get("task_result", {}).get("videos", [])
        return status, videos[0]["url"] if videos else None
    return status, None


def generate_kling_clips(script: dict, tts_duration: float = 0.0, log=print) -> list[Path]:
    """
    슬라이딩 윈도우 방식으로 Kling 클립 생성.
    - max_concurrent개까지 동시 제출, 1개 완료되면 1개 추가 제출.
    - tts_duration 기준으로 필요한 클립 수 계산.
    """
    from storage import update_script

    cfg = load_config()
    if not cfg["api"].get("kling_api_key", ""):
        log("[kling] 오류: Kling API 키 미설정")
        return []

    clip_duration = int(cfg["video"].get("kling_duration", 5))
    max_concurrent = int(cfg["video"].get("kling_max_concurrent", 3))
    poll_interval = int(cfg["video"].get("kling_poll_interval", 15))
    title = script.get("title", "")
    scenes = split_scenes(script.get("body", ""))

    if not scenes:
        log(f"[kling] 오류: 대본 본문이 비어 있음 (script_id={script['id']})")
        return []

    if tts_duration > 0:
        needed = math.ceil(tts_duration / clip_duration)
        scene_list = [scenes[i % len(scenes)] for i in range(needed)]
    else:
        scene_list = scenes

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    total = len(scene_list)
    log(f"[kling] 총 {total}개 클립 필요 (TTS {tts_duration:.1f}초 / 클립 {clip_duration}초)")

    # work_queue: 아직 제출 안 한 (index, sentence) 목록
    work_queue = list(enumerate(scene_list))
    # pending: {task_id: (index, out_path)}
    pending: dict[str, tuple[int, Path]] = {}
    clip_paths: dict[int, Path] = {}

    def submit_up_to_limit():
        while work_queue and len(pending) < max_concurrent:
            i, sentence = work_queue.pop(0)
            out_path = VIDEO_DIR / f"kling_{script['id']}_clip{i}.mp4"
            prompt = build_scene_prompt(title, sentence)
            try:
                task_id = create_video_task(prompt, cfg, log=log)
                pending[task_id] = (i, out_path)
                log(f"[kling] 클립 {i + 1}/{total} 제출 (동시 {len(pending)}개)")
            except Exception as e:
                log(f"[kling] 클립 {i + 1} 제출 오류: {e}")

    submit_up_to_limit()

    while pending:
        time.sleep(poll_interval)
        completed = []
        for task_id, (i, out_path) in list(pending.items()):
            try:
                status, video_url = check_task(task_id, cfg)
                log(f"[kling] 클립 {i + 1} 상태: {status}")
                if status == "succeed":
                    if video_url:
                        download_video(video_url, out_path, log=log)
                        clip_paths[i] = out_path
                        log(f"[kling] 클립 {i + 1} 완료: {out_path.name}")
                    completed.append(task_id)
                elif status == "failed":
                    log(f"[kling] 클립 {i + 1} 실패")
                    completed.append(task_id)
            except Exception as e:
                log(f"[kling] 클립 {i + 1} 폴링 오류: {e}")

        for task_id in completed:
            del pending[task_id]

        if completed:
            submit_up_to_limit()

    result = [clip_paths[i] for i in sorted(clip_paths)]
    if result:
        update_script(
            script["id"],
            clip_paths=[str(p) for p in result],
            status="video_ready",
        )
        log(f"[kling] {len(result)}/{total}개 클립 생성 완료")
    else:
        log(f"[kling] 오류: 생성된 클립 없음 (script_id={script['id']})")

    return result


def get_audio_duration(path: str) -> float:
    """mp3/wav 파일 길이(초) 반환. 실패 시 0.0"""
    try:
        from mutagen.mp3 import MP3
        return MP3(path).info.length
    except Exception:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def run_kling_batch(n: int = None, log=print) -> int:
    """tts_done 스크립트 n개에 대해 Kling 클립 생성. 반환값: 성공 스크립트 수"""
    from storage import get_tts_ready_scripts
    cfg = load_config()
    if n is None:
        n = cfg["upload"].get("daily_upload_limit", 3)
    scripts = get_tts_ready_scripts(limit=n)
    if not scripts:
        log("[kling] 처리할 스크립트 없음")
        return 0
    done = 0
    for s in scripts:
        tts_duration = get_audio_duration(s.get("tts_path", ""))
        if tts_duration > 0:
            log(f"[kling] TTS 길이: {tts_duration:.1f}초")
        if generate_kling_clips(s, tts_duration=tts_duration, log=log):
            done += 1
    log(f"[kling] {done}/{len(scripts)}개 스크립트 클립 생성 완료")
    return done


if __name__ == "__main__":
    run_kling_batch()
