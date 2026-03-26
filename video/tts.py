"""
Phase 3-1: 대본 → TTS mp3 변환 (OpenAI TTS or ElevenLabs)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import CONFIG_FILE, OUTPUT_DIR

AUDIO_DIR = OUTPUT_DIR / "audio"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def tts_openai(api_key: str, text: str, voice: str, model: str, out_path: Path):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
    )
    resp.stream_to_file(out_path)


def tts_elevenlabs(api_key: str, text: str, voice_id: str, out_path: Path):
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=api_key)
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    with open(out_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)


def generate_tts(script: dict, log=print) -> Path | None:
    """
    script dict의 body를 TTS 변환 → mp3 저장.
    반환값: 저장된 파일 경로 (실패 시 None)
    """
    from storage import update_script

    cfg = load_config()
    provider = cfg["api"].get("tts_provider", "openai")
    api_key = cfg["api"].get("tts_api_key", "")

    if not api_key:
        log(f"[tts] 오류: TTS API 키가 설정되지 않았습니다 (provider={provider})")
        return None

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIO_DIR / f"script_{script['id']}.mp3"

    body = script.get("body", "")
    if not body:
        log(f"[tts] 빈 대본, 스킵: script_id={script['id']}")
        return None

    log(f"[tts] TTS 변환 중: script_id={script['id']} (provider={provider})")
    try:
        if provider == "openai":
            voice = cfg["video"].get("tts_voice", "alloy")
            model = cfg["video"].get("tts_model", "tts-1-hd")
            tts_openai(api_key, body, voice, model, out_path)
        elif provider == "elevenlabs":
            voice_id = cfg["video"].get("elevenlabs_voice_id", "")
            if not voice_id:
                log("[tts] ElevenLabs voice_id 미설정")
                return None
            tts_elevenlabs(api_key, body, voice_id, out_path)
        else:
            log(f"[tts] 알 수 없는 provider: {provider}")
            return None

        update_script(script["id"], tts_path=str(out_path), status="tts_done")
        log(f"[tts] 저장 완료: {out_path}")
        return out_path

    except Exception as e:
        log(f"[tts] 오류 (script_id={script['id']}): {e}")
        return None


def run_tts_batch(n: int = None, log=print) -> int:
    """pending 스크립트 n개를 TTS 변환. 반환값: 성공 수"""
    from storage import get_pending_scripts
    cfg = load_config()
    if n is None:
        n = cfg["upload"].get("daily_upload_limit", 3)
    scripts = get_pending_scripts(limit=n)
    if not scripts:
        log("[tts] 처리할 스크립트 없음")
        return 0
    done = sum(1 for s in scripts if generate_tts(s, log=log) is not None)
    log(f"[tts] {done}/{len(scripts)}개 TTS 변환 완료")
    return done


if __name__ == "__main__":
    run_tts_batch()
