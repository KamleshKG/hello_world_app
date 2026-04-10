"""
PyPlayer — Full Featured Edition
==================================
Requirements:
    pip install customtkinter python-mpv mutagen Pillow pystray openai-whisper

Features:
  ✅ System tray  — minimize to tray, right-click menu
  ✅ Resume       — remembers last position per file (SQLite)
  ✅ Speed control — 0.5x → 2.0x (dropdown, keyboard [ ])
  ✅ Whisper       — one-click transcribe current file

Also needs: libmpv-2.dll next to this file (or in PATH)
            Download: https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import os
import sys
import math
import random
import sqlite3
from pathlib import Path
from mutagen import File as MutagenFile
from PIL import Image, ImageDraw

# ─── Optional deps ────────────────────────────────────────────────────────────
try:
    import mpv
    MPV_AVAILABLE = True
except Exception:
    MPV_AVAILABLE = False

try:
    import pystray
    from pystray import MenuItem as TrayItem
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

try:
    import whisper as _whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# ─── Paths ────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "pyplayer_resume.db"

# ─── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DARK_BG      = "#1a1a1a"
PANEL_BG     = "#242424"
CARD_BG      = "#2d2d2d"
ACCENT       = "#3b82f6"
ACCENT_HOVER = "#2563eb"
TEXT_PRI     = "#f1f5f9"
TEXT_SEC     = "#94a3b8"
TEXT_MUT     = "#475569"
SEEK_BG      = "#374151"
SEEK_FG      = "#3b82f6"
ACTIVE_ITEM  = "#1e3a5f"
GREEN        = "#22c55e"

SUPPORTED = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
    ".m4v", ".ts", ".mpg", ".mpeg",
    ".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"
}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
             ".wmv", ".m4v", ".ts", ".mpg", ".mpeg"}
AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"}
SPEEDS    = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt_time(s):
    if s is None or s < 0: return "0:00"
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def get_metadata(path):
    info = {"title": Path(path).stem, "duration": None, "artist": "", "album": ""}
    try:
        f = MutagenFile(path, easy=True)
        if f:
            info["duration"] = getattr(f.info, "length", None)
            info["title"]    = str(f.get("title",  [Path(path).stem])[0])
            info["artist"]   = str(f.get("artist", [""])[0])
            info["album"]    = str(f.get("album",  [""])[0])
    except Exception:
        pass
    return info


def make_audio_art(size=200):
    img  = Image.new("RGB", (size, size), "#1e293b")
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    r  = size // 3
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#3b82f6")
    ir = r // 3
    draw.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], fill="#1e293b")
    draw.ellipse([cx-4,  cy-4,  cx+4,  cy+4],  fill="#3b82f6")
    for i in range(8):
        a  = math.radians(i * 45)
        draw.line([(cx+(r+4)*math.cos(a),  cy+(r+4)*math.sin(a)),
                   (cx+(r+12)*math.cos(a), cy+(r+12)*math.sin(a))],
                  fill="#60a5fa", width=2)
    return img


def make_tray_image():
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="#3b82f6")
    draw.polygon([(20, 16), (20, 48), (50, 32)], fill="white")
    return img


# ─── Resume DB ────────────────────────────────────────────────────────────────

class ResumeDB:
    def __init__(self, db_path):
        self._lock = threading.Lock()
        self._con  = sqlite3.connect(str(db_path), check_same_thread=False)
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS resume
                (path TEXT PRIMARY KEY, pos REAL, updated INTEGER);
            CREATE TABLE IF NOT EXISTS recent
                (path TEXT PRIMARY KEY, updated INTEGER);
        """)
        self._con.commit()

    def save(self, path, pos):
        t = int(time.time())
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO resume VALUES(?,?,?)", (path, pos, t))
            self._con.execute(
                "INSERT OR REPLACE INTO recent VALUES(?,?)", (path, t))
            self._con.commit()

    def get(self, path):
        with self._lock:
            row = self._con.execute(
                "SELECT pos FROM resume WHERE path=?", (path,)).fetchone()
        return row[0] if row else 0.0

    def recent(self, limit=10):
        with self._lock:
            rows = self._con.execute(
                "SELECT path FROM recent ORDER BY updated DESC LIMIT ?",
                (limit,)).fetchall()
        return [r[0] for r in rows if Path(r[0]).exists()]

    def close(self):
        try: self._con.close()
        except Exception: pass


