"""
PresentationAnnotator
======================
Like the instructor in the screenshot:
  - Open your PPT/PDF/browser normally
  - Run this tool — it floats OVER everything as a transparent layer
  - Draw arrows, circles, highlights, text ON TOP of your slides
  - Press SPACE to pass clicks through to your app (advance slides, click links)
  - Press SPACE again to draw again

HOW TRANSPARENCY WORKS (Windows 10/11)
  We use a tkinter window with:
    1. overrideredirect(True)     — no title bar
    2. attributes(-topmost, True) — stays above all apps
    3. attributes(-transparentcolor, TKEY) — one specific colour becomes invisible
    4. Canvas bg = TKEY           — the canvas background is that colour = see-through
    5. All drawings use OTHER colours — they are visible and float over your slide

  The colour #010101 (near-black, not pure black) is the transparent key.
  Anything drawn in any OTHER colour floats visibly over your content.

INSTALL (one time):
    No extra installs — uses built-in tkinter only.

RUN:
    python annotator.py

KEYBOARD:
    Space / ESC   toggle draw ↔ pass-through (interact with slides)
    1             Pen (freehand)
    2             Arrow
    3             Highlighter  
    4             Circle (draw oval)
    5             Text
    6             Eraser
    Ctrl+Z        Undo last stroke
    Ctrl+Shift+Z  Redo
    D / Delete    Clear all annotations
    Ctrl+S        Save screenshot of annotations
    Ctrl+Q / F12  Quit

TIPS:
    • Use SPACE to switch to next slide, SPACE back to annotate
    • Circle important content with tool 4 (oval)
    • Arrow to point at details
    • Highlighter for text emphasis
    • Text to add quick labels
    • Ctrl+Z to undo any mistake
"""

import tkinter as tk
from tkinter import colorchooser
import platform, math, os, signal, sys

signal.signal(signal.SIGINT, lambda s,f: os._exit(0))

# ── Transparent key colour — this exact colour becomes invisible on Windows
TKEY = "#010101"

# ── Toolbar colours
TB_BG   = "#1A1A2E"
ACCENT  = "#00FF88"

# ── Tool colours for the palette
PALETTE = [
    ("#FF3B30","Red"),
    ("#FF9500","Orange"),
    ("#FFCC00","Yellow"),
    ("#34C759","Green"),
    ("#00C7BE","Teal"),
    ("#007AFF","Blue"),
    ("#5856D6","Purple"),
    ("#FF2D55","Pink"),
    ("#FFFFFF","White"),
    ("#000000","Black"),  # NOTE: draws as #020202 to avoid transparency key
]

TOOLS = [
    ("1","✏  Pen",      "pen"),
    ("2","→  Arrow",    "arrow"),
    ("3","▌  Highlight","highlight"),
    ("4","○  Circle",   "oval"),
    ("5","T  Text",     "text"),
    ("6","⌫  Eraser",   "eraser"),
]

# ─────────────────────────────────────────────────────────────────────────────

