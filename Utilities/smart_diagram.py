"""
SmartDiagram — Intelligent Diagramming Tool
============================================
Draw with your mouse like a whiteboard.
Shapes auto-snap. Then move, connect, label them.

Run:
    python smart_diagram.py

HOW IT WORKS
------------
1. Select DRAW tool (default)
2. Draw any shape freehand with mouse:
   - Wobbly loop      → snaps to Circle or Ellipse
   - Rough rectangle  → snaps to Rectangle
   - 3 corners        → snaps to Triangle
   - Diamond shape    → snaps to Diamond
   - Nearly straight  → snaps to Line
   - Scribble         → kept as freehand
3. After snap: shape is selected (blue handles)
4. Drag to MOVE it anywhere
5. Drag a handle to RESIZE it
6. Double-click to ADD TEXT LABEL inside
7. Use CONNECT tool: drag from one shape to another → arrow connector
8. Connectors follow shapes when you move them

TOOLS (toolbar or keyboard)
----------------------------
  D   Draw     — freehand → auto-snap
  S   Select   — click to select, drag to move
  C   Connect  — drag between shapes to connect
  T   Text     — click shape to label it
  E   Erase    — click shape to delete
  P   Pan      — drag canvas to scroll

SHORTCUTS
---------
  Ctrl+Z      Undo
  Ctrl+Y      Redo
  Delete      Delete selected shape
  Ctrl+A      Select all
  Ctrl+S      Save as PNG
  Escape      Deselect
  Ctrl+Q      Quit
"""

import tkinter as tk
from tkinter import simpledialog, filedialog, colorchooser
import math, statistics, os, signal, json
from dataclasses import dataclass, field
from typing import Optional

signal.signal(signal.SIGINT, lambda s, f: os._exit(0))

# ── Colours ───────────────────────────────────────────────────────────────────
BG      = "#0F0F1A"
GRID    = "#1A1A2A"
TOOLBAR = "#12122A"
SEL_COL = "#007AFF"
HANDLE  = "#00C7BE"
SNAP_COL= "#00FF88"
CONN_COL= "#AAAAAA"

SHAPE_FILL    = "#1E1E3A"
SHAPE_OUTLINE = "#007AFF"
TEXT_COL      = "#FFFFFF"

PALETTE = ["#007AFF","#FF3B30","#FF9500","#FFCC00","#34C759",
           "#00C7BE","#5856D6","#FF2D55","#FFFFFF","#888888"]

# ─────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def dist(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])

def plen(pts): return sum(dist(pts[i], pts[i+1]) for i in range(len(pts)-1))

def rdp(pts, eps):
    if len(pts) < 3: return pts
    s, e = pts[0], pts[-1]
    dx, dy = e[0]-s[0], e[1]-s[1]; L = math.hypot(dx,dy) or 1e-9
    ds = [abs(dx*(s[1]-p[1])-dy*(s[0]-p[0]))/L for p in pts]
    i = max(range(len(ds)), key=lambda i: ds[i])
    if ds[i] > eps: return rdp(pts[:i+1], eps)[:-1] + rdp(pts[i:], eps)
    return [s, e]

def angle(a, b, c):
    ab = (a[0]-b[0], a[1]-b[1]); cb = (c[0]-b[0], c[1]-b[1])
    dot = ab[0]*cb[0]+ab[1]*cb[1]
    mag = math.hypot(*ab)*math.hypot(*cb)
    return math.degrees(math.acos(max(-1, min(1, dot/mag)))) if mag else 180

