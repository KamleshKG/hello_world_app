"""
ScreenAnnotator — Interactive Demo
===================================
Runs on its OWN dark canvas window. No transparency needed.
Shows exactly how the annotation tool works in practice.

Use this to:
  - Understand all the tools before using the real overlay
  - Show your team how the annotation works
  - Practice drawing before a live presentation

Run: python annotator_demo.py
"""

import tkinter as tk
from tkinter import font as tkfont
import math, os, signal

signal.signal(signal.SIGINT, lambda s, f: os._exit(0))

# ── Colours ───────────────────────────────────────────────────────────────────
BG       = "#0F0F1A"       # dark canvas background
TOOLBAR  = "#1A1A2E"
ACCENT   = "#00FF88"
PALETTE  = ["#FF3B30","#FF9500","#FFCC00","#34C759",
            "#00C7BE","#007AFF","#5856D6","#FF2D55","#FFFFFF","#AAAAAA"]

# ── Fake "slide" content drawn on canvas to simulate a real presentation ──────
SLIDE_CONTENT = [
    # (type, args, kwargs)
    ("rect",   [80, 70, 820, 500],  {"outline":"#2A2A4A","width":2,"fill":"#13131F","dash":(6,4)}),
    ("text",   [450, 90],  {"text":"Q3 2024 Performance Review","fill":"#CCCCDD",
                             "font":("Helvetica",18,"bold")}),
    ("text",   [450, 135], {"text":"Revenue  ▲ 40%     EBITDA  ▲ 22%     Customers  ▲ 31%",
                             "fill":"#888899","font":("Helvetica",11)}),
    ("line",   [80,155,820,155],{"fill":"#2A2A4A","width":1}),
    # bar chart
    ("rect",   [130,400,190,220],{"fill":"#007AFF","outline":""}),
    ("rect",   [230,400,290,260],{"fill":"#007AFF","outline":""}),
    ("rect",   [330,400,390,190],{"fill":"#34C759","outline":""}),
    ("rect",   [430,400,490,170],{"fill":"#34C759","outline":""}),
    ("rect",   [530,400,590,220],{"fill":"#FF9500","outline":""}),
    ("rect",   [630,400,690,160],{"fill":"#34C759","outline":""}),
    ("text",   [160,415],{"text":"Q1","fill":"#666","font":("Helvetica",9)}),
    ("text",   [260,415],{"text":"Q2","fill":"#666","font":("Helvetica",9)}),
    ("text",   [360,415],{"text":"Q3","fill":"#00FF88","font":("Helvetica",9,"bold")}),
    ("text",   [460,415],{"text":"Q4","fill":"#00FF88","font":("Helvetica",9,"bold")}),
    ("text",   [560,415],{"text":"Q1'24","fill":"#666","font":("Helvetica",9)}),
    ("text",   [660,415],{"text":"Q2'24","fill":"#00FF88","font":("Helvetica",9,"bold")}),
    ("line",   [110,400,730,400],{"fill":"#333344","width":1}),
    # table
    ("rect",   [120,430,820,490],{"fill":"#13131F","outline":"#2A2A4A","width":1}),
    ("text",   [200,460],{"text":"Region","fill":"#888","font":("Helvetica",10,"bold")}),
    ("text",   [370,460],{"text":"Revenue","fill":"#888","font":("Helvetica",10,"bold")}),
    ("text",   [510,460],{"text":"Growth","fill":"#888","font":("Helvetica",10,"bold")}),
    ("text",   [660,460],{"text":"Customers","fill":"#888","font":("Helvetica",10,"bold")}),
    ("line",   [120,470,820,470],{"fill":"#2A2A4A","width":1}),
    ("text",   [200,482],{"text":"APAC","fill":"#CCC","font":("Helvetica",10)}),
    ("text",   [370,482],{"text":"$4.2M","fill":"#CCC","font":("Helvetica",10)}),
    ("text",   [510,482],{"text":"+47%","fill":"#34C759","font":("Helvetica",10,"bold")}),
    ("text",   [660,482],{"text":"1,840","fill":"#CCC","font":("Helvetica",10)}),
]

