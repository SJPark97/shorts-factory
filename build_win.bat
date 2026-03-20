@echo off
REM Windows용 .exe 빌드 스크립트
REM FFmpeg 정적 빌드를 GitHub에서 직접 다운로드해 번들에 포함

echo === 쇼츠 자동 양산기 Windows 빌드 ===

REM 가상환경
if not exist venv (
    echo [1/4] 가상환경 생성
    python -m venv venv
)
call venv\Scripts\activate

echo [2/4] 의존성 설치
pip install -q -r requirements.txt
pip install -q pyinstaller

REM ── FFmpeg 바이너리 준비 ─────────────────────────────────────────
echo [3/4] FFmpeg 바이너리 준비
if not exist "assets\ffmpeg" mkdir "assets\ffmpeg"

if not exist "assets\ffmpeg\ffmpeg.exe" (
    echo   ffmpeg.exe 없음 - GitHub에서 정적 빌드 다운로드 중...

    REM BtbN/FFmpeg-Builds 최신 Windows 64bit 정적 빌드
    set FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
    set FFMPEG_ZIP=assets\ffmpeg\ffmpeg.zip

    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile '%FFMPEG_ZIP%' -UseBasicParsing"

    if not exist "%FFMPEG_ZIP%" (
        echo   오류: 다운로드 실패. 네트워크를 확인하세요.
        exit /b 1
    )

    echo   압축 해제 중...
    powershell -NoProfile -Command ^
        "Expand-Archive -Path '%FFMPEG_ZIP%' -DestinationPath 'assets\ffmpeg\extracted' -Force"

    REM bin 폴더에서 ffmpeg.exe, ffprobe.exe만 복사
    for /f "delims=" %%i in ('dir /b /s "assets\ffmpeg\extracted\*\bin\ffmpeg.exe"') do (
        copy "%%i" "assets\ffmpeg\ffmpeg.exe" >nul
    )
    for /f "delims=" %%i in ('dir /b /s "assets\ffmpeg\extracted\*\bin\ffprobe.exe"') do (
        copy "%%i" "assets\ffmpeg\ffprobe.exe" >nul
    )

    REM 임시 파일 정리
    del "%FFMPEG_ZIP%" >nul 2>&1
    rmdir /s /q "assets\ffmpeg\extracted" >nul 2>&1

    if exist "assets\ffmpeg\ffmpeg.exe" (
        echo   다운로드 완료
    ) else (
        echo   오류: ffmpeg.exe 추출 실패
        exit /b 1
    )
) else (
    echo   이미 존재: assets\ffmpeg\ffmpeg.exe
)

REM ── PyInstaller 빌드 ─────────────────────────────────────────────
echo [4/4] PyInstaller 빌드
pyinstaller shorts.spec --clean --noconfirm

if exist "dist\쇼츠자동양산기.exe" (
    echo.
    echo 빌드 완료: dist\쇼츠자동양산기.exe
) else (
    echo 빌드 실패
    exit /b 1
)
