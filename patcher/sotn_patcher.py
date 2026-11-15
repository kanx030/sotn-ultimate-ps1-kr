# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0-or-later
# 월하의 야상곡 얼티메이트 한글 패처 - https://github.com/kanx030/sotn-ultimate-ps1-kr
"""월하의 야상곡 얼티메이트 한글 패처 (tkinter 화면)."""
import os
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import sotn_core as core

TITLE = "월하의 야상곡 얼티메이트 한글 패처"
HEADLINE = "월하의 야상곡 얼티메이트 한글 패치 " + core.VERSION
DEFAULT_NAME = core.DEFAULT_NAME

# 색 (어두운 남색 + 붉은 강조)
BG = "#120d16"
BAND = "#08060a"
CARD = "#1e1524"
EDGE = "#3a2944"
FIELD = "#0d0910"
FG = "#efe8f2"
MUTED = "#a596ad"
ACCENT = "#b3202f"
ACCENT_HI = "#d93a49"
ACCENT_LO = "#5e1a24"
OK = "#45c47a"
WARN = "#f0b44c"

BASE_W = 660


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def pick_family(root):
    fams = set(tkfont.families(root))
    for f in ("Noto Sans KR", "Noto Sans CJK KR", "NanumGothic", "Nanum Gothic"):
        if f in fams:
            return f
    return tkfont.nametofont("TkDefaultFont", root).actual("family")