DEMO_STEPS = [
    # Each step: (delay_ms, description, draw_fn_name, draw_args)
    # draw_fn_name refers to a method on DemoApp
    ("title",    0,    "Welcome! This is how ScreenAnnotator works.",         None, {}),
    ("title",    2800, "① Highlighter — mark important numbers",              None, {}),
    ("hl",       3200, None, (360,482,550,482), {"color":"#FFCC00","width":20}),
    ("hl",       3200, None, (490,482,535,482), {"color":"#FF9500","width":20}),

    ("title",    6000, "② Arrow — point at the best performing bar",          None, {}),
    ("arrow",    6400, None, (730,200,665,165), {"color":"#FF3B30","width":3}),

    ("title",    9000, "③ Circle — highlight the standout region",            None, {}),
    ("oval",     9400, None, (120,468,340,492), {"color":"#00FF88","width":2}),

    ("title",   12000, "④ Smart rect — draw rough box, snaps to clean shape", None, {}),
    ("rect",    12400, None, (115,145,825,215), {"color":"#007AFF","width":2}),

    ("title",   15000, "⑤ Text label — type anywhere",                        None, {}),
    ("typetext",15400, None, (640,200,"← Best quarter ever! 🚀"),             {"color":"#FFCC00","size":13}),

    ("title",   18500, "⑥ Pen — freehand for quick sketches",                 None, {}),
    ("wave",    18900, None, (130,195,820), {"color":"#FF2D55","width":2}),

    ("title",   21500, "⑦ ESC key → interact with app, ESC again → draw",     None, {}),

    ("title",   24500, "Demo complete!  Try the tools yourself below ↓",      None, {}),
    ("unlock",  25000, None, None, {}),
]

# ─────────────────────────────────────────────────────────────────────────────

class DemoApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ScreenAnnotator — Interactive Demo")
        self.root.config(bg=TOOLBAR)
        self.root.resizable(True, True)

        # Start 900×600, centred
        W, H = 920, 660
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self.color   = "#FF3B30"
        self.size    = 3
        self.tool    = "smart"
        self.strokes = []
        self._raw    = []
        self._cur    = None
        self._x0 = self._y0 = 0
        self._demo_aids = []
        self._demo_on   = False
        self._unlocked  = False

        self._build_ui()
        self._draw_slide()
        self.root.after(100, self._auto_start_demo)

        signal.signal(signal.SIGINT, lambda s,f: os._exit(0))

    # ─── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────
        tb = tk.Frame(self.root, bg=TOOLBAR, height=50)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        def btn(parent, text, cmd, bg="#252545", fg="#FFF", w=6):
            return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                             activebackground="#444", relief="flat",
                             font=("Helvetica",10,"bold"), width=w,
                             cursor="hand2", padx=4, pady=4)

        def sep():
            tk.Frame(tb, bg="#333355", width=1).pack(side="left",fill="y",pady=6,padx=2)

        btn(tb,"✕ EXIT", lambda:os._exit(0), bg="#FF3B30",w=6).pack(side="left",padx=(4,2),pady=4)
        sep()
        self.demo_btn = btn(tb,"▶ DEMO",self._toggle_demo,bg="#FF9500",fg="#000",w=7)
        self.demo_btn.pack(side="left",padx=2,pady=4)
        btn(tb,"🗑 Clear",self._clear_annot,bg="#333355",w=7).pack(side="left",padx=2,pady=4)
        sep()

        # tools
        tools = [("✨ Smart","smart"),("✏ Pen","pen"),("▌ Hi-lite","highlighter"),
                 ("→ Arrow","arrow"),("▭ Rect","rect"),
                 ("⬭ Oval","ellipse"),("T Text","text"),("⌫ Erase","eraser")]
        self._tbtns = {}
        for label,t in tools:
            b=btn(tb,label,lambda x=t:self._set_tool(x),w=7)
            b.pack(side="left",padx=1,pady=4)
            self._tbtns[t]=b
        self._hl_tool()
        sep()

        # colours
        for c in PALETTE:
            tk.Button(tb,bg=c,width=2,relief="flat",cursor="hand2",
                      command=lambda x=c:self._set_color(x)).pack(side="left",padx=1,pady=8)
        sep()

        # size
        tk.Label(tb,text="sz",bg=TOOLBAR,fg="#888",
                 font=("Helvetica",9)).pack(side="left",padx=(2,0))
        self._szv = tk.IntVar(value=3)
        tk.Scale(tb,from_=1,to=20,orient="horizontal",variable=self._szv,
                 length=60,bg=TOOLBAR,fg="#FFF",troughcolor="#333",
                 highlightthickness=0,showvalue=False,
                 command=lambda v:setattr(self,"size",int(v))).pack(side="left")

        # status right
        self._cdot=tk.Label(tb,text="⬤",fg=self.color,bg=TOOLBAR,font=("Helvetica",16))
        self._cdot.pack(side="right",padx=4)
        self._stat=tk.Label(tb,text="✨ SMART",fg=ACCENT,bg=TOOLBAR,
                            font=("Courier",9,"bold"))
        self._stat.pack(side="right",padx=6)

        # ── Info banner ──────────────────────────────────────────────────
        self._banner = tk.Label(self.root,
            text="▶ Demo starting... watch to learn all tools!",
            bg="#1A1A3A", fg="#FFCC00",
            font=("Helvetica",12,"bold"), pady=6)
        self._banner.pack(fill="x", side="top")

        # ── Canvas ───────────────────────────────────────────────────────
        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        self.cv.bind("<ButtonPress-1>",   self._press)
        self.cv.bind("<B1-Motion>",       self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)

        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-q>", lambda e: os._exit(0))
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

        # ── Instruction panel (bottom) ────────────────────────────────────
        info = tk.Frame(self.root, bg="#0D0D1A", height=38)
        info.pack(fill="x", side="bottom")
        info.pack_propagate(False)
        tk.Label(info,
            text="  ✨ Smart = draw any shape freely, snaps automatically  |  "
                 "Text = click once, type, Enter  |  Ctrl+Z = undo  |  Mouse optimised",
            bg="#0D0D1A", fg="#555566",
            font=("Courier",9)).pack(side="left",pady=8)

    def _set_tool(self,t):
        self.tool=t; self._hl_tool()
        self._stat.config(text=f"{t.upper()}")

    def _hl_tool(self):
        for n,b in self._tbtns.items():
            b.config(bg="#007AFF" if n==self.tool else "#252545")

    def _set_color(self,c):
        self.color=c; self._cdot.config(fg=c)

    # ─── Draw fake slide ─────────────────────────────────────────────────

    def _draw_slide(self):
        """Draw simulated presentation slide content on canvas."""
        self._slide_ids = []
        for item in SLIDE_CONTENT:
            kind,args,kw = item
            if kind=="rect":
                iid=self.cv.create_rectangle(*args,**kw)
            elif kind=="text":
                iid=self.cv.create_text(*args,anchor="center",**kw)
            elif kind=="line":
                iid=self.cv.create_line(*args,**kw)
            elif kind=="oval":
                iid=self.cv.create_oval(*args,**kw)
            else:
                continue
            self._slide_ids.append(iid)

    # ─── Demo ────────────────────────────────────────────────────────────

    def _auto_start_demo(self):
        self._start_demo()

    def _toggle_demo(self):
        if self._demo_on: self._stop_demo()
        else: self._start_demo()

    def _start_demo(self):
        self._clear_annot()
        self._demo_on = True
        self._unlocked = False
        self.demo_btn.config(text="⏹ STOP", bg="#FF3B30", fg="#FFF")

        cv = self.cv

        # ── helpers ──────────────────────────────────────────────────────

        def banner(msg, col="#FFCC00"):
            self._banner.config(text=f"  {msg}", fg=col)

        def anim_line(x0,y0,x1,y1,col,wd,ms0,n=22,arrow=False):
            iid=[None]
            for step in range(1,n+1):
                t=step/n
                xc=int(x0+(x1-x0)*t); yc=int(y0+(y1-y0)*t)
                def draw(xc=xc,yc=yc,step=step):
                    if not self._demo_on: return
                    if iid[0]: cv.delete(iid[0])
                    kw=dict(fill=col,width=wd,capstyle="round")
                    if arrow and step==n:
                        kw.update(arrow=tk.LAST,arrowshape=(12+wd*2,16+wd*2,4+wd))
                    iid[0]=cv.create_line(x0,y0,xc,yc,**kw)
                aid=self.root.after(ms0+step*26,draw)
                self._demo_aids.append(aid)

        def anim_hl(x0,y,x1,col,ms0):
            pts=[(x0+i,y) for i in range(0,x1-x0,3)]
            iid=[None]
            for step,p in enumerate(pts,1):
                def draw(flat=[c for pt in pts[:step] for c in pt][:],step=step):
                    if not self._demo_on: return
                    if len(flat)<4: return
                    if iid[0]: cv.delete(iid[0])
                    iid[0]=cv.create_line(*flat,fill=col,width=20,
                                          capstyle="round",stipple="gray50")
                aid=self.root.after(ms0+step*12,draw)
                self._demo_aids.append(aid)

        def anim_oval(x0,y0,x1,y1,col,wd,ms0):
            # draw as animated arc then snap
            iid=[None]; n=36
            for step in range(1,n+1):
                extent=step*(360/n)
                def draw(extent=extent,step=step):
                    if not self._demo_on: return
                    if iid[0]: cv.delete(iid[0])
                    iid[0]=cv.create_arc(x0,y0,x1,y1,start=0,extent=extent,
                                         outline=col,width=wd,style="arc")
                    if step==n:
                        cv.delete(iid[0])
                        iid[0]=cv.create_oval(x0,y0,x1,y1,outline=col,width=wd,fill="")
                        snap=cv.create_text((x0+x1)//2,y0-12,text="✓ snapped!",
                                            fill=ACCENT,font=("Helvetica",10,"bold"))
                        self.root.after(700,lambda:cv.delete(snap))
                aid=self.root.after(ms0+step*22,draw)
                self._demo_aids.append(aid)

        def anim_rect(x0,y0,x1,y1,col,wd,ms0):
            corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
            all_pts=[]
            for i in range(len(corners)-1):
                ax,ay=corners[i]; bx,by=corners[i+1]
                for s in range(10):
                    t=s/10
                    all_pts.append((int(ax+(bx-ax)*t),int(ay+(by-ay)*t)))
            all_pts.append(corners[-1])
            iid=[None]
            for step in range(1,len(all_pts)+1):
                def draw(pts=all_pts[:step][:],step=step):
                    if not self._demo_on: return
                    flat=[c for p in pts for c in p]
                    if len(flat)<4: return
                    if iid[0]: cv.delete(iid[0])
                    iid[0]=cv.create_line(*flat,fill=col,width=wd,
                                          capstyle="round",joinstyle="round")
                    if step==len(all_pts):
                        cv.delete(iid[0])
                        iid[0]=cv.create_rectangle(x0,y0,x1,y1,
                                                   outline=col,width=wd,fill="")
                        snap=cv.create_text((x0+x1)//2,y0-12,text="✓ snapped!",
                                            fill=ACCENT,font=("Helvetica",10,"bold"))
                        self.root.after(700,lambda:cv.delete(snap))
                aid=self.root.after(ms0+step*18,draw)
                self._demo_aids.append(aid)

        def typetext(x,y,msg,col,sz,ms0):
            iid=[None]
            for step in range(1,len(msg)+1):
                def draw(t=msg[:step][:],step=step):
                    if not self._demo_on: return
                    if iid[0]: cv.delete(iid[0])
                    iid[0]=cv.create_text(x,y,text=t,fill=col,anchor="w",
                                          font=("Helvetica",sz,"bold"))
                aid=self.root.after(ms0+step*55,draw)
                self._demo_aids.append(aid)

        def wave(x0,y,x1,col,wd,ms0):
            length=x1-x0
            pts=[(x0+i,y+int(10*math.sin(i*0.15))) for i in range(0,length,4)]
            iid=[None]
            for step in range(1,len(pts)+1):
                def draw(flat=[c for p in pts[:step] for c in p][:],step=step):
                    if not self._demo_on: return
                    if len(flat)<4: return
                    if iid[0]: cv.delete(iid[0])
                    iid[0]=cv.create_line(*flat,fill=col,width=wd,
                                          smooth=True,capstyle="round")
                aid=self.root.after(ms0+step*16,draw)
                self._demo_aids.append(aid)

        def at(ms,fn):
            aid=self.root.after(ms,fn)
            self._demo_aids.append(aid)

        # ─── TIMELINE ────────────────────────────────────────────────────
        # T=0
        at(0,   lambda: banner("👋 Welcome! Watching how ScreenAnnotator works...","#00FF88"))

        # Step 1: Highlight
        at(2000, lambda: banner("① Highlighter — mark the important growth number"))
        anim_hl(490,482,545,"#FFCC00",ms0=2400)
        anim_hl(490,460,545,"#FF9500",ms0=3200)

        # Step 2: Arrow
        at(5000, lambda: banner("② Arrow — point to the best bar in the chart"))
        anim_line(750,190,670,165,"#FF3B30",3,ms0=5400,arrow=True)

        # Step 3: Circle
        at(8000, lambda: banner("③ Circle — highlight the APAC row"))
        anim_oval(118,468,338,492,"#00FF88",2,ms0=8400)

        # Step 4: Rect
        at(11000, lambda: banner("④ Smart rect — draw rough box → snaps to clean shape"))
        anim_rect(113,148,827,210,"#007AFF",2,ms0=11400)

        # Step 5: Text
        at(14500, lambda: banner("⑤ Text — type anywhere to label"))
        typetext(640,185,"← Best Q ever! 🚀","#FFCC00",12,ms0=14900)

        # Step 6: Pen
        at(18000, lambda: banner("⑥ Freehand pen — quick underline"))
        wave(130,200,820,"#FF2D55",2,ms0=18300)

        # Step 7: Explain pass-through
        at(21000, lambda: banner("⑦ In the REAL overlay: press ESC to interact with your app, ESC again to draw","#00C7BE"))

        # Done
        at(24500, lambda: banner("✅ Demo done! Click any tool above and try it yourself ↓","#34C759"))
        at(24500, lambda: setattr(self,"_unlocked",True))
        at(24500, lambda: self.demo_btn.config(text="▶ DEMO",bg="#FF9500",fg="#000"))
        at(24500, lambda: setattr(self,"_demo_on",False))

    def _stop_demo(self):
        for aid in self._demo_aids:
            try: self.root.after_cancel(aid)
            except: pass
        self._demo_aids.clear()
        self._demo_on=False
        self._unlocked=True
        self.demo_btn.config(text="▶ DEMO",bg="#FF9500",fg="#000")
        self._banner.config(text="  Demo stopped. Try the tools yourself!",fg="#AAA")

    # ─── Manual drawing ───────────────────────────────────────────────────
    # Mouse-optimised: no smoothing for pen (looks better with mouse),
    # text placed exactly where clicked, smart tool included.

    def _press(self,e):
        if not self._unlocked: return
        self._x0,self._y0=e.x,e.y
        self._raw=[(e.x,e.y)]; self._cur=None
        col,sz=self.color,self.size

        if self.tool=="pen":
            # Mouse: smooth=False looks crisper; no pressure simulation
            self._cur=self.cv.create_line(e.x,e.y,e.x+1,e.y+1,
                fill=col,width=sz,capstyle="round",joinstyle="round")
            self.strokes.append([self.tool,self._cur,[(e.x,e.y)]])

        elif self.tool=="highlighter":
            self._cur=self.cv.create_line(e.x,e.y,e.x+1,e.y+1,
                fill=col,width=max(sz,18),capstyle="round",
                joinstyle="round",stipple="gray50")
            self.strokes.append([self.tool,self._cur,[(e.x,e.y)]])

        elif self.tool=="smart":
            # Ghost dashed preview while drawing
            self._cur=self.cv.create_line(e.x,e.y,e.x+1,e.y+1,
                fill=col,width=max(sz,2),dash=(5,4),capstyle="round")

        elif self.tool=="text":
            # Place text INPUT on press (not release) — no offset drift
            self._place_text_input(e.x, e.y)

        elif self.tool=="eraser":
            self._erase(e.x,e.y)

    def _drag(self,e):
        if not self._unlocked: return
        self._raw.append((e.x,e.y))
        col,sz=self.color,self.size

        if self.tool in("pen","highlighter"):
            self.strokes[-1][2].append((e.x,e.y))
            flat=[c for p in self.strokes[-1][2] for c in p]
            self.cv.coords(self._cur,*flat)

        elif self.tool=="smart":
            flat=[c for p in self._raw for c in p]
            if len(flat)>=4:
                self.cv.coords(self._cur,*flat)

        elif self.tool=="eraser":
            self._erase(e.x,e.y)

        elif self.tool in("arrow","rect","ellipse"):
            if self._cur: self.cv.delete(self._cur)
            x0,y0,x1,y1=self._x0,self._y0,e.x,e.y
            if self.tool=="arrow":
                self._cur=self.cv.create_line(x0,y0,x1,y1,fill=col,width=sz,
                    arrow=tk.LAST,arrowshape=(12+sz*2,16+sz*2,4+sz))
            elif self.tool=="rect":
                self._cur=self.cv.create_rectangle(x0,y0,x1,y1,
                    outline=col,width=sz,fill="")
            elif self.tool=="ellipse":
                self._cur=self.cv.create_oval(x0,y0,x1,y1,
                    outline=col,width=sz,fill="")

    def _release(self,e):
        if not self._unlocked: return

        if self.tool in("arrow","rect","ellipse") and self._cur:
            self.strokes.append([self.tool,self._cur,None])
            self._cur=None

        elif self.tool=="smart":
            # Delete ghost, run recogniser, draw clean shape
            if self._cur:
                self.cv.delete(self._cur)
                self._cur=None
            if len(self._raw)<4: return
            shape,params=self._recognise(self._raw)
            sid=self._draw_recognised(shape,params)
            if sid:
                self.strokes.append(["smart_"+shape,sid,None])
                if shape!="freehand":
                    self._show_snap(sid,shape)

    def _place_text_input(self, cx, cy):
        """Place text entry widget exactly at canvas coords cx,cy."""
        # Cancel any existing entry
        if hasattr(self,"_txt_entry") and self._txt_entry:
            self._txt_entry.destroy()
        fs = max(self.size*3, 13)
        entry = tk.Entry(self.cv, font=("Helvetica",fs,"bold"),
                         fg=self.color, bg="#1A1A30",
                         insertbackground=self.color,
                         relief="flat", bd=2, width=24)
        # create_window places widget AT canvas coords — no offset issue
        win_id = self.cv.create_window(cx, cy, window=entry,
                                        anchor="nw", tags="txt_entry")
        self._txt_entry = entry
        self._txt_cx, self._txt_cy = cx, cy
        self._txt_win_id = win_id
        entry.focus_set()

        def commit(_=None):
            t = entry.get().strip()
            if t:
                tid = self.cv.create_text(
                    self._txt_cx, self._txt_cy,
                    text=t, fill=self.color,
                    anchor="nw",
                    font=("Helvetica", fs, "bold"))
                self.strokes.append(["text", tid, None])
            self.cv.delete(self._txt_win_id)
            entry.destroy()
            self._txt_entry = None

        entry.bind("<Return>",  commit)
        entry.bind("<KP_Enter>",commit)
        entry.bind("<Escape>",  lambda _: (
            self.cv.delete(self._txt_win_id), entry.destroy(),
            setattr(self,"_txt_entry",None)))

    # ─── Shape recogniser (inline, mouse-tuned) ───────────────────────────

    def _recognise(self, raw):
        """Classify raw mouse points → shape name + params."""
        import statistics
        pts = raw[::max(1,len(raw)//80)]   # downsample to ~80 pts
        if len(pts)<6: return "freehand",{}
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        x0,y0,x1,y1=min(xs),min(ys),max(xs),max(ys)
        w=max(x1-x0,1); h=max(y1-y0,1)
        asp=w/h; diag=math.hypot(w,h)
        plen=sum(math.hypot(pts[i+1][0]-pts[i][0],pts[i+1][1]-pts[i][1])
                 for i in range(len(pts)-1))
        closed=math.hypot(pts[0][0]-pts[-1][0],pts[0][1]-pts[-1][1])<diag*0.35

        # Circle / ellipse — tight radial variance
        if closed and plen>diag*1.5:
            cx,cy=(x0+x1)/2,(y0+y1)/2
            radii=[math.hypot(p[0]-cx,p[1]-cy) for p in pts]
            vr=statistics.stdev(radii)/statistics.mean(radii)
            if vr<0.14:
                return ("circle" if 0.75<asp<1.33 else "ellipse"),\
                       {"x0":x0,"y0":y0,"x1":x1,"y1":y1}

        # Polygon via RDP
        def rdp(pts,eps):
            if len(pts)<3: return pts
            s,e=pts[0],pts[-1]
            dx,dy=e[0]-s[0],e[1]-s[1]; L=math.hypot(dx,dy) or 1e-9
            ds=[abs(dx*(s[1]-p[1])-dy*(s[0]-p[0]))/L for p in pts]
            i=max(range(len(ds)),key=lambda i:ds[i])
            if ds[i]>eps: return rdp(pts[:i+1],eps)[:-1]+rdp(pts[i:],eps)
            return [s,e]
        def ang(a,b,c):
            ab=(a[0]-b[0],a[1]-b[1]); cb=(c[0]-b[0],c[1]-b[1])
            dot=ab[0]*cb[0]+ab[1]*cb[1]
            mag=math.hypot(*ab)*math.hypot(*cb)
            return math.degrees(math.acos(max(-1,min(1,dot/mag)))) if mag else 180

        tol=max(diag*0.06,8)
        simple=rdp(pts,tol)
        if closed and len(simple)>2:
            if math.hypot(simple[0][0]-simple[-1][0],
                          simple[0][1]-simple[-1][1])<tol*2:
                simple=simple[:-1]
        n=len(simple)
        corners=[simple[i] for i in range(n)
                 if ang(simple[(i-1)%n],simple[i],simple[(i+1)%n])<80]

        if closed and len(corners)==3:
            return "triangle",{"pts":corners}
        if closed and len(corners)==4:
            angs=[ang(corners[(i-1)%4],corners[i],corners[(i+1)%4])
                  for i in range(4)]
            if all(45<a<135 for a in angs):
                return ("square" if 0.8<asp<1.25 else "rect"),\
                       {"x0":x0,"y0":y0,"x1":x1,"y1":y1}

        # Line / arrow
        if not closed:
            straight=math.hypot(pts[0][0]-pts[-1][0],
                                 pts[0][1]-pts[-1][1])/(plen or 1)
            if straight>0.85:
                tail=pts[-min(12,len(pts)):]
                if any(ang(tail[i-1],tail[i],tail[i+1])<55
                       for i in range(1,len(tail)-1)):
                    return "arrow",{"x0":pts[0][0],"y0":pts[0][1],
                                    "x1":pts[-1][0],"y1":pts[-1][1]}
                return "line",{"x0":pts[0][0],"y0":pts[0][1],
                               "x1":pts[-1][0],"y1":pts[-1][1]}
        return "freehand",{}

    def _draw_recognised(self,shape,params):
        col,sz=self.color,max(self.size,2)
        if shape=="freehand":
            flat=[c for p in self._raw for c in p]
            if len(flat)<4: flat+=flat[-2:]
            return self.cv.create_line(*flat,fill=col,width=sz,
                capstyle="round",joinstyle="round")
        if shape in("circle","ellipse"):
            return self.cv.create_oval(params["x0"],params["y0"],
                params["x1"],params["y1"],outline=col,width=sz,fill="")
        if shape in("rect","square"):
            return self.cv.create_rectangle(params["x0"],params["y0"],
                params["x1"],params["y1"],outline=col,width=sz,fill="")
        if shape=="triangle":
            flat=[c for p in params["pts"] for c in p]
            return self.cv.create_polygon(*flat,outline=col,fill="",width=sz)
        if shape in("line","arrow"):
            kw=dict(fill=col,width=sz,capstyle="round")
            if shape=="arrow":
                kw.update(arrow=tk.LAST,arrowshape=(14+sz*2,18+sz*2,5+sz))
            return self.cv.create_line(params["x0"],params["y0"],
                params["x1"],params["y1"],**kw)

    def _show_snap(self,iid,label):
        try: x0,y0,x1,y1=self.cv.bbox(iid)
        except: return
        cx=(x0+x1)//2
        lid=self.cv.create_text(cx,y0-14,text=f"✓ {label}",
            fill="#00FF88",font=("Helvetica",11,"bold"),anchor="s")
        pid=self.cv.create_rectangle(x0-3,y0-3,x1+3,y1+3,
            outline="#00FF88",width=2,dash=(5,3))
        self.root.after(900,lambda:(self.cv.delete(lid),self.cv.delete(pid)))

    def _erase(self,x,y):
        r=max(self.size*6,20)
        for iid in self.cv.find_overlapping(x-r,y-r,x+r,y+r):
            if iid not in self._slide_ids:   # never erase slide content
                self.cv.delete(iid)
                self.strokes=[s for s in self.strokes if s[1]!=iid]

    def _undo(self):
        if self.strokes:
            s=self.strokes.pop(); self.cv.delete(s[1])

    def _clear_annot(self):
        # Only delete annotation strokes, keep slide content
        for s in self.strokes: self.cv.delete(s[1])
        self.strokes.clear()

    # ─── Run ─────────────────────────────────────────────────────────────

    def run(self):
        print("="*55)
        print("  ScreenAnnotator — Interactive Demo")
        print("="*55)
        print("  • Demo auto-starts in 1 second")
        print("  • Watch the 25-second animated tutorial")
        print("  • Then try the tools yourself on the fake slide")
        print("  • This demo uses its OWN canvas window")
        print()
        print("  The REAL overlay (screen_annotator_v5.py) works")
        print("  the same way but floats over your actual apps.")
        print("="*55)
        self.root.mainloop()


if __name__ == "__main__":
    DemoApp().run()
