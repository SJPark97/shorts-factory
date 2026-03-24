"""
Phase 3-3: FFmpeg로 Kling 영상 + TTS 음성 + 자막 합성 → 최종 Shorts mp4
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import CONFIG_FILE, OUTPUT_DIR

SUBTITLE_DIR = OUTPUT_DIR / "subtitles"
OUTPUT_DIR = OUTPUT_DIR / "video"


def get_ffmpeg_bin() -> str:
    """번들 내 FFmpeg 우선 사용, 없으면 시스템 PATH fallback"""
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        bundled = meipass / name
        if bundled.exists():
            return str(bundled)
    return "ffmpeg"


def get_ffprobe_bin() -> str:
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
        bundled = meipass / name
        if bundled.exists():
            return str(bundled)
    return "ffprobe"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


# ─── 자막(SRT) 생성 ───────────────────────────────────────────────

def _seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def generate_srt(body: str, total_duration: float) -> str:
    """대본 본문을 균등 분할해 SRT 자막 생성"""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    if not sentences:
        return ""

    dur_per = total_duration / len(sentences)
    lines = []
    for i, sent in enumerate(sentences):
        start = i * dur_per
        end = (i + 1) * dur_per - 0.1
        lines.append(
            f"{i + 1}\n"
            f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}\n"
            f"{sent}\n"
        )
    return "\n".join(lines)


def save_srt(script_id: int, body: str, duration: float) -> Path:
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    srt_path = SUBTITLE_DIR / f"script_{script_id}.srt"
    srt_content = generate_srt(body, duration)
    srt_path.write_text(srt_content, encoding="utf-8")
    return srt_path


# ─── FFmpeg 합성 ──────────────────────────────────────────────────

def get_audio_duration(audio_path: Path) -> float:
    """ffprobe로 오디오 길이(초) 조회"""
    import subprocess
    result = subprocess.run(
        [
            get_ffprobe_bin(), "-v", "quiet",
            "-print_format", "json",
            "-show_streams", str(audio_path),
        ],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            return float(stream.get("duration", 0))
    return 0.0


def compose_video(video_path: Path, audio_path: Path, srt_path: Path,
                  out_path: Path, log=print):
    """FFmpeg: 영상 + 음성 + 자막 합성 (9:16, 오디오 길이 기준)"""
    import subprocess

    # SRT 경로에서 역슬래시/콜론 이스케이프 (Windows FFmpeg 호환)
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

    cmd = [
        get_ffmpeg_bin(), "-y",
        "-stream_loop", "-1",       # 영상 루프 (오디오보다 짧을 경우 대비)
        "-i", str(video_path),      # 입력 영상
        "-i", str(audio_path),      # 입력 오디오
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"subtitles={srt_escaped}:force_style="
            "'FontName=Arial,FontSize=18,PrimaryColour=&Hffffff,"
            "OutlineColour=&H000000,Outline=2,Alignment=2'"
        ),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",                # 오디오 끝나면 종료
        "-movflags", "+faststart",
        str(out_path),
    ]

    log(f"[composer] FFmpeg 합성 시작: {out_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 오류:\n{result.stderr[-500:]}")
    log(f"[composer] 합성 완료: {out_path}")


def compose(script: dict, log=print) -> Path | None:
    """
    script dict 기준으로 영상+음성+자막 합성 → 최종 mp4.
    반환값: 최종 파일 경로 (실패 시 None)
    """
    from storage import update_script

    video_path = Path(script["video_path"]) if script.get("video_path") else None
    audio_path = Path(script["tts_path"]) if script.get("tts_path") else None

    if not video_path or not audio_path:
        log(f"[composer] 영상 또는 오디오 경로 없음: script_id={script['id']}")
        return None
    if not video_path.exists():
        log(f"[composer] 영상 파일 없음: {video_path}")
        return None
    if not audio_path.exists():
        log(f"[composer] 오디오 파일 없음: {audio_path}")
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"final_{script['id']}.mp4"

    try:
        duration = get_audio_duration(audio_path)
        if duration <= 0:
            duration = load_config()["video"].get("target_duration_sec", 90)

        srt_path = save_srt(script["id"], script.get("body", ""), duration)
        compose_video(video_path, audio_path, srt_path, out_path, log=log)

        update_script(script["id"], video_path=str(out_path), status="video_done")
        return out_path

    except Exception as e:
        log(f"[composer] 오류 (script_id={script['id']}): {e}")
        return None


def run_compose_batch(n: int = None, log=print) -> int:
    """video_ready 스크립트 n개 합성. 반환값: 성공 수"""
    from storage import get_video_ready_scripts
    cfg = load_config()
    if n is None:
        n = cfg["upload"].get("daily_upload_limit", 3)
    scripts = get_video_ready_scripts(limit=n)
    if not scripts:
        log("[composer] 처리할 스크립트 없음")
        return 0
    done = sum(1 for s in scripts if compose(s, log=log) is not None)
    log(f"[composer] {done}/{len(scripts)}개 합성 완료")
    return done


if __name__ == "__main__":
    run_compose_batch()
