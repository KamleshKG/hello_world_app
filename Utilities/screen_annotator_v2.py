"""
ScreenAnnotator v2 — Screenshot Canvas
========================================
Draw on any app without touching it.

DRAW  → screenshot your screen → draw on top
SAVE  → save annotated PNG
HIDE  → hide canvas, toolbar stays

Tools: 1=Pen 2=Arrow 3=Highlight 4=Circle 5=Text 6=Eraser 7=Blur
Keys:  R/G/B/Y/O/P = colours  W=whiteboard  K=blackboard
       Ctrl+scroll = pen size  Ctrl+T = timer  Ctrl+Z = undo
       D = clear  Ctrl+S = save  Space = hide/show  F12 = quit

Shapes panel: click shape → drag on canvas to place it
Templates:    click template → stamps full diagram

pip install Pillow
"""

import tkinter as tk
from tkinter import colorchooser, filedialog, simpledialog
import os, signal, math, statistics, platform

signal.signal(signal.SIGINT, lambda s, f: os._exit(0))

try:
    from PIL import ImageGrab, Image, ImageTk, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Constants ──────────────────────────────────────────────────────────────────
TB_BG  = "#12122A"
ACCENT = "#00FF88"

PALETTE = [
    "#FF3B30","#FF6B6B","#FF9500","#FF6000",
    "#FFCC00","#FFE066","#34C759","#00C853",
    "#007AFF","#0055FF","#00C7BE","#00E5FF",
    "#5856D6","#9B59B6","#FF2D55","#FF69B4",
    "#FFFFFF","#CCCCCC","#888888","#333333",
    "#00FF88","#ADFF2F","#FF00FF","#FF4500",
]

COL_KEYS = {
    "r":"#FF3B30","g":"#34C759","b":"#007AFF",
    "y":"#FFCC00","o":"#FF9500","p":"#FF2D55",
}

TOOLS = [
    ("1","Pen",      "pen"),
    ("2","Arrow",    "arrow"),
    ("3","Hi-lite",  "highlight"),
    ("4","Circle",   "oval"),
    ("5","Text",     "text"),
    ("6","Eraser",   "eraser"),
    ("7","Blur",     "blur"),
]

# ── Shape catalogue ────────────────────────────────────────────────────────────
SHAPE_CATS = [
    ("Basic", [
        ("Rect",       "rect"),
        ("Square",     "square"),
        ("Circle",     "circle"),
        ("Ellipse",    "ellipse"),
        ("Triangle",   "triangle"),
        ("Diamond",    "diamond"),
        ("Line",       "line"),
        ("Arrow",      "arrow_s"),
        ("Dbl Arrow",  "dbl_arrow"),
        ("Cross",      "cross"),
        ("Pentagon",   "pentagon"),
        ("Hexagon",    "hexagon"),
    ]),
    ("Flowchart", [
        ("Process",    "fc_process"),
        ("Decision",   "fc_decision"),
        ("Terminate",  "fc_terminator"),
        ("Document",   "fc_document"),
        ("Data I/O",   "fc_data"),
        ("Connector",  "fc_connector"),
        ("Delay",      "fc_delay"),
        ("Manual Op",  "fc_manual"),
        ("Stored",     "fc_stored"),
    ]),
    ("UML", [
        ("Actor",      "uml_actor"),
        ("Class",      "uml_class"),
        ("Object",     "uml_object"),
        ("Component",  "uml_component"),
        ("Package",    "uml_package"),
        ("Note",       "uml_note"),
        ("UseCase",    "uml_usecase"),
        ("Lifeline",   "uml_lifeline"),
        ("Boundary",   "uml_boundary"),
        ("Control",    "uml_control"),
        ("Entity",     "uml_entity"),
        ("Interface",  "uml_interface"),
    ]),
    ("Network", [
        ("Database",   "net_database"),
        ("Server",     "net_server"),
        ("Cloud",      "net_cloud"),
        ("Router",     "net_router"),
        ("Client",     "net_client"),
        ("Firewall",   "net_firewall"),
        ("Queue",      "net_queue"),
        ("Cache",      "net_cache"),
        ("LB",         "net_lb"),
        ("Container",  "net_container"),
        ("Mobile",     "net_mobile"),
        ("Browser",    "net_browser"),
    ]),
]

