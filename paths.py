"""
개발 모드 / PyInstaller 번들 모드 모두에서 올바른 경로를 반환하는 모듈.

- 개발 모드: 프로젝트 루트 (이 파일의 상위 디렉터리)
- 번들 모드: 실행 파일 옆 디렉터리 (사용자가 접근 가능한 위치)
  → config.json, data/ 등 사용자 데이터는 번들 밖에 위치
"""
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """앱 데이터 루트 (config.json, data/ 등이 위치하는 곳)"""
    if getattr(sys, "frozen", False):
        # PyInstaller로 패키징된 경우: .app/exe 옆 디렉터리
        return Path(sys.executable).parent
    # 개발 모드: 프로젝트 루트
    return Path(__file__).parent


def get_resource_dir() -> Path:
    """번들 내부 리소스 (읽기 전용 템플릿 등)"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent


APP_DIR = get_app_dir()
CONFIG_FILE = APP_DIR / "config.json"
DATA_DIR = APP_DIR / "data"
OUTPUT_DIR = APP_DIR / "output"


def ensure_user_files():
    """첫 실행 시 config.json 템플릿 복사 + 디렉터리 생성"""
    import json, shutil

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "audio").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "video").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "subtitles").mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        template = get_resource_dir() / "config.json"
        if template.exists():
            shutil.copy(template, CONFIG_FILE)
        else:
            # 템플릿도 없으면 기본값으로 생성
            default = {
                "api": {"kling_api_key": "", "kling_api_secret": "",
                        "llm_provider": "claude", "llm_api_key": "",
                        "tts_provider": "openai", "tts_api_key": "",
                        "youtube_credentials_path": "data/youtube_credentials.json"},
                "crawl": {"categories": ["History_by_period", "Wars",
                                         "Ancient_civilizations", "Empires"],
                          "queue_refill_size": 100, "recursion_depth": 3},
                "video": {"target_duration_sec": 90, "tts_voice": "alloy",
                          "tts_model": "tts-1-hd", "elevenlabs_voice_id": "",
                          "kling_model": "kling-v1", "kling_aspect_ratio": "9:16",
                          "kling_duration": 5},
                "upload": {"daily_upload_limit": 3, "privacy_status": "public",
                           "default_tags": ["history", "shorts", "facts"],
                           "category_id": "27"},
                "channels": [],
            }
            CONFIG_FILE.write_text(
                json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8"
            )
