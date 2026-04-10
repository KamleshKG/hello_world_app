"""
PyPlayer Pure Python Edition
=============================
Zero external system dependencies — 100% pip install.

Requirements:
    pip install customtkinter ffpyplayer mutagen Pillow

Supports: MP4, MKV, AVI, MOV, WEBM, FLV, WMV, M4V, MPG,
          MP3, FLAC, WAV, OGG, M4A, AAC, OPUS, WMA

Engine: ffpyplayer (FFmpeg bundled inside the pip wheel)
UI    : customtkinter (modern dark-mode tkinter)
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import time
import os
import sys
import math
import random
from pathlib import Path
from mutagen import File as MutagenFile
from PIL import Image, ImageDraw, ImageTk

# ─── ffpyplayer ───────────────────────────────────────────────────────────────
try:
    # Silence FFmpeg's internal log spam (NAL errors, AAC duplicate warnings)
    # BEFORE importing MediaPlayer so nothing ever reaches the console.
    import ffpyplayer.tools as _fft
    _fft.set_log_callback(lambda message, level: None)
    from ffpyplayer.player import MediaPlayer
    from ffpyplayer.pic import SWScale
    FFPY_OK = True
except ImportError:
    FFPY_OK = False

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

SUPPORTED = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
    ".m4v", ".mpg", ".mpeg",
    ".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"
}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
             ".wmv", ".m4v", ".mpg", ".mpeg"}
AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"}

FRAME_RATE   = 30          # target UI refresh for video frames
POLL_MS      = int(1000 / FRAME_RATE)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt_time(seconds):
    if seconds is None or seconds < 0:
        return "0:00"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


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
    cx, cy, r = size // 2, size // 2, size // 3
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#3b82f6")
    ir = r // 3
    draw.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], fill="#1e293b")
    draw.ellipse([cx-4,  cy-4,  cx+4,  cy+4],  fill="#3b82f6")
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + (r+4)  * math.cos(angle)
        y1 = cy + (r+4)  * math.sin(angle)
        x2 = cx + (r+12) * math.cos(angle)
        y2 = cy + (r+12) * math.sin(angle)
        draw.line([x1, y1, x2, y2], fill="#60a5fa", width=2)
    return img


# ─── Custom seek bar ─────────────────────────────────────────────────────────

class SeekBar(tk.Canvas):
    def __init__(self, master, **kwargs):
        kwargs.pop("bg", None)
        super().__init__(master, height=18, bg=PANEL_BG,
                         highlightthickness=0, cursor="hand2", **kwargs)
        self._value    = 0.0
        self._hover    = False
        self._dragging = False
        self._callback = None
        self.bind("<Configure>",       self._draw)
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>",           lambda e: self._set_hover(True))
        self.bind("<Leave>",           lambda e: self._set_hover(False))

    def set_command(self, fn): self._callback = fn
    def get(self): return self._value

    def set(self, v):
        self._value = max(0.0, min(1.0, v))
        self._draw()

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def _draw(self, *_):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        ty1, ty2 = h // 2 - 2, h // 2 + 2
        r = 3 if (self._hover or self._dragging) else 2
        self.create_rectangle(8, ty1, w-8, ty2, fill=SEEK_BG, outline="")
        fx = 8 + (w-16) * self._value
        if fx > 8:
            self.create_rectangle(8, ty1, fx, ty2, fill=SEEK_FG, outline="")
        self.create_oval(fx-r, h//2-r, fx+r, h//2+r, fill=SEEK_FG, outline="")

    def _pv(self, x):
        return max(0.0, min(1.0, (x-8) / max(1, self.winfo_width()-16)))

    def _on_press(self, e):
        self._dragging = True
        self._value = self._pv(e.x)
        self._draw()
        if self._callback: self._callback(self._value)

    def _on_drag(self, e):
        if self._dragging:
            self._value = self._pv(e.x)
            self._draw()
            if self._callback: self._callback(self._value)

    def _on_release(self, e):
        self._dragging = False
        self._draw()


# ─── Playlist item widget ─────────────────────────────────────────────────────

class PlaylistItem(ctk.CTkFrame):
    def __init__(self, master, path, index, on_select, on_remove, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=8, **kwargs)
        self.path      = path
        self.index     = index
        self.on_select = on_select
        self.on_remove = on_remove
        self.active    = False
        self._build()

    def _build(self):
        meta = get_metadata(self.path)
        ext  = Path(self.path).suffix.lower()
        icon = "🎵" if ext in AUDIO_EXT else "🎬"

        self.configure(cursor="hand2")
        self.bind("<Button-1>", lambda e: self.on_select(self.index))
        self.bind("<Enter>",    self._hover_on)
        self.bind("<Leave>",    self._hover_off)

        lbl_icon = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=18), width=32)
        lbl_icon.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=4)
        lbl_icon.bind("<Button-1>", lambda e: self.on_select(self.index))

        name = meta["title"][:34] + ("…" if len(meta["title"]) > 34 else "")
        self.title_lbl = ctk.CTkLabel(self, text=name, anchor="w",
                                       font=ctk.CTkFont(size=12, weight="bold"),
                                       text_color=TEXT_PRI)
        self.title_lbl.grid(row=0, column=1, sticky="w", padx=2)
        self.title_lbl.bind("<Button-1>", lambda e: self.on_select(self.index))

        dur = fmt_time(meta["duration"]) if meta["duration"] else "--:--"
        self.sub_lbl = ctk.CTkLabel(self, text=f"{dur}  ·  {ext[1:].upper()}",
                                     anchor="w", font=ctk.CTkFont(size=11),
                                     text_color=TEXT_SEC)
        self.sub_lbl.grid(row=1, column=1, sticky="w", padx=2, pady=(0, 2))
        self.sub_lbl.bind("<Button-1>", lambda e: self.on_select(self.index))

        ctk.CTkButton(self, text="✕", width=24, height=24,
                       fg_color="transparent", text_color=TEXT_MUT,
                       hover_color=CARD_BG, corner_radius=4,
                       command=lambda: self.on_remove(self.index)
                       ).grid(row=0, column=2, rowspan=2, padx=4)
        self.columnconfigure(1, weight=1)

    def set_active(self, active):
        self.active = active
        self.configure(fg_color=ACTIVE_ITEM if active else "transparent")
        self.title_lbl.configure(text_color=ACCENT if active else TEXT_PRI)

    def _hover_on(self, *_):
        if not self.active: self.configure(fg_color=CARD_BG)

    def _hover_off(self, *_):
        if not self.active: self.configure(fg_color="transparent")


# ─── Main player ──────────────────────────────────────────────────────────────

class PyPlayerPure(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PyPlayer  ·  Pure Python")
        self.geometry("1000x660")
        self.minsize(800, 520)
        self.configure(fg_color=DARK_BG)

        # State
        self.playlist      = []
        self.current_idx   = -1
        self.is_playing    = False
        self.duration      = 0.0
        self.position      = 0.0
        self.seeking       = False
        self.volume        = 0.8        # ffpyplayer uses 0.0–1.0
        self._items_ui     = []
        self.repeat_mode   = "none"     # none | one | all
        self.shuffle_mode  = False
        self._closing      = False

        # ffpyplayer state
        self._player       = None       # MediaPlayer instance
        self._player_lock  = threading.Lock()
        self._is_video     = False
        self._frame_img    = None       # current PhotoImage on canvas
        self._eof          = False
        self._err_count    = 0          # consecutive frame errors → auto-next

        self._build_ui()

        if not FFPY_OK:
            self._show_install_msg()
            return

        # Start the frame-pull loop
        self._poll_frames()

    # ─── Install hint ─────────────────────────────────────────────────────────

    def _show_install_msg(self):
        ctk.CTkLabel(
            self.video_canvas,
            text="ffpyplayer not installed.\n\npip install ffpyplayer",
            font=ctk.CTkFont(size=14), text_color=TEXT_SEC,
            fg_color="transparent"
        ).place(relx=0.5, rely=0.5, anchor="center")

    # ─── UI build ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        # ── Left panel ────────────────────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color=DARK_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        # Video canvas — ffpyplayer draws PIL frames here via PhotoImage
        self.video_canvas = tk.Canvas(left, bg="black", highlightthickness=0)
        self.video_canvas.grid(row=0, column=0, sticky="nsew")

        # Audio art label (shown for audio-only files)
        self.art_label = tk.Label(self.video_canvas, bg="black")
        self._audio_art_photo = None

        # Title bar
        self.title_var = tk.StringVar(value="No file loaded")
        title_bar = ctk.CTkFrame(left, fg_color=PANEL_BG, height=32, corner_radius=0)
        title_bar.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(title_bar, textvariable=self.title_var,
                     font=ctk.CTkFont(size=12), text_color=TEXT_SEC,
                     anchor="w").pack(side="left", padx=12)

        # Engine badge
        ctk.CTkLabel(title_bar, text="ffpyplayer · pure python",
                     font=ctk.CTkFont(size=10), text_color=TEXT_MUT,
                     anchor="e").pack(side="right", padx=12)

        # Seek bar
        seek_frame = ctk.CTkFrame(left, fg_color=PANEL_BG, height=24, corner_radius=0)
        seek_frame.grid(row=2, column=0, sticky="ew")
        self.seek_bar = SeekBar(seek_frame)
        self.seek_bar.pack(fill="x", padx=12, pady=4)
        self.seek_bar.set_command(self._on_seek_drag)

        # Time row
        time_row = ctk.CTkFrame(left, fg_color=PANEL_BG, height=20, corner_radius=0)
        time_row.grid(row=3, column=0, sticky="ew")
        self.time_cur = ctk.CTkLabel(time_row, text="0:00",
                                      font=ctk.CTkFont(size=11), text_color=TEXT_SEC)
        self.time_cur.pack(side="left", padx=14)
        self.time_dur = ctk.CTkLabel(time_row, text="0:00",
                                      font=ctk.CTkFont(size=11), text_color=TEXT_SEC)
        self.time_dur.pack(side="right", padx=14)

        # Controls
        ctrl = ctk.CTkFrame(left, fg_color=PANEL_BG, height=60, corner_radius=0)
        ctrl.grid(row=4, column=0, sticky="ew")
        self._build_controls(ctrl)

        # ── Right panel — playlist ────────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color=PANEL_BG, width=280, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        right.grid_propagate(False)
        self._build_playlist_panel(right)

    def _build_controls(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(expand=True, fill="x", padx=16, pady=8)

        def btn(text, cmd, w=36, accent=False):
            fg = ACCENT if accent else "transparent"
            hv = ACCENT_HOVER if accent else CARD_BG
            tc = "white" if accent else TEXT_PRI
            return ctk.CTkButton(row, text=text, width=w, height=w,
                                  fg_color=fg, hover_color=hv,
                                  text_color=tc, font=ctk.CTkFont(size=16 if not accent else 20),
                                  corner_radius=w//2, command=cmd)

        self.shuffle_btn = btn("⇌", self._toggle_shuffle)
        self.shuffle_btn.configure(text_color=TEXT_MUT)
        self.shuffle_btn.pack(side="left", padx=4)

        btn("⏮", self._prev, w=40).pack(side="left", padx=4)

        self.pp_btn = ctk.CTkButton(row, text="▶", width=52, height=52,
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     text_color="white", font=ctk.CTkFont(size=22),
                                     corner_radius=26, command=self._toggle_play)
        self.pp_btn.pack(side="left", padx=4)

        btn("⏭", self._next, w=40).pack(side="left", padx=4)

        self.repeat_btn = btn("↻", self._cycle_repeat)
        self.repeat_btn.configure(text_color=TEXT_MUT)
        self.repeat_btn.pack(side="left", padx=4)

        ctk.CTkFrame(row, fg_color="transparent").pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(row, text="🔊", font=ctk.CTkFont(size=14),
                     text_color=TEXT_SEC).pack(side="left", padx=(4, 0))

        self.vol_slider = ctk.CTkSlider(row, from_=0, to=100, width=90,
                                         command=self._on_volume)
        self.vol_slider.set(int(self.volume * 100))
        self.vol_slider.pack(side="left", padx=8)

        ctk.CTkButton(row, text="⛶", width=36, height=36,
                       fg_color="transparent", text_color=TEXT_SEC,
                       font=ctk.CTkFont(size=16), hover_color=CARD_BG, corner_radius=18,
                       command=self._toggle_fullscreen).pack(side="left", padx=2)

        # Key bindings
        self.bind("<space>",  lambda e: self._toggle_play())
        self.bind("<Left>",   lambda e: self._seek_rel(-5))
        self.bind("<Right>",  lambda e: self._seek_rel(5))
        self.bind("<Up>",     lambda e: self._vol_step(5))
        self.bind("<Down>",   lambda e: self._vol_step(-5))
        self.bind("<F11>",    lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))

    def _build_playlist_panel(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        ctk.CTkLabel(hdr, text="Playlist",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT_PRI).pack(side="left")
        ctk.CTkButton(hdr, text="Clear", width=52, height=26, corner_radius=6,
                       fg_color=CARD_BG, text_color=TEXT_SEC, hover_color=SEEK_BG,
                       font=ctk.CTkFont(size=11),
                       command=self._clear_playlist).pack(side="right")

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        ctk.CTkButton(btn_row, text="+ Files", height=30, corner_radius=8,
                       fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="white",
                       font=ctk.CTkFont(size=12),
                       command=self._add_files).pack(side="left", fill="x",
                                                      expand=True, padx=(0, 4))
        ctk.CTkButton(btn_row, text="+ Folder", height=30, corner_radius=8,
                       fg_color=CARD_BG, hover_color=SEEK_BG, text_color=TEXT_PRI,
                       font=ctk.CTkFont(size=12),
                       command=self._add_folder).pack(side="left", fill="x", expand=True)

        self.pl_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                                corner_radius=0)
        self.pl_frame.grid(row=2, column=0, sticky="nsew", padx=4)

        self.count_lbl = ctk.CTkLabel(parent, text="0 items",
                                       font=ctk.CTkFont(size=11), text_color=TEXT_MUT)
        self.count_lbl.grid(row=3, column=0, pady=8)

    # ─── Frame polling loop ───────────────────────────────────────────────────
    # ffpyplayer works by calling get_frame() repeatedly.
    # We drive it from tkinter's after() so it stays on the UI thread.
    # Bad packets (NAL errors etc.) raise exceptions — we catch and count them.
    # If errors pile up past a threshold we auto-advance to the next track
    # instead of crashing or hanging.

    def _poll_frames(self):
        if self._closing:
            return

        with self._player_lock:
            player = self._player

        if player and self._is_video and self.is_playing:
            try:
                frame, val = player.get_frame()
                if val == "eof":
                    self._eof = True
                    self._err_count = 0
                    self.after(0, self._on_eof)
                elif frame is not None:
                    self._err_count = 0          # good frame — reset counter
                    img, t = frame
                    w, h = img.get_size()
                    raw  = img.to_bytearray()[0]
                    pil  = Image.frombytes("RGB", (w, h), bytes(raw))
                    cw   = self.video_canvas.winfo_width()
                    ch   = self.video_canvas.winfo_height()
                    if cw > 1 and ch > 1:
                        pil = self._fit_frame(pil, cw, ch)
                    photo = ImageTk.PhotoImage(pil)
                    self.video_canvas.create_image(
                        cw // 2, ch // 2, image=photo, anchor="center"
                    )
                    self._frame_img = photo      # hold reference to avoid GC
            except Exception:
                self._err_count += 1
                # After 60 consecutive bad frames (~2 s at 30 fps) skip track
                if self._err_count > 60:
                    self._err_count = 0
                    self.after(0, self._next)

        # Update seek bar / time display
        if player and self.is_playing and not self.seeking:
            try:
                with self._player_lock:
                    if self._player:
                        pos = self._player.get_pts()
                if pos and pos > 0:
                    self.position = pos
                    self.time_cur.configure(text=fmt_time(pos))
                    if self.duration > 0:
                        self.seek_bar.set(pos / self.duration)
            except Exception:
                pass

        self.after(POLL_MS, self._poll_frames)

    @staticmethod
    def _fit_frame(img, cw, ch):
        """Letterbox-fit PIL image into canvas dimensions."""
        iw, ih = img.size
        scale  = min(cw / iw, ch / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        return img.resize((nw, nh), Image.BILINEAR)

    # ─── Playlist management ──────────────────────────────────────────────────

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Select media files",
            filetypes=[
                ("All media", " ".join(f"*{e}" for e in SUPPORTED)),
                ("Video",     " ".join(f"*{e}" for e in VIDEO_EXT)),
                ("Audio",     " ".join(f"*{e}" for e in AUDIO_EXT)),
                ("All files", "*.*"),
            ]
        )
        for f in files:
            self._add_to_playlist(f)
        if files and self.current_idx == -1:
            self._play_index(0)

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if not folder:
            return
        found = sorted(
            str(p) for p in Path(folder).rglob("*")
            if p.suffix.lower() in SUPPORTED
        )
        for f in found:
            self._add_to_playlist(f)
        if found and self.current_idx == -1:
            self._play_index(0)

    def _add_to_playlist(self, path):
        self.playlist.append(path)
        idx  = len(self.playlist) - 1
        item = PlaylistItem(self.pl_frame, path, idx,
                             self._play_index, self._remove_item)
        item.pack(fill="x", pady=1)
        self._items_ui.append(item)
        n = len(self.playlist)
        self.count_lbl.configure(text=f"{n} item{'s' if n != 1 else ''}")

    def _remove_item(self, idx):
        if idx >= len(self.playlist):
            return
        self.playlist.pop(idx)
        self._items_ui.pop(idx).destroy()
        for i, w in enumerate(self._items_ui):
            w.index = i
        if self.current_idx == idx:
            self._stop_player()
            self.current_idx = -1
        elif self.current_idx > idx:
            self.current_idx -= 1
        n = len(self.playlist)
        self.count_lbl.configure(text=f"{n} item{'s' if n != 1 else ''}")

    def _clear_playlist(self):
        self._stop_player()
        for w in self._items_ui:
            w.destroy()
        self.playlist.clear()
        self._items_ui.clear()
        self.current_idx = -1
        self.title_var.set("No file loaded")
        self.title("PyPlayer  ·  Pure Python")
        self.seek_bar.set(0)
        self.time_cur.configure(text="0:00")
        self.time_dur.configure(text="0:00")
        self.count_lbl.configure(text="0 items")
        self.video_canvas.delete("all")
        self.art_label.place_forget()

    # ─── Playback ─────────────────────────────────────────────────────────────

    def _stop_player(self):
        with self._player_lock:
            if self._player:
                try:
                    self._player.close_player()
                except Exception:
                    pass
                self._player = None
        self.is_playing  = False
        self._eof        = False
        self.duration    = 0.0
        self.position    = 0.0
        self.pp_btn.configure(text="▶")

    def _play_index(self, idx):
        if not FFPY_OK:
            return
        if idx < 0 or idx >= len(self.playlist):
            return

        # Deactivate previous item
        if 0 <= self.current_idx < len(self._items_ui):
            self._items_ui[self.current_idx].set_active(False)

        self._stop_player()
        self._err_count  = 0
        self.current_idx = idx
        path = self.playlist[idx]
        self._items_ui[idx].set_active(True)

        ext = Path(path).suffix.lower()
        self._is_video = ext in VIDEO_EXT

        # Metadata
        meta  = get_metadata(path)
        title = meta["title"]
        if meta["artist"]:
            title = f"{meta['artist']} — {title}"
        self.title_var.set(title)
        self.title(f"PyPlayer  ·  {Path(path).name}")

        # Duration from mutagen (faster than waiting for ffpyplayer)
        if meta["duration"]:
            self.duration = meta["duration"]
            self.time_dur.configure(text=fmt_time(self.duration))

        # Audio art / clear canvas
        self.video_canvas.delete("all")
        if not self._is_video:
            art   = make_audio_art(200)
            photo = ImageTk.PhotoImage(art)
            self._audio_art_photo = photo
            self.art_label.configure(image=photo)
            cw = self.video_canvas.winfo_width()  or 600
            ch = self.video_canvas.winfo_height() or 400
            self.art_label.place(x=cw//2, y=ch//2, anchor="center")
        else:
            self.art_label.place_forget()

        # Launch ffpyplayer in a thread-safe way
        # ff_opts: volume 0-1, sync to audio for video
        ff_opts = {
            "volume": self.volume,
            "sync": "audio",
            "autoexit": False,
            "vd": "*" if self._is_video else "",
        }
        try:
            player = MediaPlayer(path, ff_opts=ff_opts)
            with self._player_lock:
                self._player = player
            self.is_playing = True
            self._eof       = False
            self.pp_btn.configure(text="⏸")
        except Exception as e:
            self.title_var.set(f"Error: {e}")

    def _toggle_play(self):
        if not FFPY_OK:
            return
        if self.current_idx == -1 and self.playlist:
            self._play_index(0)
            return
        with self._player_lock:
            player = self._player
        if not player:
            return
        self.is_playing = not self.is_playing
        player.toggle_pause()
        self.pp_btn.configure(text="⏸" if self.is_playing else "▶")

    def _prev(self):
        if self.current_idx > 0:
            self._play_index(self.current_idx - 1)

    def _next(self):
        if not self.playlist:
            return
        if self.repeat_mode == "one":
            self._play_index(self.current_idx)
            return
        if self.shuffle_mode:
            idx = random.randint(0, len(self.playlist) - 1)
        else:
            idx = self.current_idx + 1
            if idx >= len(self.playlist):
                if self.repeat_mode == "all":
                    idx = 0
                else:
                    self._stop_player()
                    return
        self._play_index(idx)

    def _on_eof(self):
        self.after(400, self._next)

    # ─── Seek / Volume ────────────────────────────────────────────────────────

    def _on_seek_drag(self, frac):
        self.seeking = True
        with self._player_lock:
            player = self._player
        if player and self.duration:
            target = frac * self.duration
            try:
                player.seek(target, relative=False)
                self.position = target
                self.time_cur.configure(text=fmt_time(target))
            except Exception:
                pass
        self.after(300, lambda: setattr(self, "seeking", False))

    def _seek_rel(self, seconds):
        with self._player_lock:
            player = self._player
        if player:
            try:
                player.seek(seconds, relative=True)
            except Exception:
                pass

    def _on_volume(self, val):
        self.volume = int(val) / 100.0
        with self._player_lock:
            player = self._player
        if player:
            try:
                player.set_volume(self.volume)
            except Exception:
                pass

    def _vol_step(self, step):
        v = max(0, min(100, int(self.volume * 100) + step))
        self.vol_slider.set(v)
        self._on_volume(v)

    # ─── Repeat / Shuffle ────────────────────────────────────────────────────

    def _cycle_repeat(self):
        modes  = ["none", "all", "one"]
        icons  = {"none": "↻",  "all": "↻¹", "one": "①"}
        colors = {"none": TEXT_MUT, "all": ACCENT, "one": ACCENT}
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % 3]
        self.repeat_btn.configure(text=icons[self.repeat_mode],
                                   text_color=colors[self.repeat_mode])

    def _toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        self.shuffle_btn.configure(
            text_color=ACCENT if self.shuffle_mode else TEXT_MUT)

    # ─── Fullscreen ───────────────────────────────────────────────────────────

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    # ─── Clean exit ───────────────────────────────────────────────────────────

    def on_close(self):
        self._closing = True
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        def _kill():
            with self._player_lock:
                player = self._player
                self._player = None
            if player:
                try:
                    player.close_player()
                except Exception:
                    pass
            time.sleep(0.5)
            os._exit(0)

        threading.Thread(target=_kill, daemon=True).start()
        try:
            self.destroy()
        except Exception:
            pass


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = PyPlayerPure()
    app.protocol("WM_DELETE_WINDOW", app.on_close)

    # Accept CLI file arguments
    for arg in sys.argv[1:]:
        if os.path.isfile(arg) and Path(arg).suffix.lower() in SUPPORTED:
            app.after(600, lambda p=arg: (
                app._add_to_playlist(p),
                app._play_index(0) if app.current_idx == -1 else None
            ))

    app.mainloop()


if __name__ == "__main__":
    main()
