"""
DiagramTool - Python Drawing Tool for Boxes, Arrows & Labels
============================================================
Usage:
  python diagram_tool.py

Requirements: Python 3.x (tkinter is built-in, no pip install needed)

Controls:
  - Toolbar buttons at top to switch modes
  - Box mode    : Click on canvas to create a box, double-click to edit label
  - Arrow mode  : Click source box, then click target box to draw arrow
  - Text mode   : Click anywhere to add floating text label
  - Select mode : Click to select, drag to move, Del to delete
  - Pan mode    : Drag canvas to pan around

Keyboard:
  Ctrl+S  : Save diagram as .json
  Ctrl+O  : Open saved diagram
  Ctrl+Z  : Undo
  Ctrl+A  : Select all
  Delete  : Delete selected
  Escape  : Deselect / cancel current action

Mouse:
  Scroll  : Zoom in/out
  Middle  : Pan

File > Export PNG to save as image
"""

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox, colorchooser
import json
import math
import os

# ─── Theming ────────────────────────────────────────────────────────────────
BG          = "#1e1e2e"
SURFACE     = "#2a2a3e"
SURFACE2    = "#313145"
ACCENT      = "#7c6fcd"
ACCENT2     = "#a89ee8"
TEXT_LIGHT  = "#e0dff5"
TEXT_MUTED  = "#888aaa"
BOX_DEFAULT = "#2e3a5c"
BOX_BORDER  = "#5a7ec8"
ARROW_COLOR = "#a0b0e0"
SEL_COLOR   = "#ffcc44"
GRID_COLOR  = "#2a2a3e"

BOX_COLORS = {
    "Blue":    ("#2e3a5c", "#5a7ec8"),
    "Green":   ("#1e3d2e", "#3aaa6a"),
    "Purple":  ("#3a2e5c", "#7c6fcd"),
    "Teal":    ("#1e3d3a", "#3aaaa0"),
    "Orange":  ("#4a3020", "#cc7744"),
    "Red":     ("#4a2020", "#cc4444"),
    "Gray":    ("#2e2e3e", "#666688"),
}

# ─── Data Models ────────────────────────────────────────────────────────────

