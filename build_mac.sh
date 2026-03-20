#!/bin/bash
# Mac용 .app + .dmg 빌드 스크립트
# FFmpeg 바이너리를 앱 안에 번들로 포함

set -e

echo "=== 쇼츠 자동 양산기 Mac 빌드 ==="

# ── 가상환경 ───────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "[1/5] 가상환경 생성"

    # Homebrew Python(Tk 포함) 우선 사용 - 시스템 Python은 Tcl/Tk 호환 문제 있음
    PYTHON=""
    for candidate in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3; do
        if [ -f "$candidate" ]; then
            PYTHON="$candidate"
            break
        fi
    done

    if [ -z "$PYTHON" ]; then
        echo "  Homebrew Python 없음 → 설치"
        brew install python3 python-tk
        PYTHON=/opt/homebrew/bin/python3
    fi

    echo "  사용 Python: $PYTHON ($($PYTHON --version))"
    $PYTHON -m venv venv
fi
source venv/bin/activate

# ── 의존성 ────────────────────────────────────────────────────────
echo "[2/5] 의존성 설치"
pip install -q -r requirements.txt
pip install -q pyinstaller

# ── FFmpeg 바이너리 준비 ───────────────────────────────────────────
echo "[3/5] FFmpeg 바이너리 준비"
FFMPEG_DIR="assets/ffmpeg"
mkdir -p "$FFMPEG_DIR"

if [ ! -f "$FFMPEG_DIR/ffmpeg" ] || [ ! -f "$FFMPEG_DIR/ffprobe" ]; then
    # Homebrew로 설치된 ffmpeg 사용 (없으면 설치)
    if ! command -v ffmpeg &>/dev/null; then
        echo "  ffmpeg 없음 → Homebrew로 설치"
        brew install ffmpeg
    fi
    FFMPEG_PATH=$(which ffmpeg)
    FFPROBE_PATH=$(which ffprobe)
    echo "  ffmpeg: $FFMPEG_PATH"
    cp "$FFMPEG_PATH" "$FFMPEG_DIR/ffmpeg"
    cp "$FFPROBE_PATH" "$FFMPEG_DIR/ffprobe"
    chmod +x "$FFMPEG_DIR/ffmpeg" "$FFMPEG_DIR/ffprobe"
    echo "  바이너리 복사 완료"
else
    echo "  이미 존재: $FFMPEG_DIR/ffmpeg"
fi

# ── PyInstaller 빌드 ──────────────────────────────────────────────
echo "[4/5] PyInstaller 빌드"
pyinstaller shorts.spec --clean --noconfirm

# ── DMG 생성 ─────────────────────────────────────────────────────
echo "[5/5] DMG 생성"
APP_PATH="dist/쇼츠자동양산기.app"
DMG_PATH="dist/쇼츠자동양산기.dmg"

if [ -d "$APP_PATH" ]; then
    rm -f "$DMG_PATH"
    hdiutil create -volname "쇼츠자동양산기" \
        -srcfolder "$APP_PATH" \
        -ov -format UDZO \
        "$DMG_PATH"
    echo ""
    echo "✅ 빌드 완료: $DMG_PATH"
    echo ""
    read -p "지금 앱을 실행할까요? (y/N): " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        open "$APP_PATH"
    fi
else
    echo "❌ .app 빌드 실패"
    exit 1
fi
