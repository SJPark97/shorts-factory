"""
Phase 5: Tkinter GUI
- 메인 화면: 터미널 로그 + 실행 버튼
- 설정창 탭: API / 크롤링 / 영상 / 업로드 / 채널 관리
"""
import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import CONFIG_FILE, ensure_user_files
ensure_user_files()


# ─── 설정 로드/저장 ───────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ─── 설정창 ───────────────────────────────────────────────────────

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("설정")
        self.geometry("560x520")
        self.resizable(False, False)
        self.grab_set()

        self.cfg = load_config()
        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_api_tab(notebook)
        self._build_crawl_tab(notebook)
        self._build_video_tab(notebook)
        self._build_upload_tab(notebook)
        self._build_channel_tab(notebook)
        self._build_help_tab(notebook)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btn_frame, text="저장", width=10, command=self._save).pack(side="right")
        tk.Button(btn_frame, text="취소", width=10, command=self.destroy).pack(side="right", padx=4)

    # ── API 탭 ──────────────────────────────────────────────────────
    def _build_api_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="API 설정")

        api = self.cfg["api"]
        rows = [
            ("Kling API Key", "kling_api_key"),
            ("Kling API Secret", "kling_api_secret"),
            ("LLM API Key", "llm_api_key"),
            ("TTS API Key", "tts_api_key"),
        ]

        self._api_vars = {}
        for i, (label, key) in enumerate(rows):
            tk.Label(frame, text=label, anchor="w").grid(
                row=i * 2, column=0, sticky="w", padx=10, pady=(8, 0))
            var = tk.StringVar(value=api.get(key, ""))
            entry = tk.Entry(frame, textvariable=var, show="*", width=45)
            entry.grid(row=i * 2 + 1, column=0, padx=10, sticky="ew")
            self._api_vars[key] = var

        # LLM / TTS 프로바이더 선택
        provider_frame = tk.LabelFrame(frame, text="프로바이더 선택", padx=8, pady=6)
        provider_frame.grid(row=len(rows) * 2, column=0, padx=10, pady=10, sticky="ew")

        tk.Label(provider_frame, text="LLM:").grid(row=0, column=0, sticky="w")
        self._llm_var = tk.StringVar(value=self.cfg["api"].get("llm_provider", "claude"))
        ttk.Combobox(provider_frame, textvariable=self._llm_var,
                     values=["claude", "openai"], width=14, state="readonly"
                     ).grid(row=0, column=1, padx=6)

        tk.Label(provider_frame, text="TTS:").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self._tts_var = tk.StringVar(value=self.cfg["api"].get("tts_provider", "openai"))
        ttk.Combobox(provider_frame, textvariable=self._tts_var,
                     values=["openai", "elevenlabs"], width=14, state="readonly"
                     ).grid(row=0, column=3, padx=6)

        frame.columnconfigure(0, weight=1)

    # ── 크롤링 탭 ───────────────────────────────────────────────────
    def _build_crawl_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="크롤링 설정")

        crawl = self.cfg["crawl"]
        all_cats = [
            "History_by_period", "Wars", "Ancient_civilizations",
            "Empires", "Military_history", "Battles", "Revolutions",
            "Historical_events", "World_War_II", "World_War_I",
        ]
        selected = crawl.get("categories", [])

        tk.Label(frame, text="Wikipedia 역사 카테고리", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))

        cat_frame = tk.Frame(frame)
        cat_frame.pack(padx=10, fill="x")
        self._cat_vars = {}
        for i, cat in enumerate(all_cats):
            var = tk.BooleanVar(value=cat in selected)
            cb = tk.Checkbutton(cat_frame, text=cat, variable=var, anchor="w")
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=4)
            self._cat_vars[cat] = var

        tk.Label(frame, text="큐 보충 시 가져올 문서 수", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(12, 2))
        self._refill_var = tk.IntVar(value=crawl.get("queue_refill_size", 100))
        tk.Spinbox(frame, from_=10, to=500, increment=10,
                   textvariable=self._refill_var, width=8
                   ).pack(anchor="w", padx=10)

        tk.Label(frame, text="재귀 탐색 깊이 (1~5)", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._depth_var = tk.IntVar(value=crawl.get("recursion_depth", 3))
        tk.Spinbox(frame, from_=1, to=5, textvariable=self._depth_var, width=8
                   ).pack(anchor="w", padx=10)

    # ── 영상 탭 ─────────────────────────────────────────────────────
    def _build_video_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="영상 설정")

        video = self.cfg["video"]

        tk.Label(frame, text="목표 영상 길이 (초)", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._duration_var = tk.IntVar(value=video.get("target_duration_sec", 90))
        ttk.Combobox(frame, textvariable=self._duration_var,
                     values=[60, 90, 120], width=10, state="readonly"
                     ).pack(anchor="w", padx=10)

        tk.Label(frame, text="OpenAI TTS 음성", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._voice_var = tk.StringVar(value=video.get("tts_voice", "alloy"))
        ttk.Combobox(frame, textvariable=self._voice_var,
                     values=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                     width=14, state="readonly"
                     ).pack(anchor="w", padx=10)

        tk.Label(frame, text="ElevenLabs Voice ID", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._el_voice_var = tk.StringVar(value=video.get("elevenlabs_voice_id", ""))
        tk.Entry(frame, textvariable=self._el_voice_var, width=40
                 ).pack(anchor="w", padx=10)
        tk.Label(frame,
                 text="  elevenlabs.io → Voices → 목소리 클릭 → URL의 마지막 ID값\n"
                      "  예) /voice/21m00Tcm4TlvDq8ikWAM/... → 21m00Tcm4TlvDq8ikWAM",
                 anchor="w", fg="gray", font=("", 9)
                 ).pack(anchor="w", padx=10)

        tk.Label(frame, text="Kling 영상 씬 길이 (초)", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._kling_dur_var = tk.IntVar(value=video.get("kling_duration", 5))
        ttk.Combobox(frame, textvariable=self._kling_dur_var,
                     values=[5, 10], width=10, state="readonly"
                     ).pack(anchor="w", padx=10)

    # ── 업로드 탭 ───────────────────────────────────────────────────
    def _build_upload_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="업로드 설정")

        upload = self.cfg["upload"]

        tk.Label(frame, text="일일 업로드 수 (최대 6)", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._daily_var = tk.IntVar(value=upload.get("daily_upload_limit", 3))
        tk.Spinbox(frame, from_=1, to=6, textvariable=self._daily_var, width=6
                   ).pack(anchor="w", padx=10)

        tk.Label(frame, text="공개 범위", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        self._privacy_var = tk.StringVar(value=upload.get("privacy_status", "public"))
        ttk.Combobox(frame, textvariable=self._privacy_var,
                     values=["public", "private", "unlisted"],
                     width=12, state="readonly"
                     ).pack(anchor="w", padx=10)

        tk.Label(frame, text="기본 태그 (쉼표 구분)", anchor="w"
                 ).pack(anchor="w", padx=10, pady=(10, 2))
        default_tags = ", ".join(upload.get("default_tags", []))
        self._tags_var = tk.StringVar(value=default_tags)
        tk.Entry(frame, textvariable=self._tags_var, width=45
                 ).pack(anchor="w", padx=10)

    # ── 채널 관리 탭 ────────────────────────────────────────────────
    def _build_channel_tab(self, nb):
        from tkinter import filedialog
        frame = ttk.Frame(nb)
        nb.add(frame, text="채널 관리")

        # 채널 행 목록
        self._channel_rows: list[dict] = []

        # 스크롤 가능한 채널 목록 영역
        canvas_frame = tk.Frame(frame)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        self._ch_canvas = tk.Canvas(canvas_frame, height=160, highlightthickness=0)
        sb = tk.Scrollbar(canvas_frame, orient="vertical", command=self._ch_canvas.yview)
        self._ch_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._ch_canvas.pack(side="left", fill="both", expand=True)

        self._ch_rows_frame = tk.Frame(self._ch_canvas)
        self._ch_canvas_window = self._ch_canvas.create_window(
            (0, 0), window=self._ch_rows_frame, anchor="nw"
        )
        self._ch_rows_frame.bind("<Configure>", lambda e: self._ch_canvas.configure(
            scrollregion=self._ch_canvas.bbox("all")
        ))
        self._ch_canvas.bind("<Configure>", lambda e: self._ch_canvas.itemconfig(
            self._ch_canvas_window, width=e.width
        ))

        # 기존 채널 로드
        for ch in self.cfg.get("channels", []):
            self._append_channel_row(
                ch.get("id", ""),
                ch.get("style", "default"),
                ch.get("active", True),
                ch.get("credentials_path", ""),
            )

        # 입력 + 추가 버튼
        input_frame = tk.Frame(frame)
        input_frame.pack(fill="x", padx=10, pady=4)

        self._ch_id_var = tk.StringVar()
        self._ch_style_var = tk.StringVar(value="default")
        self._ch_active_var = tk.BooleanVar(value=True)

        tk.Label(input_frame, text="채널ID").pack(side="left")
        tk.Entry(input_frame, textvariable=self._ch_id_var, width=18
                 ).pack(side="left", padx=4)
        tk.Label(input_frame, text="스타일").pack(side="left")
        ttk.Combobox(input_frame, textvariable=self._ch_style_var,
                     values=["default", "dramatic", "quiz", "timeline"],
                     width=10, state="readonly").pack(side="left", padx=4)
        tk.Checkbutton(input_frame, text="활성화", variable=self._ch_active_var
                       ).pack(side="left")
        tk.Button(input_frame, text="+ 추가", command=self._add_channel
                  ).pack(side="left", padx=8)

    def _append_channel_row(self, ch_id: str, style: str, active: bool, cred_path: str = ""):
        from tkinter import filedialog

        # 채널 전체를 감싸는 컨테이너 (구분선 포함)
        container = tk.Frame(self._ch_rows_frame, bd=1, relief="groove")
        container.pack(fill="x", pady=3, padx=2)

        # ── 1줄: 채널ID / 스타일 / 활성화 / 삭제 ──────────────────
        line1 = tk.Frame(container)
        line1.pack(fill="x", padx=4, pady=(4, 1))

        id_var    = tk.StringVar(value=ch_id)
        style_var = tk.StringVar(value=style)
        active_var = tk.BooleanVar(value=active)

        tk.Label(line1, text="채널ID", width=6, anchor="w").pack(side="left")
        tk.Entry(line1, textvariable=id_var, width=20).pack(side="left", padx=2)
        tk.Label(line1, text="스타일", width=6, anchor="w").pack(side="left", padx=(8, 0))
        ttk.Combobox(line1, textvariable=style_var,
                     values=["default", "dramatic", "quiz", "timeline"],
                     width=10, state="readonly").pack(side="left", padx=2)
        tk.Checkbutton(line1, text="활성화", variable=active_var).pack(side="left", padx=6)
        tk.Button(line1, text="✕", width=2, fg="red",
                  command=lambda c=container: self._remove_channel_row(c)
                  ).pack(side="right")

        # ── 2줄: credentials 파일 + 인증 버튼 ─────────────────────
        line2 = tk.Frame(container)
        line2.pack(fill="x", padx=4, pady=(1, 4))

        cred_var = tk.StringVar(value=cred_path)
        tk.Label(line2, text="인증파일", width=6, anchor="w").pack(side="left")

        cred_entry = tk.Entry(line2, textvariable=cred_var, width=28,
                              state="readonly", fg="#555")
        cred_entry.pack(side="left", padx=2)

        tk.Button(
            line2, text="파일 선택",
            command=lambda v=cred_var: v.set(
                filedialog.askopenfilename(
                    title="client_secret.json 선택",
                    filetypes=[("JSON", "*.json"), ("모든 파일", "*.*")]
                ) or v.get()
            )
        ).pack(side="left", padx=4)

        auth_btn = tk.Button(line2, text="확인 중...", width=14,
                             bg="#e0e0e0", fg="black")
        auth_btn.pack(side="left", padx=4)

        row = {"container": container, "id": id_var, "style": style_var,
               "active": active_var, "cred": cred_var, "auth_btn": auth_btn}
        self._channel_rows.append(row)
        auth_btn.config(command=lambda r=row: self._auth_channel_row(r))

        # 백그라운드에서 토큰 상태 확인
        if ch_id:
            threading.Thread(target=self._check_token_status,
                             args=(row,), daemon=True).start()

    def _check_token_status(self, row: dict):
        """백그라운드 스레드에서 토큰 유효성 확인 후 버튼 업데이트"""
        from uploader.youtube import check_token
        ch_id = row["id"].get().strip()
        if not ch_id:
            self._set_auth_btn(row, "missing")
            return
        status = check_token(ch_id)
        self._set_auth_btn(row, status)

    def _set_auth_btn(self, row: dict, status: str):
        """토큰 상태에 따라 인증 버튼 UI 업데이트 (메인 스레드 안전)"""
        configs = {
            "valid":    ("✓ 인증됨",    "#27ae60", "white"),
            "refreshed":("✓ 인증됨",    "#27ae60", "white"),
            "expired":  ("재인증 필요", "#e74c3c", "white"),
            "missing":  ("인증하기",    "#e0e0e0", "black"),
        }
        text, bg, fg = configs.get(status, ("인증하기", "#e0e0e0", "black"))
        btn = row["auth_btn"]
        try:
            btn.after(0, lambda: btn.config(text=text, bg=bg, fg=fg, state="normal"))
        except tk.TclError:
            pass  # 위젯이 이미 삭제된 경우

    def _remove_channel_row(self, container: tk.Frame):
        self._channel_rows = [r for r in self._channel_rows if r["container"] is not container]
        container.destroy()

    def _add_channel(self):
        ch_id = self._ch_id_var.get().strip()
        if not ch_id:
            messagebox.showwarning("입력 오류", "채널 ID를 입력하세요.")
            return
        self._append_channel_row(ch_id, self._ch_style_var.get(), self._ch_active_var.get())
        self._ch_id_var.set("")

    def _auth_channel_row(self, row: dict):
        from uploader.youtube import authenticate
        ch_id = row["id"].get().strip()
        cred_path = row["cred"].get().strip()
        if not ch_id:
            messagebox.showwarning("오류", "채널 ID가 비어있습니다.")
            return
        if not cred_path:
            messagebox.showwarning("인증파일 없음",
                                   "client_secret.json 파일을 먼저 선택하세요.\n"
                                   "(도움말 탭에서 발급 방법을 확인할 수 있습니다)")
            return
        row["auth_btn"].config(text="인증 중...", bg="#f39c12", fg="white", state="disabled")
        self.update()
        try:
            authenticate(channel_id=ch_id, credentials_path=cred_path, log=print)
            self._set_auth_btn(row, "valid")
        except Exception as e:
            self._set_auth_btn(row, "expired")
            messagebox.showerror("인증 오류", str(e))

    # ── 도움말 탭 ───────────────────────────────────────────────────
    def _build_help_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="도움말")

        text = scrolledtext.ScrolledText(
            frame, wrap="word", font=("", 10), state="normal",
            padx=10, pady=8, relief="flat",
        )
        text.pack(fill="both", expand=True)

        # 태그 스타일 정의
        text.tag_config("h1", font=("", 13, "bold"), spacing1=10, spacing3=4)
        text.tag_config("h2", font=("", 11, "bold"), foreground="#2c3e50", spacing1=8, spacing3=2)
        text.tag_config("step", font=("Consolas", 10), foreground="#555555", lmargin1=16, lmargin2=16)
        text.tag_config("url",  font=("", 10, "underline"), foreground="#2980b9")
        text.tag_config("warn", foreground="#e74c3c", font=("", 10, "bold"))

        def h1(t):  text.insert("end", t + "\n", "h1")
        def h2(t):  text.insert("end", t + "\n", "h2")
        def step(t): text.insert("end", t + "\n", "step")
        def url(t):  text.insert("end", t + "\n", "url")
        def warn(t): text.insert("end", t + "\n", "warn")
        def br():    text.insert("end", "\n")

        # ── Kling AI ──────────────────────────────────────────────
        h1("🎬  Kling AI API Key / Secret")
        step("영상 생성에 사용됩니다. 무료 플랜: 66 크레딧/일 (워터마크 포함)")
        step("유료 Standard: $10/월, 660 크레딧 (상업적 사용 가능)")
        br()
        h2("발급 방법")
        step("1.  https://klingai.com 접속 → 우측 상단 로그인")
        step("2.  우측 상단 프로필 아이콘 → [API] 메뉴 클릭")
        step("3.  [Create API Key] 버튼 클릭")
        step("4.  생성된 Access Key → 'Kling API Key' 란에 입력")
        step("    생성된 Secret Key  → 'Kling API Secret' 란에 입력")
        br()

        # ── Claude (Anthropic) ────────────────────────────────────
        h1("🤖  LLM API Key — Claude (Anthropic)")
        step("대본 생성에 사용됩니다. 설정에서 LLM을 'claude'로 선택한 경우.")
        br()
        h2("발급 방법")
        step("1.  https://console.anthropic.com 접속 → 회원가입/로그인")
        step("2.  좌측 메뉴 [API Keys] 클릭")
        step("3.  [Create Key] 버튼 클릭 → 이름 입력 후 생성")
        step("4.  표시되는 키(sk-ant-...) 복사 → 'LLM API Key' 란에 입력")
        warn("    ⚠  키는 생성 시 한 번만 표시됩니다. 반드시 바로 복사하세요.")
        br()

        # ── OpenAI ────────────────────────────────────────────────
        h1("🤖  LLM / TTS API Key — OpenAI")
        step("LLM을 'openai'로 선택하거나, TTS를 'openai'로 선택한 경우 사용됩니다.")
        br()
        h2("발급 방법")
        step("1.  https://platform.openai.com 접속 → 로그인")
        step("2.  우측 상단 프로필 → [API keys] 클릭")
        step("3.  [+ Create new secret key] 클릭 → 이름 입력 후 생성")
        step("4.  표시되는 키(sk-...) 복사 → 'LLM API Key' 또는 'TTS API Key' 란에 입력")
        warn("    ⚠  키는 생성 시 한 번만 표시됩니다. 반드시 바로 복사하세요.")
        br()

        # ── ElevenLabs ────────────────────────────────────────────
        h1("🔊  TTS API Key — ElevenLabs")
        step("TTS를 'elevenlabs'로 선택한 경우 사용됩니다.")
        br()
        h2("발급 방법")
        step("1.  https://elevenlabs.io 접속 → 회원가입/로그인")
        step("2.  좌측 하단 프로필 아이콘 → [API Keys] 클릭")
        step("3.  [Generate API Key] 클릭 → 키 복사 → 'TTS API Key' 란에 입력")
        br()
        h2("Voice ID 찾기 (채널 설정 → ElevenLabs Voice ID)")
        step("1.  https://elevenlabs.io/voice-library 에서 원하는 목소리 선택")
        step("2.  목소리 클릭 → 상세 페이지 URL의 마지막 ID 값이 Voice ID")
        step("    예) /voice-lab/shared/abc123xyz  →  abc123xyz")
        br()

        # ── YouTube OAuth ─────────────────────────────────────────
        h1("📺  YouTube OAuth — 클라이언트 시크릿 파일")
        step("YouTube 업로드에 사용됩니다. Google Cloud Console에서 발급합니다.")
        br()
        h2("발급 방법")
        step("1.  https://console.cloud.google.com 접속 → 로그인")
        step("2.  상단 프로젝트 선택 → [새 프로젝트] 생성 (이름 자유)")
        step("3.  좌측 메뉴 [API 및 서비스] → [라이브러리]")
        step("4.  검색창에 'YouTube Data API v3' 검색 → 클릭 → [사용 설정]")
        step("5.  좌측 메뉴 [API 및 서비스] → [OAuth 동의 화면]")
        step("    - 사용자 유형: '외부' 선택 → [만들기]")
        step("    - 앱 이름, 이메일 입력 후 저장 (나머지는 기본값)")
        step("6.  좌측 메뉴 [사용자 인증 정보] → [+ 사용자 인증 정보 만들기]")
        step("    → [OAuth 클라이언트 ID] 선택")
        step("    → 애플리케이션 유형: '데스크톱 앱' 선택 → [만들기]")
        step("7.  생성된 항목 오른쪽 ↓ 버튼 → [JSON 다운로드]")
        step("    → 다운로드된 client_secret_xxx.json 파일 저장")
        step("8.  [채널 관리] 탭 상단 '파일 선택' 버튼으로 해당 파일 선택")
        warn("    ⚠  이 파일은 절대 외부에 공유하지 마세요.")
        br()
        step("9.  채널 목록에 채널 추가 후 [인증하기] 버튼 클릭")
        step("    → 브라우저에서 YouTube 계정 로그인 → 권한 허용")
        step("    → 완료되면 버튼이 '✓ 인증됨'으로 바뀝니다.")
        br()

        text.config(state="disabled")

    # ── 저장 ────────────────────────────────────────────────────────
    def _save(self):
        cfg = load_config()

        # API
        for key, var in self._api_vars.items():
            cfg["api"][key] = var.get()
        cfg["api"]["llm_provider"] = self._llm_var.get()
        cfg["api"]["tts_provider"] = self._tts_var.get()

        # 크롤링
        cfg["crawl"]["categories"] = [
            cat for cat, var in self._cat_vars.items() if var.get()
        ]
        cfg["crawl"]["queue_refill_size"] = self._refill_var.get()
        cfg["crawl"]["recursion_depth"] = self._depth_var.get()

        # 영상
        cfg["video"]["target_duration_sec"] = self._duration_var.get()
        cfg["video"]["tts_voice"] = self._voice_var.get()
        cfg["video"]["elevenlabs_voice_id"] = self._el_voice_var.get()
        cfg["video"]["kling_duration"] = self._kling_dur_var.get()

        # 업로드
        cfg["upload"]["daily_upload_limit"] = self._daily_var.get()
        cfg["upload"]["privacy_status"] = self._privacy_var.get()
        raw_tags = self._tags_var.get()
        cfg["upload"]["default_tags"] = [
            t.strip() for t in raw_tags.split(",") if t.strip()
        ]

        # 채널
        channels = []
        for row in self._channel_rows:
            ch_id = row["id"].get().strip()
            if ch_id:
                channels.append({
                    "id": ch_id,
                    "style": row["style"].get(),
                    "active": row["active"].get(),
                    "credentials_path": row["cred"].get().strip(),
                })
        cfg["channels"] = channels

        save_config(cfg)
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")
        self.destroy()


# ─── 메인 앱 ──────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("쇼츠 자동 양산기")
        self.geometry("760x600")
        self.resizable(True, True)
        self._running = False
        self._stop_event = threading.Event()
        self._build_ui()
        # 시작 시 설정 검증 (백그라운드)
        threading.Thread(target=self._startup_validation, daemon=True).start()

    def _build_ui(self):
        from tkinter import filedialog

        # ── 상단 버튼 바 ───────────────────────────────────────────
        top = tk.Frame(self, pady=6)
        top.pack(fill="x", padx=10)

        self._btn_area = tk.Frame(top)
        self._btn_area.pack(side="left")

        self._run_btn = tk.Button(
            self._btn_area, text="▶  파이프라인 실행", width=18,
            bg="#2ecc71", fg="white", font=("", 11, "bold"),
            command=self._run_pipeline,
        )
        self._run_btn.pack(side="left")

        self._stop_btn = tk.Button(
            self._btn_area, text="■  중지", width=8,
            bg="#e67e22", fg="white", font=("", 11, "bold"),
            command=self._stop_pipeline,
        )
        self._quit_btn = tk.Button(
            self._btn_area, text="✕  종료", width=8,
            bg="#e74c3c", fg="white", font=("", 11, "bold"),
            command=self.destroy,
        )

        tk.Button(top, text="⚙  설정", width=8,
                  command=lambda: SettingsWindow(self),
                  ).pack(side="left", padx=6)

        tk.Button(top, text="로그 지우기", width=10,
                  command=self._clear_log,
                  ).pack(side="left")

        self._status_lbl = tk.Label(top, text="대기 중", fg="gray")
        self._status_lbl.pack(side="right", padx=4)

        # ── 채널 패널 ──────────────────────────────────────────────
        ch_panel = tk.LabelFrame(self, text="YouTube 채널", padx=8, pady=6)
        ch_panel.pack(fill="x", padx=10, pady=(0, 4))

        # 채널 행 목록 영역
        self._ch_status_frame = tk.Frame(ch_panel)
        self._ch_status_frame.pack(fill="x")

        # + 채널 추가 버튼
        tk.Button(ch_panel, text="＋ 채널 추가",
                  command=self._show_add_channel_dialog
                  ).pack(anchor="w", pady=(4, 0))

        # ── 로그 창 ────────────────────────────────────────────────
        self._log = scrolledtext.ScrolledText(
            self, state="disabled", font=("Consolas", 10),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
        )
        self._log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._log.tag_config("ok",   foreground="#2ecc71")
        self._log.tag_config("warn", foreground="#f39c12")
        self._log.tag_config("err",  foreground="#e74c3c")
        self._log.tag_config("info", foreground="#d4d4d4")

    def log(self, msg: str, tag: str = "info"):
        """스레드 안전 로그 출력. tag: info / ok / warn / err"""
        def _append():
            self._log.config(state="normal")
            self._log.insert("end", msg + "\n", tag)
            self._log.see("end")
            self._log.config(state="disabled")
        self.after(0, _append)

    # ── 채널 추가 다이얼로그 ────────────────────────────────────────
    def _show_add_channel_dialog(self):
        from tkinter import filedialog

        dlg = tk.Toplevel(self)
        dlg.title("채널 추가")
        dlg.geometry("420x140")
        dlg.resizable(False, False)
        dlg.grab_set()

        ch_var   = tk.StringVar()
        cred_var = tk.StringVar()

        tk.Label(dlg, text="채널 ID").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        tk.Entry(dlg, textvariable=ch_var, width=30).grid(row=0, column=1, columnspan=2, padx=10, sticky="ew")

        tk.Label(dlg, text="인증파일").grid(row=1, column=0, padx=10, sticky="w")
        tk.Entry(dlg, textvariable=cred_var, width=22, state="readonly"
                 ).grid(row=1, column=1, padx=(10, 2), sticky="ew")
        tk.Button(dlg, text="선택",
                  command=lambda: cred_var.set(
                      filedialog.askopenfilename(
                          title="client_secret.json 선택",
                          filetypes=[("JSON", "*.json"), ("모든 파일", "*.*")]
                      ) or cred_var.get()
                  )).grid(row=1, column=2, padx=(0, 10))

        btn_frame = tk.Frame(dlg)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)

        def _confirm():
            ch_id = ch_var.get().strip()
            cred  = cred_var.get().strip()
            if not ch_id:
                messagebox.showwarning("입력 오류", "채널 ID를 입력하세요.", parent=dlg)
                return
            dlg.destroy()
            self._do_auth(ch_id, cred)

        tk.Button(btn_frame, text="인증하기", width=12, command=_confirm).pack(side="left", padx=4)
        tk.Button(btn_frame, text="취소",     width=8,  command=dlg.destroy).pack(side="left")

        dlg.columnconfigure(1, weight=1)

    def _do_auth(self, ch_id: str, cred: str):
        """채널 OAuth 인증 실행 (백그라운드)"""
        from uploader.youtube import authenticate

        self.log(f"[인증] {ch_id} 인증 시작 — 브라우저를 확인하세요...", "warn")

        def _run():
            try:
                cfg = load_config()
                channels = cfg.get("channels", [])
                existing = next((c for c in channels if c["id"] == ch_id), None)
                if existing:
                    if cred:
                        existing["credentials_path"] = cred
                else:
                    channels.append({"id": ch_id, "style": "default",
                                     "active": True, "credentials_path": cred})
                cfg["channels"] = channels
                save_config(cfg)

                authenticate(channel_id=ch_id, credentials_path=cred or None, log=self.log)
                self.log(f"[인증] ✓ {ch_id} 인증 완료", "ok")
                self.after(0, self._refresh_channel_status)
            except Exception as e:
                self.log(f"[인증] ✗ {ch_id} 인증 실패: {e}", "err")

        threading.Thread(target=_run, daemon=True).start()

    def _refresh_channel_status(self):
        """채널 상태 패널 갱신 — 각 채널 row에 상태 + 재인증 버튼"""
        from uploader.youtube import check_token
        for w in self._ch_status_frame.winfo_children():
            w.destroy()

        cfg = load_config()
        channels = cfg.get("channels", [])
        if not channels:
            tk.Label(self._ch_status_frame, text="등록된 채널 없음   (아래 + 버튼으로 추가하세요)",
                     fg="gray").pack(anchor="w", padx=4)
            return

        for ch in channels:
            ch_id  = ch.get("id", "")
            cred   = ch.get("credentials_path", "")
            status = check_token(ch_id)
            ok     = status in ("valid", "refreshed")

            row_fr = tk.Frame(self._ch_status_frame)
            row_fr.pack(fill="x", pady=1)

            icon_lbl = tk.Label(row_fr,
                                text=f"{'✓' if ok else '✗'}  {ch_id}",
                                fg="#27ae60" if ok else "#e74c3c",
                                font=("", 10, "bold"), width=24, anchor="w")
            icon_lbl.pack(side="left", padx=(2, 8))

            btn_text = "✓ 인증됨" if ok else "재인증"
            btn = tk.Button(row_fr, text=btn_text, width=10,
                            command=lambda c=ch_id, p=cred: self._do_auth(c, p))
            btn.pack(side="left")

    # ── 시작 시 전체 설정 검증 ─────────────────────────────────────
    def _startup_validation(self):
        import time
        time.sleep(0.3)  # UI 렌더링 대기
        self.log("─" * 48, "info")
        self.log("  시작 검증 중...", "info")
        self.log("─" * 48, "info")

        cfg = load_config()
        api = cfg.get("api", {})
        all_ok = True

        # ── API 키 확인 ──────────────────────────────────────────
        checks = [
            ("Kling API Key",    api.get("kling_api_key", "")),
            ("Kling API Secret", api.get("kling_api_secret", "")),
            ("LLM API Key",      api.get("llm_api_key", "")),
            ("TTS API Key",      api.get("tts_api_key", "")),
        ]
        for name, val in checks:
            if val:
                self.log(f"  ✓  {name}", "ok")
            else:
                self.log(f"  ✗  {name} 미설정  →  ⚙ 설정 > API 설정 탭에서 입력하세요", "err")
                all_ok = False

        # ── 채널 토큰 확인 ────────────────────────────────────────
        from uploader.youtube import check_token
        channels = cfg.get("channels", [])
        if not channels:
            self.log("  ✗  등록된 YouTube 채널 없음  →  위 채널 패널에서 추가하세요", "err")
            all_ok = False
        else:
            for ch in channels:
                ch_id  = ch.get("id", "")
                active = ch.get("active", True)
                if not active:
                    self.log(f"  -  {ch_id}  (비활성화)", "info")
                    continue
                status = check_token(ch_id)
                if status in ("valid", "refreshed"):
                    self.log(f"  ✓  채널 [{ch_id}] 인증 유효", "ok")
                elif status == "expired":
                    self.log(f"  ✗  채널 [{ch_id}] 인증 만료  →  위 패널에서 재인증하세요", "err")
                    all_ok = False
                else:
                    self.log(f"  ✗  채널 [{ch_id}] 인증 없음  →  위 패널에서 인증하세요", "err")
                    all_ok = False

        self.log("─" * 48, "info")
        if all_ok:
            self.log("  모든 설정 정상. 파이프라인을 실행할 수 있습니다.", "ok")
        else:
            self.log("  일부 설정이 필요합니다. 위 항목을 확인하세요.", "warn")
        self.log("─" * 48, "info")

        # 채널 상태 패널도 갱신
        self.after(0, self._refresh_channel_status)

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _stop_pipeline(self):
        self._stop_event.set()
        self.after(0, lambda: self._stop_btn.config(text="중지 중...", state="disabled"))

    def _set_running(self, running: bool):
        self._running = running
        if running:
            self._run_btn.pack_forget()
            self._stop_btn.config(text="■  중지", state="normal")
            self._stop_btn.pack(side="left")
            self._quit_btn.pack(side="left", padx=(4, 0))
        else:
            self._stop_btn.pack_forget()
            self._quit_btn.pack_forget()
            self._run_btn.pack(side="left")
        status = "실행 중..." if running else "완료"
        color = "orange" if running else "green"
        self.after(0, lambda: self._status_lbl.config(text=status, fg=color))

    def _run_pipeline(self):
        if self._running:
            return

        # 파이프라인 실행 전 활성 채널 토큰 사전 검증
        cfg = load_config()
        channels = [c for c in cfg.get("channels", []) if c.get("active", True)]
        if not channels:
            channels = [{"id": "default"}]

        from uploader.youtube import check_token
        invalid = []
        for ch in channels:
            status = check_token(ch["id"])
            if status in ("expired", "missing"):
                invalid.append(ch["id"])

        if invalid:
            names = ", ".join(invalid)
            if not messagebox.askyesno(
                "인증 필요",
                f"다음 채널의 인증이 만료되었거나 없습니다:\n{names}\n\n"
                "그래도 실행할까요? (업로드 단계에서 실패할 수 있습니다)"
            ):
                return

        self._stop_event.clear()
        self._set_running(True)
        thread = threading.Thread(target=self._pipeline_thread, daemon=True)
        thread.start()

    def _pipeline_thread(self):
        try:
            from crawler.fetcher import fetch_sources
            from script.generator import generate_scripts
            from video.tts import run_tts_batch
            from video.kling import run_kling_batch
            from video.composer import run_compose_batch
            from uploader.youtube import run_upload_batch

            cfg = load_config()
            n = cfg["upload"].get("daily_upload_limit", 3)
            channels = cfg.get("channels", [])
            active_channels = [c for c in channels if c.get("active", True)]
            if not active_channels:
                active_channels = [{"id": "default", "style": "default"}]

            def stopped():
                if self._stop_event.is_set():
                    self.log("[중지] 파이프라인이 중지되었습니다.", "warn")
                    return True
                return False

            # Phase 1
            self.log("[Phase 1] Wikipedia 소스 수집")
            fetched = fetch_sources(n=n, log=self.log)
            if stopped(): return

            # Phase 2
            self.log("[Phase 2] 대본 생성")
            total_scripts = 0
            for ch in active_channels:
                if stopped(): return
                total_scripts += generate_scripts(
                    n=n, channel_id=ch.get("id", "default"),
                    style=ch.get("style", "default"), log=self.log)

            if stopped(): return

            # Phase 3-1
            self.log("[Phase 3-1] TTS 변환")
            tts_done = run_tts_batch(n=total_scripts or n, log=self.log)
            if stopped(): return

            # Phase 3-2
            self.log("[Phase 3-2] Kling 영상 생성")
            kling_done = run_kling_batch(n=tts_done or n, log=self.log)
            if stopped(): return

            # Phase 3-3
            self.log("[Phase 3-3] FFmpeg 합성")
            composed = run_compose_batch(n=kling_done or n, log=self.log)
            if stopped(): return

            # Phase 4
            self.log("[Phase 4] YouTube 업로드")
            uploaded = run_upload_batch(n=composed or n, log=self.log)

            self.after(0, lambda: messagebox.showinfo(
                "완료", "파이프라인 실행이 완료되었습니다."
            ))
        except Exception as e:
            self.log(f"[오류] {e}", "err")
            self.after(0, lambda: messagebox.showerror("오류", str(e)))
        finally:
            self._stop_event.clear()
            self.after(0, lambda: self._set_running(False))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