class Box:
    _id = 0
    def __init__(self, x, y, w=160, h=60, label="Box", color="Blue"):
        Box._id += 1
        self.id = Box._id
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.label = label
        self.color = color
        self.canvas_id = None
        self.text_id  = None

    def center(self):
        return self.x + self.w / 2, self.y + self.h / 2

    def edge_point(self, tx, ty):
        """Return point on box edge closest to (tx, ty)."""
        cx, cy = self.center()
        dx, dy = tx - cx, ty - cy
        if dx == 0 and dy == 0:
            return cx, cy
        angle = math.atan2(dy, dx)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        half_w, half_h = self.w / 2, self.h / 2
        if abs(cos_a) * half_h > abs(sin_a) * half_w:
            scale = half_w / abs(cos_a)
        else:
            scale = half_h / abs(sin_a)
        return cx + cos_a * scale, cy + sin_a * scale

    def contains(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

    def to_dict(self):
        return dict(id=self.id, x=self.x, y=self.y, w=self.w, h=self.h,
                    label=self.label, color=self.color)

    @classmethod
    def from_dict(cls, d):
        b = cls(d["x"], d["y"], d["w"], d["h"], d["label"], d.get("color","Blue"))
        b.id = d["id"]
        return b


class Arrow:
    _id = 0
    def __init__(self, src_id, dst_id, label=""):
        Arrow._id += 1
        self.id = Arrow._id
        self.src_id  = src_id
        self.dst_id  = dst_id
        self.label   = label
        self.canvas_id = None
        self.text_id   = None

    def to_dict(self):
        return dict(id=self.id, src_id=self.src_id, dst_id=self.dst_id, label=self.label)

    @classmethod
    def from_dict(cls, d):
        a = cls(d["src_id"], d["dst_id"], d.get("label", ""))
        a.id = d["id"]
        return a


class FloatText:
    _id = 0
    def __init__(self, x, y, text="Label"):
        FloatText._id += 1
        self.id = FloatText._id
        self.x, self.y = x, y
        self.text = text
        self.canvas_id = None

    def to_dict(self):
        return dict(id=self.id, x=self.x, y=self.y, text=self.text)

    @classmethod
    def from_dict(cls, d):
        ft = cls(d["x"], d["y"], d["text"])
        ft.id = d["id"]
        return ft


# ─── Main Application ────────────────────────────────────────────────────────

class DiagramApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DiagramTool — Python Drawing Canvas")
        self.root.configure(bg=BG)
        self.root.geometry("1280x800")

        self.boxes      = []
        self.arrows     = []
        self.floattexts = []
        self.selected   = None       # selected Box, Arrow or FloatText
        self.mode       = "select"   # select | box | arrow | text | pan
        self.arrow_src  = None       # first click in arrow mode
        self.undo_stack = []

        self.offset_x   = 0
        self.offset_y   = 0
        self.zoom       = 1.0
        self._drag_start= None
        self._drag_obj  = None
        self._pan_start = None

        self._build_ui()
        self._bind_events()
        self._draw_all()

    # ─── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top toolbar
        tb = tk.Frame(self.root, bg=SURFACE, height=50)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        self.mode_btns = {}
        modes = [
            ("☰ Select",  "select",  "Click & drag objects"),
            ("⬜ Box",    "box",     "Click to create box"),
            ("➜ Arrow",   "arrow",   "Click source → target"),
            ("T Text",    "text",    "Click to add text"),
            ("✥ Pan",     "pan",     "Drag to pan canvas"),
        ]
        for label, key, tip in modes:
            btn = tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                            activebackground=ACCENT, activeforeground="white",
                            relief="flat", padx=12, pady=8, cursor="hand2",
                            font=("Segoe UI", 10),
                            command=lambda k=key: self.set_mode(k))
            btn.pack(side="left", padx=2, pady=5)
            self.mode_btns[key] = btn

        # Separator
        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=4)

        # Action buttons
        actions = [
            ("🗑 Delete", self._delete_selected),
            ("✏ Edit",   self._edit_selected),
            ("🎨 Color",  self._change_color),
        ]
        for label, cmd in actions:
            tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                      activebackground="#555577", relief="flat",
                      padx=10, pady=8, cursor="hand2",
                      font=("Segoe UI", 10), command=cmd).pack(side="left", padx=2, pady=5)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=4)

        file_actions = [
            ("💾 Save",  self._save),
            ("📂 Open",  self._load),
            ("🗺 Export PNG", self._export_png),
            ("🧹 Clear", self._clear),
        ]
        for label, cmd in file_actions:
            tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                      activebackground="#555577", relief="flat",
                      padx=10, pady=8, cursor="hand2",
                      font=("Segoe UI", 10), command=cmd).pack(side="left", padx=2, pady=5)

        # Zoom indicator
        self.zoom_var = tk.StringVar(value="100%")
        tk.Label(tb, textvariable=self.zoom_var, bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 10)).pack(side="right", padx=12)
        tk.Button(tb, text="⟳ Reset View", bg=SURFACE2, fg=TEXT_MUTED,
                  relief="flat", padx=8, pady=8, cursor="hand2",
                  font=("Segoe UI", 9), command=self._reset_view).pack(side="right", padx=2, pady=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready  •  Select a tool from the toolbar")
        sb = tk.Label(self.root, textvariable=self.status_var,
                      bg=SURFACE, fg=TEXT_MUTED, font=("Segoe UI", 9),
                      anchor="w", padx=12, pady=4)
        sb.pack(fill="x", side="bottom")

        # Canvas
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0,
                                cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        # Help panel (right side)
        help_frame = tk.Frame(self.root, bg=SURFACE, width=200)
        help_frame.pack(fill="y", side="right")
        help_frame.pack_propagate(False)

        tk.Label(help_frame, text="SHORTCUTS", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold"), pady=12).pack()
        help_text = [
            ("Ctrl+S", "Save"),
            ("Ctrl+O", "Open"),
            ("Ctrl+Z", "Undo"),
            ("Ctrl+A", "Select all"),
            ("Del",    "Delete"),
            ("Esc",    "Deselect"),
            ("Scroll", "Zoom"),
            ("Middle", "Pan"),
            ("Dbl-click", "Edit label"),
        ]
        for key, desc in help_text:
            row = tk.Frame(help_frame, bg=SURFACE)
            row.pack(fill="x", padx=12, pady=1)
            tk.Label(row, text=key, bg=SURFACE2, fg=ACCENT2,
                     font=("Consolas", 9), padx=4, width=10).pack(side="left")
            tk.Label(row, text=desc, bg=SURFACE, fg=TEXT_MUTED,
                     font=("Segoe UI", 9), padx=6).pack(side="left")

        tk.Frame(help_frame, bg=SURFACE2, height=1).pack(fill="x", pady=12, padx=8)

        tk.Label(help_frame, text="TIPS", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack()
        tips = [
            "Double-click any box\nor arrow to edit its\nlabel",
            "Arrow mode:\n1. Click source box\n2. Click target box",
            "Use Color button to\nchange box color",
            "Zoom with scroll\nPan with middle button",
        ]
        for tip in tips:
            tk.Label(help_frame, text=tip, bg=SURFACE, fg=TEXT_MUTED,
                     font=("Segoe UI", 8), justify="left",
                     wraplength=180, padx=12, pady=4).pack(anchor="w")

        self.set_mode("select")

    def _bind_events(self):
        c = self.canvas
        c.bind("<Button-1>",        self._on_click)
        c.bind("<B1-Motion>",       self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_dblclick)
        c.bind("<Button-2>",        self._on_pan_start)
        c.bind("<B2-Motion>",       self._on_pan)
        c.bind("<Button-4>",        lambda e: self._zoom(1.1, e))  # Linux scroll up
        c.bind("<Button-5>",        lambda e: self._zoom(0.9, e))  # Linux scroll down
        c.bind("<MouseWheel>",      self._on_mousewheel)            # Windows/Mac

        self.root.bind("<Control-s>", lambda e: self._save())
        self.root.bind("<Control-o>", lambda e: self._load())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-a>", lambda e: self._select_all())
        self.root.bind("<Delete>",    lambda e: self._delete_selected())
        self.root.bind("<Escape>",    lambda e: self._escape())

    # ─── Mode ───────────────────────────────────────────────────────────────

    def set_mode(self, mode):
        self.mode = mode
        self.arrow_src = None
        self.selected  = None
        for k, btn in self.mode_btns.items():
            btn.configure(bg=ACCENT if k == mode else SURFACE2,
                          fg="white" if k == mode else TEXT_LIGHT)
        cursors = {"select":"arrow","box":"crosshair","arrow":"crosshair",
                   "text":"xterm","pan":"fleur"}
        self.canvas.configure(cursor=cursors.get(mode,"crosshair"))
        status_msgs = {
            "select": "Select mode  •  Click to select, drag to move",
            "box":    "Box mode  •  Click on canvas to create a new box",
            "arrow":  "Arrow mode  •  Click a source box, then a target box",
            "text":   "Text mode  •  Click anywhere to add a floating label",
            "pan":    "Pan mode  •  Drag to pan the canvas",
        }
        self.status_var.set(status_msgs.get(mode, ""))
        self._draw_all()

    # ─── Coordinate helpers ──────────────────────────────────────────────────

    def _to_world(self, cx, cy):
        return (cx - self.offset_x) / self.zoom, (cy - self.offset_y) / self.zoom

    def _to_canvas(self, wx, wy):
        return wx * self.zoom + self.offset_x, wy * self.zoom + self.offset_y

    # ─── Hit testing ─────────────────────────────────────────────────────────

    def _box_at(self, wx, wy):
        for b in reversed(self.boxes):
            if b.contains(wx, wy):
                return b
        return None

    def _arrow_at(self, wx, wy, tol=8):
        for a in self.arrows:
            src = self._box_by_id(a.src_id)
            dst = self._box_by_id(a.dst_id)
            if not src or not dst:
                continue
            x1, y1 = src.edge_point(*dst.center())
            x2, y2 = dst.edge_point(*src.center())
            # Distance from point to segment
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            t = max(0, min(1, ((wx-x1)*dx + (wy-y1)*dy) / length**2))
            px, py = x1 + t*dx, y1 + t*dy
            if math.hypot(wx-px, wy-py) < tol / self.zoom:
                return a
        return None

    def _floattext_at(self, wx, wy, tol=20):
        for ft in reversed(self.floattexts):
            if abs(ft.x - wx) < tol and abs(ft.y - wy) < tol:
                return ft
        return None

    def _box_by_id(self, bid):
        for b in self.boxes:
            if b.id == bid:
                return b
        return None

    # ─── Events ──────────────────────────────────────────────────────────────

    def _on_click(self, event):
        wx, wy = self._to_world(event.x, event.y)

        if self.mode == "pan":
            self._pan_start = (event.x, event.y)
            return

        if self.mode == "box":
            self._push_undo()
            b = Box(wx - 80, wy - 30, label="Box")
            self.boxes.append(b)
            self._draw_all()
            self._edit_box_label(b)
            return

        if self.mode == "text":
            self._push_undo()
            ft = FloatText(wx, wy)
            self.floattexts.append(ft)
            self._draw_all()
            self._edit_floattext(ft)
            return

        if self.mode == "arrow":
            hit_box = self._box_at(wx, wy)
            if hit_box:
                if self.arrow_src is None:
                    self.arrow_src = hit_box
                    self.selected  = hit_box
                    self.status_var.set(f"Arrow mode  •  Now click the TARGET box  (source: {hit_box.label})")
                    self._draw_all()
                else:
                    if hit_box.id != self.arrow_src.id:
                        self._push_undo()
                        a = Arrow(self.arrow_src.id, hit_box.id)
                        self.arrows.append(a)
                    self.arrow_src = None
                    self.selected  = None
                    self.status_var.set("Arrow mode  •  Click a source box, then a target box")
                    self._draw_all()
            return

        if self.mode == "select":
            hit = (self._box_at(wx, wy)
                   or self._arrow_at(wx, wy)
                   or self._floattext_at(wx, wy))
            self.selected = hit
            if hit:
                self._drag_start  = (wx, wy)
                self._drag_obj    = hit
                self._drag_origin = (
                    (hit.x, hit.y) if isinstance(hit, (Box, FloatText))
                    else None
                )
            self._draw_all()

    def _on_drag(self, event):
        if self.mode == "pan" and self._pan_start:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self._pan_start = (event.x, event.y)
            self._draw_all()
            return

        if self.mode == "select" and self._drag_start and self._drag_obj:
            wx, wy = self._to_world(event.x, event.y)
            dx = wx - self._drag_start[0]
            dy = wy - self._drag_start[1]
            obj = self._drag_obj
            if isinstance(obj, Box):
                ox, oy = self._drag_origin
                obj.x = ox + dx
                obj.y = oy + dy
            elif isinstance(obj, FloatText):
                ox, oy = self._drag_origin
                obj.x = ox + dx
                obj.y = oy + dy
            self._draw_all()

    def _on_release(self, event):
        if self._drag_obj:
            self._push_undo()
        self._drag_obj   = None
        self._drag_start = None
        self._pan_start  = None

    def _on_dblclick(self, event):
        wx, wy = self._to_world(event.x, event.y)
        hit_box = self._box_at(wx, wy)
        if hit_box:
            self._edit_box_label(hit_box)
            return
        hit_arrow = self._arrow_at(wx, wy)
        if hit_arrow:
            self._edit_arrow_label(hit_arrow)
            return
        hit_ft = self._floattext_at(wx, wy)
        if hit_ft:
            self._edit_floattext(hit_ft)

    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y)

    def _on_pan(self, event):
        if self._pan_start:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self._pan_start = (event.x, event.y)
            self._draw_all()

    def _on_mousewheel(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self._zoom(factor, event)

    def _zoom(self, factor, event=None):
        old = self.zoom
        self.zoom = max(0.2, min(5.0, self.zoom * factor))
        if event:
            cx, cy = event.x, event.y
            self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
            self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)
        self.zoom_var.set(f"{int(self.zoom*100)}%")
        self._draw_all()

    def _escape(self):
        self.arrow_src = None
        self.selected  = None
        self.status_var.set("Deselected  •  Escape pressed")
        self._draw_all()

    # ─── Drawing ─────────────────────────────────────────────────────────────

    def _draw_all(self):
        c = self.canvas
        c.delete("all")
        self._draw_grid()

        # Draw arrows first (under boxes)
        for a in self.arrows:
            self._draw_arrow(a)

        # Draw boxes
        for b in self.boxes:
            self._draw_box(b)

        # Draw floating text
        for ft in self.floattexts:
            self._draw_floattext(ft)

        # Draw arrow-in-progress
        if self.mode == "arrow" and self.arrow_src:
            cx, cy = self._to_canvas(*self.arrow_src.center())
            c.create_oval(cx-6, cy-6, cx+6, cy+6,
                          fill=SEL_COLOR, outline="", tags="tmp")

    def _draw_grid(self):
        c = self.canvas
        w = c.winfo_width() or 1280
        h = c.winfo_height() or 800
        spacing = 40 * self.zoom
        ox = self.offset_x % spacing
        oy = self.offset_y % spacing
        x = ox
        while x < w:
            c.create_line(x, 0, x, h, fill=GRID_COLOR, width=1)
            x += spacing
        y = oy
        while y < h:
            c.create_line(0, y, w, y, fill=GRID_COLOR, width=1)
            y += spacing

    def _draw_box(self, box):
        c = self.canvas
        x1, y1 = self._to_canvas(box.x, box.y)
        x2, y2 = self._to_canvas(box.x + box.w, box.y + box.h)
        fill, border = BOX_COLORS.get(box.color, (BOX_DEFAULT, BOX_BORDER))
        is_sel = (self.selected is box) or (
            self.mode == "arrow" and self.arrow_src is box)

        # Shadow
        c.create_rectangle(x1+4, y1+4, x2+4, y2+4,
                            fill="#111122", outline="", tags="box_shadow")
        # Body
        c.create_rectangle(x1, y1, x2, y2,
                            fill=fill, outline="", tags="box_body")
        # Accent top bar
        bar_h = max(4, (y2 - y1) * 0.08)
        c.create_rectangle(x1, y1, x2, y1 + bar_h,
                            fill=border, outline="", tags="box_bar")
        # Border
        border_color = SEL_COLOR if is_sel else border
        lw = 2 if is_sel else 1
        c.create_rectangle(x1, y1, x2, y2,
                            fill="", outline=border_color,
                            width=lw, tags="box_border")
        # Label
        font_size = max(8, int(12 * self.zoom))
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        c.create_text(cx, cy, text=box.label, fill=TEXT_LIGHT,
                      font=("Segoe UI", font_size), anchor="center",
                      width=(x2-x1-8), tags="box_label")

    def _draw_arrow(self, arrow):
        c = self.canvas
        src = self._box_by_id(arrow.src_id)
        dst = self._box_by_id(arrow.dst_id)
        if not src or not dst:
            return

        # Start/end at box edges
        tx, ty = dst.center()
        sx, sy = src.center()
        ex1, ey1 = src.edge_point(tx, ty)
        ex2, ey2 = dst.edge_point(sx, sy)

        cx1, cy1 = self._to_canvas(ex1, ey1)
        cx2, cy2 = self._to_canvas(ex2, ey2)

        is_sel = (self.selected is arrow)
        color  = SEL_COLOR if is_sel else ARROW_COLOR
        lw     = 2 if is_sel else 1.5

        c.create_line(cx1, cy1, cx2, cy2,
                      fill=color, width=lw,
                      arrow=tk.LAST,
                      arrowshape=(12*self.zoom, 15*self.zoom, 5*self.zoom),
                      smooth=False, tags="arrow")

        # Arrow label
        if arrow.label:
            mx = (cx1 + cx2) / 2
            my = (cy1 + cy2) / 2
            font_size = max(7, int(10 * self.zoom))
            c.create_text(mx, my - 10*self.zoom, text=arrow.label,
                          fill=ACCENT2, font=("Segoe UI", font_size),
                          tags="arrow_label")

    def _draw_floattext(self, ft):
        c = self.canvas
        cx, cy = self._to_canvas(ft.x, ft.y)
        is_sel = (self.selected is ft)
        font_size = max(8, int(13 * self.zoom))
        c.create_text(cx, cy, text=ft.text, fill=ACCENT2 if not is_sel else SEL_COLOR,
                      font=("Segoe UI", font_size, "bold"), anchor="center",
                      tags="floattext")
        if is_sel:
            # Draw selection ring
            c.create_oval(cx-10, cy-10, cx+10, cy+10,
                          outline=SEL_COLOR, width=1, fill="")

    # ─── Edit helpers ────────────────────────────────────────────────────────

    def _edit_box_label(self, box):
        new_label = simpledialog.askstring(
            "Edit Box", "Enter label:", initialvalue=box.label,
            parent=self.root)
        if new_label is not None:
            box.label = new_label
            self._draw_all()

    def _edit_arrow_label(self, arrow):
        new_label = simpledialog.askstring(
            "Edit Arrow", "Enter label for this arrow:", initialvalue=arrow.label,
            parent=self.root)
        if new_label is not None:
            arrow.label = new_label
            self._draw_all()

    def _edit_floattext(self, ft):
        new_text = simpledialog.askstring(
            "Edit Text", "Enter text:", initialvalue=ft.text,
            parent=self.root)
        if new_text is not None:
            ft.text = new_text
            self._draw_all()

    def _edit_selected(self):
        if isinstance(self.selected, Box):
            self._edit_box_label(self.selected)
        elif isinstance(self.selected, Arrow):
            self._edit_arrow_label(self.selected)
        elif isinstance(self.selected, FloatText):
            self._edit_floattext(self.selected)
        else:
            self.status_var.set("Nothing selected to edit")

    def _change_color(self):
        if not isinstance(self.selected, Box):
            self.status_var.set("Select a box first to change its color")
            return
        # Show color picker dialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Choose Box Color")
        dlg.configure(bg=SURFACE)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Select box color:", bg=SURFACE, fg=TEXT_LIGHT,
                 font=("Segoe UI", 11), pady=12, padx=16).pack()

        chosen = tk.StringVar(value=self.selected.color)
        for name, (fill, border) in BOX_COLORS.items():
            row = tk.Frame(dlg, bg=SURFACE)
            row.pack(fill="x", padx=16, pady=2)
            tk.Radiobutton(row, text=name, variable=chosen, value=name,
                           bg=SURFACE, fg=TEXT_LIGHT, selectcolor=fill,
                           activebackground=SURFACE,
                           font=("Segoe UI", 10)).pack(side="left")
            tk.Frame(row, bg=fill, width=40, height=16).pack(side="right", padx=4)

        def apply():
            self.selected.color = chosen.get()
            self._draw_all()
            dlg.destroy()

        tk.Button(dlg, text="Apply", bg=ACCENT, fg="white", relief="flat",
                  padx=20, pady=6, cursor="hand2",
                  command=apply).pack(pady=12)

    # ─── Undo ─────────────────────────────────────────────────────────────────

    def _push_undo(self):
        state = self._serialize()
        self.undo_stack.append(state)
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def _undo(self):
        if not self.undo_stack:
            self.status_var.set("Nothing to undo")
            return
        state = self.undo_stack.pop()
        self._deserialize(state)
        self._draw_all()
        self.status_var.set("Undone")

    # ─── Delete / Select all ─────────────────────────────────────────────────

    def _delete_selected(self):
        if not self.selected:
            return
        self._push_undo()
        if isinstance(self.selected, Box):
            bid = self.selected.id
            self.boxes = [b for b in self.boxes if b.id != bid]
            self.arrows = [a for a in self.arrows
                           if a.src_id != bid and a.dst_id != bid]
        elif isinstance(self.selected, Arrow):
            aid = self.selected.id
            self.arrows = [a for a in self.arrows if a.id != aid]
        elif isinstance(self.selected, FloatText):
            fid = self.selected.id
            self.floattexts = [ft for ft in self.floattexts if ft.id != fid]
        self.selected = None
        self._draw_all()

    def _select_all(self):
        self.status_var.set(f"All selected  •  {len(self.boxes)} boxes, "
                            f"{len(self.arrows)} arrows")

    def _clear(self):
        if messagebox.askyesno("Clear Canvas",
                               "Delete everything on the canvas?"):
            self._push_undo()
            self.boxes.clear()
            self.arrows.clear()
            self.floattexts.clear()
            self.selected = None
            self._draw_all()

    def _reset_view(self):
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 1.0
        self.zoom_var.set("100%")
        self._draw_all()

    # ─── Serialise / Deserialise ──────────────────────────────────────────────

    def _serialize(self):
        return {
            "boxes":      [b.to_dict()  for b in self.boxes],
            "arrows":     [a.to_dict()  for a in self.arrows],
            "floattexts": [ft.to_dict() for ft in self.floattexts],
        }

    def _deserialize(self, data):
        self.boxes      = [Box.from_dict(d)       for d in data.get("boxes", [])]
        self.arrows     = [Arrow.from_dict(d)     for d in data.get("arrows", [])]
        self.floattexts = [FloatText.from_dict(d) for d in data.get("floattexts", [])]
        # Fix ID counters
        if self.boxes:
            Box._id      = max(b.id for b in self.boxes)
        if self.arrows:
            Arrow._id    = max(a.id for a in self.arrows)
        if self.floattexts:
            FloatText._id = max(ft.id for ft in self.floattexts)

    # ─── File I/O ─────────────────────────────────────────────────────────────

    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Diagram JSON", "*.json"), ("All files", "*.*")],
            title="Save Diagram")
        if path:
            with open(path, "w") as f:
                json.dump(self._serialize(), f, indent=2)
            self.status_var.set(f"Saved → {os.path.basename(path)}")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Diagram JSON", "*.json"), ("All files", "*.*")],
            title="Open Diagram")
        if path:
            with open(path) as f:
                data = json.load(f)
            self._push_undo()
            self._deserialize(data)
            self._draw_all()
            self.status_var.set(f"Loaded ← {os.path.basename(path)}")

    def _export_png(self):
        try:
            from PIL import ImageGrab
        except ImportError:
            messagebox.showinfo(
                "Export PNG",
                "Install Pillow for PNG export:\n  pip install Pillow\n\n"
                "Alternatively use the Print Screen key or Windows Snipping Tool "
                "to capture the canvas.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="Export PNG")
        if path:
            x = self.root.winfo_rootx() + self.canvas.winfo_x()
            y = self.root.winfo_rooty() + self.canvas.winfo_y()
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
            img.save(path)
            self.status_var.set(f"Exported → {os.path.basename(path)}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("DiagramTool")
    app = DiagramApp(root)

    # Demo objects so canvas is not empty on first launch
    b1 = Box(100, 150, label="Start", color="Green")
    b2 = Box(350, 150, label="Process A", color="Blue")
    b3 = Box(600, 150, label="Decision", color="Purple")
    b4 = Box(350, 320, label="Process B", color="Orange")
    b5 = Box(600, 320, label="End", color="Teal")
    app.boxes = [b1, b2, b3, b4, b5]
    a1 = Arrow(b1.id, b2.id, "input")
    a2 = Arrow(b2.id, b3.id)
    a3 = Arrow(b3.id, b4.id, "No")
    a4 = Arrow(b3.id, b5.id, "Yes")
    a5 = Arrow(b4.id, b5.id)
    app.arrows = [a1, a2, a3, a4, a5]
    ft = FloatText(350, 460, "Double-click any box to edit its label")
    app.floattexts = [ft]
    app._draw_all()

    root.mainloop()


if __name__ == "__main__":
    main()