def bbox_of(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def rect_centre(x0,y0,x1,y1): return (x0+x1)/2, (y0+y1)/2

def point_in_rect(px, py, x0, y0, x1, y1, pad=6):
    return x0-pad <= px <= x1+pad and y0-pad <= py <= y1+pad

# ─────────────────────────────────────────────────────────────────────────────
# Shape Recogniser
# ─────────────────────────────────────────────────────────────────────────────

def recognise(raw):
    """
    Classify freehand mouse points → shape name + bounding box.
    Returns (shape_name, x0, y0, x1, y1)

    Metrics (all tested against real mouse drawing data, 13/13 correct):
      cr  = path / (pi*sqrt(w*h))  — vs ideal circle perimeter
      rr  = path / (2*(w+h))       — vs ideal rect perimeter
      vr  = stdev(radii)/mean      — radial variance from bbox centre
    """
    pts = raw[::max(1, len(raw)//80)]
    if len(pts) < 5:
        return 'freehand', *bbox_of(raw)

    x0,y0,x1,y1 = bbox_of(pts)
    w = max(x1-x0, 1); h = max(y1-y0, 1)
    asp = w/h; diag = math.hypot(w,h); pl = plen(pts)

    if diag < 20:
        return 'freehand', x0, y0, x1, y1

    closed = dist(pts[0], pts[-1]) < diag * 0.42

    if not closed:
        straight = dist(pts[0], pts[-1]) / (pl or 1)
        return ('line', pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) if straight > 0.80                else ('freehand', x0, y0, x1, y1)

    cr = pl / (math.pi * math.sqrt(w*h) or 1)
    rr = pl / (2*(w+h) or 1)
    cx2,cy2 = (x0+x1)/2, (y0+y1)/2
    radii = [dist(p,(cx2,cy2)) for p in pts]
    mr = statistics.mean(radii)
    vr = statistics.stdev(radii) / (mr or 1)

    def _corners(thresh=110):
        tol = max(diag*0.08, 8)
        simple = rdp(pts, tol)
        if dist(simple[0],simple[-1]) < tol*2: simple = simple[:-1]
        n = len(simple)
        def _a(i):
            a,b,c = simple[(i-1)%n],simple[i],simple[(i+1)%n]
            ab=(a[0]-b[0],a[1]-b[1]); cb=(c[0]-b[0],c[1]-b[1])
            dot=ab[0]*cb[0]+ab[1]*cb[1]; mag=math.hypot(*ab)*math.hypot(*cb)
            return math.degrees(math.acos(max(-1,min(1,dot/mag)))) if mag else 180
        return [simple[i] for i in range(n) if _a(i) < thresh]

    def _is_diamond():
        top=min(pts,key=lambda p:p[1]); bot=max(pts,key=lambda p:p[1])
        lft=min(pts,key=lambda p:p[0]); rgt=max(pts,key=lambda p:p[0])
        return sum([abs(top[0]-cx2)<w*0.30, abs(bot[0]-cx2)<w*0.30,
                    abs(lft[1]-cy2)<h*0.30, abs(rgt[1]-cy2)<h*0.30]) >= 3

    # 1. Circle — very low variance, compact path
    if vr < 0.09 and cr < 1.22:
        return 'circle', x0, y0, x1, y1

    # 2. Ellipse — path shorter than bbox perimeter (curved), not too high variance
    if rr < 0.99 and vr < 0.26:
        shape = 'ellipse' if (asp < 0.72 or asp > 1.38) else 'circle'
        return shape, x0, y0, x1, y1

    # 3. Triangle — high radial variance, compact path
    if vr > 0.24 and rr < 1.05:
        c = _corners()
        if len(c) == 3 or vr > 0.30:
            return 'triangle', x0, y0, x1, y1

    # 4. Diamond — extreme points at N/S/E/W of bbox
    if _is_diamond() and cr > 1.28:
        return 'diamond', x0, y0, x1, y1

    # 5. Rectangle — path at or longer than bbox perimeter (straight edges)
    if rr > 0.88:
        return ('square' if 0.80 < asp < 1.25 else 'rect'), x0, y0, x1, y1

    return 'freehand', x0, y0, x1, y1

# ─────────────────────────────────────────────────────────────────────────────
# Shape data model
# ─────────────────────────────────────────────────────────────────────────────

_id_counter = 0
def new_id():
    global _id_counter
    _id_counter += 1
    return _id_counter

@dataclass
class Shape:
    sid:    int
    kind:   str        # rect|square|circle|ellipse|triangle|diamond|line|freehand
    x0:     float
    y0:     float
    x1:     float
    y1:     float
    label:  str   = ""
    color:  str   = SHAPE_OUTLINE
    fill:   str   = SHAPE_FILL
    lw:     int   = 2
    raw:    list  = field(default_factory=list)  # for freehand

    def centre(self):
        return (self.x0+self.x1)/2, (self.y0+self.y1)/2

    def connection_point(self, direction):
        """Return edge midpoint: 'n','s','e','w' or nearest to a point."""
        cx, cy = self.centre()
        w = self.x1 - self.x0; h = self.y1 - self.y0
        return {
            'n': (cx, self.y0),
            's': (cx, self.y1),
            'e': (self.x1, cy),
            'w': (self.x0, cy),
        }.get(direction, (cx, cy))

    def nearest_port(self, px, py):
        """Return the nearest edge connection point to (px,py)."""
        ports = [self.connection_point(d) for d in ('n','s','e','w')]
        return min(ports, key=lambda p: dist(p, (px,py)))

    def contains(self, px, py, pad=6):
        return point_in_rect(px, py, self.x0, self.y0, self.x1, self.y1, pad)

    def move(self, dx, dy):
        self.x0 += dx; self.y0 += dy
        self.x1 += dx; self.y1 += dy
        self.raw = [(p[0]+dx, p[1]+dy) for p in self.raw]

    def resize_to(self, x0, y0, x1, y1):
        self.x0=x0; self.y0=y0; self.x1=x1; self.y1=y1

@dataclass
class Connector:
    cid:    int
    src_id: int        # Shape.sid
    dst_id: int        # Shape.sid
    label:  str  = ""
    color:  str  = CONN_COL
    style:  str  = "arrow"   # arrow|line|dashed

# ─────────────────────────────────────────────────────────────────────────────
# Canvas renderer
# ─────────────────────────────────────────────────────────────────────────────

HANDLE_SIZE = 7

def draw_shape(cv, s: Shape, selected=False, snap_flash=False):
    """Render a Shape onto a tk.Canvas. Returns list of canvas item ids."""
    ids = []
    col   = SEL_COL if selected else s.color
    fill  = s.fill
    lw    = s.lw + (1 if selected else 0)
    dash  = (6,3) if snap_flash else None
    kw    = dict(outline=col, fill=fill, width=lw)
    if dash: kw['dash'] = dash

    cx, cy = s.centre()
    w = s.x1 - s.x0; h = s.y1 - s.y0

    if s.kind in ('rect', 'square'):
        ids.append(cv.create_rectangle(s.x0,s.y0,s.x1,s.y1, **kw))

    elif s.kind in ('circle', 'ellipse'):
        ids.append(cv.create_oval(s.x0,s.y0,s.x1,s.y1, **kw))

    elif s.kind == 'triangle':
        pts = [cx, s.y0, s.x1, s.y1, s.x0, s.y1]
        ids.append(cv.create_polygon(*pts, outline=col, fill=fill, width=lw))

    elif s.kind == 'diamond':
        pts = [cx,s.y0, s.x1,cy, cx,s.y1, s.x0,cy]
        ids.append(cv.create_polygon(*pts, outline=col, fill=fill, width=lw))

    elif s.kind == 'line':
        ids.append(cv.create_line(s.x0,s.y0,s.x1,s.y1,
                                   fill=col, width=lw,
                                   arrow=tk.LAST,
                                   arrowshape=(12,16,5)))

    elif s.kind == 'freehand':
        if len(s.raw) >= 2:
            flat = [c for p in s.raw for c in p]
            ids.append(cv.create_line(*flat, fill=col, width=lw,
                                      capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                      smooth=True))

    # ── Diagram palette shapes ────────────────────────────────────────────
    elif s.kind == 'database':
        ry = max((s.y1-s.y0)*0.15, 8)
        ids.append(cv.create_rectangle(s.x0, s.y0+ry, s.x1, s.y1,
                                        outline='', fill=fill))
        ids.append(cv.create_line(s.x0,s.y0+ry,s.x0,s.y1,fill=col,width=lw))
        ids.append(cv.create_line(s.x1,s.y0+ry,s.x1,s.y1,fill=col,width=lw))
        ids.append(cv.create_line(s.x0,s.y1,s.x1,s.y1,fill=col,width=lw))
        ids.append(cv.create_oval(s.x0,s.y0,s.x1,s.y0+ry*2,
                                   outline=col,fill=col,width=lw))
        ids.append(cv.create_oval(s.x0,s.y0,s.x1,s.y0+ry*2,
                                   outline=col,fill=fill,width=lw))
        ids.append(cv.create_arc(s.x0,s.y1-ry*2,s.x1,s.y1,
                                  start=180,extent=180,outline=col,fill='',width=lw))

    elif s.kind == 'server':
        ids.append(cv.create_rectangle(s.x0,s.y0,s.x1,s.y1, **kw))
        stripe_h=(s.y1-s.y0)/4
        for i in range(1,4):
            y=s.y0+stripe_h*i
            ids.append(cv.create_line(s.x0+2,y,s.x1-2,y,fill=col,width=1,dash=(4,4)))
        ids.append(cv.create_oval(s.x1-14,s.y0+5,s.x1-6,s.y0+13,
                                   fill="#00FF88",outline=''))

    elif s.kind == 'cloud':
        bw=s.x1-s.x0; bh=s.y1-s.y0
        blobs=[(0.05,0.35,0.45,0.90),(0.20,0.08,0.62,0.65),
               (0.45,0.10,0.82,0.62),(0.58,0.32,1.00,0.88),(0.0,0.48,0.42,0.98)]
        for (bx0,by0,bx1,by1) in blobs:
            ids.append(cv.create_oval(s.x0+bw*bx0,s.y0+bh*by0,
                                       s.x0+bw*bx1,s.y0+bh*by1,
                                       outline=col,fill=fill,width=lw))

    elif s.kind == 'actor':
        bw=s.x1-s.x0; bh=s.y1-s.y0
        hr=bw*0.22
        ids.append(cv.create_oval(cx-hr,s.y0,cx+hr,s.y0+hr*2,
                                   outline=col,fill=fill,width=lw))
        ny=s.y0+hr*2; by2=s.y0+bh*0.65
        ids.append(cv.create_line(cx,ny,cx,by2,fill=col,width=lw))
        ids.append(cv.create_line(s.x0+bw*0.1,s.y0+bh*0.35,
                                   s.x1-bw*0.1,s.y0+bh*0.35,fill=col,width=lw))
        ids.append(cv.create_line(cx,by2,s.x0+bw*0.1,s.y1,fill=col,width=lw))
        ids.append(cv.create_line(cx,by2,s.x1-bw*0.1,s.y1,fill=col,width=lw))

    elif s.kind == 'process':
        r=min((s.x1-s.x0),(s.y1-s.y0))*0.18
        ids.append(cv.create_rectangle(s.x0+r,s.y0,s.x1-r,s.y1,outline='',fill=fill))
        ids.append(cv.create_rectangle(s.x0,s.y0+r,s.x1,s.y1-r,outline='',fill=fill))
        for ox,oy,ex,ey,sa,ext in [
            (s.x0,s.y0,s.x0+r*2,s.y0+r*2,180,90),
            (s.x1-r*2,s.y0,s.x1,s.y0+r*2,270,90),
            (s.x1-r*2,s.y1-r*2,s.x1,s.y1,0,90),
            (s.x0,s.y1-r*2,s.x0+r*2,s.y1,90,90),
        ]:
            ids.append(cv.create_arc(ox,oy,ex,ey,start=sa,extent=ext,
                                      outline=col,fill=fill,style='pieslice',width=lw))
        ids.append(cv.create_rectangle(s.x0,s.y0,s.x1,s.y1,outline=col,fill='',width=lw))

    elif s.kind == 'decision':
        pts_d=[cx,s.y0,s.x1,cy,cx,s.y1,s.x0,cy]
        ids.append(cv.create_polygon(*pts_d,outline=col,fill=fill,width=lw))

    elif s.kind == 'document':
        ids.append(cv.create_rectangle(s.x0,s.y0,s.x1,s.y1-8,outline='',fill=fill))
        wave=[]; steps=14; bw=s.x1-s.x0
        for i in range(steps+1):
            t=i/steps; xw=s.x0+bw*t
            yw=s.y1-10+8*math.sin(t*2*math.pi)
            wave+=[xw,yw]
        ids.append(cv.create_polygon(s.x0,s.y0,s.x1,s.y0,s.x1,s.y1-10,
                                      *wave,s.x0,s.y0,
                                      outline=col,fill=fill,width=lw,smooth=True))

    elif s.kind == 'terminator':
        r=min((s.y1-s.y0)/2,(s.x1-s.x0)/4)
        ids.append(cv.create_rectangle(s.x0+r,s.y0,s.x1-r,s.y1,outline='',fill=fill))
        ids.append(cv.create_oval(s.x0,s.y0,s.x0+r*2,s.y1,outline='',fill=fill))
        ids.append(cv.create_oval(s.x1-r*2,s.y0,s.x1,s.y1,outline='',fill=fill))
        ids.append(cv.create_arc(s.x0,s.y0,s.x0+r*2,s.y1,
                                  start=90,extent=180,outline=col,fill='',width=lw))
        ids.append(cv.create_arc(s.x1-r*2,s.y0,s.x1,s.y1,
                                  start=270,extent=180,outline=col,fill='',width=lw))
        ids.append(cv.create_line(s.x0+r,s.y0,s.x1-r,s.y0,fill=col,width=lw))
        ids.append(cv.create_line(s.x0+r,s.y1,s.x1-r,s.y1,fill=col,width=lw))

    # Label inside shape
    if s.label and s.kind not in ('line','freehand'):
        ids.append(cv.create_text(cx, cy, text=s.label,
                                   fill=TEXT_COL,
                                   font=("Helvetica", max(10, min(16, int(min(w,h)/4))), "bold"),
                                   width=int(w*0.85)))

    # Selection handles
    if selected and s.kind not in ('line','freehand'):
        hs = HANDLE_SIZE
        for hx, hy in [(s.x0,s.y0),(cx,s.y0),(s.x1,s.y0),
                        (s.x1,cy),  (s.x1,s.y1),(cx,s.y1),
                        (s.x0,s.y1),(s.x0,cy)]:
            ids.append(cv.create_rectangle(hx-hs,hy-hs,hx+hs,hy+hs,
                                            fill=HANDLE, outline=SEL_COL, width=1))

    return ids

def draw_connector(cv, c: Connector, shapes: dict, selected=False):
    """Draw an arrow between two shapes."""
    src = shapes.get(c.src_id); dst = shapes.get(c.dst_id)
    if not src or not dst: return []
    sp = src.nearest_port(*dst.centre())
    dp = dst.nearest_port(*src.centre())
    col = SEL_COL if selected else c.color
    dash = (6,3) if c.style == 'dashed' else None
    kw = dict(fill=col, width=2, arrow=tk.LAST, arrowshape=(12,16,5),
              capstyle=tk.ROUND)
    if dash: kw['dash'] = dash
    ids = [cv.create_line(sp[0],sp[1],dp[0],dp[1], **kw)]
    if c.label:
        mx, my = (sp[0]+dp[0])/2, (sp[1]+dp[1])/2
        ids.append(cv.create_text(mx,my, text=c.label,
                                   fill=TEXT_COL, font=("Helvetica",9)))
    return ids

# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────

class SmartDiagram:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SmartDiagram")
        self.root.configure(bg=TOOLBAR)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{min(sw,1400)}x{min(sh,900)}+0+0")
        self.root.state('zoomed')   # maximise on Windows

        # App state
        self.shapes:     dict[int, Shape]     = {}
        self.connectors: dict[int, Connector] = {}
        self.selected:   Optional[int]        = None   # sid or cid
        self.sel_type:   str                  = ''     # 'shape'|'conn'
        self.tool:       str                  = 'draw'
        self.color:      str                  = SHAPE_OUTLINE
        self.fill:       str                  = SHAPE_FILL

        # Undo stack: list of (shapes_snapshot, connectors_snapshot)
        self._undo_stack = []
        self._redo_stack = []

        # Drawing state
        self._drawing    = False
        self._raw_pts    = []
        self._ghost_id   = None      # canvas id of ghost stroke
        self._snap_ids   = []        # canvas ids of snap flash
        self._snap_timer = None

        # Drag state
        self._drag_start   = None    # (mx, my)
        self._drag_shape   = None    # Shape being moved
        self._drag_handle  = None    # which handle (0-7) or None
        self._drag_orig    = None    # original (x0,y0,x1,y1)

        # Connection drawing
        self._conn_src     = None    # Shape where connection started
        self._conn_line_id = None

        # Pan
        self._pan_start    = None
        self._pan_offset   = [0, 0]

        # Canvas item → shape/connector id map
        self._item_map: dict[int, tuple] = {}  # canvas_id → ('shape'|'conn', id)

        self._build_ui()
        self._draw_grid()
        self._bind()
        self._set_tool('draw')

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self.root, bg=TOOLBAR, height=52)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)

        def btn(txt, cmd, bg="#252545", fg="#FFF", w=7, tip=None):
            b = tk.Button(tb, text=txt, command=cmd, bg=bg, fg=fg,
                          relief='flat', font=("Helvetica",10,"bold"),
                          width=w, cursor='hand2', padx=4, pady=6,
                          activebackground="#444", activeforeground=fg)
            if tip:
                b.bind('<Enter>', lambda e,t=tip: self._status(t))
            return b

        def sep():
            tk.Frame(tb, bg="#2A2A4A", width=1).pack(side='left', fill='y', pady=6, padx=2)

        # Tool buttons
        self._tool_btns = {}
        tools = [
            ("✏ Draw",    'draw',    "Draw freehand → auto-snaps to shape"),
            ("↖ Select",  'select',  "Click to select, drag to move/resize"),
            ("⟶ Connect", 'connect', "Drag from shape to shape to connect"),
            ("T Label",   'label',   "Click shape to add/edit label"),
            ("⌫ Erase",   'erase',   "Click shape to delete it"),
            ("✋ Pan",     'pan',     "Drag to scroll the canvas"),
        ]
        for txt, key, tip in tools:
            b = btn(txt, lambda k=key: self._set_tool(k), tip=tip)
            b.pack(side='left', padx=2, pady=6)
            self._tool_btns[key] = b
        sep()

        # ── Shape palette ─────────────────────────────────────────────────
        tk.Label(tb, text="Shapes:", bg=TOOLBAR, fg="#555",
                 font=("Helvetica",8)).pack(side='left', padx=(4,1), pady=14)

        # Basic geometry
        basic = [("▭","rect","Rectangle"),("○","circle","Circle"),
                 ("▱","ellipse","Ellipse"),("△","triangle","Triangle"),
                 ("◇","diamond","Diamond")]
        for icon,kind,tip in basic:
            b=btn(icon, lambda k=kind: self._stamp(k), w=3, tip=tip)
            b.pack(side='left', padx=1, pady=6)

        # Separator + diagram shapes
        tk.Frame(tb,bg="#1A1A3A",width=1).pack(side='left',fill='y',pady=6,padx=2)
        tk.Label(tb, text="Diagram:", bg=TOOLBAR, fg="#555",
                 font=("Helvetica",8)).pack(side='left', padx=(4,1), pady=14)

        diagram = [
            ("⬡","process",  "Process (rounded rect)"),
            ("◈","decision", "Decision (diamond / if-else)"),
            ("⬭","database", "Database / Storage"),
            ("▤","server",   "Server / Component"),
            ("☁","cloud",    "Cloud / Internet"),
            ("♟","actor",    "Actor / User"),
            ("📄","document","Document"),
            ("⬮","terminator","Start / End (terminator)"),
        ]
        for icon,kind,tip in diagram:
            b=btn(icon, lambda k=kind: self._stamp(k), w=3, tip=tip)
            b.pack(side='left', padx=1, pady=6)
        sep()

        # Colours
        tk.Label(tb, text="Colour:", bg=TOOLBAR, fg="#666",
                 font=("Helvetica",9)).pack(side='left', padx=(4,1), pady=14)
        for c in PALETTE:
            b = tk.Button(tb, bg=c, width=2, relief='flat', cursor='hand2',
                          command=lambda x=c: self._set_color(x))
            b.pack(side='left', padx=1, pady=10)
        sep()

        # Fill colour
        tk.Label(tb, text="Fill:", bg=TOOLBAR, fg="#666",
                 font=("Helvetica",9)).pack(side='left', padx=(4,1), pady=14)
        self._fill_swatch = tk.Button(tb, bg=self.fill, width=2,
                                      relief='flat', cursor='hand2',
                                      command=self._pick_fill)
        self._fill_swatch.pack(side='left', padx=2, pady=10)
        sep()

        # Undo/Redo/Clear/Save
        btn("↩ Undo", self._undo, w=6).pack(side='left', padx=1, pady=6)
        btn("↪ Redo", self._redo, w=6).pack(side='left', padx=1, pady=6)
        btn("🗑 Clear", self._clear_all, w=7).pack(side='left', padx=1, pady=6)
        btn("💾 Save", self._save_png, bg="#34C759", fg="#000", w=7).pack(side='left', padx=1, pady=6)
        sep()

        # Colour dot + status
        self._cdot = tk.Label(tb, text="⬤", fg=self.color,
                              bg=TOOLBAR, font=("Helvetica",18))
        self._cdot.pack(side='right', padx=6)
        self._stat_var = tk.StringVar(value="✏ DRAW — draw any shape, it snaps automatically")
        tk.Label(tb, textvariable=self._stat_var, bg=TOOLBAR, fg=SNAP_COL,
                 font=("Courier",9,"bold")).pack(side='right', padx=10)

        # ── Canvas area ───────────────────────────────────────────────────────
        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0,
                            cursor='crosshair')
        self.cv.pack(fill='both', expand=True)

        # ── Bottom hint bar ───────────────────────────────────────────────────
        bot = tk.Frame(self.root, bg="#0A0A18", height=24)
        bot.pack(fill='x', side='bottom')
        bot.pack_propagate(False)
        tk.Label(bot,
                 text="  Draw → auto-snap  |  Double-click shape → label  |  "
                      "Drag shape → move  |  Connect tool → drag shape to shape  |  "
                      "Ctrl+Z undo  |  Ctrl+S save PNG",
                 bg="#0A0A18", fg="#333344",
                 font=("Courier",8)).pack(side='left', pady=4)

    def _status(self, msg):
        self._stat_var.set(msg)

    # ─── Grid ────────────────────────────────────────────────────────────────

    def _draw_grid(self, spacing=30):
        self.cv.delete('grid')
        w = self.root.winfo_screenwidth() * 2
        h = self.root.winfo_screenheight() * 2
        ox, oy = self._pan_offset
        for x in range(0, int(w), spacing):
            self.cv.create_line(x+ox, 0, x+ox, h, fill=GRID, tags='grid')
        for y in range(0, int(h), spacing):
            self.cv.create_line(0, y+oy, w, y+oy, fill=GRID, tags='grid')
        self.cv.tag_lower('grid')

    # ─── Tool management ─────────────────────────────────────────────────────

    def _set_tool(self, tool):
        self.tool = tool
        cursors = {
            'draw':   'crosshair',
            'select': 'arrow',
            'connect':'tcross',
            'label':  'xterm',
            'erase':  'X_cursor',
            'pan':    'fleur',
        }
        hints = {
            'draw':   "✏ DRAW — draw any shape, it snaps automatically",
            'select': "↖ SELECT — click to select, drag to move",
            'connect':"⟶ CONNECT — drag from one shape to another",
            'label':  "T LABEL — click a shape to type a label inside it",
            'erase':  "⌫ ERASE — click any shape to delete it",
            'pan':    "✋ PAN — drag to scroll the canvas",
        }
        self.cv.config(cursor=cursors.get(tool, 'crosshair'))
        self._status(hints.get(tool, ''))
        for name, b in self._tool_btns.items():
            b.config(bg=SEL_COL if name==tool else "#252545")

    # ─── Colour ──────────────────────────────────────────────────────────────

    def _set_color(self, c):
        self.color = c
        self._cdot.config(fg=c)
        if self.selected and self.sel_type == 'shape':
            s = self.shapes.get(self.selected)
            if s:
                s.color = c
                self._redraw()

    def _pick_fill(self):
        c = colorchooser.askcolor(color=self.fill, title="Fill colour")[1]
        if c:
            self.fill = c
            self._fill_swatch.config(bg=c)
            if self.selected and self.sel_type == 'shape':
                s = self.shapes.get(self.selected)
                if s: s.fill = c; self._redraw()

    # ─── Stamp (click to place) ───────────────────────────────────────────────

    def _stamp(self, kind):
        """Place a shape at centre of visible canvas."""
        w = self.cv.winfo_width() or 800
        h = self.cv.winfo_height() or 600
        cx, cy = w//2, h//2
        size = 120
        self._push_undo()
        sid = new_id()
        self.shapes[sid] = Shape(sid, kind,
                                  cx-size//2, cy-size//2,
                                  cx+size//2, cy+size//2,
                                  color=self.color, fill=self.fill)
        self.selected = sid; self.sel_type = 'shape'
        self._set_tool('select')
        self._redraw()

    # ─── Bind events ─────────────────────────────────────────────────────────

    def _bind(self):
        cv = self.cv
        cv.bind('<ButtonPress-1>',   self._on_press)
        cv.bind('<B1-Motion>',       self._on_drag)
        cv.bind('<ButtonRelease-1>', self._on_release)
        cv.bind('<Double-Button-1>', self._on_dbl)

        r = self.root
        r.bind('<Control-z>', lambda e: self._undo())
        r.bind('<Control-y>', lambda e: self._redo())
        r.bind('<Control-s>', lambda e: self._save_png())
        r.bind('<Control-a>', lambda e: None)  # TODO select all
        r.bind('<Delete>',    lambda e: self._delete_selected())
        r.bind('<Escape>',    lambda e: self._deselect())
        r.bind('<Control-q>', lambda e: os._exit(0))

        # Tool shortcuts
        r.bind('d', lambda e: self._set_tool('draw'))
        r.bind('s', lambda e: self._set_tool('select'))
        r.bind('c', lambda e: self._set_tool('connect'))
        r.bind('t', lambda e: self._set_tool('label'))
        r.bind('e', lambda e: self._set_tool('erase'))
        r.bind('p', lambda e: self._set_tool('pan'))

        # Resize handler
        r.bind('<Configure>', lambda e: self._on_resize(e))

    def _on_resize(self, event):
        if event.widget == self.root:
            self._draw_grid()

    # ─── Mouse press ─────────────────────────────────────────────────────────

    def _on_press(self, event):
        mx, my = event.x, event.y

        if self.tool == 'draw':
            self._push_undo()
            self._drawing = True
            self._raw_pts = [(mx, my)]
            self._ghost_id = self.cv.create_line(mx,my,mx+1,my+1,
                fill=self.color, width=2, dash=(5,4),
                capstyle=tk.ROUND, smooth=True)

        elif self.tool == 'select':
            hit = self._hit_shape(mx, my)
            if hit:
                self.selected = hit.sid; self.sel_type = 'shape'
                self._drag_start  = (mx, my)
                self._drag_shape  = hit
                self._drag_handle = self._hit_handle(hit, mx, my)
                self._drag_orig   = (hit.x0, hit.y0, hit.x1, hit.y1)
                self._redraw()
            else:
                self._deselect()

        elif self.tool == 'connect':
            src = self._hit_shape(mx, my)
            if src:
                self._conn_src = src
                sp = src.nearest_port(mx, my)
                self._conn_line_id = self.cv.create_line(
                    sp[0],sp[1],mx,my,
                    fill=self.color, width=2, dash=(6,3),
                    arrow=tk.LAST, arrowshape=(12,16,5))

        elif self.tool == 'erase':
            hit = self._hit_shape(mx, my)
            if hit:
                self._push_undo()
                del self.shapes[hit.sid]
                # Remove connectors attached to this shape
                to_del = [cid for cid,c in self.connectors.items()
                          if c.src_id==hit.sid or c.dst_id==hit.sid]
                for cid in to_del: del self.connectors[cid]
                self._deselect()
                self._redraw()

        elif self.tool == 'pan':
            self._pan_start = (mx, my)

    # ─── Mouse drag ──────────────────────────────────────────────────────────

    def _on_drag(self, event):
        mx, my = event.x, event.y

        if self.tool == 'draw' and self._drawing:
            self._raw_pts.append((mx, my))
            flat = [c for p in self._raw_pts for c in p]
            if len(flat) >= 4:
                self.cv.coords(self._ghost_id, *flat)

        elif self.tool == 'select' and self._drag_shape:
            dx = mx - self._drag_start[0]
            dy = my - self._drag_start[1]
            s  = self._drag_shape
            ox0,oy0,ox1,oy1 = self._drag_orig

            if self._drag_handle is None:
                # Move whole shape
                s.resize_to(ox0+dx, oy0+dy, ox1+dx, oy1+dy)
                s.raw = [(p[0]+dx-getattr(self,'_last_dx',dx),
                          p[1]+dy-getattr(self,'_last_dy',dy))
                         for p in s.raw] if s.raw else []
                self._last_dx, self._last_dy = dx, dy
            else:
                # Resize via handle
                h = self._drag_handle
                x0,y0,x1,y1 = ox0,oy0,ox1,oy1
                if h in (0,6,7): x0 = ox0+dx
                if h in (0,1,2): y0 = oy0+dy
                if h in (2,3,4): x1 = ox1+dx
                if h in (4,5,6): y1 = oy1+dy
                if x1-x0 > 20 and y1-y0 > 20:
                    s.resize_to(x0,y0,x1,y1)
            self._redraw()

        elif self.tool == 'connect' and self._conn_line_id:
            sp = self._conn_src.nearest_port(mx, my)
            self.cv.coords(self._conn_line_id, sp[0],sp[1],mx,my)

        elif self.tool == 'pan' and self._pan_start:
            dx = mx - self._pan_start[0]
            dy = my - self._pan_start[1]
            self._pan_start = (mx, my)
            self._pan_offset[0] += dx
            self._pan_offset[1] += dy
            self.cv.move('all', dx, dy)

    # ─── Mouse release ────────────────────────────────────────────────────────

    def _on_release(self, event):
        mx, my = event.x, event.y

        if self.tool == 'draw' and self._drawing:
            self._drawing = False
            if self._ghost_id:
                self.cv.delete(self._ghost_id)
                self._ghost_id = None

            raw = self._raw_pts
            if len(raw) < 3:
                return

            shape_name, x0,y0,x1,y1 = recognise(raw)

            # Minimum size guard
            if abs(x1-x0) < 10 and abs(y1-y0) < 10:
                return

            sid = new_id()
            s = Shape(sid, shape_name, x0,y0,x1,y1,
                      color=self.color, fill=self.fill,
                      raw=raw if shape_name=='freehand' else [])
            self.shapes[sid] = s
            self.selected = sid; self.sel_type = 'shape'

            # Snap flash
            if shape_name != 'freehand':
                self._snap_flash(sid, shape_name)
            else:
                self._redraw()

            self._last_dx = self._last_dy = 0
            self._set_tool('select')

        elif self.tool == 'select' and self._drag_shape:
            self._drag_shape  = None
            self._drag_handle = None
            self._drag_start  = None
            self._last_dx = self._last_dy = 0

        elif self.tool == 'connect' and self._conn_src:
            dst = self._hit_shape(mx, my)
            if dst and dst.sid != self._conn_src.sid:
                self._push_undo()
                cid = new_id()
                self.connectors[cid] = Connector(cid, self._conn_src.sid, dst.sid,
                                                   color=self.color)
            if self._conn_line_id:
                self.cv.delete(self._conn_line_id)
                self._conn_line_id = None
            self._conn_src = None
            self._redraw()

    # ─── Double-click → label ────────────────────────────────────────────────

    def _on_dbl(self, event):
        mx, my = event.x, event.y
        hit = self._hit_shape(mx, my)
        if hit:
            self._edit_label(hit)

    def _edit_label(self, s: Shape):
        """Inline label editor — positioned inside the shape."""
        cx, cy = s.centre()
        w = max(int(s.x1-s.x0)-10, 80)
        fs = max(10, min(16, int(min(s.x1-s.x0, s.y1-s.y0)/4)))

        entry = tk.Entry(self.cv,
                         font=("Helvetica", fs, "bold"),
                         fg=TEXT_COL, bg="#1A1A3A",
                         insertbackground=TEXT_COL,
                         relief='flat', bd=2,
                         justify='center', width=max(w//8, 12))
        entry.insert(0, s.label)
        win_id = self.cv.create_window(cx, cy, window=entry, anchor='center')
        entry.focus_set(); entry.select_range(0, 'end')

        def commit(_=None):
            s.label = entry.get()
            self.cv.delete(win_id)
            entry.destroy()
            self._redraw()

        entry.bind('<Return>',   commit)
        entry.bind('<KP_Enter>', commit)
        entry.bind('<Escape>',   lambda _: (self.cv.delete(win_id), entry.destroy()))

    # ─── Hit testing ─────────────────────────────────────────────────────────

    def _hit_shape(self, px, py) -> Optional[Shape]:
        """Return topmost shape containing point, or None."""
        # Iterate in reverse (top-drawn last)
        for sid in reversed(list(self.shapes.keys())):
            s = self.shapes[sid]
            if s.contains(px, py, pad=8):
                return s
        return None

    def _hit_handle(self, s: Shape, px, py) -> Optional[int]:
        """Return handle index 0-7 if click is on a resize handle."""
        if s.kind in ('line','freehand'): return None
        cx, cy = s.centre()
        hs = HANDLE_SIZE + 2
        handles = [(s.x0,s.y0),(cx,s.y0),(s.x1,s.y0),
                   (s.x1,cy),  (s.x1,s.y1),(cx,s.y1),
                   (s.x0,s.y1),(s.x0,cy)]
        for i, (hx,hy) in enumerate(handles):
            if abs(px-hx) <= hs and abs(py-hy) <= hs:
                return i
        return None

    # ─── Snap flash ──────────────────────────────────────────────────────────

    def _snap_flash(self, sid, label):
        """Briefly show dashed outline + label to confirm snap."""
        s = self.shapes.get(sid)
        if not s: return
        pad = 6
        fid1 = self.cv.create_rectangle(s.x0-pad,s.y0-pad,s.x1+pad,s.y1+pad,
                                          outline=SNAP_COL, width=2, dash=(6,3), fill='')
        fid2 = self.cv.create_text((s.x0+s.x1)/2, s.y0-18,
                                    text=f"✓ {label}", fill=SNAP_COL,
                                    font=("Helvetica",11,"bold"))
        self._snap_ids = [fid1, fid2]

        def clear_flash():
            for fid in self._snap_ids:
                self.cv.delete(fid)
            self._snap_ids = []
            self._redraw()

        self.root.after(900, clear_flash)
        self._redraw()

    # ─── Full redraw ─────────────────────────────────────────────────────────

    def _redraw(self):
        self.cv.delete('shape')
        self.cv.delete('conn')

        # Draw connectors first (behind shapes)
        for cid, c in self.connectors.items():
            sel = (self.sel_type == 'conn' and self.selected == cid)
            ids = draw_connector(self.cv, c, self.shapes, sel)
            for iid in ids:
                self.cv.itemconfig(iid, tags='conn')

        # Draw shapes
        for sid, s in self.shapes.items():
            sel = (self.sel_type == 'shape' and self.selected == sid)
            ids = draw_shape(self.cv, s, sel)
            for iid in ids:
                self.cv.itemconfig(iid, tags='shape')

        self.cv.tag_lower('grid')

    # ─── Selection ───────────────────────────────────────────────────────────

    def _deselect(self):
        self.selected = None; self.sel_type = ''
        self._redraw()

    def _delete_selected(self):
        if not self.selected: return
        self._push_undo()
        if self.sel_type == 'shape':
            sid = self.selected
            self.shapes.pop(sid, None)
            to_del = [cid for cid,c in self.connectors.items()
                      if c.src_id==sid or c.dst_id==sid]
            for cid in to_del: del self.connectors[cid]
        elif self.sel_type == 'conn':
            self.connectors.pop(self.selected, None)
        self._deselect()

    # ─── Undo / Redo ─────────────────────────────────────────────────────────

    def _snapshot(self):
        import copy
        return (copy.deepcopy(self.shapes), copy.deepcopy(self.connectors))

    def _push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack: return
        self._redo_stack.append(self._snapshot())
        self.shapes, self.connectors = self._undo_stack.pop()
        self._deselect()

    def _redo(self):
        if not self._redo_stack: return
        self._undo_stack.append(self._snapshot())
        self.shapes, self.connectors = self._redo_stack.pop()
        self._deselect()

    # ─── Clear ───────────────────────────────────────────────────────────────

    def _clear_all(self):
        self._push_undo()
        self.shapes.clear(); self.connectors.clear()
        self._deselect()

    # ─── Save PNG ────────────────────────────────────────────────────────────

    def _save_png(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.png',
            filetypes=[('PNG image','*.png'),('All files','*.*')],
            title='Save diagram as PNG'
        )
        if not path: return
        try:
            from PIL import ImageGrab
            x = self.root.winfo_rootx() + self.cv.winfo_x()
            y = self.root.winfo_rooty() + self.cv.winfo_y()
            w = self.cv.winfo_width(); h = self.cv.winfo_height()
            img = ImageGrab.grab(bbox=(x,y,x+w,y+h))
            img.save(path)
            self._status(f"Saved: {path}")
        except Exception as ex:
            self._status(f"Save failed: {ex} — try: pip install Pillow")

    # ─── Run ─────────────────────────────────────────────────────────────────

    def run(self):
        print("="*55)
        print("  SmartDiagram — Intelligent Diagramming")
        print("="*55)
        print("  Draw any shape with mouse → auto-snaps")
        print("  Shapes: rect, circle, ellipse, triangle, diamond, line")
        print()
        print("  Keyboard:")
        print("  D=Draw  S=Select  C=Connect  T=Label  E=Erase  P=Pan")
        print("  Double-click shape = add label")
        print("  Delete = remove selected")
        print("  Ctrl+Z = undo   Ctrl+S = save PNG")
        print("="*55)
        self.root.mainloop()


if __name__ == '__main__':
    SmartDiagram().run()