# ─── Seek bar ─────────────────────────────────────────────────────────────────

class SeekBar(tk.Canvas):
    def __init__(self, master, **kwargs):
        kwargs.pop("bg", None)
        super().__init__(master, height=16, bg=PANEL_BG,
                         highlightthickness=0, cursor="hand2", **kwargs)
        self._v = 0.0
        self._hover = self._drag = False
        self._cb = None
        self.bind("<Configure>",       self._draw)
        self.bind("<ButtonPress-1>",   self._press)
        self.bind("<B1-Motion>",       self._move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", False) or self._draw())
        self.bind("<Enter>",           lambda e: setattr(self, "_hover", True)  or self._draw())
        self.bind("<Leave>",           lambda e: setattr(self, "_hover", False) or self._draw())

    def set_command(self, fn): self._cb = fn
    def get(self): return self._v
    def set(self, v):
        self._v = max(0.0, min(1.0, v))
        self._draw()

    def _draw(self, *_):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        y1, y2 = h//2-2, h//2+2
        r = 4 if (self._hover or self._drag) else 3
        self.create_rectangle(8, y1, w-8, y2, fill=SEEK_BG, outline="")
        fx = 8 + (w-16)*self._v
        if fx > 8:
            self.create_rectangle(8, y1, fx, y2, fill=SEEK_FG, outline="")
        self.create_oval(fx-r, h//2-r, fx+r, h//2+r, fill=SEEK_FG, outline="")

    def _pv(self, x): return max(0.0, min(1.0, (x-8)/max(1, self.winfo_width()-16)))

    def _press(self, e):
        self._drag = True
        self._v = self._pv(e.x)
        self._draw()
        if self._cb: self._cb(self._v)

    def _move(self, e):
        if self._drag:
            self._v = self._pv(e.x)
            self._draw()
            if self._cb: self._cb(self._v)


# ─── Playlist item ────────────────────────────────────────────────────────────

class PlaylistItem(ctk.CTkFrame):
    def __init__(self, master, path, index, on_select, on_remove, **kw):
        super().__init__(master, fg_color="transparent", corner_radius=8, **kw)
        self.path = path; self.index = index
        self.on_select = on_select; self.on_remove = on_remove
        self.active = False
        self._build()

    def _build(self):
        meta = get_metadata(self.path)
        ext  = Path(self.path).suffix.lower()
        icon = "🎵" if ext in AUDIO_EXT else "🎬"
        self.configure(cursor="hand2")
        self.bind("<Button-1>", lambda e: self.on_select(self.index))
        self.bind("<Enter>",    lambda e: self.configure(fg_color=CARD_BG) if not self.active else None)
        self.bind("<Leave>",    lambda e: self.configure(fg_color=ACTIVE_ITEM if self.active else "transparent"))

        ic = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=16), width=28)
        ic.grid(row=0, column=0, rowspan=2, padx=(6,2), pady=3)
        ic.bind("<Button-1>", lambda e: self.on_select(self.index))

        name = meta["title"][:32] + ("…" if len(meta["title"])>32 else "")
        self.title_lbl = ctk.CTkLabel(self, text=name, anchor="w",
                                       font=ctk.CTkFont(size=11, weight="bold"),
                                       text_color=TEXT_PRI)
        self.title_lbl.grid(row=0, column=1, sticky="w")
        self.title_lbl.bind("<Button-1>", lambda e: self.on_select(self.index))

        dur = fmt_time(meta["duration"]) if meta["duration"] else "--:--"
        sub = ctk.CTkLabel(self, text=f"{dur}  {ext[1:].upper()}", anchor="w",
                            font=ctk.CTkFont(size=10), text_color=TEXT_SEC)
        sub.grid(row=1, column=1, sticky="w")
        sub.bind("<Button-1>", lambda e: self.on_select(self.index))

        ctk.CTkButton(self, text="✕", width=20, height=20,
                       fg_color="transparent", text_color=TEXT_MUT,
                       hover_color=CARD_BG, corner_radius=4,
                       command=lambda: self.on_remove(self.index)
                       ).grid(row=0, column=2, rowspan=2, padx=3)
        self.columnconfigure(1, weight=1)

    def set_active(self, v):
        self.active = v
        self.configure(fg_color=ACTIVE_ITEM if v else "transparent")
        self.title_lbl.configure(text_color=ACCENT if v else TEXT_PRI)


# ─── Speed popup ──────────────────────────────────────────────────────────────

