"""
Phase 4: YouTube Data API v3 업로드 + OAuth 2.0 인증
"""
import json
import sys
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import CONFIG_FILE, DATA_DIR

TOKEN_DIR = DATA_DIR

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE = "youtube"
API_VERSION = "v3"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


# ─── OAuth 인증 ───────────────────────────────────────────────────

def get_token_path(channel_id: str) -> Path:
    return TOKEN_DIR / f"token_{channel_id}.json"


def check_token(channel_id: str) -> str:
    """
    토큰 유효성 확인.
    반환값: "valid" | "refreshed" | "expired" | "missing"
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import TransportError
    import requests as _req

    token_path = get_token_path(channel_id)
    if not token_path.exists():
        return "missing"

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception:
        return "expired"

    if creds.valid:
        return "valid"

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return "refreshed"
        except Exception:
            return "expired"

    return "expired"


def authenticate(channel_id: str = "default",
                 credentials_path: str = None,
                 open_browser: bool = True,
                 log=print):
    """
    OAuth 2.0 인증. 토큰 파일 없으면 브라우저 열어서 인증.
    반환값: google.oauth2.credentials.Credentials
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    token_path = get_token_path(channel_id)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log(f"[youtube] 토큰 갱신 중 (channel={channel_id})")
            creds.refresh(Request())
        else:
            cred_path = Path(credentials_path) if credentials_path else None
            if not cred_path:
                raise FileNotFoundError(
                    "인증 파일 경로가 지정되지 않았습니다. "
                    "채널 관리 탭에서 client_secret.json 파일을 선택하세요."
                )

            if not cred_path.exists():
                raise FileNotFoundError(
                    f"YouTube OAuth 클라이언트 시크릿 파일 없음: {cred_path}\n"
                    "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고 "
                    "해당 경로에 저장하세요."
                )

            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            if open_browser:
                log(f"[youtube] 브라우저에서 인증을 완료하세요 (channel={channel_id})")
                creds = flow.run_local_server(port=0)
            else:
                creds = flow.run_console()

        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        log(f"[youtube] 토큰 저장됨: {token_path}")

    return creds


def build_youtube_client(channel_id: str = "default", log=print):
    from googleapiclient.discovery import build
    creds = authenticate(channel_id, log=log)
    return build(API_SERVICE, API_VERSION, credentials=creds)


# ─── 업로드 ───────────────────────────────────────────────────────

def upload_video(script: dict, video_path: Path,
                 channel_id: str = "default", log=print) -> str | None:
    """
    YouTube에 영상 업로드.
    반환값: YouTube video_id (실패 시 None)
    """
    sys.path.insert(0, str(ROOT))
    from storage import update_script
    from googleapiclient.http import MediaFileUpload

    cfg = load_config()
    upload_cfg = cfg.get("upload", {})
    privacy = upload_cfg.get("privacy_status", "public")
    default_tags = upload_cfg.get("default_tags", [])
    category_id = upload_cfg.get("category_id", "27")

    hashtags = script.get("hashtags", [])
    all_tags = list(dict.fromkeys(hashtags + default_tags + ["Shorts"]))

    title = script.get("title", "History Facts")
    # YouTube 제목 최대 100자
    title = title[:97] + "..." if len(title) > 100 else title

    description = (
        f"{script.get('body', '')[:4500]}\n\n"
        f"{' '.join('#' + t for t in hashtags)}\n"
        "#Shorts #History #HistoryFacts\n\n"
        "⚠️ This video was created with AI assistance."
    )

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": all_tags[:500],       # YouTube 태그 최대 500자
            "categoryId": category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            # 2024 YouTube 정책: AI 생성 콘텐츠 공시
            "containsSyntheticMedia": True,
        },
    }

    try:
        log(f"[youtube] 업로드 시작: {title}")
        youtube = build_youtube_client(channel_id, log=log)

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # 5MB 청크
        )

        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log(f"[youtube] 업로드 진행: {pct}%")

        video_id = response["id"]
        update_script(script["id"], status="uploaded")
        log(f"[youtube] 업로드 완료: https://youtu.be/{video_id}")
        return video_id

    except Exception as e:
        log(f"[youtube] 오류 (script_id={script['id']}): {e}")
        return None


def run_upload_batch(n: int = None, log=print) -> int:
    """video_done 스크립트 n개 업로드. 반환값: 성공 수"""
    sys.path.insert(0, str(ROOT))
    from storage import get_all_scripts
    cfg = load_config()
    if n is None:
        n = cfg["upload"].get("daily_upload_limit", 3)

    # 채널 목록 로드
    channels = cfg.get("channels", [])
    active_channels = [c for c in channels if c.get("active", True)] or [
        {"id": "default", "style": "default"}
    ]

    ready = [s for s in get_all_scripts() if s.get("status") == "video_done"][:n]
    if not ready:
        log("[youtube] 업로드할 영상 없음")
        return 0

    done = 0
    for script in ready:
        video_path = Path(script["video_path"]) if script.get("video_path") else None
        if not video_path or not video_path.exists():
            log(f"[youtube] 영상 파일 없음, 스킵: script_id={script['id']}")
            continue

        # 채널이 여럿이면 채널 ID 기반으로 맞는 채널 선택
        channel_id = script.get("channel_id", "default")
        result = upload_video(script, video_path, channel_id=channel_id, log=log)
        if result:
            done += 1

    log(f"[youtube] {done}/{len(ready)}개 업로드 완료")
    return done


if __name__ == "__main__":
    run_upload_batch()