# ── Shape renderer ─────────────────────────────────────────────────────────────
def draw_shape(cv, kind, x0, y0, x1, y1, col, sz, fill=""):
    ids = []
    cx, cy = (x0+x1)/2, (y0+y1)/2
    w, h = max(x1-x0, 1), max(y1-y0, 1)
    kw = dict(tags="stroke")

    if kind in ("rect","square","fc_process","uml_object","uml_package","net_client"):
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,width=sz,fill=fill,**kw))
        if kind == "uml_object":
            ids.append(cv.create_line(x0,y0+h*0.3,x1,y0+h*0.3, fill=col,width=1,**kw))

    elif kind in ("circle","ellipse","uml_usecase"):
        ids.append(cv.create_oval(x0,y0,x1,y1, outline=col,width=sz,fill=fill,**kw))

    elif kind == "triangle":
        ids.append(cv.create_polygon(cx,y0, x1,y1, x0,y1,
                                      outline=col,fill=fill,width=sz,**kw))

    elif kind in ("diamond","fc_decision"):
        ids.append(cv.create_polygon(cx,y0, x1,cy, cx,y1, x0,cy,
                                      outline=col,fill=fill,width=sz,**kw))

    elif kind == "line":
        ids.append(cv.create_line(x0,cy, x1,cy, fill=col,width=sz,**kw))

    elif kind == "arrow_s":
        ids.append(cv.create_line(x0,cy, x1,cy, fill=col,width=sz,
                                   arrow=tk.LAST, arrowshape=(14,18,5),**kw))

    elif kind == "dbl_arrow":
        ids.append(cv.create_line(x0,cy, x1,cy, fill=col,width=sz,
                                   arrow=tk.BOTH, arrowshape=(14,18,5),**kw))

    elif kind == "cross":
        ids.append(cv.create_line(cx,y0, cx,y1, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x0,cy, x1,cy, fill=col,width=sz,**kw))

    elif kind == "pentagon":
        pts = []
        for i in range(5):
            a = math.pi/2 + 2*math.pi*i/5
            pts += [cx+w/2*math.cos(a), cy+h/2*math.sin(a)]
        ids.append(cv.create_polygon(*pts, outline=col,fill=fill,width=sz,**kw))

    elif kind == "hexagon":
        pts = []
        for i in range(6):
            a = math.pi/6 + math.pi*i/3
            pts += [cx+w/2*math.cos(a), cy+h/2*math.sin(a)]
        ids.append(cv.create_polygon(*pts, outline=col,fill=fill,width=sz,**kw))

    elif kind == "fc_terminator":
        r = min(h/2, w/4)
        ids.append(cv.create_arc(x0,y0,x0+r*2,y1, start=90,extent=180,
                                  outline=col,fill=fill,width=sz,style="arc",**kw))
        ids.append(cv.create_arc(x1-r*2,y0,x1,y1, start=270,extent=180,
                                  outline=col,fill=fill,width=sz,style="arc",**kw))
        ids.append(cv.create_line(x0+r,y0,x1-r,y0, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x0+r,y1,x1-r,y1, fill=col,width=sz,**kw))

    elif kind == "fc_document":
        ids.append(cv.create_rectangle(x0,y0,x1,y1-8, outline='',fill=fill,**kw))
        wave = []
        for i in range(13):
            t = i/12
            wave += [x0+w*t, y1-8+7*math.sin(t*2*math.pi)]
        ids.append(cv.create_polygon(x0,y0,x1,y0,x1,y1-8,*wave,x0,y0,
                                      outline=col,fill=fill,width=sz,smooth=True,**kw))

    elif kind == "fc_data":
        off = w*0.15
        ids.append(cv.create_polygon(x0+off,y0, x1,y0, x1-off,y1, x0,y1,
                                      outline=col,fill=fill,width=sz,**kw))

    elif kind == "fc_connector":
        r = min(w,h)/2
        ids.append(cv.create_oval(cx-r,cy-r,cx+r,cy+r,
                                   outline=col,fill=fill,width=sz,**kw))

    elif kind == "fc_delay":
        ids.append(cv.create_rectangle(x0,y0,x1-h/2,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_arc(x1-h,y0,x1,y1, start=270,extent=180,
                                  outline=col,fill=fill,width=sz,**kw))

    elif kind == "fc_manual":
        off = w*0.12
        ids.append(cv.create_polygon(x0+off,y0, x1-off,y0, x1,y1, x0,y1,
                                      outline=col,fill=fill,width=sz,**kw))

    elif kind == "fc_stored":
        ids.append(cv.create_rectangle(x0+w*0.1,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x0,y0,x0,y1, fill=col,width=sz,**kw))

    elif kind == "uml_actor":
        hr = w*0.22
        ids.append(cv.create_oval(cx-hr,y0,cx+hr,y0+hr*2, outline=col,fill=fill,width=sz,**kw))
        ny = y0+hr*2; by2 = y0+h*0.65
        ids.append(cv.create_line(cx,ny,cx,by2, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x0+w*0.1,y0+h*0.35,x1-w*0.1,y0+h*0.35, fill=col,width=sz,**kw))
        ids.append(cv.create_line(cx,by2,x0+w*0.1,y1, fill=col,width=sz,**kw))
        ids.append(cv.create_line(cx,by2,x1-w*0.1,y1, fill=col,width=sz,**kw))

    elif kind == "uml_class":
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x0,y0+h*0.28,x1,y0+h*0.28, fill=col,width=1,**kw))
        ids.append(cv.create_line(x0,y0+h*0.60,x1,y0+h*0.60, fill=col,width=1,**kw))
        ids.append(cv.create_text(cx,y0+h*0.14, text="ClassName",
                                   fill=col, font=("Helvetica",max(8,int(h*0.1)),"bold"),**kw))

    elif kind == "uml_component":
        ids.append(cv.create_rectangle(x0+w*0.15,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        tab_w, tab_h = w*0.18, h*0.18
        for ty in [y0+h*0.25, y0+h*0.55]:
            ids.append(cv.create_rectangle(x0,ty,x0+tab_w*1.3,ty+tab_h,
                                            outline=col,fill=fill,width=sz,**kw))

    elif kind == "uml_note":
        fold = min(w,h)*0.2
        ids.append(cv.create_polygon(x0,y0, x1-fold,y0, x1,y0+fold,x1,y1, x0,y1,
                                      outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x1-fold,y0,x1-fold,y0+fold,x1,y0+fold,
                                   fill=col,width=sz,**kw))

    elif kind == "uml_lifeline":
        box_h = h*0.18
        ids.append(cv.create_rectangle(x0,y0,x1,y0+box_h, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(cx,y0+box_h,cx,y1, fill=col,width=max(1,sz-1),dash=(6,4),**kw))

    elif kind == "uml_boundary":
        ids.append(cv.create_oval(x0+w*0.15,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x0,y0+h*0.2,x0,y1-h*0.2, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x0,cy,x0+w*0.15,cy, fill=col,width=sz,**kw))

    elif kind == "uml_control":
        ids.append(cv.create_oval(x0,y0+h*0.1,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(cx,y0+h*0.1,cx,y0, fill=col,width=sz,**kw))
        ids.append(cv.create_line(cx-w*0.1,y0+h*0.08,cx,y0, fill=col,width=sz,**kw))

    elif kind == "uml_entity":
        ids.append(cv.create_oval(x0,y0,x1,y1-h*0.1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x0,y1,x1,y1, fill=col,width=sz,**kw))

    elif kind == "uml_interface":
        ids.append(cv.create_line(cx,y0,cx,y1-min(w,h)*0.35, fill=col,width=sz,**kw))
        r = min(w,h)*0.18
        ids.append(cv.create_oval(cx-r,y1-r*2,cx+r,y1, outline=col,fill=fill,width=sz,**kw))

    elif kind == "net_database":
        ry = max(h*0.15, 8)
        ids.append(cv.create_rectangle(x0,y0+ry,x1,y1, outline='',fill=fill,**kw))
        ids.append(cv.create_line(x0,y0+ry,x0,y1, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x1,y0+ry,x1,y1, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x0,y1,x1,y1, fill=col,width=sz,**kw))
        ids.append(cv.create_oval(x0,y0,x1,y0+ry*2, outline=col,fill=col,width=sz,**kw))
        ids.append(cv.create_oval(x0,y0,x1,y0+ry*2, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_arc(x0,y1-ry*2,x1,y1, start=180,extent=180,outline=col,fill='',width=sz,**kw))

    elif kind == "net_server":
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        for i in range(1,4):
            y = y0+(y1-y0)*i/4
            ids.append(cv.create_line(x0+4,y,x1-4,y, fill=col,width=1,dash=(4,4),**kw))
        ids.append(cv.create_oval(x1-14,y0+5,x1-6,y0+13, fill="#00FF88",outline='',**kw))

    elif kind == "net_cloud":
        blobs = [(0.05,0.35,0.45,0.90),(0.20,0.08,0.62,0.65),
                 (0.45,0.10,0.82,0.62),(0.58,0.32,1.00,0.88),(0.00,0.48,0.42,0.98)]
        for bx0,by0,bx1,by1 in blobs:
            ids.append(cv.create_oval(x0+w*bx0,y0+h*by0,x0+w*bx1,y0+h*by1,
                                       outline=col,fill=fill,width=sz,**kw))

    elif kind == "net_router":
        ids.append(cv.create_oval(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x0+w*0.15,cy,x1-w*0.15,cy, fill=col,width=sz,**kw))
        ids.append(cv.create_line(cx,y0+h*0.15,cx,y1-h*0.15, fill=col,width=sz,**kw))

    elif kind == "net_firewall":
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        bh = h/3
        for row in range(3):
            ry = y0+bh*row
            ids.append(cv.create_line(x0,ry,x1,ry, fill=col,width=1,**kw))
            for bx in [x0+w*0.25, x0+w*0.5, x0+w*0.75]:
                ids.append(cv.create_line(bx,ry,bx,ry+bh, fill=col,width=1,**kw))

    elif kind == "net_queue":
        ry = min(h*0.4, w*0.15)
        ids.append(cv.create_rectangle(x0+ry,y0,x1-ry,y1, outline='',fill=fill,**kw))
        ids.append(cv.create_line(x0+ry,y0,x1-ry,y0, fill=col,width=sz,**kw))
        ids.append(cv.create_line(x0+ry,y1,x1-ry,y1, fill=col,width=sz,**kw))
        ids.append(cv.create_oval(x1-ry*2,y0,x1,y1, outline=col,fill=col,width=sz,**kw))
        ids.append(cv.create_oval(x1-ry*2,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_arc(x0,y0,x0+ry*2,y1, start=90,extent=180,
                                  outline=col,fill=fill,width=sz,**kw))

    elif kind == "net_cache":
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        bx = [cx,cx-w*0.15,cx+w*0.1,cx-w*0.1,cx+w*0.15,cx]
        by = [y0+h*0.1,cy,cy,cy,cy,y1-h*0.1]
        flat = [v for pair in zip(bx,by) for v in pair]
        ids.append(cv.create_line(*flat, fill=col,width=sz,**kw))

    elif kind == "net_lb":
        ids.append(cv.create_oval(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_polygon(x0+w*0.25,y0+h*0.2,x0+w*0.25,y1-h*0.2,x1-w*0.15,cy,
                                      outline=col,fill=col,width=1,**kw))

    elif kind == "net_container":
        tab_h = h*0.18
        ids.append(cv.create_rectangle(x0,y0+tab_h,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_rectangle(x0,y0,x0+w*0.45,y0+tab_h,
                                        outline=col,fill=col,width=1,**kw))

    elif kind == "net_mobile":
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        ids.append(cv.create_line(x0,y0+h*0.12,x1,y0+h*0.12, fill=col,width=1,**kw))
        ids.append(cv.create_line(x0,y1-h*0.1,x1,y1-h*0.1, fill=col,width=1,**kw))
        r = min(w,h)*0.1
        ids.append(cv.create_oval(cx-r,y1-h*0.075,cx+r,y1-h*0.02,
                                   outline=col,fill='',width=1,**kw))

    elif kind == "net_browser":
        ids.append(cv.create_rectangle(x0,y0,x1,y1, outline=col,fill=fill,width=sz,**kw))
        bar_h = h*0.2
        ids.append(cv.create_line(x0,y0+bar_h,x1,y0+bar_h, fill=col,width=1,**kw))
        ids.append(cv.create_rectangle(x0+w*0.2,y0+bar_h*0.2,x1-w*0.05,y0+bar_h*0.8,
                                        outline=col,fill='',width=1,**kw))

    return ids


# ── Templates ──────────────────────────────────────────────────────────────────
# Each shape: (kind, x0f, y0f, x1f, y1f, label)
# Each arrow: (x0f, y0f, x1f, y1f)
# All fractions 0.0–1.0 relative to template bounding box

TEMPLATES = {
    "Client-Server": {
        "desc": "Client → App Server → Database",
        "w": 600, "h": 240,
        "shapes": [
            ("net_client",   0.01,0.25,0.20,0.75, "Client"),
            ("net_server",   0.38,0.20,0.62,0.80, "App Server"),
            ("net_database", 0.78,0.20,0.99,0.80, "Database"),
        ],
        "arrows": [(0.20,0.50,0.38,0.50),(0.62,0.50,0.78,0.50)],
    },
    "3-Tier Web": {
        "desc": "Browser → LB → App → DB",
        "w": 720, "h": 240,
        "shapes": [
            ("net_browser",  0.00,0.25,0.18,0.75, "Browser"),
            ("net_lb",       0.27,0.28,0.44,0.72, "LB"),
            ("net_server",   0.53,0.20,0.72,0.80, "App Server"),
            ("net_database", 0.80,0.20,0.99,0.80, "Database"),
        ],
        "arrows": [(0.18,0.50,0.27,0.50),(0.44,0.50,0.53,0.50),(0.72,0.50,0.80,0.50)],
    },
    "Microservices": {
        "desc": "API Gateway → services → DB",
        "w": 640, "h": 360,
        "shapes": [
            ("net_client",   0.00,0.38,0.16,0.62, "Client"),
            ("net_lb",       0.22,0.38,0.38,0.62, "API GW"),
            ("net_server",   0.50,0.05,0.72,0.30, "Auth Svc"),
            ("net_server",   0.50,0.38,0.72,0.62, "Order Svc"),
            ("net_server",   0.50,0.70,0.72,0.95, "Product Svc"),
            ("net_database", 0.80,0.38,0.99,0.62, "Shared DB"),
        ],
        "arrows": [
            (0.16,0.50,0.22,0.50),
            (0.38,0.50,0.50,0.18),
            (0.38,0.50,0.50,0.50),
            (0.38,0.50,0.50,0.82),
            (0.72,0.50,0.80,0.50),
        ],
    },
    "Event-Driven": {
        "desc": "Producer → Queue → Consumer",
        "w": 580, "h": 220,
        "shapes": [
            ("net_server",  0.01,0.25,0.22,0.75, "Producer"),
            ("net_queue",   0.32,0.30,0.68,0.70, "Msg Queue"),
            ("net_server",  0.78,0.25,0.99,0.75, "Consumer"),
        ],
        "arrows": [(0.22,0.50,0.32,0.50),(0.68,0.50,0.78,0.50)],
    },
    "CI/CD Pipeline": {
        "desc": "Code → Build → Test → Deploy",
        "w": 700, "h": 200,
        "shapes": [
            ("net_browser",   0.00,0.25,0.18,0.75, "Code Repo"),
            ("net_server",    0.25,0.25,0.43,0.75, "Build"),
            ("net_server",    0.50,0.25,0.68,0.75, "Test"),
            ("net_container", 0.75,0.25,0.99,0.75, "Deploy"),
        ],
        "arrows": [(0.18,0.50,0.25,0.50),(0.43,0.50,0.50,0.50),(0.68,0.50,0.75,0.50)],
    },
    "DevOps Pipeline": {
        "desc": "Plan→Code→Build→Test→Release→Monitor",
        "w": 760, "h": 200,
        "shapes": [
            ("fc_process",  0.00,0.25,0.14,0.75, "Plan"),
            ("fc_process",  0.17,0.25,0.31,0.75, "Code"),
            ("net_server",  0.34,0.20,0.49,0.80, "Build"),
            ("fc_decision", 0.52,0.15,0.67,0.85, "Test OK?"),
            ("fc_document", 0.70,0.25,0.84,0.75, "Release"),
            ("net_cache",   0.87,0.25,0.99,0.75, "Monitor"),
        ],
        "arrows": [
            (0.14,0.50,0.17,0.50),(0.31,0.50,0.34,0.50),(0.49,0.50,0.52,0.50),
            (0.67,0.50,0.70,0.50),(0.84,0.50,0.87,0.50),
        ],
    },
    "UML Use Case": {
        "desc": "System boundary + actors + use cases",
        "w": 540, "h": 340,
        "shapes": [
            ("uml_actor",   0.00,0.15,0.14,0.48, "User"),
            ("uml_actor",   0.00,0.55,0.14,0.88, "Admin"),
            ("rect",        0.17,0.02,0.83,0.98, ""),
            ("uml_usecase", 0.24,0.12,0.62,0.32, "Login"),
            ("uml_usecase", 0.24,0.40,0.62,0.60, "View Data"),
            ("uml_usecase", 0.24,0.68,0.62,0.88, "Manage Users"),
            ("uml_actor",   0.84,0.40,0.99,0.73, "Database"),
        ],
        "arrows": [
            (0.14,0.30,0.24,0.22),(0.14,0.35,0.24,0.50),
            (0.07,0.62,0.24,0.78),(0.62,0.50,0.84,0.57),
        ],
    },
    "UML Class": {
        "desc": "3 classes with inheritance",
        "w": 560, "h": 300,
        "shapes": [
            ("uml_class", 0.01,0.10,0.32,0.55, "Person"),
            ("uml_class", 0.36,0.10,0.67,0.55, "Employee"),
            ("uml_class", 0.71,0.10,0.99,0.55, "Department"),
            ("uml_note",  0.01,0.68,0.42,0.98, "extends Person"),
        ],
        "arrows": [(0.32,0.32,0.36,0.32),(0.67,0.32,0.71,0.32)],
    },
    "Sequence Diagram": {
        "desc": "3 lifelines with messages",
        "w": 540, "h": 360,
        "shapes": [
            ("uml_lifeline", 0.05,0.02,0.30,0.98, "Client"),
            ("uml_lifeline", 0.37,0.02,0.63,0.98, "Server"),
            ("uml_lifeline", 0.70,0.02,0.95,0.98, "Database"),
        ],
        "arrows": [
            (0.30,0.22,0.37,0.22),(0.63,0.30,0.70,0.30),
            (0.70,0.42,0.63,0.42),(0.37,0.55,0.30,0.55),
        ],
    },
    "Flowchart": {
        "desc": "Start→Input→Decision→Process→End",
        "w": 260, "h": 480,
        "shapes": [
            ("fc_terminator", 0.10,0.01,0.90,0.12, "Start"),
            ("fc_process",    0.10,0.20,0.90,0.33, "Get Input"),
            ("fc_decision",   0.05,0.42,0.95,0.58, "Valid?"),
            ("fc_process",    0.10,0.67,0.90,0.80, "Process"),
            ("fc_terminator", 0.10,0.88,0.90,0.99, "End"),
        ],
        "arrows": [
            (0.50,0.12,0.50,0.20),(0.50,0.33,0.50,0.42),
            (0.50,0.58,0.50,0.67),(0.50,0.80,0.50,0.88),
        ],
    },
}


def draw_template(cv, key, ox, oy, col, bbox_w=None, bbox_h=None):
    """Stamp a full template at (ox,oy), optionally scaled to bbox_w x bbox_h.
    Returns all canvas ids."""
    tmpl = TEMPLATES.get(key)
    if not tmpl:
        return []
    # Scale to dragged bbox if provided, else use natural size
    W = bbox_w if bbox_w else tmpl["w"]
    H = bbox_h if bbox_h else tmpl["h"]
    all_ids = []
    sz = max(1, min(3, int(min(W,H)/120)))  # line weight scales with size

    for kind, xf0,yf0,xf1,yf1, lbl in tmpl["shapes"]:
        sx0 = ox + xf0*W;  sy0 = oy + yf0*H
        sx1 = ox + xf1*W;  sy1 = oy + yf1*H
        ids = draw_shape(cv, kind, sx0,sy0,sx1,sy1, col, sz, fill="")
        all_ids.extend(ids)
        if lbl:
            cx2 = (sx0+sx1)/2;  cy2 = (sy0+sy1)/2
            fs = max(7, min(13, int((sy1-sy0)*0.22)))
            all_ids.append(cv.create_text(cx2, cy2, text=lbl, fill=col,
                                           font=("Helvetica",fs,"bold"),
                                           justify="center", tags="stroke"))

    for xf0,yf0,xf1,yf1 in tmpl["arrows"]:
        all_ids.append(cv.create_line(
            ox+xf0*W, oy+yf0*H, ox+xf1*W, oy+yf1*H,
            fill=col, width=sz, arrow=tk.LAST, arrowshape=(10,14,4), tags="stroke"))

    return all_ids


# ── Shape recogniser ───────────────────────────────────────────────────────────
def recognise(raw):
    if len(raw) < 6:
        return "freehand"
    pts = raw[::max(1, len(raw)//80)]
    xs = [p[0] for p in pts];  ys = [p[1] for p in pts]
    x0,y0,x1,y1 = min(xs),min(ys),max(xs),max(ys)
    w = max(x1-x0,1);  h = max(y1-y0,1);  asp = w/h
    diag = math.hypot(w,h)
    pl = sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
             for i in range(len(pts)-1))
    if diag < 20:
        return "freehand"
    closed = math.hypot(pts[0][0]-pts[-1][0], pts[0][1]-pts[-1][1]) < diag*0.42
    cr = pl / (math.pi*math.sqrt(w*h) or 1)
    rr = pl / (2*(w+h) or 1)
    cx2,cy2 = (x0+x1)/2, (y0+y1)/2
    radii = [math.hypot(p[0]-cx2, p[1]-cy2) for p in pts]
    mr = statistics.mean(radii)
    vr = statistics.stdev(radii) / (mr or 1)
    if not closed:
        return "line" if math.hypot(pts[0][0]-pts[-1][0],
                                     pts[0][1]-pts[-1][1])/(pl or 1) > 0.80 else "freehand"
    if vr < 0.09 and cr < 1.22:   return "circle"
    if rr < 0.99 and vr < 0.26:   return "ellipse" if (asp<0.72 or asp>1.38) else "circle"
    if vr > 0.24 and rr < 1.05:   return "triangle"
    if rr > 0.88:                  return "square" if 0.80<asp<1.25 else "rect"
    return "freehand"

def bbox(pts):
    xs=[p[0] for p in pts];  ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)


# ── Main app ───────────────────────────────────────────────────────────────────
class ScreenAnnotator:

    def __init__(self):
        if not HAS_PIL:
            print("\n  pip install Pillow\n")
            input("Press Enter to exit...")
            os._exit(1)

        # State
        self.draw_mode      = False
        self.tool           = "pen"
        self.color          = "#FF3B30"
        self.size           = 4
        self.strokes        = []
        self._raw           = []
        self._cur_id        = None
        self._x0 = self._y0 = 0
        self._txt_entry     = None
        self._txt_win       = None
        self._screenshot    = None
        self._bg_photo      = None
        self._whiteboard_col= None
        self._timer_id      = None
        self._timer_job     = None
        self._timer_secs    = 0
        self._smart         = False
        self._pending_shape = None
        self._pending_template = None

        self.root = tk.Tk()
        self.root.title("ScreenAnnotator v2")
        self.root.withdraw()
        self.root.update()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.sw, self.sh = sw, sh

        self._make_canvas(sw, sh)
        self._make_toolbar(sw)
        self._bind()
        self._poll()
        print("Ready — press DRAW to begin")

    # ── Canvas window ─────────────────────────────────────────────────────────

    def _make_canvas(self, sw, sh):
        cw = tk.Toplevel(self.root)
        cw.overrideredirect(True)
        cw.geometry(f"{sw}x{sh}+0+0")
        cw.attributes("-topmost", True)
        cw.withdraw()
        self.canvas_win = cw

        self.cv = tk.Canvas(cw, bg="#0A0A14", highlightthickness=0, cursor="crosshair")
        self.cv.pack(fill="both", expand=True)

        self.cv.bind("<ButtonPress-1>",   self._press)
        self.cv.bind("<B1-Motion>",       self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<Control-MouseWheel>", self._scroll_sz)
        self.cv.bind("<Control-Button-4>",   lambda e: self._adj_sz(1))
        self.cv.bind("<Control-Button-5>",   lambda e: self._adj_sz(-1))

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _make_toolbar(self, sw):
        tb = tk.Toplevel(self.root)
        tb.overrideredirect(True)
        tb.attributes("-topmost", True)
        tb.config(bg=TB_BG)
        self._tb = tb

        W, H = min(sw-10, 1160), 58
        tb.geometry(f"{W}x{H}+{(sw-W)//2}+3")
        tb.bind("<ButtonPress-1>",
                lambda e: (setattr(self,"_tbx",e.x), setattr(self,"_tby",e.y)))
        tb.bind("<B1-Motion>", lambda e: tb.geometry(
            f"+{max(0,tb.winfo_x()+e.x-self._tbx)}"
            f"+{max(0,tb.winfo_y()+e.y-self._tby)}"))

        row = tk.Frame(tb, bg=TB_BG)
        row.pack(fill="both", expand=True, padx=4, pady=3)

        def B(txt, cmd, bg="#252545", fg="#FFF", w=None):
            b = tk.Button(row, text=txt, command=cmd, bg=bg, fg=fg,
                          relief="flat", font=("Helvetica",10,"bold"),
                          cursor="hand2", padx=4, pady=5,
                          activebackground="#444", activeforeground=fg)
            if w:
                b.config(width=w)
            return b

        def sep():
            tk.Frame(row, bg="#2A2A4A", width=1).pack(
                side="left", fill="y", pady=4, padx=2)

        # Exit
        B("EXIT", self._quit, "#FF3B30","#FFF",5).pack(side="left", padx=(2,3))
        sep()

        # DRAW / SAVE / HIDE
        self.tog_draw = B("DRAW", self._draw_fresh, ACCENT, "#000", 7)
        self.tog_draw.pack(side="left", padx=(2,1))
        B("SAVE", self._save, "#34C759", "#000", 6).pack(side="left", padx=1)
        self.tog_hide = B("HIDE", self._hide_canvas, "#FF3B30","#FFF",6)
        self.tog_hide.pack(side="left", padx=(1,2))
        sep()

        # Drawing tools
        self._tbtns = {}
        for key, label, tool in TOOLS:
            b = B(f"[{key}]{label}", lambda t=tool: self._set_tool(t), w=9)
            b.pack(side="left", padx=1)
            self._tbtns[tool] = b

        # Smart + panels
        self.smart_btn = B("Smart:OFF", self._toggle_smart, "#1A2A1A","#0F0",9)
        self.smart_btn.pack(side="left", padx=1)
        self.shapes_btn = B("Shapes", self._toggle_shape_panel, "#252545","#FFD700",7)
        self.shapes_btn.pack(side="left", padx=1)
        self.tmpl_btn = B("Templates", self._toggle_tmpl_panel, "#252545","#FFB347",9)
        self.tmpl_btn.pack(side="left", padx=1)
        sep()

        # Whiteboard
        B("W", self._wb_white, "#EEE","#000",3).pack(side="left", padx=1)
        B("K", self._wb_black, "#111","#FFF",3).pack(side="left", padx=1)
        sep()

        # Colours (first 16)
        for c in PALETTE[:16]:
            tk.Button(row, bg=c, width=2, relief="flat", cursor="hand2",
                      command=lambda x=c: self._set_color(x)).pack(
                          side="left", padx=1, pady=8)
        B("+", self._pick_color, w=2).pack(side="left", padx=2)
        sep()

        # Size
        tk.Label(row, text="sz", bg=TB_BG, fg="#555",
                 font=("Helvetica",9)).pack(side="left")
        self._szv = tk.IntVar(value=4)
        tk.Scale(row, from_=1, to=30, orient="horizontal", variable=self._szv,
                 length=70, bg=TB_BG, fg="#FFF", troughcolor="#333",
                 highlightthickness=0, showvalue=False,
                 command=lambda v: (setattr(self,"size",int(v)),
                                    self._sz_lbl.config(text=str(int(v))))).pack(side="left")
        self._sz_lbl = tk.Label(row, text="4", bg=TB_BG, fg="#AAA",
                                 font=("Helvetica",9), width=2)
        self._sz_lbl.pack(side="left")
        sep()

        # Actions
        B("Undo",  self._undo,           w=5).pack(side="left", padx=1)
        B("Clear", self._clear,          w=5).pack(side="left", padx=1)
        B("Timer", self._timer_dialog, "#223","#FFF",5).pack(side="left", padx=1)
        B("Move",  self._toggle_tb_pos, "#334455","#AAF",5).pack(side="left", padx=1)

        # Right side
        self._cdot = tk.Label(row, text="●", fg=self.color, bg=TB_BG,
                               font=("Helvetica",18))
        self._cdot.pack(side="right", padx=4)
        self._stat = tk.Label(row, text="  Click DRAW to begin",
                               fg=ACCENT, bg=TB_BG, font=("Courier",9,"bold"))
        self._stat.pack(side="right", padx=6)

        self._hl_tool()
        self._update_tog()

    # ── Screenshot ────────────────────────────────────────────────────────────

    def _draw_fresh(self):
        self.draw_mode = True
        self.canvas_win.withdraw()
        self._tb.withdraw()
        self.root.update()
        self.root.after(150, self._do_screenshot)

    def _do_screenshot(self):
        try:
            img = ImageGrab.grab(bbox=None, all_screens=True)
            self._screenshot = img
            img_r = img.resize((self.sw, self.sh), Image.LANCZOS)
            self._bg_photo = ImageTk.PhotoImage(img_r)
            self.cv.delete("bg_img")
            self.cv.create_image(0,0,anchor="nw",image=self._bg_photo,tags="bg_img")
            self.cv.tag_lower("bg_img")
            self.cv.tag_raise("stroke")
            self._whiteboard_col = None
        except Exception as ex:
            print(f"Screenshot: {ex}")
            self.cv.delete("bg_img")
            self.cv.create_rectangle(0,0,self.sw,self.sh,fill="#1A1A2E",outline="",tags="bg_img")

        self.canvas_win.deiconify()
        self.canvas_win.attributes("-topmost", True)
        self._tb.deiconify()
        self._tb.lift()
        self._tb.attributes("-topmost", True)
        self._update_tog()

    def _hide_canvas(self):
        self.draw_mode = False
        self._cancel_timer()
        if self._txt_entry:
            self._cancel_text()
        self.canvas_win.withdraw()
        self._update_tog()

    def _show_canvas(self):
        if not self._screenshot and not self._whiteboard_col:
            self._draw_fresh()
            return
        self.draw_mode = True
        self.canvas_win.deiconify()
        self.canvas_win.attributes("-topmost", True)
        self._tb.lift()
        self._tb.attributes("-topmost", True)
        self._update_tog()

    def _toggle_mode(self):
        if self.draw_mode:
            self._hide_canvas()
        else:
            self._show_canvas()

    def _update_tog(self):
        if self.draw_mode:
            self.tog_draw.config(state="disabled", bg="#333", fg="#666")
            self.tog_hide.config(state="normal",   bg="#FF3B30", fg="#FFF")
            self._stat.config(text=f"  {self.tool.upper()}  |  toolbar always active")
        else:
            self.tog_draw.config(state="normal",  bg=ACCENT, fg="#000")
            self.tog_hide.config(state="disabled", bg="#333",  fg="#666")
            self._stat.config(text="  Click DRAW — screenshots current screen")

    # ── Whiteboard ────────────────────────────────────────────────────────────

    def _wb_white(self):  self._set_wb("#FFFFFF")
    def _wb_black(self):  self._set_wb("#111111")

    def _set_wb(self, col):
        self._whiteboard_col = col
        self.draw_mode = True
        self.canvas_win.deiconify()
        self.canvas_win.attributes("-topmost", True)
        self._tb.deiconify()
        self._tb.lift()
        self._tb.attributes("-topmost", True)
        self.cv.delete("bg_img")
        self.cv.create_rectangle(0,0,self.sw,self.sh, fill=col, outline="", tags="bg_img")
        self.cv.tag_lower("bg_img")
        self._update_tog()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _press(self, e):
        self._x0, self._y0 = e.x, e.y
        self._raw = [(e.x, e.y)]
        self._cur_id = None
        col = self.color;  sz = self.size

        if self.tool == "template" and self._pending_template:
            # Show dashed preview rect while dragging — same mechanic as shape
            self._cur_id = self.cv.create_rectangle(
                e.x,e.y,e.x+1,e.y+1, outline=self.color, width=2,
                dash=(6,3), fill="", tags="stroke")
            return

        elif self.tool == "shape":
            self._cur_id = self.cv.create_rectangle(
                e.x,e.y,e.x+1,e.y+1, outline=col, width=2, dash=(5,3),
                fill="", tags="stroke")

        elif self.tool == "pen":
            self._cur_id = self.cv.create_line(
                e.x,e.y,e.x+1,e.y+1, fill=col, width=sz,
                capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="stroke")
            self.strokes.append([self._cur_id])

        elif self.tool == "highlight":
            self._cur_id = self.cv.create_line(
                e.x,e.y,e.x+1,e.y+1, fill=col, width=max(sz,20),
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
                stipple="gray50", tags="stroke")
            self.strokes.append([self._cur_id])

        elif self.tool == "eraser":
            self._erase_at(e.x, e.y)

        elif self.tool == "text":
            self._begin_text(e.x, e.y)

    def _drag(self, e):
        self._raw.append((e.x, e.y))
        col = self.color;  sz = self.size

        if self.tool in ("shape","template") and self._cur_id:
            self.cv.coords(self._cur_id, self._x0,self._y0, e.x,e.y)

        elif self.tool in ("pen","highlight") and self._cur_id:
            flat = [c for p in self._raw for c in p]
            self.cv.coords(self._cur_id, *flat)

        elif self.tool == "eraser":
            self._erase_at(e.x, e.y)

        elif self.tool == "arrow":
            if self._cur_id:
                self.cv.delete(self._cur_id)
            self._cur_id = self.cv.create_line(
                self._x0,self._y0,e.x,e.y, fill=col, width=max(sz,2),
                arrow=tk.LAST, arrowshape=(16+sz*2,20+sz*2,6+sz),
                capstyle=tk.ROUND, tags="stroke")

        elif self.tool == "oval":
            if self._cur_id:
                self.cv.delete(self._cur_id)
            self._cur_id = self.cv.create_oval(
                self._x0,self._y0,e.x,e.y, outline=col, width=max(sz,2),
                fill="", tags="stroke")

        elif self.tool == "blur":
            if self._cur_id:
                self.cv.delete(self._cur_id)
            self._cur_id = self.cv.create_rectangle(
                self._x0,self._y0,e.x,e.y, outline="#FF3B30", width=2,
                dash=(6,4), fill="", tags="stroke")

    def _release(self, e):
        if self.tool == "template" and self._cur_id and self._pending_template:
            self.cv.delete(self._cur_id)
            self._cur_id = None
            x0 = min(self._x0,e.x);  y0 = min(self._y0,e.y)
            x1 = max(self._x0,e.x);  y1 = max(self._y0,e.y)
            if abs(x1-x0) > 20 and abs(y1-y0) > 20:
                # Template origin = top-left of drag rect
                ids = draw_template(self.cv, self._pending_template,
                                     x0, y0, self.color, bbox_w=x1-x0, bbox_h=y1-y0)
                if ids:
                    self.strokes.append(ids)
                self._stat.config(
                    text=f"  {self._pending_template} placed — drag again for another")

        elif self.tool == "shape" and self._cur_id and self._pending_shape:
            self.cv.delete(self._cur_id)
            self._cur_id = None
            x0,y0,x1,y1 = self._x0,self._y0,e.x,e.y
            if abs(x1-x0) > 8 and abs(y1-y0) > 8:
                ids = draw_shape(self.cv, self._pending_shape,
                                  min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1),
                                  self.color, max(self.size,2), fill="")
                if ids:
                    self.strokes.append(ids)
                    self._stat.config(
                        text=f"  {self._pending_shape} placed — drag again for another")

        elif self.tool in ("arrow","oval") and self._cur_id:
            self.strokes.append([self._cur_id])
            self._cur_id = None

        elif self.tool == "blur":
            if self._cur_id:
                self.cv.delete(self._cur_id)
                self._cur_id = None
            self._apply_blur(self._x0,self._y0,e.x,e.y)

        elif self.tool == "pen" and self._smart and len(self._raw) > 5:
            shape = recognise(self._raw)
            if shape != "freehand":
                if self.strokes:
                    for iid in self.strokes[-1]:
                        self.cv.delete(iid)
                    self.strokes.pop()
                self._draw_snapped(shape)

        elif self.tool in ("pen","highlight"):
            self._cur_id = None

        self._raw = []

    def _draw_snapped(self, shape):
        raw = self._raw
        x0,y0,x1,y1 = bbox(raw)
        col = self.color;  sz = max(self.size, 2)
        cx,cy = (x0+x1)/2, (y0+y1)/2
        ids = []

        if shape in ("rect","square"):
            ids.append(self.cv.create_rectangle(x0,y0,x1,y1,
                outline=col,width=sz,fill="",tags="stroke"))
        elif shape in ("circle","ellipse"):
            ids.append(self.cv.create_oval(x0,y0,x1,y1,
                outline=col,width=sz,fill="",tags="stroke"))
        elif shape == "triangle":
            ids.append(self.cv.create_polygon(cx,y0,x1,y1,x0,y1,
                outline=col,fill="",width=sz,tags="stroke"))
        elif shape == "line":
            ids.append(self.cv.create_line(
                raw[0][0],raw[0][1],raw[-1][0],raw[-1][1],
                fill=col,width=sz,capstyle=tk.ROUND,tags="stroke"))

        if ids:
            self.strokes.append(ids)
            lbl = self.cv.create_text((x0+x1)//2,y0-14, text=f"✓ {shape}",
                fill="#00FF88", font=("Helvetica",11,"bold"),
                anchor="s", tags="stroke")
            self.root.after(900, lambda: self.cv.delete(lbl))

    # ── Blur ──────────────────────────────────────────────────────────────────

    def _apply_blur(self, x0, y0, x1, y1):
        if not self._screenshot:
            return
        rx0,rx1 = min(x0,x1),max(x0,x1)
        ry0,ry1 = min(y0,y1),max(y0,y1)
        if rx1-rx0 < 4 or ry1-ry0 < 4:
            return
        try:
            rw = self._screenshot.width  / self.sw
            rh = self._screenshot.height / self.sh
            box = (int(rx0*rw),int(ry0*rh),int(rx1*rw),int(ry1*rh))
            region = self._screenshot.crop(box)
            small = region.resize((max(1,(box[2]-box[0])//8),
                                   max(1,(box[3]-box[1])//8)), Image.NEAREST)
            blurred = small.resize(region.size, Image.NEAREST).filter(
                ImageFilter.GaussianBlur(6))
            self._screenshot.paste(blurred, box)
            img_r = self._screenshot.resize((self.sw,self.sh), Image.LANCZOS)
            self._bg_photo = ImageTk.PhotoImage(img_r)
            self.cv.delete("bg_img")
            self.cv.create_image(0,0,anchor="nw",image=self._bg_photo,tags="bg_img")
            self.cv.tag_lower("bg_img")
            self.cv.tag_raise("stroke")
            self.strokes.append(["__blur__"])
        except Exception as ex:
            print(f"Blur: {ex}")

    # ── Eraser ────────────────────────────────────────────────────────────────

    def _erase_at(self, x, y):
        r = max(self.size*7, 28)
        for iid in self.cv.find_overlapping(x-r,y-r,x+r,y+r):
            if "bg_img" in self.cv.gettags(iid):
                continue
            self.cv.delete(iid)
            self.strokes = [s for s in self.strokes if iid not in s]

    # ── Text ──────────────────────────────────────────────────────────────────

    def _begin_text(self, x, y):
        if self._txt_entry:
            self._commit_text()
        fs = max(self.size*3, 14)
        entry = tk.Entry(self.cv, font=("Helvetica",fs,"bold"),
                         fg=self.color, bg="#0A0A20",
                         insertbackground=self.color,
                         relief="flat", bd=2, width=26)
        self._txt_win = self.cv.create_window(x,y,window=entry,anchor="nw",tags="stroke")
        self._txt_entry = entry
        self._txt_x, self._txt_y, self._txt_fs = x, y, fs
        entry.focus_set()
        entry.bind("<Return>",   lambda _: self._commit_text())
        entry.bind("<KP_Enter>", lambda _: self._commit_text())
        entry.bind("<Escape>",   lambda _: self._cancel_text())

    def _commit_text(self):
        if not self._txt_entry:
            return
        txt = self._txt_entry.get().strip()
        self.cv.delete(self._txt_win)
        self._txt_entry.destroy()
        self._txt_entry = None;  self._txt_win = None
        if txt:
            iid = self.cv.create_text(self._txt_x,self._txt_y, text=txt,
                fill=self.color, anchor="nw",
                font=("Helvetica",self._txt_fs,"bold"), tags="stroke")
            self.strokes.append([iid])

    def _cancel_text(self):
        if self._txt_win:   self.cv.delete(self._txt_win)
        if self._txt_entry: self._txt_entry.destroy()
        self._txt_entry = None;  self._txt_win = None

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _timer_dialog(self):
        secs = simpledialog.askinteger(
            "Break Timer", "Seconds (e.g. 300 = 5 min):",
            minvalue=5, maxvalue=3600, initialvalue=300, parent=self._tb)
        if secs:
            self._start_timer(secs)

    def _start_timer(self, secs):
        self._cancel_timer()
        if not self.draw_mode:
            self._wb_black()
        self._timer_secs = secs
        self._tick_timer()

    def _tick_timer(self):
        if self._timer_id:
            self.cv.delete(self._timer_id)
        m,s = divmod(self._timer_secs, 60)
        col = "#00FF88" if self._timer_secs>60 else "#FFCC00" if self._timer_secs>10 else "#FF3B30"
        self._timer_id = self.cv.create_text(
            self.sw//2, self.sh//2, text=f"{m:02d}:{s:02d}", fill=col,
            font=("Helvetica",int(self.sh*0.18),"bold"), anchor="center", tags="stroke")
        if self._timer_secs > 0:
            self._timer_secs -= 1
            self._timer_job = self.root.after(1000, self._tick_timer)
        else:
            self.cv.itemconfig(self._timer_id, text="Time!", fill="#FF3B30")

    def _cancel_timer(self):
        if self._timer_job: self.root.after_cancel(self._timer_job); self._timer_job=None
        if self._timer_id:  self.cv.delete(self._timer_id);          self._timer_id=None

    # ── Undo / Clear / Save ───────────────────────────────────────────────────

    def _undo(self):
        if not self.strokes:
            return
        g = self.strokes.pop()
        if g == ["__blur__"]:
            self._stat.config(text="  Blur undo: retaking screenshot...")
            self._draw_fresh()
        else:
            for iid in g:
                self.cv.delete(iid)

    def _clear(self):
        for s in self.strokes:
            for iid in s:
                if iid != "__blur__":
                    self.cv.delete(iid)
        self.strokes.clear()
        self._cancel_timer()

    def _save(self):
        if not self.draw_mode:
            self._stat.config(text="  Click DRAW first, then SAVE")
            return

        # Grab canvas FIRST before moving windows
        try:
            self.root.update()
            x = self.canvas_win.winfo_rootx()
            y = self.canvas_win.winfo_rooty()
            w = self.canvas_win.winfo_width()
            h = self.canvas_win.winfo_height()
            captured = ImageGrab.grab(bbox=(x,y,x+w,y+h))
        except Exception as ex:
            self._stat.config(text=f"  Capture failed: {ex}")
            return

        # Lower canvas so dialog appears on top
        self.canvas_win.attributes("-topmost", False)
        self.canvas_win.lower()
        self._tb.lift()
        self._tb.attributes("-topmost", True)
        self.root.update()

        path = filedialog.asksaveasfilename(
            parent=self._tb,
            defaultextension=".png",
            filetypes=[("PNG image","*.png"),("All files","*.*")],
            title="Save annotated screenshot")

        # Restore canvas
        self.canvas_win.attributes("-topmost", True)
        self.canvas_win.lift()
        self._tb.lift()
        self._tb.attributes("-topmost", True)
        self.root.update()

        if path:
            try:
                captured.save(path)
                self._stat.config(text=f"  Saved: {os.path.basename(path)}")
                print(f"Saved: {path}")
            except Exception as ex:
                self._stat.config(text=f"  Save failed: {ex}")
        else:
            self._stat.config(text=f"  {self.tool.upper()}  |  toolbar active")

    # ── Tools / colour / size ─────────────────────────────────────────────────

    def _set_tool(self, t):
        self._pending_shape = None
        self._pending_template = None
        self.tool = t
        self._hl_tool()
        cursors = {"text":"xterm","eraser":"dotbox","blur":"sizing"}
        self.cv.config(cursor=cursors.get(t,"crosshair"))
        self._stat.config(text=f"  {t.upper()}  |  toolbar active")
        if self._txt_entry:
            self._commit_text()

    def _hl_tool(self):
        for n,b in self._tbtns.items():
            b.config(bg="#007AFF" if n==self.tool else "#252545")

    def _set_color(self, c):
        self.color = c
        self._cdot.config(fg=c if c != "#FFFFFF" else "#CCCCCC")

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.color, title="Colour")[1]
        if c:
            self._set_color(c)

    def _adj_sz(self, delta):
        new = max(1, min(30, self.size+delta))
        self.size = new
        self._szv.set(new)
        self._sz_lbl.config(text=str(new))

    def _scroll_sz(self, e):
        self._adj_sz(1 if e.delta > 0 else -1)

    def _toggle_smart(self):
        self._smart = not self._smart
        if self._smart:
            self.smart_btn.config(text="Smart:ON",  bg="#0A3A0A", fg="#00FF88")
        else:
            self.smart_btn.config(text="Smart:OFF", bg="#1A2A1A", fg="#0F0")

    # ── Shape palette panel ───────────────────────────────────────────────────

    def _toggle_shape_panel(self):
        if hasattr(self,"_shape_panel") and self._shape_panel.winfo_exists():
            self._shape_panel.destroy()
            self.shapes_btn.config(bg="#252545", fg="#FFD700")
            return
        self.shapes_btn.config(bg="#007AFF", fg="#FFF")
        self._build_shape_panel()

    def _build_shape_panel(self):
        sw, sh = self.sw, self.sh
        tb_y = self._tb.winfo_y()
        tb_h = self._tb.winfo_height() or 58
        panel_y = tb_y + tb_h + 4
        panel_w = 540

        panel = tk.Toplevel(self.root)
        panel.overrideredirect(True)
        panel.attributes("-topmost", True)
        panel.config(bg="#0E0E24")
        panel.geometry(f"{panel_w}x10+{(sw-panel_w)//2}+{panel_y}")
        self._shape_panel = panel

        panel.bind("<ButtonPress-1>",
                   lambda e: (setattr(self,"_spx",e.x), setattr(self,"_spy",e.y)))
        panel.bind("<B1-Motion>", lambda e: panel.geometry(
            f"+{max(0,panel.winfo_x()+e.x-self._spx)}"
            f"+{max(0,panel.winfo_y()+e.y-self._spy)}"))

        BTN_W=90;  BTN_H=34;  PAD=6;  MAX_COLS=5
        CAT_COL="#00FF88"

        def make_btn(parent, label, kind, x, y):
            f = tk.Frame(parent, bg="#1A1A38",
                         highlightbackground="#2A2A4A", highlightthickness=1,
                         width=BTN_W, height=BTN_H, cursor="hand2")
            f.place(x=x, y=y)
            f.pack_propagate(False)

            c = tk.Canvas(f, bg="#1A1A38", highlightthickness=0, width=BTN_W, height=BTN_H)
            c.pack(fill="both", expand=True)

            try:
                draw_shape(c, kind, 5,4,int(BTN_W*0.42),BTN_H-14, "#007AFF",1,"#0A1A2A")
            except Exception:
                c.create_rectangle(5,4,int(BTN_W*0.42),BTN_H-14,outline="#007AFF",fill="#0A1A2A",width=1)

            c.create_text(BTN_W//2+6, BTN_H-7, text=label,
                          fill="#CCCCDD", font=("Helvetica",7,"bold"), anchor="center")

            def on_click(_=None):
                self._select_shape(kind)

            def on_enter(_=None):
                f.config(highlightbackground="#007AFF");  c.config(bg="#1A2A4A")

            def on_leave(_=None):
                f.config(highlightbackground="#2A2A4A");  c.config(bg="#1A1A38")

            for widget in (f, c):
                widget.bind("<Button-1>", on_click)
                widget.bind("<Enter>",    on_enter)
                widget.bind("<Leave>",    on_leave)

        total_h = 8
        for cat_name, shapes in SHAPE_CATS:
            lbl = tk.Label(panel, text=f"  {cat_name}", bg="#0E0E24", fg=CAT_COL,
                           font=("Helvetica",9,"bold"), anchor="w")
            lbl.place(x=0, y=total_h, width=panel_w, height=18)
            total_h += 20

            col_idx = 0
            for label, kind in shapes:
                bx = PAD + col_idx*(BTN_W+PAD)
                make_btn(panel, label, kind, bx, total_h)
                col_idx += 1
                if col_idx >= MAX_COLS:
                    col_idx = 0
                    total_h += BTN_H + PAD

            if col_idx > 0:
                total_h += BTN_H + PAD
            total_h += 4

        total_h += 8
        panel.geometry(f"{panel_w}x{min(total_h,sh-panel_y-40)}+{(sw-panel_w)//2}+{panel_y}")

        tk.Button(panel, text="✕", command=self._toggle_shape_panel,
                  bg="#FF3B30", fg="#FFF", relief="flat",
                  font=("Helvetica",9,"bold"), cursor="hand2",
                  width=3).place(x=panel_w-30, y=2, width=26, height=18)

    def _select_shape(self, kind):
        self._pending_shape = kind
        self.tool = "shape"
        self._hl_tool()
        self.cv.config(cursor="crosshair")
        if self.draw_mode:
            self._stat.config(text=f"  {kind} — DRAG on canvas to place")
        else:
            self._stat.config(text=f"  {kind} ready — press DRAW first, then drag")

    # ── Templates panel ───────────────────────────────────────────────────────

    def _toggle_tmpl_panel(self):
        if hasattr(self,"_tmpl_panel") and self._tmpl_panel.winfo_exists():
            self._tmpl_panel.destroy()
            self.tmpl_btn.config(bg="#252545", fg="#FFB347")
            return
        self.tmpl_btn.config(bg="#FF8C00", fg="#FFF")
        self._build_tmpl_panel()

    def _build_tmpl_panel(self):
        sw, sh = self.sw, self.sh
        tb_y = self._tb.winfo_y()
        tb_h = self._tb.winfo_height() or 58
        panel_y = tb_y + tb_h + 4
        panel_w = 620

        panel = tk.Toplevel(self.root)
        panel.overrideredirect(True)
        panel.attributes("-topmost", True)
        panel.config(bg="#0E0E24")
        panel.geometry(f"{panel_w}x400+{(sw-panel_w)//2}+{panel_y}")
        self._tmpl_panel = panel

        panel.bind("<ButtonPress-1>",
                   lambda e: (setattr(self,"_tpx",e.x), setattr(self,"_tpy",e.y)))
        panel.bind("<B1-Motion>", lambda e: panel.geometry(
            f"+{max(0,panel.winfo_x()+e.x-self._tpx)}"
            f"+{max(0,panel.winfo_y()+e.y-self._tpy)}"))

        hdr = tk.Frame(panel, bg="#1A1A38", height=28)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  Architecture Templates — click Stamp to place",
                 bg="#1A1A38", fg="#FFB347",
                 font=("Helvetica",9,"bold")).pack(side="left", pady=4)
        tk.Button(hdr, text="✕", command=self._toggle_tmpl_panel,
                  bg="#FF3B30", fg="#FFF", relief="flat",
                  font=("Helvetica",9,"bold"), cursor="hand2",
                  width=3).pack(side="right", padx=4, pady=2)

        cf = tk.Frame(panel, bg="#0E0E24")
        cf.pack(fill="both", expand=True)

        scv = tk.Canvas(cf, bg="#0E0E24", highlightthickness=0)
        sb  = tk.Scrollbar(cf, orient="vertical", command=scv.yview)
        scv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        scv.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(scv, bg="#0E0E24")
        scv.create_window((0,0), window=inner, anchor="nw")

        CARD_W=290;  CARD_H=130;  PAD=8
        cols=2;  col=0;  cur_x=PAD;  cur_y=PAD

        for tkey, tmpl in TEMPLATES.items():
            card = tk.Frame(inner, bg="#1A1A38",
                             highlightbackground="#2A2A5A", highlightthickness=1,
                             width=CARD_W, height=CARD_H, cursor="hand2")
            card.place(x=cur_x, y=cur_y)
            card.pack_propagate(False)

            PW = CARD_W-116;  PH = CARD_H-4
            prev = tk.Canvas(card, bg="#0A0A20", width=PW, height=PH, highlightthickness=0)
            prev.place(x=0, y=0)

            TW = tmpl["w"];  TH = tmpl["h"]
            sc = min((PW-8)/TW, (PH-8)/TH) * 0.85
            ox = (PW-TW*sc)/2;  oy = (PH-TH*sc)/2

            for kind,xf0,yf0,xf1,yf1,lbl in tmpl["shapes"]:
                try:
                    draw_shape(prev, kind,
                                ox+xf0*TW*sc, oy+yf0*TH*sc,
                                ox+xf1*TW*sc, oy+yf1*TH*sc,
                                "#007AFF", 1, "")
                except Exception:
                    pass

            for xf0,yf0,xf1,yf1 in tmpl["arrows"]:
                prev.create_line(ox+xf0*TW*sc,oy+yf0*TH*sc,
                                  ox+xf1*TW*sc,oy+yf1*TH*sc,
                                  fill="#007AFF",width=1,arrow=tk.LAST,arrowshape=(5,7,2))

            info = tk.Frame(card, bg="#1A1A38", width=112)
            info.place(x=CARD_W-112, y=0, width=112, height=CARD_H)

            tk.Label(info, text=tkey, bg="#1A1A38", fg="#FFB347",
                     font=("Helvetica",8,"bold"),
                     wraplength=108, justify="left").pack(anchor="w", padx=4, pady=(6,2))
            tk.Label(info, text=tmpl["desc"], bg="#1A1A38", fg="#666",
                     font=("Helvetica",7),
                     wraplength=108, justify="left").pack(anchor="w", padx=4)

            tk.Button(info, text="Select",
                      command=lambda k=tkey: self._stamp_template(k),
                      bg="#007AFF", fg="#FFF", relief="flat",
                      font=("Helvetica",8,"bold"), cursor="hand2").pack(
                          side="bottom", fill="x", padx=4, pady=4)

            def on_enter(e, c=card): c.config(highlightbackground="#007AFF")
            def on_leave(e, c=card): c.config(highlightbackground="#2A2A5A")

            card.bind("<Enter>", on_enter);  card.bind("<Leave>", on_leave)
            prev.bind("<Button-1>", lambda e, k=tkey: self._stamp_template(k))
            prev.bind("<Enter>", on_enter);  prev.bind("<Leave>", on_leave)

            col += 1
            if col >= cols:
                col = 0;  cur_x = PAD;  cur_y += CARD_H + PAD
            else:
                cur_x += CARD_W + PAD

        if col > 0:
            cur_y += CARD_H + PAD
        total_h = cur_y + PAD

        inner.config(width=panel_w-20, height=total_h)
        scv.config(scrollregion=(0,0,panel_w-20,total_h))
        real_h = min(total_h+32, sh-panel_y-40)
        panel.geometry(f"{panel_w}x{real_h}+{(sw-panel_w)//2}+{panel_y}")

        def _on_scroll(e):
            scv.yview_scroll(int(-1*(e.delta/120)), "units")

        panel.bind("<MouseWheel>", _on_scroll)
        scv.bind("<MouseWheel>", _on_scroll)

    def _stamp_template(self, key):
        """Select template — user then clicks on canvas to place it there."""
        self._pending_template = key
        self._pending_shape = None
        self.tool = "template"
        self._hl_tool()
        self.cv.config(cursor="crosshair")
        tmpl = TEMPLATES.get(key, {})
        w = tmpl.get("w", 600)
        h = tmpl.get("h", 300)
        if self.draw_mode:
            self._stat.config(
                text=f"  {key} selected — DRAG on canvas to place and size it")
        else:
            self._stat.config(
                text=f"  {key} ready — press DRAW first, then drag to place")

    # ── Toolbar position ──────────────────────────────────────────────────────

    def _toggle_tb_pos(self):
        sw = self.sw;  sh = self.sh
        W = self._tb.winfo_width() or min(sw-10, 1160)
        H = self._tb.winfo_height() or 58
        if self._tb.winfo_y() < sh//2:
            self._tb.geometry(f"+{(sw-W)//2}+{sh-H-4}")
        else:
            self._tb.geometry(f"+{(sw-W)//2}+3")

    # ── Key bindings ──────────────────────────────────────────────────────────

    def _bind(self):
        wins = (self.root, self.canvas_win, self._tb)

        def guard(fn):
            def handler(e):
                if self._txt_entry:
                    return
                if isinstance(e.widget.focus_get(), tk.Entry):
                    return
                fn()
            return handler

        for win in wins:
            win.bind("<space>",       guard(self._toggle_mode))
            win.bind("<Escape>",      guard(self._hide_canvas))
            win.bind("<Control-z>",   lambda e: self._undo())
            win.bind("<Delete>",      guard(self._clear))
            win.bind("<Control-s>",   lambda e: self._save())
            win.bind("<F12>",         lambda e: self._quit())
            win.bind("<Control-q>",   lambda e: self._quit())
            win.bind("<Control-t>",   lambda e: self._timer_dialog())
            win.bind("<w>",           guard(self._wb_white))
            win.bind("<k>",           guard(self._wb_black))

            for key, col in COL_KEYS.items():
                win.bind(key, lambda e, c=col: (
                    None if (self._txt_entry or
                             isinstance(e.widget.focus_get(), tk.Entry))
                    else self._set_color(c)))

        tool_map = {"1":"pen","2":"arrow","3":"highlight",
                    "4":"oval","5":"text","6":"eraser","7":"blur"}
        for key, tool in tool_map.items():
            for win in wins:
                win.bind(key, lambda e, t=tool: (
                    None if (self._txt_entry or
                             isinstance(e.widget.focus_get(), tk.Entry))
                    else self._set_tool(t)))

        for win in (self.root, self._tb):
            win.bind("<d>", guard(self._clear))

        self.cv.bind("<Control-MouseWheel>", self._scroll_sz)
        self.cv.bind("<Control-Button-4>",   lambda e: self._adj_sz(1))
        self.cv.bind("<Control-Button-5>",   lambda e: self._adj_sz(-1))

    # ── Quit / poll ───────────────────────────────────────────────────────────

    def _quit(self):
        print("[ScreenAnnotator] Quit.")
        os._exit(0)

    def _poll(self):
        if self.draw_mode and self._tb.winfo_exists():
            try:
                self._tb.lift()
                self._tb.attributes("-topmost", True)
            except Exception:
                pass
        self.root.after(200, self._poll)

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        print("=" * 56)
        print("  ScreenAnnotator v2")
        print("=" * 56)
        print("  DRAW = screenshot → draw on it")
        print("  SAVE = save PNG    HIDE = hide canvas")
        print()
        print("  1=Pen 2=Arrow 3=Highlight 4=Circle 5=Text 6=Erase 7=Blur")
        print("  Shapes = click shape → drag to place on canvas")
        print("  Templates = click Stamp → full diagram appears")
        print("  W=whiteboard  K=blackboard  Smart=shape snap")
        print("  R/G/B/Y/O/P = colour  Ctrl+scroll = size")
        print("  Space=hide/show  Ctrl+Z=undo  D=clear  F12=quit")
        print("=" * 56)
        self.root.mainloop()


if __name__ == "__main__":
    ScreenAnnotator().run()