class SpeedPopup(tk.Toplevel):
    """Tiny floating window that appears below the speed button."""
    def __init__(self, parent, current_speed, on_select):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=CARD_BG)
        self.attributes("-topmost", True)

        for spd in SPEEDS:
            active = abs(spd - current_speed) < 0.01
            fg = ACCENT if active else TEXT_PRI
            bg = SEEK_BG if active else CARD_BG
            hv = ACCENT_HOVER if active else SEEK_BG
            tk.Button(
                self, text=f"{spd}×", font=("Segoe UI", 10),
                fg=fg, bg=bg, activebackground=hv, activeforeground="white",
                relief="flat", padx=14, pady=4, cursor="hand2",
                command=lambda s=spd: (on_select(s), self.destroy())
            ).pack(fill="x")

        # Close on click-outside
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.focus_set()


# ─── Main player ──────────────────────────────────────────────────────────────

class PyPlayer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PyPlayer")
        self.geometry("1020x660")
        self.minsize(700, 480)
        self.configure(fg_color=DARK_BG)

        # Force window to appear on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"1020x660+{(sw-1020)//2}+{(sh-660)//2}")
        self.lift()
        self.focus_force()

        # State
        self.playlist    = []
        self.current_idx = -1
        self.is_playing  = False
        self.duration    = 0.0
        self.seeking     = False
        self.volume      = 80
        self._items_ui   = []
        self.repeat_mode = "none"
        self.shuffle_mode = False
        self._closing    = False
        self._speed_idx  = SPEEDS.index(1.0)
        self._whisper_model = None
        self._whisper_busy  = False
        self._tray_icon     = None
        self._in_tray       = False

        self.db      = ResumeDB(DB_PATH)
        self._player = None

        self._build_ui()
        self._init_mpv()
        self._setup_tray()
        self._autosave_tick()

    # ══════════════════════════════════════════════════════════════════════════
    # MPV
    # ══════════════════════════════════════════════════════════════════════════

    def _init_mpv(self):
        if not MPV_AVAILABLE:
            self._no_mpv_label()
            return
        try:
            self._player = mpv.MPV(
                wid=str(int(self.video_frame.winfo_id())),
                vo="gpu", hwdec="auto-safe",
                keep_open=True, idle=True,
                volume=self.volume,
                log_handler=print, loglevel="warn"
            )
            self._player.observe_property("time-pos",    self._on_time_pos)
            self._player.observe_property("duration",    self._on_duration)
            self._player.observe_property("eof-reached", self._on_eof)
            self._player.observe_property("pause",       self._on_pause_chg)
        except Exception as e:
            self._no_mpv_label(str(e))

    def _no_mpv_label(self, err=""):
        tk.Label(self.video_frame,
                 text=("libmpv not found.\n\n"
                       "Place libmpv-2.dll next to player.py\n"
                       "Download: sourceforge.net/projects/mpv-player-windows\n\n"
                       + err),
                 font=("Segoe UI", 11), fg=TEXT_SEC, bg="black",
                 justify="left", wraplength=380
                 ).place(relx=0.5, rely=0.5, anchor="center")

    # ══════════════════════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Draggable PanedWindow ─────────────────────────────────────────────
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               bg=DARK_BG, sashwidth=6, sashpad=2,
                               sashrelief="flat", opaqueresize=True,
                               showhandle=False)
        pane.pack(fill="both", expand=True, padx=6, pady=6)
        self._pane = pane

        # ── LEFT: video area + compact controls ───────────────────────────────
        left = tk.Frame(pane, bg=DARK_BG)
        pane.add(left, minsize=380, stretch="always", width=730)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        # Video canvas
        self.video_frame = tk.Frame(left, bg="black")
        self.video_frame.grid(row=0, column=0, sticky="nsew")

        self.art_label = tk.Label(self.video_frame, bg="black")

        # ── Title bar (1 line, very compact) ─────────────────────────────────
        tbar = tk.Frame(left, bg=PANEL_BG, height=24)
        tbar.grid(row=1, column=0, sticky="ew")
        tbar.columnconfigure(0, weight=1)
        tbar.grid_propagate(False)

        self.title_var = tk.StringVar(value="No file loaded")
        tk.Label(tbar, textvariable=self.title_var,
                 font=("Segoe UI", 9), fg=TEXT_SEC, bg=PANEL_BG,
                 anchor="w").grid(row=0, column=0, sticky="w", padx=8)

        self.resume_var = tk.StringVar(value="")
        tk.Label(tbar, textvariable=self.resume_var,
                 font=("Segoe UI", 9), fg=GREEN, bg=PANEL_BG
                 ).grid(row=0, column=1, sticky="e", padx=4)

        self.speed_var = tk.StringVar(value="1.0×")
        tk.Label(tbar, textvariable=self.speed_var,
                 font=("Segoe UI", 9), fg=TEXT_MUT, bg=PANEL_BG
                 ).grid(row=0, column=2, sticky="e", padx=8)

        # ── Seek bar ──────────────────────────────────────────────────────────
        sbar_frame = tk.Frame(left, bg=PANEL_BG, height=20)
        sbar_frame.grid(row=2, column=0, sticky="ew")
        sbar_frame.grid_propagate(False)
        self.seek_bar = SeekBar(sbar_frame)
        self.seek_bar.pack(fill="x", padx=8, pady=2)
        self.seek_bar.set_command(self._on_seek_drag)

        # ── Time row ──────────────────────────────────────────────────────────
        trow = tk.Frame(left, bg=PANEL_BG, height=16)
        trow.grid(row=3, column=0, sticky="ew")
        trow.grid_propagate(False)
        self.time_cur = tk.Label(trow, text="0:00",
                                  font=("Segoe UI", 8), fg=TEXT_MUT, bg=PANEL_BG)
        self.time_cur.pack(side="left", padx=10)
        self.time_dur = tk.Label(trow, text="0:00",
                                  font=("Segoe UI", 8), fg=TEXT_MUT, bg=PANEL_BG)
        self.time_dur.pack(side="right", padx=10)

        # ── Controls — single compact row ─────────────────────────────────────
        ctrl = tk.Frame(left, bg=PANEL_BG, height=52)
        ctrl.grid(row=4, column=0, sticky="ew")
        ctrl.grid_propagate(False)
        self._build_controls(ctrl)

        # ── RIGHT: playlist ───────────────────────────────────────────────────
        right = ctk.CTkFrame(pane, fg_color=PANEL_BG, corner_radius=8)
        pane.add(right, minsize=200, stretch="never", width=270)
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)
        self._build_playlist_panel(right)

    def _build_controls(self, parent):
        """Everything in ONE row — transport · vol · speed · whisper · fullscreen."""
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(expand=True, fill="both", padx=10)

        def ibtn(text, cmd, size=15, w=34, h=34, fg=TEXT_PRI, bg=PANEL_BG):
            b = tk.Button(row, text=text, command=cmd,
                           font=("Segoe UI", size), fg=fg, bg=bg,
                           activebackground=CARD_BG, activeforeground=fg,
                           relief="flat", bd=0, cursor="hand2",
                           width=2, padx=0)
            b.pack(side="left", padx=1, pady=8)
            return b

        # ── Shuffle
        self.shuffle_btn = tk.Button(
            row, text="⇌", font=("Segoe UI", 13), fg=TEXT_MUT, bg=PANEL_BG,
            activebackground=CARD_BG, activeforeground=TEXT_MUT,
            relief="flat", bd=0, cursor="hand2", width=2,
            command=self._toggle_shuffle)
        self.shuffle_btn.pack(side="left", padx=2, pady=8)

        # ── Prev / Play / Next
        ibtn("⏮", self._prev, size=14)

        self.pp_btn = tk.Button(
            row, text="▶", font=("Segoe UI", 18), fg="white", bg=ACCENT,
            activebackground=ACCENT_HOVER, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", width=2,
            command=self._toggle_play)
        self.pp_btn.pack(side="left", padx=4, pady=6)

        ibtn("⏭", self._next, size=14)

        # ── Repeat
        self.repeat_btn = tk.Button(
            row, text="↻", font=("Segoe UI", 13), fg=TEXT_MUT, bg=PANEL_BG,
            activebackground=CARD_BG, activeforeground=TEXT_MUT,
            relief="flat", bd=0, cursor="hand2", width=2,
            command=self._cycle_repeat)
        self.repeat_btn.pack(side="left", padx=2, pady=8)

        # ── Separator
        tk.Frame(row, bg=SEEK_BG, width=1, height=28).pack(
            side="left", padx=8, pady=12)

        # ── Volume icon + slider (compact)
        tk.Label(row, text="🔊", font=("Segoe UI", 12),
                 fg=TEXT_SEC, bg=PANEL_BG).pack(side="left", padx=(0, 2))
        self.vol_slider = ctk.CTkSlider(row, from_=0, to=100, width=80,
                                         height=14, command=self._on_volume)
        self.vol_slider.set(self.volume)
        self.vol_slider.pack(side="left", padx=4, pady=10)

        # ── Separator
        tk.Frame(row, bg=SEEK_BG, width=1, height=28).pack(
            side="left", padx=8, pady=12)

        # ── Speed button (shows popup)
        self.speed_btn = tk.Button(
            row, text="1.0×", font=("Segoe UI", 10), fg=TEXT_SEC, bg=CARD_BG,
            activebackground=SEEK_BG, activeforeground=TEXT_PRI,
            relief="flat", bd=0, cursor="hand2", padx=6, pady=2,
            command=self._show_speed_popup)
        self.speed_btn.pack(side="left", padx=4, pady=10)

        # ── Whisper button
        self.whisper_btn = tk.Button(
            row, text="🎙", font=("Segoe UI", 14), fg=TEXT_SEC, bg=PANEL_BG,
            activebackground=CARD_BG, activeforeground=TEXT_PRI,
            relief="flat", bd=0, cursor="hand2", width=2,
            command=self._transcribe)
        self.whisper_btn.pack(side="left", padx=4, pady=8)
        if not WHISPER_AVAILABLE:
            self.whisper_btn.configure(fg=TEXT_MUT, cursor="")

        # ── Fullscreen (right-aligned)
        tk.Frame(row, bg=PANEL_BG).pack(side="left", fill="x", expand=True)
        ibtn("⛶", self._toggle_fullscreen, size=14, fg=TEXT_MUT)

        # ── Key bindings
        self.bind("<space>",        lambda e: self._toggle_play())
        self.bind("<Left>",         lambda e: self._seek_rel(-5))
        self.bind("<Right>",        lambda e: self._seek_rel(5))
        self.bind("<Up>",           lambda e: self._vol_step(5))
        self.bind("<Down>",         lambda e: self._vol_step(-5))
        self.bind("<bracketleft>",  lambda e: self._speed_step(-1))
        self.bind("<bracketright>", lambda e: self._speed_step(1))
        self.bind("<F11>",          lambda e: self._toggle_fullscreen())
        self.bind("<Escape>",       lambda e: self.attributes("-fullscreen", False))

    def _build_playlist_panel(self, parent):
        # Header
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ctk.CTkLabel(hdr, text="Playlist",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_PRI).pack(side="left")
        ctk.CTkButton(hdr, text="Clear", width=48, height=24,
                       corner_radius=6, fg_color=CARD_BG,
                       text_color=TEXT_SEC, hover_color=SEEK_BG,
                       font=ctk.CTkFont(size=10),
                       command=self._clear_playlist).pack(side="right")

        # Add buttons
        br = ctk.CTkFrame(parent, fg_color="transparent")
        br.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        ctk.CTkButton(br, text="+ Files", height=28, corner_radius=6,
                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                       text_color="white", font=ctk.CTkFont(size=11),
                       command=self._add_files
                       ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(br, text="+ Folder", height=28, corner_radius=6,
                       fg_color=CARD_BG, hover_color=SEEK_BG,
                       text_color=TEXT_PRI, font=ctk.CTkFont(size=11),
                       command=self._add_folder
                       ).pack(side="left", fill="x", expand=True)

        # Recent
        ctk.CTkButton(parent, text="⏱ Recent", height=22, corner_radius=6,
                       fg_color="transparent", text_color=TEXT_MUT,
                       hover_color=CARD_BG, font=ctk.CTkFont(size=10),
                       command=self._load_recent
                       ).grid(row=2, column=0, sticky="ew", padx=10,
                               pady=(0, 4))

        # Scrollable list
        self.pl_frame = ctk.CTkScrollableFrame(
            parent, fg_color="transparent", corner_radius=0)
        self.pl_frame.grid(row=3, column=0, sticky="nsew", padx=2)

        # Count
        self.count_lbl = ctk.CTkLabel(parent, text="0 items",
                                       font=ctk.CTkFont(size=10),
                                       text_color=TEXT_MUT)
        self.count_lbl.grid(row=4, column=0, pady=6)

    # ══════════════════════════════════════════════════════════════════════════
    # TRAY
    # ══════════════════════════════════════════════════════════════════════════

    def _setup_tray(self):
        if not TRAY_AVAILABLE:
            return
        menu = pystray.Menu(
            TrayItem("PyPlayer", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            TrayItem("Show window",  self._tray_show),
            TrayItem("Hide to tray", self._tray_hide),
            pystray.Menu.SEPARATOR,
            TrayItem("Play / Pause", lambda i, it: self.after(0, self._toggle_play)),
            TrayItem("Next",         lambda i, it: self.after(0, self._next)),
            TrayItem("Previous",     lambda i, it: self.after(0, self._prev)),
            pystray.Menu.SEPARATOR,
            TrayItem("Exit",         lambda i, it: self.after(0, self.on_close)),
        )
        self._tray_icon = pystray.Icon(
            "PyPlayer", make_tray_image(), "PyPlayer", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()
        # NOTE: we do NOT bind <Unmap> here anymore.
        # Auto-hide-on-minimize was causing the window to vanish unexpectedly.
        # Use tray right-click → "Hide to tray" explicitly instead.

    def _tray_hide(self, *_):
        self._in_tray = True
        self.after(0, self.withdraw)

    def _tray_show(self, *_):
        self.after(0, self._show_window)

    def _tray_toggle(self, *_):
        if self._in_tray:
            self.after(0, self._show_window)
        else:
            self._tray_hide()

    def _show_window(self):
        self._in_tray = False
        self.deiconify()
        self.lift()
        self.focus_force()

    # ══════════════════════════════════════════════════════════════════════════
    # PLAYLIST
    # ══════════════════════════════════════════════════════════════════════════

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Select media files",
            filetypes=[("All media", " ".join(f"*{e}" for e in SUPPORTED)),
                       ("All files", "*.*")])
        for f in files: self._add_to_playlist(f)
        if files and self.current_idx == -1: self._play_index(0)

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if not folder: return
        found = sorted(str(p) for p in Path(folder).rglob("*")
                       if p.suffix.lower() in SUPPORTED)
        for f in found: self._add_to_playlist(f)
        if found and self.current_idx == -1: self._play_index(0)

    def _load_recent(self):
        for f in self.db.recent(10):
            if f not in self.playlist:
                self._add_to_playlist(f)
        if self.current_idx == -1 and self.playlist:
            self._play_index(0)

    def _add_to_playlist(self, path):
        self.playlist.append(path)
        idx  = len(self.playlist) - 1
        item = PlaylistItem(self.pl_frame, path, idx,
                             self._play_index, self._remove_item)
        item.pack(fill="x", pady=1)
        self._items_ui.append(item)
        n = len(self.playlist)
        self.count_lbl.configure(text=f"{n} item{'s' if n!=1 else ''}")

    def _remove_item(self, idx):
        if idx >= len(self.playlist): return
        self.playlist.pop(idx)
        self._items_ui.pop(idx).destroy()
        for i, w in enumerate(self._items_ui): w.index = i
        if self.current_idx == idx:
            if self._player: self._player.stop()
            self.current_idx = -1
            self.is_playing  = False
            self.pp_btn.configure(text="▶")
        elif self.current_idx > idx:
            self.current_idx -= 1
        n = len(self.playlist)
        self.count_lbl.configure(text=f"{n} item{'s' if n!=1 else ''}")

    def _clear_playlist(self):
        if self._player: self._player.stop()
        for w in self._items_ui: w.destroy()
        self.playlist.clear(); self._items_ui.clear()
        self.current_idx = -1; self.is_playing = False
        self.pp_btn.configure(text="▶")
        self.title_var.set("No file loaded")
        self.seek_bar.set(0)
        self.time_cur.configure(text="0:00")
        self.time_dur.configure(text="0:00")
        self.count_lbl.configure(text="0 items")
        self.resume_var.set("")

    # ══════════════════════════════════════════════════════════════════════════
    # PLAYBACK
    # ══════════════════════════════════════════════════════════════════════════

    def _play_index(self, idx):
        if not self._player or not (0 <= idx < len(self.playlist)): return
        self._save_pos()
        if 0 <= self.current_idx < len(self._items_ui):
            self._items_ui[self.current_idx].set_active(False)
        self.current_idx = idx
        path = self.playlist[idx]
        self._items_ui[idx].set_active(True)

        meta  = get_metadata(path)
        title = meta["title"]
        if meta["artist"]: title = f"{meta['artist']} — {title}"
        self.title_var.set(title)
        self.title(f"PyPlayer · {Path(path).name}")

        ext = Path(path).suffix.lower()
        if ext in AUDIO_EXT:
            img   = make_audio_art(180)
            photo = tk.PhotoImage(data=self._pil_to_tkdata(img))
            self._art_photo = photo
            self.art_label.configure(image=photo)
            self.art_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.art_label.place_forget()

        self._player.play(path)
        self._player.pause = False
        self.is_playing = True
        self.pp_btn.configure(text="⏸")
        self._apply_speed()

        saved = self.db.get(path)
        if saved and saved > 5:
            self.after(800, lambda p=saved: self._do_resume(p))
        else:
            self.resume_var.set("")

        if self._tray_icon:
            try: self._tray_icon.title = f"PyPlayer · {meta['title']}"
            except Exception: pass

    @staticmethod
    def _pil_to_tkdata(img):
        import io, base64
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue())

    def _do_resume(self, pos):
        if self._player and self.is_playing:
            try:
                self._player.seek(pos, reference="absolute")
                self.resume_var.set(f"↩ {fmt_time(pos)}")
                self.after(4000, lambda: self.resume_var.set(""))
            except Exception: pass

    def _toggle_play(self):
        if not self._player: return
        if self.current_idx == -1 and self.playlist:
            self._play_index(0); return
        self._player.pause = not self._player.pause
        self.is_playing = not self._player.pause
        self.pp_btn.configure(text="⏸" if self.is_playing else "▶")

    def _prev(self):
        if self.current_idx > 0: self._play_index(self.current_idx - 1)

    def _next(self):
        if not self.playlist: return
        if self.repeat_mode == "one":
            self._play_index(self.current_idx); return
        if self.shuffle_mode:
            idx = random.randint(0, len(self.playlist)-1)
        else:
            idx = self.current_idx + 1
            if idx >= len(self.playlist):
                if self.repeat_mode == "all": idx = 0
                else: return
        self._play_index(idx)

    def _on_eof(self, name, value):
        if value:
            self._save_pos()
            self.after(300, self._next)

    def _on_pause_chg(self, name, value):
        if value is not None:
            self.is_playing = not value
            self.after(0, lambda: self.pp_btn.configure(
                text="⏸" if self.is_playing else "▶"))

    # ══════════════════════════════════════════════════════════════════════════
    # SEEK / VOLUME
    # ══════════════════════════════════════════════════════════════════════════

    def _on_time_pos(self, name, value):
        if value is None or self.seeking: return
        self.after(0, lambda: self._upd_seek(value))

    def _on_duration(self, name, value):
        if value:
            self.duration = value
            self.after(0, lambda: self.time_dur.configure(text=fmt_time(value)))

    def _upd_seek(self, pos):
        if self.duration > 0: self.seek_bar.set(pos / self.duration)
        self.time_cur.configure(text=fmt_time(pos))

    def _on_seek_drag(self, frac):
        self.seeking = True
        if self._player and self.duration:
            self._player.seek(frac * self.duration, reference="absolute")
        self.after(200, lambda: setattr(self, "seeking", False))

    def _seek_rel(self, s):
        if self._player: self._player.seek(s, reference="relative")

    def _on_volume(self, val):
        self.volume = int(val)
        if self._player: self._player.volume = self.volume

    def _vol_step(self, step):
        v = max(0, min(100, self.volume + step))
        self.vol_slider.set(v); self._on_volume(v)

    # ══════════════════════════════════════════════════════════════════════════
    # SPEED
    # ══════════════════════════════════════════════════════════════════════════

    def _show_speed_popup(self):
        btn = self.speed_btn
        x   = btn.winfo_rootx()
        y   = btn.winfo_rooty() - len(SPEEDS) * 30 - 4
        popup = SpeedPopup(self, SPEEDS[self._speed_idx], self._set_speed)
        popup.geometry(f"+{x}+{y}")

    def _set_speed(self, speed):
        self._speed_idx = SPEEDS.index(speed)
        self._apply_speed()

    def _speed_step(self, d):
        self._speed_idx = max(0, min(len(SPEEDS)-1, self._speed_idx + d))
        self._apply_speed()

    def _apply_speed(self):
        spd = SPEEDS[self._speed_idx]
        lbl = f"{spd}×"
        self.speed_var.set(lbl)
        self.speed_btn.configure(text=lbl)
        if self._player:
            try: self._player.speed = spd
            except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    # REPEAT / SHUFFLE
    # ══════════════════════════════════════════════════════════════════════════

    def _cycle_repeat(self):
        modes  = ["none", "all", "one"]
        icons  = {"none": "↻", "all": "↻¹", "one": "①"}
        colors = {"none": TEXT_MUT, "all": ACCENT, "one": ACCENT}
        self.repeat_mode = modes[(modes.index(self.repeat_mode)+1) % 3]
        self.repeat_btn.configure(
            text=icons[self.repeat_mode], fg=colors[self.repeat_mode])

    def _toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        self.shuffle_btn.configure(
            fg=ACCENT if self.shuffle_mode else TEXT_MUT)

    # ══════════════════════════════════════════════════════════════════════════
    # FULLSCREEN
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    # ══════════════════════════════════════════════════════════════════════════
    # RESUME / AUTOSAVE
    # ══════════════════════════════════════════════════════════════════════════

    def _save_pos(self):
        if not self._player: return
        if not (0 <= self.current_idx < len(self.playlist)): return
        try:
            pos = self._player.time_pos
            if pos and pos > 5:
                self.db.save(self.playlist[self.current_idx], pos)
        except Exception: pass

    def _autosave_tick(self):
        if not self._closing:
            self._save_pos()
            self.after(5000, self._autosave_tick)

    # ══════════════════════════════════════════════════════════════════════════
    # WHISPER
    # ══════════════════════════════════════════════════════════════════════════

    def _transcribe(self):
        if not WHISPER_AVAILABLE:
            messagebox.showinfo("Whisper",
                "Install first:\npip install openai-whisper")
            return
        if self._whisper_busy:
            messagebox.showinfo("Whisper", "Already transcribing…"); return
        if self.current_idx < 0:
            messagebox.showinfo("Whisper", "No file playing."); return

        path = self.playlist[self.current_idx]
        self._whisper_busy = True
        self.whisper_btn.configure(text="⏳", cursor="")

        def _run():
            try:
                if self._whisper_model is None:
                    self.after(0, lambda: self.whisper_btn.configure(text="📦"))
                    self._whisper_model = _whisper.load_model("medium")
                result = self._whisper_model.transcribe(path)
                text   = result["text"].strip()
                out    = Path(path).with_suffix(".txt")
                out.write_text(text, encoding="utf-8")
                self.after(0, lambda: self._show_transcript(text, out))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Whisper", str(e)))
            finally:
                self._whisper_busy = False
                self.after(0, lambda: self.whisper_btn.configure(
                    text="🎙", cursor="hand2"))

        threading.Thread(target=_run, daemon=True).start()

    def _show_transcript(self, text, out):
        win = ctk.CTkToplevel(self)
        win.title(f"Transcript — {out.name}")
        win.geometry("680x480")
        win.configure(fg_color=DARK_BG)
        ctk.CTkLabel(win, text=f"Saved: {out}",
                     font=ctk.CTkFont(size=10), text_color=GREEN
                     ).pack(anchor="w", padx=14, pady=(10, 2))
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(size=12),
                              fg_color=PANEL_BG, text_color=TEXT_PRI,
                              wrap="word")
        box.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        box.insert("1.0", text)
        box.configure(state="disabled")
        ctk.CTkButton(win, text="Copy",
                       command=lambda: (self.clipboard_clear(),
                                        self.clipboard_append(text))
                       ).pack(pady=(0, 10))

    # ══════════════════════════════════════════════════════════════════════════
    # CLOSE
    # ══════════════════════════════════════════════════════════════════════════

    def on_close(self):
        self._closing = True
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self._save_pos()
        self.db.close()
        if self._tray_icon:
            try: self._tray_icon.stop()
            except Exception: pass
        player = self._player
        self._player = None

        def _kill():
            if player:
                try: player.quit(0)
                except Exception: pass
                try: player.terminate()
                except Exception: pass
            time.sleep(1.5)
            os._exit(0)

        threading.Thread(target=_kill, daemon=True).start()
        try: self.destroy()
        except Exception: pass


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = PyPlayer()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    for arg in sys.argv[1:]:
        if os.path.isfile(arg) and Path(arg).suffix.lower() in SUPPORTED:
            app.after(600, lambda p=arg: (
                app._add_to_playlist(p),
                app._play_index(0) if app.current_idx == -1 else None
            ))
    app.mainloop()


if __name__ == "__main__":
    main()
