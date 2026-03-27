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


def create_video_task(prompt: str, cfg: dict) -> str | None:
    """Kling AI 영상 생성 태스크 생성. 반환값: task_id"""
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

    resp = requests.post(
        f"{KLING_BASE}/v1/videos/text2video",
        headers=_headers(cfg),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
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


def generate_kling_clips(script: dict, tts_duration: float = 0.0, log=print) -> list[Path]:
    """
    대본 문장별로 Kling 클립 생성.
    - tts_duration: TTS 오디오 길이(초). 0이면 문장 수 기준으로만 생성.
    - 반환값: 생성된 클립 경로 리스트 (1개 이상이면 storage에 저장 후 video_ready 상태로 변경)
    """
    from storage import update_script

    cfg = load_config()
    api_key = cfg["api"].get("kling_api_key", "")
    if not api_key:
        log("[kling] 오류: Kling API 키 미설정")
        return []

    clip_duration = int(cfg["video"].get("kling_duration", 5))
    title = script.get("title", "")
    scenes = split_scenes(script.get("body", ""))

    if not scenes:
        log(f"[kling] 오류: 대본 본문이 비어 있음 (script_id={script['id']})")
        return []

    # TTS 길이 기준으로 필요한 클립 수 계산 (최소 문장 수만큼은 생성)
    if tts_duration > 0:
        needed = math.ceil(tts_duration / clip_duration)
        # 문장을 순환하며 needed개 채우기
        scene_list = [scenes[i % len(scenes)] for i in range(needed)]
    else:
        scene_list = scenes

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []

    for i, sentence in enumerate(scene_list):
        out_path = VIDEO_DIR / f"kling_{script['id']}_clip{i}.mp4"
        prompt = build_scene_prompt(title, sentence)
        log(f"[kling] 클립 {i + 1}/{len(scene_list)} 생성 요청")
        try:
            task_id = create_video_task(prompt, cfg)
            log(f"[kling] 태스크 생성됨: {task_id}")
            video_url = poll_task(task_id, cfg, timeout=600, log=log)
            download_video(video_url, out_path, log=log)
            clip_paths.append(out_path)
            log(f"[kling] 클립 {i + 1} 완료: {out_path.name}")
        except Exception as e:
            log(f"[kling] 클립 {i + 1} 오류: {e}")

    if clip_paths:
        update_script(
            script["id"],
            clip_paths=[str(p) for p in clip_paths],
            status="video_ready",
        )
        log(f"[kling] {len(clip_paths)}/{len(scene_list)}개 클립 생성 완료")
    else:
        log(f"[kling] 오류: 생성된 클립 없음 (script_id={script['id']})")

    return clip_paths


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
    done = sum(1 for s in scripts if generate_kling_clips(s, log=log))
    log(f"[kling] {done}/{len(scripts)}개 스크립트 클립 생성 완료")
    return done


if __name__ == "__main__":
    run_kling_batch()