class App:
    def __init__(self, root):
        self.root = root
        root.title(TITLE)
        root.configure(bg=BG)
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.q = queue.Queue()
        self.worker = None
        self.cancel_flag = threading.Event()
        self.cands = []
        self.log_open = False

        fam = pick_family(root)
        self.f_base = (fam, 10)
        self.f_small = (fam, 9)
        self.f_card = (fam, 11, "bold")
        self.f_head = (fam, 15, "bold")
        self.f_btn = (fam, 13, "bold")
        self.f_result = (fam, 16, "bold")
        self._style()
        self._build()
        self._resize()
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.log("지원하는 이미지:\n" + core.expected_text())
        self.root.after(100, self.pump)

    # ------------------------------------------------------------ 모양
    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=self.f_base,
                    bordercolor=EDGE, lightcolor=CARD, darkcolor=CARD, troughcolor=FIELD,
                    fieldbackground=FIELD, selectbackground=ACCENT, selectforeground=FG,
                    focuscolor=ACCENT, insertcolor=FG)
        s.configure("Card.TFrame", background=CARD, relief="solid", borderwidth=1)
        s.configure("Card.TLabel", background=CARD, foreground=FG)
        s.configure("CardTitle.TLabel", background=CARD, foreground=FG, font=self.f_card)
        s.configure("Step.TLabel", background=ACCENT, foreground="#ffffff", font=self.f_card,
                    padding=(7, 0))
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=self.f_small)
        s.configure("Found.TLabel", background=CARD, foreground=OK, font=self.f_base)
        s.configure("Miss.TLabel", background=CARD, foreground=WARN, font=self.f_base)
        s.configure("Bg.TLabel", background=BG, foreground=MUTED, font=self.f_small)
        s.configure("Result.TLabel", background=BG, font=self.f_result)
        s.configure("TEntry", fieldbackground=FIELD, foreground=FG, bordercolor=EDGE,
                    lightcolor=FIELD, darkcolor=FIELD, padding=4)
        s.map("TEntry", fieldbackground=[("disabled", CARD), ("readonly", FIELD)],
              foreground=[("disabled", MUTED)], bordercolor=[("focus", ACCENT)])
        s.configure("TCombobox", fieldbackground=FIELD, background=EDGE, foreground=FG,
                    arrowcolor=FG, bordercolor=EDGE, lightcolor=FIELD, darkcolor=FIELD, padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", FIELD), ("disabled", CARD)],
              foreground=[("disabled", MUTED)], selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", FG)])
        self.root.option_add("*TCombobox*Listbox.background", FIELD)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.font", self.f_base)
        s.configure("TButton", background=EDGE, foreground=FG, bordercolor=EDGE,
                    lightcolor=EDGE, darkcolor=EDGE, padding=(10, 4))
        s.map("TButton", background=[("disabled", CARD), ("active", "#4e3858")],
              foreground=[("disabled", MUTED)])
        s.configure("Link.TButton", background=CARD, foreground=MUTED, bordercolor=CARD,
                    lightcolor=CARD, darkcolor=CARD, padding=(2, 0), font=self.f_small)
        s.map("Link.TButton", background=[("active", CARD), ("disabled", CARD)],
              foreground=[("active", FG), ("disabled", EDGE)])
        s.configure("Toggle.TButton", background=BG, foreground=MUTED, bordercolor=BG,
                    lightcolor=BG, darkcolor=BG, padding=(0, 0), font=self.f_small)
        s.map("Toggle.TButton", background=[("active", BG)], foreground=[("active", FG)])
        s.configure("Start.TButton", background=ACCENT, foreground="#ffffff", font=self.f_btn,
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT, padding=(10, 8))
        s.map("Start.TButton", background=[("disabled", ACCENT_LO), ("active", ACCENT_HI)],
              foreground=[("disabled", "#c9a0a4")])
        s.configure("TRadiobutton", background=CARD, foreground=FG, indicatorbackground=FIELD,
                    indicatorforeground=ACCENT, font=self.f_base)
        s.map("TRadiobutton", background=[("active", CARD)],
              indicatorbackground=[("selected", FIELD)], foreground=[("disabled", MUTED)])
        s.configure("Card.TCheckbutton", background=CARD, foreground=FG, indicatorbackground=FIELD,
                    indicatorforeground=ACCENT, font=self.f_base)
        s.map("Card.TCheckbutton", background=[("active", CARD)],
              indicatorbackground=[("selected", FIELD)], foreground=[("disabled", MUTED)])
        s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=FIELD,
                    bordercolor=EDGE, lightcolor=ACCENT_HI, darkcolor=ACCENT, thickness=14)
        s.configure("Vertical.TScrollbar", background=EDGE, troughcolor=FIELD, arrowcolor=FG,
                    bordercolor=FIELD)

    def _card(self, parent, num, title):
        c = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8, 12, 10))
        c.pack(fill="x", pady=(0, 8))
        c.columnconfigure(1, weight=1)
        h = ttk.Frame(c, style="Card.TFrame", borderwidth=0)
        h.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(h, text=num, style="Step.TLabel").pack(side="left")
        ttk.Label(h, text="  " + title, style="CardTitle.TLabel").pack(side="left")
        return c

    def _build(self):
        root = self.root
        # 제목 띠
        band = tk.Frame(root, bg=BAND, height=int(96 * self.scale))
        band.pack(fill="x")
        band.pack_propagate(False)
        try:
            lf = "logo.png" if self.scale < 1.25 else ("logo_15.png" if self.scale < 1.75 else "logo_2.png")
            self.logo = tk.PhotoImage(file=resource(lf))
            tk.Label(band, image=self.logo, bg=BAND, bd=0).pack(side="left", padx=(16, 14))
        except tk.TclError:
            pass
        tb = tk.Frame(band, bg=BAND)
        tb.pack(side="left")
        tk.Label(tb, text=HEADLINE, bg=BAND, fg=FG, font=self.f_head).pack(anchor="w")
        tk.Label(tb, text="원본으로 새로 패치하거나, 예전 한글판을 최신 판으로 바꿉니다", bg=BAND, fg=MUTED,
                 font=self.f_small).pack(anchor="w")
        tk.Frame(root, bg=ACCENT, height=3).pack(fill="x")

        body = ttk.Frame(root, padding=(16, 12, 16, 10))
        body.pack(fill="both", expand=True)

        # ① 원본
        c1 = self._card(body, "1", "원본 또는 예전 한글판 폴더 선택")
        self.src_dir = tk.StringVar()
        self.e_src = ttk.Entry(c1, textvariable=self.src_dir, state="readonly")
        self.e_src.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8))
        self.b_src = ttk.Button(c1, text="폴더 고르기", command=self.pick_folder)
        self.b_src.grid(row=1, column=2, sticky="e")
        self.found = ttk.Label(c1, text="롬 파일(bin/cue, CHD, iso)이 있는 폴더를 고르세요. 원본인지 예전 한글판인지는 자동으로 알아냅니다.",
                               style="Muted.TLabel")
        self.found.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.cand_var = tk.StringVar()
        self.cb = ttk.Combobox(c1, textvariable=self.cand_var, state="readonly")
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.on_cand())
        self.b_file = ttk.Button(c1, text="파일 직접 고르기…", style="Link.TButton", command=self.pick_file)
        self.b_file.grid(row=4, column=2, sticky="e", pady=(4, 0))

        # ② 형식
        c2 = self._card(body, "2", "저장 방식 (원본으로 새로 만들 때)")
        self.fmt = tk.StringVar(value="bincue")
        self.r1 = ttk.Radiobutton(c2, text="BIN/CUE", variable=self.fmt, value="bincue")
        self.r1.grid(row=1, column=0, sticky="w")
        ttk.Label(c2, text="압축 없는 이미지 (bin 1개 약 709MB + cue).",
                  style="Muted.TLabel").grid(row=1, column=1, columnspan=2, sticky="w", padx=(6, 0))
        self.r2 = ttk.Radiobutton(c2, text="CHD", variable=self.fmt, value="chd")
        self.r2.grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(c2, text="압축 이미지 한 파일 (약 530MB). 대부분의 에뮬레이터에서 바로 실행.",
                  style="Muted.TLabel").grid(row=2, column=1, columnspan=2, sticky="w", padx=(6, 0), pady=(4, 0))

        # ③ 저장
        c3 = self._card(body, "3", "저장 위치 · 이름 (원본으로 새로 만들 때)")
        self.out = tk.StringVar()
        self.e_out = ttk.Entry(c3, textvariable=self.out)
        self.e_out.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8))
        self.b_out = ttk.Button(c3, text="폴더 고르기", command=self.pick_out)
        self.b_out.grid(row=1, column=2, sticky="e")
        ttk.Label(c3, text="파일 이름", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.name = tk.StringVar(value=DEFAULT_NAME)
        self.e_name = ttk.Entry(c3, textvariable=self.name)
        self.e_name.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(6, 0), padx=(8, 0))
        ttk.Label(c3, text="예전 한글판은 이 칸과 상관없이 원래 자리에서 같은 이름·형식으로 최신 판이 됩니다.",
                  style="Muted.TLabel").grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # 시작/진행
        act = ttk.Frame(body)
        act.pack(fill="x", pady=(4, 0))
        act.columnconfigure(0, weight=1)
        self.b_start = ttk.Button(act, text="패치 시작", style="Start.TButton", command=self.start)
        self.b_start.grid(row=0, column=0, sticky="ew")
        self.b_cancel = ttk.Button(act, text="취소", command=self.cancel, state="disabled")
        self.b_cancel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.bar = ttk.Progressbar(act, maximum=1000)
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        st = ttk.Frame(act)
        st.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.stage = ttk.Label(st, text="대기 중", style="Bg.TLabel")
        self.stage.pack(side="left")
        self.b_log = ttk.Button(st, text="▸ 기록 보기", style="Toggle.TButton", command=self.toggle_log)
        self.b_log.pack(side="right")
        self.result = ttk.Label(act, text="", style="Result.TLabel", anchor="center")
        self.result.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        self.log_frame = tk.Frame(body, bg=BG)
        self.log_box = tk.Text(self.log_frame, height=8, wrap="word", state="disabled", bg=FIELD, fg=FG,
                               insertbackground=FG, relief="flat", font=self.f_small,
                               highlightthickness=1, highlightbackground=EDGE, padx=6, pady=4)
        sb = ttk.Scrollbar(self.log_frame, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)
        self.log_box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.inputs = [self.b_src, self.b_file, self.cb, self.r1, self.r2, self.e_out, self.b_out,
                       self.e_name, self.b_start]

    def _resize(self):
        """가로는 고정, 세로는 내용(후보 목록·기록 창 펼침)에 맞춰 정한다. 사용자가 크기를 바꿀 수는 없음."""
        self.root.update_idletasks()
        h = self.root.winfo_reqheight()
        self.root.geometry(f"{int(BASE_W * self.scale)}x{h}")

    def toggle_log(self):
        self.log_open = not self.log_open
        if self.log_open:
            self.log_frame.pack(fill="both", expand=True, pady=(6, 0))
            self.b_log.configure(text="▾ 기록 접기")
        else:
            self.log_frame.pack_forget()
            self.b_log.configure(text="▸ 기록 보기")
        self._resize()

    # ------------------------------------------------------------ 입력
    def pick_folder(self):
        p = filedialog.askdirectory(title="원본 롬 파일이 있는 폴더 고르기")
        if p:
            self.set_folder(os.path.normpath(p))

    def set_folder(self, folder, quiet=False):
        self.src_dir.set(folder)
        self.cands = core.scan_folder(folder)
        self.cb.grid_forget()
        if not self.cands:
            msg = core.not_found_message(folder)
            self.found.configure(text="✖ 원본이나 예전 한글판을 찾지 못했습니다. (기록 보기에서 자세히)",
                                 style="Miss.TLabel")
            self._resize()
            self.log(msg)
            if not quiet:
                messagebox.showwarning(TITLE, msg)
            return
        if not self.out.get():
            self.out.set(folder)
        if len(self.cands) > 1:
            self.cb["values"] = [self.cand_text(c) for c in self.cands]
            self.cb.current(0)
            self.cb.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self._resize()
        self.log(f"폴더에서 후보 {len(self.cands)}개를 찾았습니다. (원본·한글판 구별은 패치할 때 확인)")
        for c in self.cands:
            self.log("  " + self.cand_text(c))
        self.on_cand()

    def cand_text(self, c):
        rel = os.path.relpath(c["src"], self.src_dir.get())
        return f"{c['kind']} · {rel}"

    def selected(self):
        if not self.cands:
            return None
        i = self.cb.current() if len(self.cands) > 1 else 0
        return self.cands[max(i, 0)]

    def on_cand(self):
        c = self.selected()
        if not c:
            return
        more = f"   (후보 {len(self.cands)}개 — 아래 목록에서 고를 수 있어요)" if len(self.cands) > 1 else ""
        self.found.configure(
            text=f"✔ 찾음: {os.path.basename(c['src'])}\n     {c['kind']} — 원본인지 예전 한글판인지는 패치할 때 확인합니다{more}",
            style="Found.TLabel")

    def pick_file(self):
        p = filedialog.askopenfilename(
            title="원본 또는 예전 한글판 이미지 직접 고르기",
            filetypes=[("CD 이미지 (cue, bin, chd, iso, img)", "*.cue *.bin *.chd *.iso *.img"), ("모든 파일", "*.*")])
        if not p:
            return
        p = os.path.normpath(p)
        self.src_dir.set(os.path.dirname(p))
        self.cb.grid_forget()
        self.cands = [{"src": p, "kind": "직접 고른 파일"}]
        self.found.configure(text=f"직접 고른 파일: {os.path.basename(p)}\n     원본인지 예전 한글판인지는 패치할 때 확인합니다.",
                             style="Found.TLabel")
        if not self.out.get():
            self.out.set(os.path.dirname(p))
        self._resize()

    def pick_out(self):
        p = filedialog.askdirectory(title="저장할 폴더 고르기")
        if p:
            self.out.set(os.path.normpath(p))

    def log(self, s):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", s + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------ 작업
    def set_busy(self, busy):
        for w in self.inputs:
            if w is self.cb:
                w.configure(state="disabled" if busy else "readonly")
            else:
                w.configure(state="disabled" if busy else "normal")
        self.b_cancel.configure(state="normal" if busy else "disabled")

    def start(self):
        c = self.selected()
        out, name = self.out.get().strip(), self.name.get().strip()
        if not c:
            messagebox.showerror(TITLE, "먼저 ① 에서 원본이나 예전 한글판이 있는 폴더를 골라 주세요.")
            return
        if not out or not os.path.isdir(out):
            messagebox.showerror(TITLE, "③ 에서 저장할 폴더를 골라 주세요.")
            return
        if not name:
            name = DEFAULT_NAME
            self.name.set(name)
        self.cancel_flag.clear()
        self.set_busy(True)
        self.bar["value"] = 0
        self.result.configure(text="")
        self.log("\n── 패치 시작 ──\n원본: " + c["src"])
        self.worker = threading.Thread(target=self.work, args=(c["src"], out, name, self.fmt.get(), True),
                                       daemon=True)
        self.worker.start()

    def work(self, src, out, name, fmt, replace):
        try:
            made = core.run_patch(
                src, out, name, fmt,
                log=lambda s: self.q.put(("log", s)),
                progress=lambda st, f: self.q.put(("prog", st, f)),
                cancel=self.cancel_flag.is_set,
                replace=replace)
            self.q.put(("done", made))
        except core.AlreadyLatest as e:
            self.q.put(("latest", str(e)))
        except core.Cancelled:
            self.q.put(("cancelled",))
        except core.PatchError as e:
            self.q.put(("error", str(e)))
        except Exception as e:  # 예상 못 한 오류
            self.q.put(("error", f"예상하지 못한 오류가 났습니다:\n{type(e).__name__}: {e}"))

    def pump(self):
        try:
            while True:
                m = self.q.get_nowait()
                k = m[0]
                if k == "log":
                    self.log(m[1])
                elif k == "prog":
                    self.stage.configure(text=f"{m[1]}  {m[2] * 100:5.1f}%")
                    self.bar["value"] = m[2] * 1000
                elif k == "done":
                    self.set_busy(False)
                    self.log("완료! " + m[1][1] + "\n" + "\n".join(m[1][0]))
                    self.stage.configure(text="완료 — 결과가 최신 한글판과 정확히 일치합니다")
                    self.result.configure(text="✔ 패치 성공", foreground=OK)
                    self.on_done(m[1])
                elif k == "latest":
                    self.set_busy(False)
                    self.log(m[1])
                    self.stage.configure(text="이미 최신 판입니다")
                    self.result.configure(text="✔ 이미 최신입니다", foreground=OK)
                    self.bar["value"] = 1000
                    messagebox.showinfo(TITLE, m[1])
                elif k == "cancelled":
                    self.set_busy(False)
                    self.log("취소했습니다. 임시 파일을 지웠습니다.")
                    self.stage.configure(text="취소됨 — 임시 파일을 지웠습니다")
                    self.result.configure(text="취소됨", foreground=WARN)
                    self.bar["value"] = 0
                elif k == "error":
                    self.set_busy(False)
                    self.log("오류: " + m[1])
                    self.stage.configure(text="실패 — 자세한 내용은 기록을 보세요")
                    self.result.configure(text="✖ 패치 실패", foreground=ACCENT_HI)
                    self.bar["value"] = 0
                    self.on_error(m[1])
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def on_done(self, made):
        messagebox.showinfo(TITLE, made[1] + "\n\n파일:\n" + "\n".join(made[0]))

    def on_error(self, msg):
        messagebox.showerror(TITLE, msg)

    def cancel(self):
        if self.worker and self.worker.is_alive():
            self.cancel_flag.set()
            self.log("취소하는 중...")

    def close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(TITLE, "작업 중입니다. 취소하고 닫을까요?"):
                return
            self.cancel_flag.set()
            self.worker.join(15)
        self.root.destroy()


def cli(args):
    """창 없이 실행 (시험용): --cli <이미지 또는 폴더> <저장폴더> <이름> <bincue|chd> <new|replace> <기록파일>"""
    src, out, name, fmt, replace, logf = args
    with open(logf, "w", encoding="utf-8") as lf:
        def log(s):
            lf.write(s + "\n")
            lf.flush()
        try:
            if os.path.isdir(src):
                cands = core.scan_folder(src)
                for c in cands:
                    log(f"후보: {c['kind']} | {c['src']}")
                if not cands:
                    log("결과: 오류\n" + core.not_found_message(src))
                    return 2
                src = cands[0]["src"]
            made, what = core.run_patch(src, out, name, fmt, log, lambda st, f: None, lambda: False,
                                        replace=(replace == "replace"))
            log("결과: 성공 " + what + " " + " | ".join(made))
            return 0
        except core.PatchError as e:
            log("결과: 오류\n" + str(e))
            return 2


def make_root():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.iconbitmap(default=resource("icon.ico"))
    except Exception:
        pass
    return root


def main():
    if len(sys.argv) == 8 and sys.argv[1] == "--cli":
        sys.exit(cli(sys.argv[2:]))
    root = make_root()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
