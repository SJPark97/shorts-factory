# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec 파일
Mac:     pyinstaller shorts.spec  →  dist/쇼츠자동양산기.app
Windows: pyinstaller shorts.spec  →  dist/쇼츠자동양산기.exe
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

# FFmpeg 바이너리 (build_mac.sh / build_win.bat 실행 후 생성됨)
_ffmpeg_dir = ROOT / "assets" / "ffmpeg"
if sys.platform == "win32":
    _ffmpeg_bins = [
        (str(_ffmpeg_dir / "ffmpeg.exe"), "."),
        (str(_ffmpeg_dir / "ffprobe.exe"), "."),
    ]
else:
    _ffmpeg_bins = [
        (str(_ffmpeg_dir / "ffmpeg"), "."),
        (str(_ffmpeg_dir / "ffprobe"), "."),
    ]

# 존재하는 바이너리만 포함
_ffmpeg_bins = [(src, dst) for src, dst in _ffmpeg_bins if Path(src).exists()]

a = Analysis(
    [str(ROOT / "gui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=_ffmpeg_bins,
    datas=[
        # config.json 템플릿 (번들 내부 리소스용)
        (str(ROOT / "config.json"), "."),
    ],
    hiddenimports=[
        # 크롤러
        "crawler.build_queue",
        "crawler.fetcher",
        # 대본
        "script.generator",
        # 영상
        "video.tts",
        "video.kling",
        "video.composer",
        # 업로더
        "uploader.youtube",
        # 스토리지
        "storage",
        "paths",
        # 외부 라이브러리
        "anthropic",
        "openai",
        "elevenlabs",
        "elevenlabs.client",
        "googleapiclient",
        "googleapiclient.discovery",
        "googleapiclient.http",
        "google.oauth2.credentials",
        "google_auth_oauthlib.flow",
        "google.auth.transport.requests",
        "requests",
        "tqdm",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="쇼츠자동양산기",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,        # GUI 앱 → 터미널 창 없음
        argv_emulation=True,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        strip=False,
        upx=True,
        name="쇼츠자동양산기",
    )
    app = BUNDLE(
        coll,
        name="쇼츠자동양산기.app",
        icon=None,            # 아이콘 추가 시: icon="assets/icon.icns"
        bundle_identifier="com.yourname.shorts-automation",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )

else:
    # Windows
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas,
        name="쇼츠자동양산기",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,        # GUI 앱 → 콘솔 창 없음
        icon=None,            # 아이콘 추가 시: icon="assets/icon.ico"
    )