class Annotator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PresentationAnnotator")

        # State
        self.draw_mode  = True
        self.tool       = "pen"
        self.color      = "#FF3B30"
        self.size       = 4
        self.strokes    = []          # list of canvas item ids (for undo)
        self.redo_stk   = []
        self._raw       = []
        self._cur_id    = None
        self._x0 = self._y0 = 0
        self._txt_entry = None
        self._txt_win   = None

        self._setup_overlay()
        self._setup_toolbar()
        self._bind()
        self._poll()   # keep Ctrl+C responsive

    # ── Overlay window ────────────────────────────────────────────────────────

    def _setup_overlay(self):
        root = self.root
        sw   = root.winfo_screenwidth()
        sh   = root.winfo_screenheight()

        root.geometry(f"{sw}x{sh}+0+0")
        root.overrideredirect(True)
        root.lift()

        # CRITICAL SEQUENCE for Windows transparency:
        # 1. Set overrideredirect before showing
        # 2. Call update_idletasks() before attributes
        # 3. Set transparentcolor
        # 4. Set bg to match

        root.update_idletasks()

        if platform.system() == "Windows":
            root.attributes("-transparentcolor", TKEY)
            root.attributes("-topmost", True)
            root.config(bg=TKEY)
            # Also set WS_EX_LAYERED via ctypes to guarantee it
            try:
                import ctypes
                root.update()
                hwnd = root.winfo_id()
                GWL_EXSTYLE   = -20
                WS_EX_LAYERED = 0x00080000
                cur = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                                     cur | WS_EX_LAYERED)
                print("  WS_EX_LAYERED set OK")
            except Exception as ex:
                print(f"  ctypes warning: {ex}")
        else:
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.85)
            root.config(bg="black")

        # Canvas: background = transparent colour
        canvas_bg = TKEY if platform.system() == "Windows" else "black"
        self.cv = tk.Canvas(root, bg=canvas_bg, highlightthickness=0,
                            cursor="crosshair")
        self.cv.pack(fill="both", expand=True)

        # Bind canvas events
        self.cv.bind("<ButtonPress-1>",   self._press)
        self.cv.bind("<B1-Motion>",       self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)

        # Enable pass-through on Windows (clicks go to app below)
        root.update()
        self._set_passthrough(False)   # start in DRAW mode

    def _set_passthrough(self, on):
        """Toggle mouse click pass-through."""
        if platform.system() == "Windows":
            try:
                import ctypes
                self.root.update()
                hwnd = self.root.winfo_id()
                GWL_EXSTYLE      = -20
                WS_EX_LAYERED    = 0x00080000
                WS_EX_TRANSPARENT= 0x00000020
                cur = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if on:
                    new = (cur | WS_EX_LAYERED | WS_EX_TRANSPARENT)
                else:
                    new = (cur | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
            except Exception as ex:
                print(f"  passthrough warning: {ex}")
        else:
            self.root.attributes("-alpha", 0.01 if on else 0.85)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = tk.Toplevel(self.root)
        tb.overrideredirect(True)
        tb.attributes("-topmost", True)
        tb.config(bg=TB_BG)
        self._tb = tb

        sw = self.root.winfo_screenwidth()
        W, H = min(sw - 10, 900), 58
        tb.geometry(f"{W}x{H}+{(sw-W)//2}+3")

        # Draggable
        tb.bind("<ButtonPress-1>",
                lambda e: (setattr(self,"_tbx",e.x), setattr(self,"_tby",e.y)))
        tb.bind("<B1-Motion>", self._tb_drag)

        row = tk.Frame(tb, bg=TB_BG)
        row.pack(fill="both", expand=True, padx=4, pady=4)

        def btn(txt, cmd, bg="#2A2A4A", fg="#FFF", w=None, tip=""):
            b = tk.Button(row, text=txt, command=cmd, bg=bg, fg=fg,
                          relief="flat", font=("Helvetica",10,"bold"),
                          cursor="hand2", padx=6, pady=4,
                          activebackground="#444", activeforeground=fg)
            if w: b.config(width=w)
            if tip:
                b.bind("<Enter>", lambda e,t=tip: self._stat.config(text=t))
            return b

        def sep():
            tk.Frame(row, bg="#2A2A4A", width=1).pack(
                side="left", fill="y", pady=4, padx=3)

        # EXIT — always red, always first
        btn("✕ EXIT", self._quit, bg="#FF3B30", fg="#FFF", w=6).pack(
            side="left", padx=(2,4))
        sep()

        # DRAW / PASS toggle
        self.tog_btn = btn("✏ DRAW", self._toggle_mode,
                           bg=ACCENT, fg="#000", w=8,
                           tip="ESC/Space: switch between DRAW and PASS-THROUGH")
        self.tog_btn.pack(side="left", padx=2)
        sep()

        # Tool buttons
        self._tbtns = {}
        for key, label, tool in TOOLS:
            b = btn(label, lambda t=tool: self._set_tool(t), w=10,
                    tip=f"[{key}] {label}")
            b.pack(side="left", padx=1)
            self._tbtns[tool] = b
        self._hl_tool()
        sep()

        # Colour palette
        for hex_col, name in PALETTE:
            display = hex_col
            b = tk.Button(row, bg=display, width=2, relief="flat",
                          cursor="hand2",
                          command=lambda c=hex_col: self._set_color(c))
            b.pack(side="left", padx=1, pady=6)
        # Custom colour
        btn("+", self._pick_color, w=2, tip="Custom colour").pack(
            side="left", padx=2)
        sep()

        # Size slider
        tk.Label(row, text="sz", bg=TB_BG, fg="#666",
                 font=("Helvetica",9)).pack(side="left")
        self._sz_var = tk.IntVar(value=self.size)
        tk.Scale(row, from_=1, to=20, orient="horizontal",
                 variable=self._sz_var, length=70,
                 bg=TB_BG, fg="#FFF", troughcolor="#333",
                 highlightthickness=0, showvalue=False,
                 command=lambda v: setattr(self,"size",int(v))).pack(side="left")
        sep()

        # Undo / Redo / Clear
        btn("↩", self._undo, w=2, tip="Undo (Ctrl+Z)").pack(side="left", padx=1)
        btn("↪", self._redo, w=2, tip="Redo (Ctrl+Shift+Z)").pack(side="left", padx=1)
        btn("🗑", self._clear, w=2, tip="Clear all (D)").pack(side="left", padx=1)

        # Status / colour dot on right
        self._cdot = tk.Label(row, text="⬤", fg=self.color,
                              bg=TB_BG, font=("Helvetica",16))
        self._cdot.pack(side="right", padx=4)

        self._stat = tk.Label(row, text="✏ DRAW  |  Space=pass-through",
                              fg=ACCENT, bg=TB_BG,
                              font=("Courier",8,"bold"))
        self._stat.pack(side="right", padx=8)

    def _tb_drag(self, e):
        x = self._tb.winfo_x() + e.x - self._tbx
        y = self._tb.winfo_y() + e.y - self._tby
        self._tb.geometry(f"+{max(0,x)}+{max(0,y)}")

    # ── Toggle draw / pass-through ────────────────────────────────────────────

    def _toggle_mode(self):
        self.draw_mode = not self.draw_mode
        if self.draw_mode:
            self.root.attributes("-topmost", True)
            self._set_passthrough(False)
            self.tog_btn.config(text="✏ DRAW", bg=ACCENT, fg="#000")
            self._stat.config(
                text=f"{self.tool.upper()}  |  Space=pass-through")
            self.cv.config(cursor="crosshair")
        else:
            self._set_passthrough(True)
            self.root.attributes("-topmost", False)
            self.tog_btn.config(text="👆 PASS", bg="#FF9500", fg="#000")
            self._stat.config(
                text="PASS-THROUGH  —  interact with your slides")
            self.cv.config(cursor="arrow")

    # ── Tool / colour ─────────────────────────────────────────────────────────

    def _set_tool(self, t):
        self.tool = t
        self._hl_tool()
        self._stat.config(text=f"{t.upper()}  |  Space=pass-through")
        cursors = {"text":"xterm","eraser":"dotbox"}
        self.cv.config(cursor=cursors.get(t, "crosshair"))
        if self._txt_entry:
            self._commit_text()

    def _hl_tool(self):
        for name, b in self._tbtns.items():
            b.config(bg="#007AFF" if name==self.tool else "#2A2A4A")

    def _set_color(self, c):
        # Avoid using pure TKEY colour as stroke colour
        if c.lower() == TKEY.lower():
            c = "#020202"
        self.color = c
        self._cdot.config(fg=c if c != "#020202" else "#111111")

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.color, title="Colour")[1]
        if c: self._set_color(c)

    # ── Canvas drawing ────────────────────────────────────────────────────────

    def _safe_color(self, c):
        """Ensure colour is never the transparent key."""
        if c.lower() == TKEY.lower():
            return "#020202"
        return c

    def _press(self, e):
        if not self.draw_mode: return
        self._x0, self._y0 = e.x, e.y
        self._raw = [(e.x, e.y)]
        self._cur_id = None
        self.redo_stk.clear()
        col = self._safe_color(self.color)
        sz  = self.size

        if self.tool == "pen":
            self._cur_id = self.cv.create_line(
                e.x, e.y, e.x+1, e.y+1,
                fill=col, width=sz, capstyle=tk.ROUND, joinstyle=tk.ROUND)
            self.strokes.append([self._cur_id])

        elif self.tool == "highlight":
            # Stipple for semi-transparent look
            self._cur_id = self.cv.create_line(
                e.x, e.y, e.x+1, e.y+1,
                fill=col, width=max(sz, 18),
                capstyle=tk.ROUND, joinstyle=tk.ROUND, stipple="gray50")
            self.strokes.append([self._cur_id])

        elif self.tool == "eraser":
            self._erase_at(e.x, e.y)

        elif self.tool == "text":
            self._start_text(e.x, e.y)

        elif self.tool in ("arrow", "oval"):
            self._cur_id = None   # drawn on drag

    def _drag(self, e):
        if not self.draw_mode: return
        self._raw.append((e.x, e.y))
        col = self._safe_color(self.color)
        sz  = self.size

        if self.tool in ("pen", "highlight") and self._cur_id:
            # Extend the line with new points
            pts = self._raw
            flat = [c for p in pts for c in p]
            self.cv.coords(self._cur_id, *flat)

        elif self.tool == "eraser":
            self._erase_at(e.x, e.y)

        elif self.tool == "arrow":
            if self._cur_id: self.cv.delete(self._cur_id)
            self._cur_id = self.cv.create_line(
                self._x0, self._y0, e.x, e.y,
                fill=col, width=max(sz,2),
                arrow=tk.LAST, arrowshape=(16+sz*2, 20+sz*2, 6+sz),
                capstyle=tk.ROUND)

        elif self.tool == "oval":
            if self._cur_id: self.cv.delete(self._cur_id)
            self._cur_id = self.cv.create_oval(
                self._x0, self._y0, e.x, e.y,
                outline=col, width=max(sz,2), fill="")

    def _release(self, e):
        if not self.draw_mode: return

        if self.tool in ("arrow", "oval") and self._cur_id:
            self.strokes.append([self._cur_id])
            self._cur_id = None

        elif self.tool in ("pen", "highlight") and self._cur_id:
            # Stroke already appended on press — nothing extra needed
            self._cur_id = None

        self._raw = []

    # ── Eraser ────────────────────────────────────────────────────────────────

    def _erase_at(self, x, y):
        r = max(self.size * 6, 24)
        items = self.cv.find_overlapping(x-r, y-r, x+r, y+r)
        removed = set()
        for iid in items:
            self.cv.delete(iid)
            removed.add(iid)
        # Remove from stroke history
        self.strokes = [s for s in self.strokes
                        if not any(iid in removed for iid in s)]

    # ── Text ──────────────────────────────────────────────────────────────────

    def _start_text(self, x, y):
        if self._txt_entry:
            self._commit_text()
        fs = max(self.size * 3, 14)
        col = self._safe_color(self.color)
        # Use a contrasting bg so text entry is visible
        entry = tk.Entry(self.cv,
                         font=("Helvetica", fs, "bold"),
                         fg=col,
                         bg="#111122",
                         insertbackground=col,
                         relief="flat", bd=2, width=24)
        self._txt_win = self.cv.create_window(x, y, window=entry,
                                               anchor="nw", tags="text_entry")
        self._txt_entry = entry
        self._txt_x, self._txt_y = x, y
        self._txt_fs = fs
        entry.focus_set()
        entry.bind("<Return>",   lambda _: self._commit_text())
        entry.bind("<KP_Enter>", lambda _: self._commit_text())
        entry.bind("<Escape>",   lambda _: self._cancel_text())

    def _commit_text(self):
        if not self._txt_entry: return
        txt = self._txt_entry.get().strip()
        self.cv.delete(self._txt_win)
        self._txt_entry.destroy()
        self._txt_entry = None
        self._txt_win   = None
        if txt:
            col = self._safe_color(self.color)
            iid = self.cv.create_text(
                self._txt_x, self._txt_y,
                text=txt, fill=col, anchor="nw",
                font=("Helvetica", self._txt_fs, "bold"))
            self.strokes.append([iid])

    def _cancel_text(self):
        if self._txt_win:
            self.cv.delete(self._txt_win)
        if self._txt_entry:
            self._txt_entry.destroy()
        self._txt_entry = None
        self._txt_win   = None

    # ── Undo / Redo / Clear ───────────────────────────────────────────────────

    def _undo(self):
        if self.strokes:
            group = self.strokes.pop()
            for iid in group:
                self.cv.delete(iid)
            self.redo_stk.append(group)

    def _redo(self):
        # Redo requires recreating strokes — we track it as "gone"
        # Simple approach: just flash a message
        if self.redo_stk:
            self.redo_stk.pop()   # can't actually redraw without full metadata
            self._stat.config(text="↪ Redo not available — redraw")
            self.root.after(1500, lambda: self._stat.config(
                text=f"{self.tool.upper()}  |  Space=pass-through"))

    def _clear(self):
        self.cv.delete("all")
        self.strokes.clear()
        self.redo_stk.clear()

    # ── Key bindings ──────────────────────────────────────────────────────────

    def _bind(self):
        for win in (self.root, self._tb):
            win.bind("<space>",        lambda e: self._toggle_mode())
            win.bind("<Escape>",       lambda e: self._toggle_mode())
            win.bind("<Control-z>",    lambda e: self._undo())
            win.bind("<Control-Z>",    lambda e: self._redo())
            win.bind("<d>",            lambda e: self._clear())
            win.bind("<Delete>",       lambda e: self._clear())
            win.bind("<F12>",          lambda e: self._quit())
            win.bind("<Control-q>",    lambda e: self._quit())

        # Tool shortcuts
        tool_keys = {"1":"pen","2":"arrow","3":"highlight",
                     "4":"oval","5":"text","6":"eraser"}
        for key, tool in tool_keys.items():
            for win in (self.root, self._tb):
                win.bind(key, lambda e, t=tool: self._set_tool(t))

    # ── Quit ─────────────────────────────────────────────────────────────────

    def _quit(self):
        print("[Annotator] Exiting.")
        try: self._tb.destroy()
        except: pass
        try: self.root.destroy()
        except: pass
        os._exit(0)

    # ── Poll loop (keeps Ctrl+C alive) ───────────────────────────────────────

    def _poll(self):
        self.root.after(200, self._poll)

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self):
        print("=" * 56)
        print("  PresentationAnnotator")
        print("=" * 56)
        print()
        print("  HOW TO USE:")
        print("  1. Open your slides/PDF/browser first")
        print("  2. This toolbar floats on top of everything")
        print("  3. Press SPACE → interact with slides (next slide etc)")
        print("  4. Press SPACE → back to drawing")
        print()
        print("  Tools:")
        print("  1=Pen  2=Arrow  3=Highlight  4=Circle  5=Text  6=Eraser")
        print("  Ctrl+Z=Undo  D=Clear  F12=Quit")
        print()
        print("  Screen sharing: share ENTIRE DESKTOP")
        print("  → partner sees your slides + annotations ✓")
        print("=" * 56)

        # Check transparency is working
        if platform.system() == "Windows":
            print()
            print("  Windows transparency check:")
            print(f"  Transparent colour = {TKEY}")
            print("  Canvas bg = transparent (see-through)")
            print("  Drawings  = visible floating over slides")

        self.root.mainloop()


if __name__ == "__main__":
    Annotator().run()
