"""
DiagramTool v4.0  —  Full-Featured UML Canvas + Code Analyser
==============================================================
Run:   python diagram_tool_v4.py
Needs: Python 3.x  (tkinter built-in)
Opt:   pip install Pillow   (PNG export)

NEW IN v4
──────────────────────────────────────────────────────────────
Canvas:
  ✓ Snap-to-grid          (toggle S key or toolbar)
  ✓ Copy / Paste          Ctrl+C / Ctrl+V  (single or multi)
  ✓ Multi-select          Rubber-band drag on empty canvas
                          Shift+Click to add to selection
  ✓ Group move            Drag any selected box moves all
  ✓ Orthogonal arrows     L-shaped routing (toggle O key)
  ✓ SVG export            File → Export SVG
  ✓ Right-click menu      Edit / Color / Shape / Copy / Delete
  ✓ Minimap               Bottom-right corner overview

Code Analysis:
  ✓ Analyse .py / .java file or entire folder
  ✓ Detects: Inheritance, Interface implementation,
             Composition (strong/weak), Aggregation,
             Dependency injection (@Autowired / ctor inject)
  ✓ Imports classified: stdlib / third-party / local file
  ✓ Correct UML arrow per relationship type

All v3 features kept:
  28 GoF + UML templates, 12 shape palette, resize handles,
  zoom, pan, undo, save/load JSON, PNG export, box colours.
──────────────────────────────────────────────────────────────
"""

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import json, math, os, copy, sys

# ═══ THEME ═══════════════════════════════════════════════════════════════════
BG         = "#1e1e2e"
SURFACE    = "#2a2a3e"
SURFACE2   = "#313145"
SURFACE3   = "#252538"
ACCENT     = "#7c6fcd"
ACCENT2    = "#a89ee8"
TEXT_LIGHT = "#e0dff5"
TEXT_MUTED = "#888aaa"
ARROW_COL  = "#a0b0e0"
SEL_COL    = "#ffcc44"
HANDLE_COL = "#44ccff"
GRID_COL   = "#252535"
SNAP_COL   = "#3a3a5a"
RBAND_COL  = "#7c6fcd"

BOX_COLORS = {
    "Blue":   ("#2e3a5c","#5a7ec8"), "Green": ("#1e3d2e","#3aaa6a"),
    "Purple": ("#3a2e5c","#7c6fcd"), "Teal":  ("#1e3d3a","#3aaaa0"),
    "Orange": ("#4a3020","#cc7744"), "Red":   ("#4a2020","#cc4444"),
    "Gray":   ("#2e2e3e","#666688"), "Yellow":("#3a3a1e","#aaaa3a"),
    "Pink":   ("#3a1e3a","#cc44cc"),
}

SHAPE_PALETTE = [
    ("rect","Rectangle","▭"),("roundrect","Round Rect","▢"),
    ("circle","Circle","●"),("ellipse","Ellipse","⬭"),
    ("diamond","Diamond","◇"),("triangle","Triangle","△"),
    ("hexagon","Hexagon","⬡"),("parallelogram","Parallelogram","▱"),
    ("note","Note","📄"),("cylinder","Cylinder/DB","🗄"),
    ("actor","Actor","🧍"),("oval","Oval/Term.","⬮"),
]

LINE_STYLES = [("solid","──── Solid"),("dashed","- - - Dashed")]

HEAD_STYLES = [
    ("open",        "▷  Open  (Association)"),
    ("filled",      "▶  Filled  (Navigation)"),
    ("inheritance", "△  Hollow triangle  (Inheritance / Realization)"),
    ("diamond",     "◇  Hollow diamond  (Aggregation)"),
    ("odiamond",    "◆  Filled diamond  (Composition)"),
    ("none",        "—  No head  (plain line)"),
]

GRID_SIZE = 20   # snap grid in world units

# ═══ DATA MODELS ══════════════════════════════════════════════════════════════

class Box:
    _id = 0
    def __init__(self,x,y,w=160,h=70,label="Box",color="Blue",shape="rect"):
        Box._id+=1
        self.id=Box._id; self.x=x; self.y=y; self.w=w; self.h=h
        self.label=label; self.color=color; self.shape=shape

    def center(self): return self.x+self.w/2, self.y+self.h/2

    def edge_point(self,tx,ty):
        cx,cy=self.center(); dx,dy=tx-cx,ty-cy
        if dx==0 and dy==0: return cx,cy
        a=math.atan2(dy,dx); ca,sa=math.cos(a),math.sin(a)
        hw,hh=self.w/2,self.h/2
        s=self.shape
        if s in("circle","ellipse","oval"):
            d=math.hypot(ca/hw,sa/hh); scale=1/d if d else hw
        elif s=="diamond":
            denom=abs(ca)*hh+abs(sa)*hw
            scale=(hw*hh)/denom if denom else hw
        else:
            scale=hw/abs(ca) if abs(ca)*hh>abs(sa)*hw else hh/abs(sa)
        return cx+ca*scale, cy+sa*scale

    def contains(self,x,y):
        return self.x<=x<=self.x+self.w and self.y<=y<=self.y+self.h

    def handle_rects(self):
        x,y,w,h=self.x,self.y,self.w,self.h; mx,my=x+w/2,y+h/2
        return {"nw":(x,y),"n":(mx,y),"ne":(x+w,y),
                "w":(x,my),"e":(x+w,my),
                "sw":(x,y+h),"s":(mx,y+h),"se":(x+w,y+h)}

    def snap(self,gs=GRID_SIZE):
        self.x=round(self.x/gs)*gs; self.y=round(self.y/gs)*gs

    def to_dict(self):
        return dict(id=self.id,x=self.x,y=self.y,w=self.w,h=self.h,
                    label=self.label,color=self.color,shape=self.shape)

    @classmethod
    def from_dict(cls,d):
        b=cls(d["x"],d["y"],d["w"],d["h"],d["label"],
              d.get("color","Blue"),d.get("shape","rect"))
        b.id=d["id"]; return b


class Arrow:
    _id=0
    def __init__(self,src_id,dst_id,label="",
                 line_style="solid",head_style="open",orthogonal=False):
        Arrow._id+=1; self.id=Arrow._id
        self.src_id=src_id; self.dst_id=dst_id; self.label=label
        self.line_style=line_style; self.head_style=head_style
        self.orthogonal=orthogonal

    def to_dict(self):
        return dict(id=self.id,src_id=self.src_id,dst_id=self.dst_id,
                    label=self.label,line_style=self.line_style,
                    head_style=self.head_style,orthogonal=self.orthogonal)

    @classmethod
    def from_dict(cls,d):
        a=cls(d["src_id"],d["dst_id"],d.get("label",""),
              d.get("line_style","solid"),d.get("head_style","open"),
              d.get("orthogonal",False))
        a.id=d["id"]; return a


class FloatText:
    _id=0
    def __init__(self,x,y,text="Label",style="normal"):
        FloatText._id+=1; self.id=FloatText._id
        self.x=x; self.y=y; self.text=text; self.style=style

    def to_dict(self):
        return dict(id=self.id,x=self.x,y=self.y,text=self.text,style=self.style)

    @classmethod
    def from_dict(cls,d):
        ft=cls(d["x"],d["y"],d["text"],d.get("style","normal"))
        ft.id=d["id"]; return ft


# ═══ TEMPLATES (all 28, compact) ═════════════════════════════════════════════

def _b(x,y,w,h,label,color="Blue",shape="rect"):
    Box._id+=1
    return dict(id=Box._id,x=x,y=y,w=w,h=h,label=label,color=color,shape=shape)

def _a(sid,did,label="",ls="solid",hs="open"):
    Arrow._id+=1
    return dict(id=Arrow._id,src_id=sid,dst_id=did,
                label=label,line_style=ls,head_style=hs,orthogonal=False)

def _t(x,y,text,style="normal"):
    FloatText._id+=1
    return dict(id=FloatText._id,x=x,y=y,text=text,style=style)

def tpl_class_diagram():
    an=_b(280,60,220,100,"Animal\n──────────────\n- name: String\n- age: int\n──────────────\n+ speak(): void\n+ move(): void","Purple")
    dg=_b(100,260,200,90,"Dog\n──────────────\n- breed: String\n──────────────\n+ speak(): void\n+ fetch(): void","Blue")
    ct=_b(480,260,200,90,"Cat\n──────────────\n- indoor: bool\n──────────────\n+ speak(): void\n+ purr(): void","Blue")
    ow=_b(280,460,220,80,"Owner\n──────────────\n- name: String\n──────────────\n+ adopt(a:Animal)","Green")
    return dict(boxes=[an,dg,ct,ow],arrows=[
        _a(dg["id"],an["id"],"","solid","inheritance"),
        _a(ct["id"],an["id"],"","solid","inheritance"),
        _a(ow["id"],an["id"],"owns  1..*","solid","open")],
        floattexts=[_t(390,20,"Class Diagram — Inheritance & Association","heading")])

def tpl_interface_diagram():
    iface=_b(280,60,220,80,"«interface»\nPaymentGateway\n──────────────\n+ charge(amount)\n+ refund(txId)","Teal")
    cls1=_b(60,240,200,80,"StripeGateway\n──────────────\n+ charge(amount)\n+ refund(txId)","Blue")
    cls2=_b(300,240,200,80,"PayPalGateway\n──────────────\n+ charge(amount)\n+ refund(txId)","Blue")
    cls3=_b(540,240,200,80,"RazorpayGateway\n──────────────\n+ charge(amount)\n+ refund(txId)","Blue")
    client=_b(280,420,220,70,"CheckoutService\n──────────────\n- gw: PaymentGateway\n+ process(cart)","Green")
    return dict(boxes=[iface,cls1,cls2,cls3,client],arrows=[
        _a(cls1["id"],iface["id"],"implements","dashed","inheritance"),
        _a(cls2["id"],iface["id"],"implements","dashed","inheritance"),
        _a(cls3["id"],iface["id"],"implements","dashed","inheritance"),
        _a(client["id"],iface["id"],"uses","dashed","open")],
        floattexts=[_t(390,20,"Interface Diagram","heading")])

def tpl_sequence_diagram():
    u=_b(60,60,120,50,"User","Gray"); ui=_b(240,60,120,50,"UI Layer","Blue")
    svc=_b(420,60,120,50,"Service","Purple"); db=_b(600,60,120,50,"Database","Teal")
    lu=_b(115,110,10,400,"","Gray"); lui=_b(295,110,10,400,"","Blue")
    ls=_b(475,110,10,400,"","Purple"); ld=_b(655,110,10,400,"","Teal")
    return dict(boxes=[u,ui,svc,db,lu,lui,ls,ld],arrows=[
        _a(lu["id"],lui["id"],"1: login(user,pwd)","solid","filled"),
        _a(lui["id"],ls["id"],"2: authenticate()","solid","filled"),
        _a(ls["id"],ld["id"],"3: SELECT user WHERE…","solid","filled"),
        _a(ld["id"],ls["id"],"4: user record","dashed","open"),
        _a(ls["id"],lui["id"],"5: token","dashed","open"),
        _a(lui["id"],lu["id"],"6: dashboard","dashed","open")],
        floattexts=[_t(390,20,"Sequence Diagram — Login Flow","heading")])

def tpl_activity_diagram():
    s=_b(300,40,80,80,"Start","Green","oval"); s1=_b(280,160,200,60,"Receive Order","Blue")
    d1=_b(290,270,200,80,"In Stock?","Orange","diamond")
    s2a=_b(80,400,200,60,"Notify Backorder","Red"); s2b=_b(460,400,200,60,"Pick & Pack","Blue")
    s3=_b(460,510,200,60,"Ship Order","Blue"); s4=_b(280,620,200,60,"Send Confirmation","Teal")
    end=_b(300,730,80,80,"End","Gray","oval")
    return dict(boxes=[s,s1,d1,s2a,s2b,s3,s4,end],arrows=[
        _a(s["id"],s1["id"]),_a(s1["id"],d1["id"]),
        _a(d1["id"],s2a["id"],"No"),_a(d1["id"],s2b["id"],"Yes"),
        _a(s2a["id"],s4["id"]),_a(s2b["id"],s3["id"]),
        _a(s3["id"],s4["id"]),_a(s4["id"],end["id"])],
        floattexts=[_t(390,10,"Activity Diagram — Order Processing","heading")])

def tpl_workflow_diagram():
    texts=[_t(60,120,"Customer","heading"),_t(60,280,"Sales","heading"),
           _t(60,440,"Finance","heading"),_t(60,600,"Delivery","heading"),
           _t(390,20,"Workflow Diagram — Order to Cash","heading")]
    b1=_b(160,90,160,60,"Place Order","Blue"); b2=_b(380,90,160,60,"Confirm Order","Blue")
    b3=_b(160,250,160,60,"Quote & Approve","Green"); b4=_b(380,250,160,60,"Create SO","Green")
    b5=_b(600,250,160,60,"Notify Customer","Green")
    b6=_b(160,410,160,60,"Invoice","Orange"); b7=_b(380,410,160,60,"Payment","Orange")
    b8=_b(600,410,160,60,"Receipt","Orange")
    b9=_b(160,570,160,60,"Dispatch","Teal"); b10=_b(380,570,160,60,"Transit","Teal")
    b11=_b(600,570,160,60,"Delivered","Teal")
    return dict(boxes=[b1,b2,b3,b4,b5,b6,b7,b8,b9,b10,b11],arrows=[
        _a(b1["id"],b2["id"]),_a(b2["id"],b3["id"]),_a(b3["id"],b4["id"],"approved"),
        _a(b4["id"],b5["id"]),_a(b4["id"],b6["id"]),_a(b6["id"],b7["id"]),
        _a(b7["id"],b8["id"]),_a(b4["id"],b9["id"]),_a(b9["id"],b10["id"]),
        _a(b10["id"],b11["id"]),_a(b5["id"],b1["id"],"notify")],floattexts=texts)

# GoF patterns (compact — same logic as v3, abbreviated here)
def _gof(title,boxes,arrows):
    return dict(boxes=boxes,arrows=arrows,
                floattexts=[_t(390,10,f"GoF — {title}","heading")])

def tpl_singleton():
    b=_b(240,80,300,130,"Singleton\n──────────────\n- instance: Singleton\n──────────────\n- Singleton()\n+ getInstance(): Singleton","Purple")
    n=_b(60,60,160,60,"Only ONE instance\never created","Gray")
    return _gof("Creational — Singleton",[b,n],[_a(n["id"],b["id"],"","dashed","open")])
def tpl_factory_method():
    cr=_b(220,60,260,90,"Creator\n──────────────\n+ factoryMethod(): Product\n+ operation(): void","Purple")
    cc=_b(220,240,260,80,"ConcreteCreator\n──────────────\n+ factoryMethod(): Product","Blue")
    pr=_b(560,60,200,80,"«interface»\nProduct\n──────────────\n+ use(): void","Teal")
    cp=_b(560,240,200,80,"ConcreteProduct\n──────────────\n+ use(): void","Blue")
    return _gof("Creational — Factory Method",[cr,cc,pr,cp],[
        _a(cc["id"],cr["id"],"","solid","inheritance"),_a(cp["id"],pr["id"],"implements","dashed","inheritance"),
        _a(cr["id"],pr["id"],"creates","dashed","open"),_a(cc["id"],cp["id"],"creates","dashed","open")])
def tpl_abstract_factory():
    af=_b(260,40,260,100,"«interface»\nAbstractFactory\n──────────────\n+ createA(): AbstractA\n+ createB(): AbstractB","Teal")
    f1=_b(60,220,240,80,"ConcreteFactory1\n──────────────\n+ createA(): ConcreteA1\n+ createB(): ConcreteB1","Blue")
    f2=_b(480,220,240,80,"ConcreteFactory2\n──────────────\n+ createA(): ConcreteA2","Blue")
    aa=_b(260,220,180,60,"«interface»\nAbstractA\n+ use()","Teal")
    ab=_b(260,320,180,60,"«interface»\nAbstractB\n+ use()","Teal")
    ca1=_b(60,420,160,50,"ConcreteA1","Green"); ca2=_b(480,420,160,50,"ConcreteA2","Green")
    cb1=_b(60,490,160,50,"ConcreteB1","Orange"); cb2=_b(480,490,160,50,"ConcreteB2","Orange")
    return _gof("Creational — Abstract Factory",[af,f1,f2,aa,ab,ca1,ca2,cb1,cb2],[
        _a(f1["id"],af["id"],"","solid","inheritance"),_a(f2["id"],af["id"],"","solid","inheritance"),
        _a(ca1["id"],aa["id"],"","solid","inheritance"),_a(ca2["id"],aa["id"],"","solid","inheritance"),
        _a(cb1["id"],ab["id"],"","solid","inheritance"),_a(cb2["id"],ab["id"],"","solid","inheritance"),
        _a(f1["id"],ca1["id"],"creates","dashed","open"),_a(f2["id"],ca2["id"],"creates","dashed","open")])
def tpl_builder():
    d=_b(60,100,180,80,"Director\n──────────────\n- builder: Builder\n+ construct()","Green")
    bl=_b(320,60,240,100,"«interface»\nBuilder\n──────────────\n+ buildPartA()\n+ buildPartB()\n+ getResult(): Product","Teal")
    cb=_b(320,240,240,90,"ConcreteBuilder\n──────────────\n+ buildPartA()\n+ buildPartB()\n+ getResult(): Product","Blue")
    pr=_b(320,390,240,80,"Product\n──────────────\n- partA\n- partB","Purple")
    return _gof("Creational — Builder",[d,bl,cb,pr],[
        _a(d["id"],bl["id"],"uses","solid","open"),_a(cb["id"],bl["id"],"","solid","inheritance"),
        _a(cb["id"],pr["id"],"builds","dashed","open")])
def tpl_prototype():
    p=_b(240,60,240,90,"«interface»\nPrototype\n──────────────\n+ clone(): Prototype","Teal")
    c1=_b(80,240,220,80,"ConcretePrototype1\n──────────────\n+ clone(): Prototype","Blue")
    c2=_b(460,240,220,80,"ConcretePrototype2\n──────────────\n+ clone(): Prototype","Blue")
    cl=_b(240,420,240,70,"Client\n──────────────\n+ operation(): void","Green")
    return _gof("Creational — Prototype",[p,c1,c2,cl],[
        _a(c1["id"],p["id"],"","solid","inheritance"),_a(c2["id"],p["id"],"","solid","inheritance"),
        _a(cl["id"],p["id"],"clone()","dashed","open")])
def tpl_adapter():
    t=_b(240,60,240,80,"«interface»\nTarget\n──────────────\n+ request(): void","Teal")
    a=_b(240,220,240,90,"Adapter\n──────────────\n- adaptee: Adaptee\n──────────────\n+ request(): void","Blue")
    ad=_b(560,220,220,80,"Adaptee\n──────────────\n+ specificRequest(): void","Orange")
    cl=_b(240,390,240,70,"Client\n──────────────\n+ doWork(t: Target)","Green")
    return _gof("Structural — Adapter",[t,a,ad,cl],[
        _a(a["id"],t["id"],"implements","solid","inheritance"),
        _a(a["id"],ad["id"],"delegates","solid","open"),_a(cl["id"],t["id"],"uses","dashed","open")])
def tpl_bridge():
    ab=_b(60,60,240,90,"Abstraction\n──────────────\n- impl: Implementor\n──────────────\n+ operation()","Purple")
    ra=_b(60,240,240,80,"RefinedAbstraction\n──────────────\n+ operation()","Blue")
    im=_b(400,60,240,90,"«interface»\nImplementor\n──────────────\n+ operationImpl()","Teal")
    c1=_b(320,240,200,80,"ConcreteImpl1\n──────────────\n+ operationImpl()","Green")
    c2=_b(540,240,200,80,"ConcreteImpl2\n──────────────\n+ operationImpl()","Green")
    return _gof("Structural — Bridge",[ab,ra,im,c1,c2],[
        _a(ra["id"],ab["id"],"","solid","inheritance"),_a(c1["id"],im["id"],"","solid","inheritance"),
        _a(c2["id"],im["id"],"","solid","inheritance"),_a(ab["id"],im["id"],"uses","solid","open")])
def tpl_composite():
    c=_b(240,60,240,90,"«interface»\nComponent\n──────────────\n+ operation()\n+ add(c)\n+ remove(c)","Teal")
    l=_b(60,260,200,80,"Leaf\n──────────────\n+ operation()","Blue")
    co=_b(480,260,240,90,"Composite\n──────────────\n- children: List\n──────────────\n+ operation()","Purple")
    return _gof("Structural — Composite",[c,l,co],[
        _a(l["id"],c["id"],"","solid","inheritance"),_a(co["id"],c["id"],"","solid","inheritance"),
        _a(co["id"],c["id"],"0..*","solid","diamond")])
def tpl_decorator():
    c=_b(240,60,220,80,"«interface»\nComponent\n──────────────\n+ operation()","Teal")
    cc=_b(60,240,220,80,"ConcreteComponent\n──────────────\n+ operation()","Blue")
    d=_b(460,240,240,90,"Decorator\n──────────────\n- wrappee: Component\n──────────────\n+ operation()","Purple")
    da=_b(380,410,220,80,"ConcreteDecoratorA\n──────────────\n+ operation()\n+ extraA()","Orange")
    db=_b(620,410,220,80,"ConcreteDecoratorB\n──────────────\n+ operation()\n+ extraB()","Orange")
    return _gof("Structural — Decorator",[c,cc,d,da,db],[
        _a(cc["id"],c["id"],"","solid","inheritance"),_a(d["id"],c["id"],"","solid","inheritance"),
        _a(d["id"],c["id"],"wraps","dashed","open"),_a(da["id"],d["id"],"","solid","inheritance"),
        _a(db["id"],d["id"],"","solid","inheritance")])
def tpl_facade():
    f=_b(280,60,220,80,"Facade\n──────────────\n+ operationA()\n+ operationB()","Purple")
    s1=_b(60,240,180,70,"SubsystemA\n──────────────\n+ doThingA()","Blue")
    s2=_b(280,240,180,70,"SubsystemB\n──────────────\n+ doThingB()","Blue")
    s3=_b(500,240,180,70,"SubsystemC\n──────────────\n+ doThingC()","Blue")
    cl=_b(280,400,220,70,"Client\n──────────────\n+ run()","Green")
    return _gof("Structural — Facade",[f,s1,s2,s3,cl],[
        _a(f["id"],s1["id"]),_a(f["id"],s2["id"]),_a(f["id"],s3["id"]),
        _a(cl["id"],f["id"],"uses","solid","open")])
def tpl_flyweight():
    fw=_b(240,60,260,90,"«interface»\nFlyweight\n──────────────\n+ operation(extrinsicState)","Teal")
    cf=_b(120,240,240,80,"ConcreteFlyweight\n──────────────\n- intrinsicState\n+ operation(extState)","Blue")
    uf=_b(440,240,240,80,"UnsharedFlyweight\n──────────────\n- allState\n+ operation(extState)","Orange")
    fa=_b(240,420,260,80,"FlyweightFactory\n──────────────\n- pool: Map\n+ getFlyweight(key)","Purple")
    cl=_b(240,570,260,70,"Client\n──────────────\n+ run()","Green")
    return _gof("Structural — Flyweight",[fw,cf,uf,fa,cl],[
        _a(cf["id"],fw["id"],"","solid","inheritance"),_a(uf["id"],fw["id"],"","solid","inheritance"),
        _a(fa["id"],fw["id"],"manages","dashed","open"),_a(cl["id"],fa["id"],"requests","solid","open")])
def tpl_proxy():
    i=_b(240,60,220,80,"«interface»\nSubject\n──────────────\n+ request()","Teal")
    r=_b(60,240,220,80,"RealSubject\n──────────────\n+ request()","Blue")
    p=_b(460,240,220,90,"Proxy\n──────────────\n- real: RealSubject\n──────────────\n+ request()","Purple")
    cl=_b(240,420,220,70,"Client\n──────────────\n+ run()","Green")
    return _gof("Structural — Proxy",[i,r,p,cl],[
        _a(r["id"],i["id"],"","solid","inheritance"),_a(p["id"],i["id"],"","solid","inheritance"),
        _a(p["id"],r["id"],"delegates","solid","open"),_a(cl["id"],p["id"],"uses","solid","open")])
def tpl_chain():
    h=_b(240,60,240,90,"«abstract»\nHandler\n──────────────\n- next: Handler\n──────────────\n+ handle(req)\n+ setNext(h)","Purple")
    h1=_b(60,260,200,80,"ConcreteHandler1\n──────────────\n+ handle(req)","Blue")
    h2=_b(300,260,200,80,"ConcreteHandler2\n──────────────\n+ handle(req)","Blue")
    h3=_b(540,260,200,80,"ConcreteHandler3\n──────────────\n+ handle(req)","Blue")
    cl=_b(240,430,240,70,"Client\n──────────────\n+ run()","Green")
    return _gof("Behavioral — Chain of Responsibility",[h,h1,h2,h3,cl],[
        _a(h1["id"],h["id"],"","solid","inheritance"),_a(h2["id"],h["id"],"","solid","inheritance"),
        _a(h3["id"],h["id"],"","solid","inheritance"),
        _a(h1["id"],h2["id"],"next","solid","open"),_a(h2["id"],h3["id"],"next","solid","open"),
        _a(cl["id"],h1["id"],"send request","dashed","open")])
def tpl_command():
    i=_b(60,60,180,90,"Invoker\n──────────────\n- cmd: Command\n──────────────\n+ invoke()","Green")
    c=_b(300,60,220,80,"«interface»\nCommand\n──────────────\n+ execute()\n+ undo()","Teal")
    cc=_b(300,230,220,90,"ConcreteCommand\n──────────────\n- receiver: Receiver\n──────────────\n+ execute()\n+ undo()","Blue")
    r=_b(580,60,180,80,"Receiver\n──────────────\n+ action()\n+ undoAction()","Orange")
    cl=_b(300,410,220,70,"Client\n──────────────\n+ run()","Purple")
    return _gof("Behavioral — Command",[i,c,cc,r,cl],[
        _a(i["id"],c["id"],"uses","solid","open"),_a(cc["id"],c["id"],"","solid","inheritance"),
        _a(cc["id"],r["id"],"calls","solid","open"),_a(cl["id"],cc["id"],"creates","dashed","open")])
def tpl_observer():
    s=_b(240,60,260,100,"Subject / Observable\n──────────────\n- observers: List\n──────────────\n+ attach(o)\n+ detach(o)\n+ notify()","Purple")
    o=_b(240,260,260,80,"«interface»\nObserver\n──────────────\n+ update(event)","Teal")
    c1=_b(60,420,220,80,"ConcreteObserver1\n──────────────\n+ update(event)","Blue")
    c2=_b(500,420,220,80,"ConcreteObserver2\n──────────────\n+ update(event)","Blue")
    return _gof("Behavioral — Observer",[s,o,c1,c2],[
        _a(s["id"],o["id"],"notifies","solid","open"),
        _a(c1["id"],o["id"],"","solid","inheritance"),_a(c2["id"],o["id"],"","solid","inheritance")])
def tpl_strategy():
    c=_b(60,60,200,90,"Context\n──────────────\n- strategy: Strategy\n──────────────\n+ executeStrategy()","Purple")
    s=_b(340,60,240,80,"«interface»\nStrategy\n──────────────\n+ execute(data): Result","Teal")
    cs1=_b(240,240,220,80,"ConcreteStrategyA\n──────────────\n+ execute(data)","Blue")
    cs2=_b(480,240,220,80,"ConcreteStrategyB\n──────────────\n+ execute(data)","Blue")
    return _gof("Behavioral — Strategy",[c,s,cs1,cs2],[
        _a(c["id"],s["id"],"uses","solid","open"),_a(cs1["id"],s["id"],"","solid","inheritance"),
        _a(cs2["id"],s["id"],"","solid","inheritance")])
def tpl_template_method():
    a=_b(220,60,300,120,"AbstractClass\n──────────────\n+ templateMethod()  «final»\n──────────────\n# primitiveOp1()  «abstract»\n# primitiveOp2()  «abstract»","Purple")
    c1=_b(80,280,260,90,"ConcreteClass1\n──────────────\n# primitiveOp1()\n# primitiveOp2()","Blue")
    c2=_b(400,280,260,90,"ConcreteClass2\n──────────────\n# primitiveOp1()\n# primitiveOp2()","Blue")
    return _gof("Behavioral — Template Method",[a,c1,c2],[
        _a(c1["id"],a["id"],"","solid","inheritance"),_a(c2["id"],a["id"],"","solid","inheritance")])
def tpl_state():
    c=_b(60,60,200,90,"Context\n──────────────\n- state: State\n──────────────\n+ request()\n+ setState(s)","Purple")
    s=_b(340,60,220,80,"«interface»\nState\n──────────────\n+ handle(ctx)","Teal")
    cs1=_b(240,240,220,80,"ConcreteStateA\n──────────────\n+ handle(ctx)","Blue")
    cs2=_b(480,240,220,80,"ConcreteStateB\n──────────────\n+ handle(ctx)","Blue")
    return _gof("Behavioral — State",[c,s,cs1,cs2],[
        _a(c["id"],s["id"],"uses","solid","open"),_a(cs1["id"],s["id"],"","solid","inheritance"),
        _a(cs2["id"],s["id"],"","solid","inheritance"),_a(cs1["id"],cs2["id"],"transition","dashed","open")])
def tpl_iterator():
    ag=_b(240,60,240,80,"«interface»\nAggregate\n──────────────\n+ createIterator()","Teal")
    it=_b(240,240,240,90,"«interface»\nIterator\n──────────────\n+ hasNext(): bool\n+ next(): Object\n+ reset()","Teal")
    ca=_b(40,420,240,80,"ConcreteAggregate\n──────────────\n+ createIterator()","Blue")
    ci=_b(440,420,240,80,"ConcreteIterator\n──────────────\n+ hasNext()\n+ next()","Blue")
    cl=_b(580,60,180,70,"Client\n──────────────\n+ run()","Green")
    return _gof("Behavioral — Iterator",[ag,it,ca,ci,cl],[
        _a(ca["id"],ag["id"],"","solid","inheritance"),_a(ci["id"],it["id"],"","solid","inheritance"),
        _a(ca["id"],ci["id"],"creates","dashed","open"),
        _a(cl["id"],ag["id"],"uses","solid","open"),_a(cl["id"],it["id"],"uses","solid","open")])
def tpl_mediator():
    m=_b(240,60,240,80,"«interface»\nMediator\n──────────────\n+ notify(sender, event)","Teal")
    cm=_b(240,220,240,80,"ConcreteMediator\n──────────────\n+ notify(sender, event)","Purple")
    c1=_b(40,400,200,80,"ComponentA\n──────────────\n- mediator: Mediator\n+ operationA()","Blue")
    c2=_b(260,400,200,80,"ComponentB\n──────────────\n- mediator: Mediator\n+ operationB()","Blue")
    c3=_b(480,400,200,80,"ComponentC\n──────────────\n- mediator: Mediator\n+ operationC()","Blue")
    return _gof("Behavioral — Mediator",[m,cm,c1,c2,c3],[
        _a(cm["id"],m["id"],"","solid","inheritance"),
        _a(c1["id"],m["id"],"notifies","dashed","open"),_a(c2["id"],m["id"],"notifies","dashed","open"),
        _a(c3["id"],m["id"],"notifies","dashed","open"),
        _a(cm["id"],c1["id"],"coordinates","solid","open"),
        _a(cm["id"],c2["id"],"coordinates","solid","open"),
        _a(cm["id"],c3["id"],"coordinates","solid","open")])
def tpl_memento():
    o=_b(60,60,220,90,"Originator\n──────────────\n- state: State\n──────────────\n+ save(): Memento\n+ restore(m)","Purple")
    m=_b(360,60,220,90,"Memento\n──────────────\n- state: State\n──────────────\n+ getState(): State","Blue")
    c=_b(360,240,220,90,"Caretaker\n──────────────\n- history: List<Memento>\n──────────────\n+ backup()\n+ undo()","Green")
    return _gof("Behavioral — Memento",[o,m,c],[
        _a(o["id"],m["id"],"creates","solid","open"),
        _a(c["id"],m["id"],"stores","solid","odiamond"),
        _a(c["id"],o["id"],"restores via","dashed","open")])
def tpl_interpreter():
    e=_b(220,60,260,80,"«interface»\nExpression\n──────────────\n+ interpret(ctx): bool","Teal")
    te=_b(60,240,240,80,"TerminalExpression\n──────────────\n+ interpret(ctx): bool","Blue")
    ne=_b(460,240,240,90,"NonterminalExpression\n──────────────\n- exprs: List\n──────────────\n+ interpret(ctx): bool","Blue")
    c=_b(220,400,260,80,"Context\n──────────────\n+ lookup(name)\n+ assign(name, val)","Purple")
    cl=_b(580,400,180,70,"Client\n──────────────\n+ run()","Green")
    return _gof("Behavioral — Interpreter",[e,te,ne,c,cl],[
        _a(te["id"],e["id"],"","solid","inheritance"),_a(ne["id"],e["id"],"","solid","inheritance"),
        _a(ne["id"],e["id"],"0..*","solid","diamond"),
        _a(cl["id"],c["id"],"creates","dashed","open"),_a(cl["id"],e["id"],"uses","dashed","open")])
def tpl_visitor():
    v=_b(240,60,260,90,"«interface»\nVisitor\n──────────────\n+ visitA(e: ConcreteA)\n+ visitB(e: ConcreteB)","Teal")
    cv1=_b(60,240,240,80,"ConcreteVisitor1\n──────────────\n+ visitA()\n+ visitB()","Blue")
    cv2=_b(480,240,240,80,"ConcreteVisitor2\n──────────────\n+ visitA()\n+ visitB()","Blue")
    el=_b(240,420,260,80,"«interface»\nElement\n──────────────\n+ accept(v: Visitor)","Teal")
    ea=_b(60,580,240,80,"ConcreteElementA\n──────────────\n+ accept(v: Visitor)","Green")
    eb=_b(480,580,240,80,"ConcreteElementB\n──────────────\n+ accept(v: Visitor)","Green")
    return _gof("Behavioral — Visitor",[v,cv1,cv2,el,ea,eb],[
        _a(cv1["id"],v["id"],"","solid","inheritance"),_a(cv2["id"],v["id"],"","solid","inheritance"),
        _a(ea["id"],el["id"],"","solid","inheritance"),_a(eb["id"],el["id"],"","solid","inheritance"),
        _a(el["id"],v["id"],"accepts","dashed","open")])

TEMPLATES = {
    "UML Diagrams": {
        "Class Diagram":tpl_class_diagram,"Interface Diagram":tpl_interface_diagram,
        "Sequence Diagram":tpl_sequence_diagram,"Activity Diagram":tpl_activity_diagram,
        "Workflow Diagram":tpl_workflow_diagram,
    },
    "GoF — Creational": {
        "Singleton":tpl_singleton,"Factory Method":tpl_factory_method,
        "Abstract Factory":tpl_abstract_factory,"Builder":tpl_builder,"Prototype":tpl_prototype,
    },
    "GoF — Structural": {
        "Adapter":tpl_adapter,"Bridge":tpl_bridge,"Composite":tpl_composite,
        "Decorator":tpl_decorator,"Facade":tpl_facade,"Flyweight":tpl_flyweight,"Proxy":tpl_proxy,
    },
    "GoF — Behavioral": {
        "Chain of Responsibility":tpl_chain,"Command":tpl_command,"Interpreter":tpl_interpreter,
        "Iterator":tpl_iterator,"Mediator":tpl_mediator,"Memento":tpl_memento,
        "Observer":tpl_observer,"State":tpl_state,"Strategy":tpl_strategy,
        "Template Method":tpl_template_method,"Visitor":tpl_visitor,
    },
}

# ═══ MAIN APPLICATION ═════════════════════════════════════════════════════════

class DiagramApp:
    HANDLE_R = 5

    def __init__(self, root):
        self.root = root
        self.root.title("DiagramTool v4.0 — UML + Code Analyser")
        self.root.configure(bg=BG)
        self.root.geometry("1560x920")

        self.boxes, self.arrows, self.floattexts = [], [], []
        self.selected_items = set()   # set of ids (Box/Arrow/FloatText)
        self.selected       = None    # primary selected item (for single ops)
        self.mode           = "select"
        self.arrow_src      = None
        self.undo_stack     = []
        self.clipboard      = []      # copied boxes

        self.offset_x, self.offset_y = 40, 40
        self.zoom = 1.0

        self._drag_start    = None
        self._drag_obj      = None
        self._drag_origin   = None
        self._drag_origins  = {}      # multi-select drag origins
        self._pan_start     = None
        self._resize_handle = None
        self._resize_origin = None
        self._rband_start   = None    # rubber-band selection start (canvas coords)
        self._rband_rect    = None

        self._pending_shape = None
        self.snap_enabled   = tk.BooleanVar(value=True)
        self.ortho_enabled  = tk.BooleanVar(value=False)
        self.minimap_enabled= tk.BooleanVar(value=True)

        self.new_line_style = tk.StringVar(value="solid")
        self.new_head_style = tk.StringVar(value="open")
        self.new_color      = tk.StringVar(value="Blue")

        self._build_ui()
        self._bind_events()
        self._draw_all()

    # ═══ UI BUILD ═════════════════════════════════════════════════════════════

    def _build_ui(self):
        tb = tk.Frame(self.root, bg=SURFACE, height=52)
        tb.pack(fill="x", side="top"); tb.pack_propagate(False)

        self.mode_btns = {}
        for label, key in [("☰ Select","select"),("➜ Arrow","arrow"),
                            ("T Text","text"),("✥ Pan","pan")]:
            btn = tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                            activebackground=ACCENT, activeforeground="white",
                            relief="flat", padx=10, pady=8, cursor="hand2",
                            font=("Segoe UI",10),
                            command=lambda k=key: self.set_mode(k))
            btn.pack(side="left", padx=2, pady=6)
            self.mode_btns[key] = btn

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        # Arrow controls
        af = tk.Frame(tb, bg=SURFACE); af.pack(side="left", padx=4)
        tk.Label(af, text="Line:", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI",8)).grid(row=0,column=0)
        self._line_cb = ttk.Combobox(af, textvariable=self.new_line_style,
                                     values=[v for v,_ in LINE_STYLES],
                                     width=7, state="readonly")
        self._line_cb.grid(row=0,column=1,padx=2)
        self._line_disp = tk.Label(af, text="──── Solid", bg=SURFACE, fg=ACCENT2,
                                   font=("Segoe UI",9), width=13, anchor="w")
        self._line_disp.grid(row=0,column=2,padx=2)
        tk.Label(af, text="Head:", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI",8)).grid(row=0,column=3,padx=(8,0))
        self._head_cb = ttk.Combobox(af, textvariable=self.new_head_style,
                                     values=[v for v,_ in HEAD_STYLES],
                                     width=13, state="readonly")
        self._head_cb.grid(row=0,column=4,padx=2)
        self._head_disp = tk.Label(af, text="▷  Open  (Association)",
                                   bg=SURFACE, fg=ACCENT2, font=("Segoe UI",9),
                                   width=28, anchor="w")
        self._head_disp.grid(row=0,column=5,padx=2)
        def _upd_line(*_):
            self._line_disp.config(text=dict(LINE_STYLES).get(self.new_line_style.get(),""))
        def _upd_head(*_):
            self._head_disp.config(text=dict(HEAD_STYLES).get(self.new_head_style.get(),""))
        self.new_line_style.trace_add("write",_upd_line)
        self.new_head_style.trace_add("write",_upd_head)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        # Toggle buttons
        for text, var, tip in [
            ("⊞ Snap", self.snap_enabled,  "Snap to grid (S)"),
            ("⤡ Ortho",self.ortho_enabled, "Orthogonal arrows (O)"),
            ("🗺 Map",  self.minimap_enabled,"Minimap"),
        ]:
            cb = tk.Checkbutton(tb, text=text, variable=var,
                                bg=SURFACE, fg=TEXT_LIGHT, selectcolor=ACCENT,
                                activebackground=SURFACE,
                                font=("Segoe UI",9), cursor="hand2",
                                command=self._draw_all)
            cb.pack(side="left", padx=3, pady=8)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        for label,cmd in [("🗑 Del",self._delete_selected),
                          ("✏ Edit",self._edit_selected),
                          ("🎨 Color",self._change_color),
                          ("📋 Copy",self._copy),("📌 Paste",self._paste)]:
            tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                      activebackground="#555577", relief="flat",
                      padx=8, pady=8, cursor="hand2",
                      font=("Segoe UI",10), command=cmd).pack(side="left",padx=2,pady=6)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)
        tk.Button(tb, text="📐 Templates", bg=ACCENT, fg="white",
                  relief="flat", padx=10, pady=8, cursor="hand2",
                  font=("Segoe UI",10,"bold"),
                  command=self._show_template_panel).pack(side="left",padx=3,pady=6)

        tk.Button(tb, text="🔍 Analyse Code", bg="#2a5c2a", fg="white",
                  relief="flat", padx=10, pady=8, cursor="hand2",
                  font=("Segoe UI",10,"bold"),
                  command=self._analyse_code).pack(side="left",padx=3,pady=6)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)
        for label,cmd in [("💾 Save",self._save),("📂 Open",self._load),
                          ("🖼 PNG",self._export_png),("✦ SVG",self._export_svg),
                          ("🧹 Clear",self._clear)]:
            tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                      activebackground="#555577", relief="flat",
                      padx=8, pady=8, cursor="hand2",
                      font=("Segoe UI",10), command=cmd).pack(side="left",padx=2,pady=6)

        self.zoom_var = tk.StringVar(value="100%")
        tk.Button(tb, text="⟳", bg=SURFACE2, fg=TEXT_MUTED, relief="flat",
                  padx=6, pady=8, cursor="hand2",
                  command=self._reset_view).pack(side="right",padx=4,pady=6)
        tk.Label(tb, textvariable=self.zoom_var, bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI",10)).pack(side="right",padx=6)

        self.status_var = tk.StringVar(value="DiagramTool v4  •  🔍 Analyse Code to auto-generate class diagrams from .py / .java files")
        tk.Label(self.root, textvariable=self.status_var, bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI",9), anchor="w", padx=12, pady=4).pack(fill="x",side="bottom")

        body = tk.Frame(self.root, bg=BG); body.pack(fill="both",expand=True)
        self._build_palette(body)
        self._build_info(body)
        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.set_mode("select")

    def _build_palette(self, parent):
        pal = tk.Frame(parent, bg=SURFACE3, width=126); pal.pack(fill="y",side="left"); pal.pack_propagate(False)
        tk.Label(pal, text="SHAPES", bg=SURFACE3, fg=TEXT_MUTED,
                 font=("Segoe UI",9,"bold"), pady=6).pack()
        self.pal_btns = {}
        for key,label,sym in SHAPE_PALETTE:
            frame=tk.Frame(pal,bg=SURFACE3,cursor="hand2"); frame.pack(fill="x",padx=5,pady=1)
            pv=tk.Canvas(frame,bg=SURFACE2,width=32,height=24,highlightthickness=1,highlightbackground=SURFACE2)
            pv.pack(side="left"); self._draw_shape_preview(pv,key)
            btn=tk.Label(frame,text=label,bg=SURFACE3,fg=TEXT_MUTED,font=("Segoe UI",8),padx=3,anchor="w",cursor="hand2")
            btn.pack(side="left",fill="x",expand=True)
            self.pal_btns[key]=(frame,btn,pv)
            for w in (frame,btn,pv):
                w.bind("<Button-1>",lambda e,k=key:self._palette_click(k))
                w.bind("<Enter>",   lambda e,k=key:self._palette_hover(k,True))
                w.bind("<Leave>",   lambda e,k=key:self._palette_hover(k,False))

    def _draw_shape_preview(self,cv,key):
        cv.delete("all"); W,H=32,24; pad=3
        fill=BOX_COLORS["Blue"][0]; out=BOX_COLORS["Blue"][1]
        x1,y1,x2,y2=pad,pad,W-pad,H-pad; cx,cy=W//2,H//2
        if key=="rect":        cv.create_rectangle(x1,y1,x2,y2,fill=fill,outline=out)
        elif key=="roundrect": cv.create_rectangle(x1,y1,x2,y2,fill=fill,outline=out)
        elif key in("circle",):
            r=min(W,H)//2-pad; cv.create_oval(cx-r,cy-r,cx+r,cy+r,fill=fill,outline=out)
        elif key in("ellipse","oval"): cv.create_oval(x1,y1,x2,y2,fill=fill,outline=out)
        elif key=="diamond":   cv.create_polygon(cx,y1,x2,cy,cx,y2,x1,cy,fill=fill,outline=out)
        elif key=="triangle":  cv.create_polygon(cx,y1,x2,y2,x1,y2,fill=fill,outline=out)
        elif key=="hexagon":
            pts=[]
            for i in range(6):
                a=math.radians(60*i-30); r=min(W,H)//2-pad
                pts+=[cx+r*math.cos(a),cy+r*math.sin(a)]
            cv.create_polygon(pts,fill=fill,outline=out)
        elif key=="parallelogram":
            sk=6; cv.create_polygon(x1+sk,y1,x2,y1,x2-sk,y2,x1,y2,fill=fill,outline=out)
        elif key=="note":
            fold=6; cv.create_polygon(x1,y1,x2-fold,y1,x2,y1+fold,x2,y2,x1,y2,fill=fill,outline=out)
        elif key=="cylinder":
            ry=4; cv.create_rectangle(x1,y1+ry,x2,y2-ry,fill=fill,outline="")
            cv.create_oval(x1,y1,x2,y1+ry*2,fill=fill,outline=out)
            cv.create_oval(x1,y2-ry*2,x2,y2,fill=fill,outline=out)
            cv.create_line(x1,y1+ry,x1,y2-ry,fill=out); cv.create_line(x2,y1+ry,x2,y2-ry,fill=out)
        elif key=="actor":
            r=3; cv.create_oval(cx-r,y1,cx+r,y1+r*2,fill=fill,outline=out)
            cv.create_line(cx,y1+r*2,cx,H-5,fill=out)
            cv.create_line(x1+2,y1+r*3+1,x2-2,y1+r*3+1,fill=out)
            cv.create_line(cx,H-5,x1+2,y2,fill=out); cv.create_line(cx,H-5,x2-2,y2,fill=out)

    def _build_info(self, parent):
        info=tk.Frame(parent,bg=SURFACE,width=175); info.pack(fill="y",side="right"); info.pack_propagate(False)
        tk.Label(info,text="SHORTCUTS",bg=SURFACE,fg=TEXT_MUTED,font=("Segoe UI",9,"bold"),pady=6).pack()
        for key,desc in [("Ctrl+S","Save"),("Ctrl+O","Open"),("Ctrl+Z","Undo"),
                         ("Ctrl+C","Copy"),("Ctrl+V","Paste"),
                         ("Del","Delete"),("Esc","Deselect"),
                         ("S","Toggle snap"),("O","Toggle ortho arrows"),
                         ("Scroll","Zoom"),("Middle","Pan"),("Dbl-click","Edit")]:
            row=tk.Frame(info,bg=SURFACE); row.pack(fill="x",padx=6,pady=1)
            tk.Label(row,text=key,bg=SURFACE2,fg=ACCENT2,font=("Consolas",8),padx=3,width=10).pack(side="left")
            tk.Label(row,text=desc,bg=SURFACE,fg=TEXT_MUTED,font=("Segoe UI",8),padx=3).pack(side="left")
        tk.Frame(info,bg=SURFACE2,height=1).pack(fill="x",pady=5,padx=5)
        tk.Label(info,text="MULTI-SELECT",bg=SURFACE,fg=TEXT_MUTED,font=("Segoe UI",8,"bold")).pack()
        tk.Label(info,text="Drag empty canvas\nor Shift+Click\nto multi-select.\nDrag any selected\nbox to move all.",
                 bg=SURFACE,fg=TEXT_MUTED,font=("Segoe UI",7),justify="left",padx=10,pady=3).pack(anchor="w")
        tk.Frame(info,bg=SURFACE2,height=1).pack(fill="x",pady=5,padx=5)
        self.sel_info=tk.Label(info,text="Nothing selected",bg=SURFACE,fg=TEXT_MUTED,
                               font=("Segoe UI",7),justify="left",padx=10,pady=3,wraplength=160)
        self.sel_info.pack(anchor="w")

    # ═══ PALETTE ══════════════════════════════════════════════════════════════

    def _palette_click(self,key):
        self._pending_shape=key
        for k,(frame,btn,cv) in self.pal_btns.items():
            active=(k==key)
            frame.config(bg=ACCENT if active else SURFACE3)
            btn.config(bg=ACCENT if active else SURFACE3, fg="white" if active else TEXT_MUTED)
        self.mode="shape"
        for k,b in self.mode_btns.items(): b.configure(bg=SURFACE2,fg=TEXT_LIGHT)
        self.canvas.configure(cursor="crosshair")
        self.status_var.set(f"Shape  •  Click canvas to place: {key}  •  Escape to cancel")

    def _palette_hover(self,key,entering):
        if self._pending_shape==key: return
        frame,btn,cv=self.pal_btns[key]
        frame.config(bg=SURFACE2 if entering else SURFACE3)
        btn.config(bg=SURFACE2 if entering else SURFACE3)

    # ═══ MODE ═════════════════════════════════════════════════════════════════

    def set_mode(self,mode):
        self.mode=mode; self._pending_shape=None
        for k,(frame,btn,cv) in self.pal_btns.items():
            frame.config(bg=SURFACE3); btn.config(bg=SURFACE3,fg=TEXT_MUTED)
        self.arrow_src=None; self.selected=None; self.selected_items.clear()
        for k,b in self.mode_btns.items():
            b.configure(bg=ACCENT if k==mode else SURFACE2,fg="white" if k==mode else TEXT_LIGHT)
        cursors={"select":"arrow","arrow":"crosshair","text":"xterm","pan":"fleur"}
        self.canvas.configure(cursor=cursors.get(mode,"arrow"))
        msgs={"select":"Select  •  Click=select · Shift+Click=add to selection · Drag empty=rubber-band · Drag handle=resize",
              "arrow": "Arrow  •  Click SOURCE → click TARGET  |  Set Line & Head style above",
              "text":  "Text  •  Click to drop a floating label",
              "pan":   "Pan  •  Drag to scroll  |  Middle mouse"}
        self.status_var.set(msgs.get(mode,""))
        self._update_sel_info(); self._draw_all()

    # ═══ COORDS ═══════════════════════════════════════════════════════════════

    def _to_world(self,cx,cy): return (cx-self.offset_x)/self.zoom,(cy-self.offset_y)/self.zoom
    def _to_canvas(self,wx,wy): return wx*self.zoom+self.offset_x,wy*self.zoom+self.offset_y

    def _snap(self,v):
        if self.snap_enabled.get():
            return round(v/GRID_SIZE)*GRID_SIZE
        return v

    # ═══ HIT TEST ═════════════════════════════════════════════════════════════

    def _box_at(self,wx,wy):
        for b in reversed(self.boxes):
            if b.contains(wx,wy): return b
        return None

    def _handle_at(self,box,wx,wy):
        tol=self.HANDLE_R*1.8/self.zoom
        for key,(hx,hy) in box.handle_rects().items():
            if abs(wx-hx)<tol and abs(wy-hy)<tol: return key
        return None

    def _arrow_at(self,wx,wy,tol=8):
        for a in self.arrows:
            src=self._box_by_id(a.src_id); dst=self._box_by_id(a.dst_id)
            if not src or not dst: continue
            x1,y1=src.edge_point(*dst.center()); x2,y2=dst.edge_point(*src.center())
            dx,dy=x2-x1,y2-y1; length=math.hypot(dx,dy)
            if length==0: continue
            t=max(0,min(1,((wx-x1)*dx+(wy-y1)*dy)/length**2))
            px,py=x1+t*dx,y1+t*dy
            if math.hypot(wx-px,wy-py)<tol/self.zoom: return a
        return None

    def _floattext_at(self,wx,wy,tol=22):
        for ft in reversed(self.floattexts):
            if abs(ft.x-wx)<tol and abs(ft.y-wy)<tol: return ft
        return None

    def _box_by_id(self,bid):
        for b in self.boxes:
            if b.id==bid: return b
        return None

    # ═══ EVENTS ═══════════════════════════════════════════════════════════════

    def _bind_events(self):
        c=self.canvas
        c.bind("<Button-1>",        self._on_click)
        c.bind("<B1-Motion>",       self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_dblclick)
        c.bind("<Button-2>",        self._on_pan_start)
        c.bind("<B2-Motion>",       self._on_pan)
        c.bind("<Button-3>",        self._on_right_click)
        c.bind("<Button-4>",        lambda e:self._zoom(1.1,e))
        c.bind("<Button-5>",        lambda e:self._zoom(0.9,e))
        c.bind("<MouseWheel>",      self._on_mousewheel)
        self.root.bind("<Control-s>",lambda e:self._save())
        self.root.bind("<Control-o>",lambda e:self._load())
        self.root.bind("<Control-z>",lambda e:self._undo())
        self.root.bind("<Control-a>",lambda e:self._select_all_boxes())
        self.root.bind("<Control-c>",lambda e:self._copy())
        self.root.bind("<Control-v>",lambda e:self._paste())
        self.root.bind("<Delete>",   lambda e:self._delete_selected())
        self.root.bind("<Escape>",   lambda e:self._escape())
        self.root.bind("<s>",        lambda e:self.snap_enabled.set(not self.snap_enabled.get()))
        self.root.bind("<o>",        lambda e:self.ortho_enabled.set(not self.ortho_enabled.get()))

    def _on_click(self,event):
        wx,wy=self._to_world(event.x,event.y)
        shift=(event.state & 0x0001)!=0

        if self.mode=="pan":
            self._pan_start=(event.x,event.y); return

        if self.mode=="shape":
            self._push_undo()
            shape=self._pending_shape or "rect"
            sizes={"circle":(80,80),"ellipse":(120,70),"diamond":(120,80),
                   "triangle":(100,80),"hexagon":(100,80),"oval":(120,60),
                   "actor":(60,100),"cylinder":(100,80)}
            w,h=sizes.get(shape,(160,70))
            sx,sy=self._snap(wx-w//2),self._snap(wy-h//2)
            b=Box(sx,sy,w,h,shape.capitalize(),self.new_color.get(),shape)
            self.boxes.append(b); self.selected=b
            self.selected_items={b.id}; self._update_sel_info(); self._draw_all()
            return

        if self.mode=="text":
            self._push_undo()
            ft=FloatText(wx,wy); self.floattexts.append(ft)
            self._draw_all(); self._edit_floattext(ft); return

        if self.mode=="arrow":
            hit=self._box_at(wx,wy)
            if hit:
                if self.arrow_src is None:
                    self.arrow_src=hit; self.selected=hit
                    self.status_var.set(f"Arrow  •  Now click TARGET  (source: {hit.label[:25]})")
                    self._draw_all()
                else:
                    if hit.id!=self.arrow_src.id:
                        self._push_undo()
                        a=Arrow(self.arrow_src.id,hit.id,"",
                                self.new_line_style.get(),self.new_head_style.get(),
                                self.ortho_enabled.get())
                        self.arrows.append(a)
                    self.arrow_src=None; self.selected=None
                    self.status_var.set("Arrow  •  Click SOURCE → TARGET")
                    self._draw_all()
            return

        if self.mode=="select":
            # Resize handle check
            if isinstance(self.selected,Box):
                h_key=self._handle_at(self.selected,wx,wy)
                if h_key:
                    b=self.selected
                    self._resize_handle=h_key
                    self._resize_origin=(b.x,b.y,b.w,b.h,wx,wy); return

            hit=(self._box_at(wx,wy) or self._arrow_at(wx,wy) or self._floattext_at(wx,wy))
            if hit:
                if shift:
                    if hit.id in self.selected_items: self.selected_items.discard(hit.id)
                    else: self.selected_items.add(hit.id)
                    self.selected=hit
                else:
                    if hit.id not in self.selected_items:
                        self.selected_items={hit.id}
                    self.selected=hit
                # Set up drag
                self._drag_start=(wx,wy); self._drag_obj=hit
                self._drag_origin=((hit.x,hit.y) if isinstance(hit,(Box,FloatText)) else None)
                # Multi-drag origins
                self._drag_origins={b.id:(b.x,b.y)
                                    for b in self.boxes if b.id in self.selected_items}
            else:
                if not shift:
                    self.selected=None; self.selected_items.clear()
                # Start rubber-band
                self._rband_start=(event.x,event.y)
            self._update_sel_info(); self._draw_all()

    def _on_drag(self,event):
        wx,wy=self._to_world(event.x,event.y)

        if self.mode=="pan" and self._pan_start:
            dx=event.x-self._pan_start[0]; dy=event.y-self._pan_start[1]
            self.offset_x+=dx; self.offset_y+=dy; self._pan_start=(event.x,event.y)
            self._draw_all(); return

        # Rubber-band selection
        if self.mode=="select" and self._rband_start and not self._drag_obj:
            self._rband_rect=(self._rband_start[0],self._rband_start[1],event.x,event.y)
            # Highlight boxes inside band
            x1,y1=self._to_world(*self._rband_start); x2,y2=wx,wy
            rx1,rx2=min(x1,x2),max(x1,x2); ry1,ry2=min(y1,y2),max(y1,y2)
            self.selected_items={b.id for b in self.boxes
                                 if b.x<rx2 and b.x+b.w>rx1 and b.y<ry2 and b.y+b.h>ry1}
            self._draw_all(); return

        # Resize
        if self.mode=="select" and self._resize_handle and isinstance(self.selected,Box):
            ox,oy,ow,oh,sx,sy=self._resize_origin; dx,dy=wx-sx,wy-sy; b=self.selected; MIN=30
            if "e" in self._resize_handle: b.w=max(MIN,self._snap(ow+dx)-b.x+b.x)
            if "s" in self._resize_handle: b.h=max(MIN,self._snap(oh+dy)-b.y+b.y)
            if "w" in self._resize_handle:
                nw=max(MIN,ow-dx); b.x=self._snap(ox+(ow-nw)); b.w=nw
            if "n" in self._resize_handle:
                nh=max(MIN,oh-dy); b.y=self._snap(oy+(oh-nh)); b.h=nh
            self._update_sel_info(); self._draw_all(); return

        # Move (single or multi)
        if self.mode=="select" and self._drag_start and self._drag_obj:
            dxw=wx-self._drag_start[0]; dyw=wy-self._drag_start[1]
            if len(self.selected_items)>1:
                for b in self.boxes:
                    if b.id in self._drag_origins:
                        ox,oy=self._drag_origins[b.id]
                        b.x=self._snap(ox+dxw); b.y=self._snap(oy+dyw)
            else:
                obj=self._drag_obj
                if isinstance(obj,(Box,FloatText)):
                    ox,oy=self._drag_origin
                    obj.x=self._snap(ox+dxw); obj.y=self._snap(oy+dyw)
            self._update_sel_info(); self._draw_all()

    def _on_release(self,event):
        if self._drag_obj or self._resize_handle: self._push_undo()
        if self._rband_rect:
            # Finalize rubber-band
            self._rband_rect=None; self._rband_start=None
            if self.selected_items:
                self.selected=next((b for b in self.boxes if b.id in self.selected_items),None)
            self._update_sel_info(); self._draw_all(); return
        self._drag_obj=None; self._drag_start=None
        self._resize_handle=None; self._resize_origin=None
        self._rband_start=None; self._rband_rect=None
        self._pan_start=None

    def _on_dblclick(self,event):
        wx,wy=self._to_world(event.x,event.y)
        hit=(self._box_at(wx,wy) or self._arrow_at(wx,wy) or self._floattext_at(wx,wy))
        if isinstance(hit,Box): self._edit_box_label(hit)
        elif isinstance(hit,Arrow): self._edit_arrow_label(hit)
        elif isinstance(hit,FloatText): self._edit_floattext(hit)

    def _on_pan_start(self,e): self._pan_start=(e.x,e.y)
    def _on_pan(self,e):
        if self._pan_start:
            dx=e.x-self._pan_start[0]; dy=e.y-self._pan_start[1]
            self.offset_x+=dx; self.offset_y+=dy; self._pan_start=(e.x,e.y)
            self._draw_all()

    def _on_right_click(self,event):
        wx,wy=self._to_world(event.x,event.y)
        hit=(self._box_at(wx,wy) or self._arrow_at(wx,wy) or self._floattext_at(wx,wy))
        if hit:
            self.selected=hit; self.selected_items={hit.id}
            self._update_sel_info(); self._draw_all()
        self._show_context_menu(event,hit)

    def _show_context_menu(self,event,hit):
        menu=tk.Menu(self.root,tearoff=0,bg=SURFACE,fg=TEXT_LIGHT,
                     activebackground=ACCENT,activeforeground="white",
                     font=("Segoe UI",10))
        if hit:
            menu.add_command(label="✏  Edit label",    command=self._edit_selected)
            if isinstance(hit,Box):
                menu.add_command(label="🎨  Change color", command=self._change_color)
                menu.add_command(label="◈  Change shape",  command=self._change_shape)
            menu.add_separator()
            menu.add_command(label="📋  Copy",          command=self._copy)
            menu.add_command(label="🗑  Delete",        command=self._delete_selected)
        else:
            menu.add_command(label="📌  Paste",         command=self._paste)
            menu.add_command(label="🧹  Clear canvas",  command=self._clear)
        menu.add_separator()
        menu.add_command(label="💾  Save diagram",  command=self._save)
        menu.add_command(label="✦  Export SVG",     command=self._export_svg)
        menu.add_command(label="🔍  Analyse code",  command=self._analyse_code)
        try: menu.tk_popup(event.x_root,event.y_root)
        finally: menu.grab_release()

    def _on_mousewheel(self,e):
        self._zoom(1.1 if e.delta>0 else 0.9,e)

    def _zoom(self,factor,event=None):
        old=self.zoom; self.zoom=max(0.1,min(8.0,self.zoom*factor))
        if event:
            cx,cy=event.x,event.y
            self.offset_x=cx-(cx-self.offset_x)*(self.zoom/old)
            self.offset_y=cy-(cy-self.offset_y)*(self.zoom/old)
        self.zoom_var.set(f"{int(self.zoom*100)}%")
        self._draw_all()

    def _escape(self):
        self.arrow_src=None; self.selected=None; self.selected_items.clear()
        self._pending_shape=None; self._rband_rect=None; self._rband_start=None
        for k,(frame,btn,cv) in self.pal_btns.items():
            frame.config(bg=SURFACE3); btn.config(bg=SURFACE3,fg=TEXT_MUTED)
        if self.mode not in self.mode_btns: self.set_mode("select")
        self._update_sel_info(); self._draw_all()

    # ═══ DRAWING ══════════════════════════════════════════════════════════════

    def _draw_all(self):
        c=self.canvas; c.delete("all")
        self._draw_grid()
        for a in self.arrows: self._draw_arrow(a)
        for b in self.boxes:  self._draw_box(b)
        for ft in self.floattexts: self._draw_floattext(ft)
        # Multi-select highlight
        for b in self.boxes:
            if b.id in self.selected_items and b is not self.selected:
                x1,y1=self._to_canvas(b.x,b.y); x2,y2=self._to_canvas(b.x+b.w,b.y+b.h)
                c.create_rectangle(x1-2,y1-2,x2+2,y2+2,outline=RBAND_COL,width=2,dash=(4,3))
        if isinstance(self.selected,Box): self._draw_handles(self.selected)
        # Rubber-band rect
        if self._rband_rect:
            x1,y1,x2,y2=self._rband_rect
            c.create_rectangle(x1,y1,x2,y2,outline=RBAND_COL,fill=RBAND_COL,
                               stipple="gray12",dash=(4,3))
        if self.mode=="arrow" and self.arrow_src:
            cx,cy=self._to_canvas(*self.arrow_src.center())
            c.create_oval(cx-7,cy-7,cx+7,cy+7,fill=SEL_COL,outline="")
        if self.minimap_enabled.get(): self._draw_minimap()

    def _draw_grid(self):
        c=self.canvas; w=c.winfo_width() or 1400; h=c.winfo_height() or 800
        sp=GRID_SIZE*self.zoom; ox=self.offset_x%sp; oy=self.offset_y%sp
        gc=SNAP_COL if self.snap_enabled.get() else GRID_COL
        x=ox
        while x<w: c.create_line(x,0,x,h,fill=gc,width=1); x+=sp
        y=oy
        while y<h: c.create_line(0,y,w,y,fill=gc,width=1); y+=sp

    def _draw_box(self,box):
        c=self.canvas
        x1,y1=self._to_canvas(box.x,box.y); x2,y2=self._to_canvas(box.x+box.w,box.y+box.h)
        fill,border=BOX_COLORS.get(box.color,("#2e3a5c","#5a7ec8"))
        is_sel=(self.selected is box or (self.mode=="arrow" and self.arrow_src is box))
        bc=SEL_COL if is_sel else border; lw=2 if is_sel else 1
        fs=max(7,int(10*self.zoom)); W=x2-x1; H=y2-y1; cx=(x1+x2)/2; cy=(y1+y2)/2
        s=box.shape
        if s=="rect":
            c.create_rectangle(x1+3,y1+3,x2+3,y2+3,fill="#111122",outline="")
            c.create_rectangle(x1,y1,x2,y2,fill=fill,outline="")
            bar=max(3,H*0.06); c.create_rectangle(x1,y1,x2,y1+bar,fill=border,outline="")
            c.create_rectangle(x1,y1,x2,y2,fill="",outline=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W-10,justify="center")
        elif s=="roundrect":
            r=min(10*self.zoom,W/4,H/4)
            c.create_rectangle(x1+3,y1+3,x2+3,y2+3,fill="#111122",outline="")
            self._rounded_rect(c,x1,y1,x2,y2,r,fill=fill,outline=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W-10,justify="center")
        elif s in("circle","ellipse","oval"):
            c.create_oval(x1,y1,x2,y2,fill=fill,outline=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W-12,justify="center")
        elif s=="diamond":
            c.create_polygon(cx,y1,x2,cy,cx,y2,x1,cy,fill=fill,outline=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W*0.6,justify="center")
        elif s=="triangle":
            c.create_polygon(cx,y1,x2,y2,x1,y2,fill=fill,outline=bc,width=lw)
            c.create_text(cx,y1+(y2-y1)*0.6,text=box.label,fill=TEXT_LIGHT,
                          font=("Consolas",fs),anchor="center",width=W-10,justify="center")
        elif s=="hexagon":
            pts=[]
            for i in range(6):
                a=math.radians(60*i-30); pts+=[cx+(W/2)*math.cos(a),cy+(H/2)*math.sin(a)]
            c.create_polygon(pts,fill=fill,outline=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W*0.7,justify="center")
        elif s=="parallelogram":
            sk=min(20*self.zoom,W*0.2)
            c.create_polygon(x1+sk,y1,x2,y1,x2-sk,y2,x1,y2,fill=fill,outline=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W-sk*2-4,justify="center")
        elif s=="note":
            fold=min(16*self.zoom,W*0.2)
            c.create_polygon(x1,y1,x2-fold,y1,x2,y1+fold,x2,y2,x1,y2,fill=fill,outline=bc,width=lw)
            c.create_line(x2-fold,y1,x2-fold,y1+fold,x2,y1+fold,fill=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W-fold-4,justify="center")
        elif s=="cylinder":
            ry=min(14*self.zoom,H*0.2)
            c.create_rectangle(x1,y1+ry,x2,y2-ry,fill=fill,outline="")
            c.create_oval(x1,y1,x2,y1+ry*2,fill=fill,outline=bc,width=lw)
            c.create_oval(x1,y2-ry*2,x2,y2,fill=fill,outline=bc,width=lw)
            c.create_line(x1,y1+ry,x1,y2-ry,fill=bc,width=lw)
            c.create_line(x2,y1+ry,x2,y2-ry,fill=bc,width=lw)
            c.create_text(cx,cy,text=box.label,fill=TEXT_LIGHT,font=("Consolas",fs),
                          anchor="center",width=W-8,justify="center")
        elif s=="actor":
            r=min(12*self.zoom,H*0.15)
            c.create_oval(cx-r,y1,cx+r,y1+r*2,fill=fill,outline=bc,width=lw)
            by=y1+r*2+(H*0.25); ay=y1+r*2+(H*0.1)
            c.create_line(cx,y1+r*2,cx,by,fill=bc,width=lw)
            c.create_line(x1+4,ay,x2-4,ay,fill=bc,width=lw)
            c.create_line(cx,by,x1+4,y2-4,fill=bc,width=lw)
            c.create_line(cx,by,x2-4,y2-4,fill=bc,width=lw)
            if box.label: c.create_text(cx,y2,text=box.label,fill=TEXT_LIGHT,
                                        font=("Segoe UI",fs),anchor="s",width=W)

    def _rounded_rect(self,c,x1,y1,x2,y2,r,**kw):
        pts=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        c.create_polygon(pts,smooth=True,**kw)

    def _draw_handles(self,box):
        c=self.canvas
        for key,(hx,hy) in box.handle_rects().items():
            cx,cy=self._to_canvas(hx,hy); r=self.HANDLE_R
            c.create_rectangle(cx-r,cy-r,cx+r,cy+r,fill=HANDLE_COL,outline="white",width=1)

    def _draw_arrow(self,arrow):
        c=self.canvas
        src=self._box_by_id(arrow.src_id); dst=self._box_by_id(arrow.dst_id)
        if not src or not dst: return
        tx,ty=dst.center(); sx,sy=src.center()
        ex1,ey1=src.edge_point(tx,ty); ex2,ey2=dst.edge_point(sx,sy)
        cx1,cy1=self._to_canvas(ex1,ey1); cx2,cy2=self._to_canvas(ex2,ey2)
        is_sel=(self.selected is arrow)
        color=SEL_COL if is_sel else ARROW_COL; lw=2 if is_sel else 1.5
        dash=(6,4) if getattr(arrow,"line_style","solid")=="dashed" else ()
        head=getattr(arrow,"head_style","open")
        ortho=getattr(arrow,"orthogonal",False)

        # Orthogonal routing: L-shaped via midpoint
        if ortho:
            mx=(cx1+cx2)/2
            pts=[cx1,cy1, mx,cy1, mx,cy2, cx2,cy2]
            if head=="none":
                c.create_line(*pts,fill=color,width=lw,dash=dash)
            elif head=="inheritance":
                c.create_line(*pts,fill=color,width=lw,dash=dash)
                self._tri_head(c,mx,cy2,cx2,cy2,color,False)
            elif head=="filled":
                c.create_line(*pts,fill=color,width=lw,dash=dash,
                              arrow=tk.LAST,arrowshape=(12*self.zoom,14*self.zoom,5*self.zoom))
            elif head in("diamond","odiamond"):
                c.create_line(*pts,fill=color,width=lw,dash=dash)
                self._dia_head(c,mx,cy2,cx2,cy2,color,head=="odiamond")
            else:
                c.create_line(*pts,fill=color,width=lw,dash=dash,
                              arrow=tk.LAST,arrowshape=(10*self.zoom,12*self.zoom,4*self.zoom))
        else:
            if head=="none":
                c.create_line(cx1,cy1,cx2,cy2,fill=color,width=lw,dash=dash)
            elif head=="inheritance":
                c.create_line(cx1,cy1,cx2,cy2,fill=color,width=lw,dash=dash)
                self._tri_head(c,cx1,cy1,cx2,cy2,color,False)
            elif head=="filled":
                c.create_line(cx1,cy1,cx2,cy2,fill=color,width=lw,dash=dash,
                              arrow=tk.LAST,arrowshape=(12*self.zoom,14*self.zoom,5*self.zoom))
            elif head in("diamond","odiamond"):
                c.create_line(cx1,cy1,cx2,cy2,fill=color,width=lw,dash=dash)
                self._dia_head(c,cx1,cy1,cx2,cy2,color,head=="odiamond")
            else:
                c.create_line(cx1,cy1,cx2,cy2,fill=color,width=lw,dash=dash,
                              arrow=tk.LAST,arrowshape=(10*self.zoom,12*self.zoom,4*self.zoom))

        if arrow.label:
            mx2,my2=(cx1+cx2)/2,(cy1+cy2)/2
            fs=max(6,int(9*self.zoom))
            c.create_text(mx2,my2-10*self.zoom,text=arrow.label,fill=ACCENT2,font=("Segoe UI",fs))

    def _tri_head(self,c,x1,y1,x2,y2,color,filled):
        a=math.atan2(y2-y1,x2-x1); s=14*self.zoom; sp=math.radians(25)
        p1x=x2-s*math.cos(a-sp); p1y=y2-s*math.sin(a-sp)
        p2x=x2-s*math.cos(a+sp); p2y=y2-s*math.sin(a+sp)
        c.create_polygon(x2,y2,p1x,p1y,p2x,p2y,fill=color if filled else BG,outline=color,width=1.5)

    def _dia_head(self,c,x1,y1,x2,y2,color,open_):
        a=math.atan2(y2-y1,x2-x1); s=14*self.zoom
        tx,ty=x2,y2; bx=tx-s*math.cos(a); by=ty-s*math.sin(a)
        mx=tx-(s/2)*math.cos(a); my=ty-(s/2)*math.sin(a)
        p=a+math.pi/2; w=s*0.45
        lx=mx+w*math.cos(p); ly=my+w*math.sin(p)
        rx=mx-w*math.cos(p); ry=my-w*math.sin(p)
        c.create_polygon(tx,ty,lx,ly,bx,by,rx,ry,fill=BG if open_ else color,outline=color,width=1.5)

    def _draw_floattext(self,ft):
        c=self.canvas; cx,cy=self._to_canvas(ft.x,ft.y)
        is_sel=(self.selected is ft); fs=max(8,int(11*self.zoom))
        fonts={"heading":("Segoe UI",fs+2,"bold"),"note":("Segoe UI",fs,"italic"),"normal":("Segoe UI",fs)}
        font=fonts.get(getattr(ft,"style","normal"),("Segoe UI",fs))
        c.create_text(cx,cy,text=ft.text,fill=SEL_COL if is_sel else ACCENT2,font=font,anchor="center")
        if is_sel: c.create_oval(cx-8,cy-8,cx+8,cy+8,outline=SEL_COL,width=1,fill="")

    def _draw_minimap(self):
        c=self.canvas; cw=c.winfo_width() or 1; ch=c.winfo_height() or 1
        if cw<200 or ch<200: return
        mw,mh=160,110; mx=cw-mw-10; my=ch-mh-10
        c.create_rectangle(mx,my,mx+mw,my+mh,fill="#1a1a2a",outline=ACCENT2,width=1)
        if not self.boxes: return
        all_x=[b.x for b in self.boxes]+[b.x+b.w for b in self.boxes]
        all_y=[b.y for b in self.boxes]+[b.y+b.h for b in self.boxes]
        if not all_x: return
        wxmin,wxmax=min(all_x),max(all_x); wymin,wymax=min(all_y),max(all_y)
        ww=max(wxmax-wxmin,1); wh=max(wymax-wymin,1)
        scale=min((mw-10)/ww,(mh-10)/wh)
        ox=mx+5-(wxmin*scale); oy=my+5-(wymin*scale)
        for b in self.boxes:
            fill,border=BOX_COLORS.get(b.color,("#2e3a5c","#5a7ec8"))
            bx1=ox+b.x*scale; by1=oy+b.y*scale
            bx2=bx1+b.w*scale; by2=by1+b.h*scale
            c.create_rectangle(bx1,by1,bx2,by2,fill=fill,outline=border,width=0.5)
        # Viewport rectangle
        vx1,vy1=self._to_world(0,0); vx2,vy2=self._to_world(cw,ch)
        vbx1=ox+vx1*scale; vby1=oy+vy1*scale
        vbx2=ox+vx2*scale; vby2=oy+vy2*scale
        c.create_rectangle(vbx1,vby1,vbx2,vby2,outline=SEL_COL,width=1,fill="",dash=(3,2))
        c.create_text(mx+mw//2,my+2,text="MAP",fill=TEXT_MUTED,font=("Segoe UI",6,"bold"),anchor="n")

    # ═══ EDIT HELPERS ═════════════════════════════════════════════════════════

    def _update_sel_info(self):
        n=len(self.selected_items)
        if n>1:
            self.sel_info.config(text=f"{n} items selected")
        elif isinstance(self.selected,Box):
            self.sel_info.config(text=f"Box: {self.selected.shape}\nColor: {self.selected.color}\nW:{int(self.selected.w)} H:{int(self.selected.h)}\nX:{int(self.selected.x)} Y:{int(self.selected.y)}")
        elif isinstance(self.selected,Arrow):
            self.sel_info.config(text=f"Arrow\n{self.selected.line_style} / {self.selected.head_style}")
        elif isinstance(self.selected,FloatText):
            self.sel_info.config(text=f"Text: {self.selected.text[:30]}")
        else:
            self.sel_info.config(text="Nothing selected")

    def _edit_box_label(self,box):
        dlg=tk.Toplevel(self.root); dlg.title("Edit Label")
        dlg.configure(bg=SURFACE); dlg.geometry("440x260"); dlg.grab_set()
        tk.Label(dlg,text="Label (Ctrl+Enter to apply):",bg=SURFACE,fg=TEXT_LIGHT,font=("Segoe UI",10),pady=6).pack()
        txt=tk.Text(dlg,bg=BG,fg=TEXT_LIGHT,font=("Consolas",10),insertbackground=TEXT_LIGHT,wrap="word",height=8,padx=8,pady=5)
        txt.pack(fill="both",expand=True,padx=12); txt.insert("1.0",box.label); txt.focus_set()
        def apply(): box.label=txt.get("1.0","end-1c"); self._draw_all(); dlg.destroy()
        tk.Button(dlg,text="Apply",bg=ACCENT,fg="white",relief="flat",padx=14,pady=5,cursor="hand2",command=apply).pack(pady=6)
        dlg.bind("<Control-Return>",lambda e:apply())

    def _edit_arrow_label(self,arrow):
        new=simpledialog.askstring("Arrow Label","Label:",initialvalue=arrow.label,parent=self.root)
        if new is not None: arrow.label=new; self._draw_all()

    def _edit_floattext(self,ft):
        new=simpledialog.askstring("Text","Text:",initialvalue=ft.text,parent=self.root)
        if new is not None: ft.text=new; self._draw_all()

    def _edit_selected(self):
        if isinstance(self.selected,Box): self._edit_box_label(self.selected)
        elif isinstance(self.selected,Arrow): self._edit_arrow_label(self.selected)
        elif isinstance(self.selected,FloatText): self._edit_floattext(self.selected)

    def _change_color(self):
        if not isinstance(self.selected,Box): return
        dlg=tk.Toplevel(self.root); dlg.title("Color"); dlg.configure(bg=SURFACE); dlg.grab_set()
        chosen=tk.StringVar(value=self.selected.color)
        for name,(fill,border) in BOX_COLORS.items():
            row=tk.Frame(dlg,bg=SURFACE); row.pack(fill="x",padx=14,pady=2)
            tk.Radiobutton(row,text=name,variable=chosen,value=name,bg=SURFACE,fg=TEXT_LIGHT,
                           selectcolor=fill,activebackground=SURFACE,font=("Segoe UI",10)).pack(side="left")
            tk.Frame(row,bg=fill,width=40,height=14).pack(side="right",padx=4)
        def apply(): self.selected.color=chosen.get(); self._draw_all(); dlg.destroy()
        tk.Button(dlg,text="Apply",bg=ACCENT,fg="white",relief="flat",padx=18,pady=5,cursor="hand2",command=apply).pack(pady=8)

    def _change_shape(self):
        if not isinstance(self.selected,Box): return
        dlg=tk.Toplevel(self.root); dlg.title("Shape"); dlg.configure(bg=SURFACE); dlg.grab_set()
        chosen=tk.StringVar(value=getattr(self.selected,"shape","rect"))
        for key,label,sym in SHAPE_PALETTE:
            tk.Radiobutton(dlg,text=f"{sym}  {label}",variable=chosen,value=key,
                           bg=SURFACE,fg=TEXT_LIGHT,selectcolor=ACCENT,activebackground=SURFACE,
                           font=("Segoe UI",10),anchor="w").pack(fill="x",padx=14,pady=1)
        def apply(): self.selected.shape=chosen.get(); self._draw_all(); dlg.destroy()
        tk.Button(dlg,text="Apply",bg=ACCENT,fg="white",relief="flat",padx=18,pady=5,cursor="hand2",command=apply).pack(pady=8)

    # ═══ COPY / PASTE ═════════════════════════════════════════════════════════

    def _copy(self):
        selected_boxes=[b for b in self.boxes if b.id in self.selected_items]
        if not selected_boxes and isinstance(self.selected,Box):
            selected_boxes=[self.selected]
        self.clipboard=[copy.deepcopy(b.to_dict()) for b in selected_boxes]
        self.status_var.set(f"Copied {len(self.clipboard)} box(es)  •  Ctrl+V to paste")

    def _paste(self):
        if not self.clipboard: return
        self._push_undo()
        new_ids={}; offset=30
        for bd in self.clipboard:
            Box._id+=1; new_id=Box._id
            new_ids[bd["id"]]=new_id
            nb=Box(bd["x"]+offset,bd["y"]+offset,bd["w"],bd["h"],
                   bd["label"],bd.get("color","Blue"),bd.get("shape","rect"))
            nb.id=new_id; self.boxes.append(nb)
        self.selected_items={nid for nid in new_ids.values()}
        self.selected=self.boxes[-1] if self.boxes else None
        self._update_sel_info(); self._draw_all()
        self.status_var.set(f"Pasted {len(self.clipboard)} box(es)")

    # ═══ UNDO ═════════════════════════════════════════════════════════════════

    def _push_undo(self):
        self.undo_stack.append(self._serialize())
        if len(self.undo_stack)>60: self.undo_stack.pop(0)

    def _undo(self):
        if not self.undo_stack: self.status_var.set("Nothing to undo"); return
        self._deserialize(self.undo_stack.pop()); self._draw_all()
        self.status_var.set("Undone")

    def _delete_selected(self):
        if not self.selected: return
        self._push_undo()
        ids=self.selected_items if self.selected_items else {self.selected.id}
        if any(isinstance(b,Box) and b.id in ids for b in self.boxes):
            self.boxes=[b for b in self.boxes if b.id not in ids]
            self.arrows=[a for a in self.arrows if a.src_id not in ids and a.dst_id not in ids]
        elif isinstance(self.selected,Arrow):
            self.arrows=[a for a in self.arrows if a.id!=self.selected.id]
        elif isinstance(self.selected,FloatText):
            self.floattexts=[ft for ft in self.floattexts if ft.id!=self.selected.id]
        self.selected=None; self.selected_items.clear()
        self._update_sel_info(); self._draw_all()

    def _select_all_boxes(self):
        self.selected_items={b.id for b in self.boxes}
        if self.boxes: self.selected=self.boxes[-1]
        self._update_sel_info(); self._draw_all()
        self.status_var.set(f"Selected all {len(self.boxes)} boxes")

    def _clear(self):
        if messagebox.askyesno("Clear","Delete everything?"):
            self._push_undo(); self.boxes.clear(); self.arrows.clear(); self.floattexts.clear()
            self.selected=None; self.selected_items.clear(); self._draw_all()

    def _reset_view(self):
        self.offset_x=40; self.offset_y=40; self.zoom=1.0; self.zoom_var.set("100%"); self._draw_all()

    # ═══ CODE ANALYSIS ════════════════════════════════════════════════════════

    def _analyse_code(self):
        path=filedialog.askopenfilename(
            title="Select .py or .java file (or Cancel to choose folder)",
            filetypes=[("Python","*.py"),("Java","*.java"),("All","*.*")])
        if not path:
            path=filedialog.askdirectory(title="Select folder with .py / .java files")
        if not path: return

        # Add the tool's directory to sys.path so code_analyzer can find code_layout
        tool_dir=os.path.dirname(os.path.abspath(__file__))
        if tool_dir not in sys.path: sys.path.insert(0,tool_dir)

        try:
            import importlib
            self.status_var.set(f"Analysing: {os.path.basename(path)} …")
            self.root.update()

            # Auto-detect Spring Boot project
            p = __import__("pathlib").Path(path)
            is_spring = (
                p.is_dir() and (
                    any(p.rglob("pom.xml")) or any(p.rglob("build.gradle"))
                ) and any(p.rglob("*.java"))
            )
            if is_spring:
                import spring_analyzer
                importlib.reload(spring_analyzer)
                data = spring_analyzer.analyze_spring(path)
                self.status_var.set(f"Spring Boot project detected — analysing layers…")
                self.root.update()
            else:
                import code_analyzer
                importlib.reload(code_analyzer)
                data = code_analyzer.analyze(path)
        except Exception as e:
            messagebox.showerror("Analysis Error",
                f"Could not analyse the file:\n\n{e}\n\n"
                "Make sure code_analyzer.py and code_layout.py\n"
                "are in the same folder as diagram_tool_v4.py")
            return

        if not data.get("boxes"):
            messagebox.showinfo("No Classes Found",
                "No classes were detected in the selected file(s).\n"
                "Make sure the file contains class definitions.")
            return

        if (self.boxes or self.arrows) and not messagebox.askyesno(
                "Load Analysis","Replace current canvas with analysis result?"):
            return

        self._push_undo()
        Box._id=Arrow._id=FloatText._id=0
        self._deserialize(data)
        self.offset_x=40; self.offset_y=60; self.zoom=0.9; self.zoom_var.set("90%")
        self._draw_all()
        n_cls=len(self.boxes); n_rel=len(self.arrows)
        self.status_var.set(
            f"Analysis complete  •  {n_cls} classes · {n_rel} relationships  •  "
            f"Double-click any box to edit  •  Drag to rearrange")

    # ═══ TEMPLATES ════════════════════════════════════════════════════════════

    def _show_template_panel(self):
        dlg=tk.Toplevel(self.root); dlg.title("📐 Templates")
        dlg.configure(bg=BG); dlg.geometry("780x600"); dlg.resizable(True,True); dlg.grab_set()
        tk.Label(dlg,text="UML & GoF Design Pattern Templates",bg=BG,fg=TEXT_LIGHT,
                 font=("Segoe UI",14,"bold"),pady=10).pack()
        style=ttk.Style(); style.theme_use("clam")
        style.configure("TNotebook",background=BG,borderwidth=0)
        style.configure("TNotebook.Tab",background=SURFACE2,foreground=TEXT_MUTED,padding=[12,5],font=("Segoe UI",10))
        style.map("TNotebook.Tab",background=[("selected",ACCENT)],foreground=[("selected","white")])
        style.configure("TFrame",background=BG)
        nb=ttk.Notebook(dlg); nb.pack(fill="both",expand=True,padx=12,pady=4)
        cat_colors={"UML Diagrams":("#3aaaa0","#1e3d3a"),"GoF — Creational":("#7c6fcd","#3a2e5c"),
                    "GoF — Structural":("#3aaa6a","#1e3d2e"),"GoF — Behavioral":("#cc7744","#4a3020")}
        for category,patterns in TEMPLATES.items():
            frame=ttk.Frame(nb); nb.add(frame,text=category)
            cf=tk.Canvas(frame,bg=BG,highlightthickness=0)
            sb=tk.Scrollbar(frame,orient="vertical",command=cf.yview)
            cf.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y"); cf.pack(side="left",fill="both",expand=True)
            inner=tk.Frame(cf,bg=BG); cf.create_window((0,0),window=inner,anchor="nw")
            col=0; fg,bg=cat_colors.get(category,(ACCENT2,SURFACE2))
            for name,fn in patterns.items():
                card=tk.Frame(inner,bg=SURFACE,padx=10,pady=8,cursor="hand2")
                card.grid(row=col//2,column=col%2,padx=8,pady=6,sticky="nsew")
                tk.Label(card,text=category.upper(),bg=bg,fg=fg,font=("Segoe UI",7,"bold"),padx=5,pady=1).pack(anchor="w")
                tk.Label(card,text=name,bg=SURFACE,fg=TEXT_LIGHT,font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(3,1))
                tk.Button(card,text="Load →",bg=ACCENT,fg="white",relief="flat",padx=8,pady=3,cursor="hand2",
                          font=("Segoe UI",9,"bold"),
                          command=lambda f=fn,d=dlg:self._load_template(f,d)).pack(anchor="e",pady=(6,0))
                col+=1
            inner.update_idletasks(); cf.configure(scrollregion=cf.bbox("all"))
            inner.columnconfigure(0,weight=1); inner.columnconfigure(1,weight=1)
        tk.Button(dlg,text="Close",bg=SURFACE2,fg=TEXT_LIGHT,relief="flat",padx=18,pady=5,cursor="hand2",command=dlg.destroy).pack(pady=8)

    def _load_template(self,fn,dlg):
        if (self.boxes or self.arrows) and not messagebox.askyesno("Load Template","Replace current canvas?",parent=dlg): return
        self._push_undo(); Box._id=Arrow._id=FloatText._id=0
        self._deserialize(fn())
        self.offset_x=40; self.offset_y=40; self.zoom=1.0; self.zoom_var.set("100%")
        self._draw_all(); dlg.destroy()
        self.status_var.set("Template loaded  •  Double-click any element to edit")

    # ═══ SERIALISE ════════════════════════════════════════════════════════════

    def _serialize(self):
        return dict(boxes=[b.to_dict() for b in self.boxes],
                    arrows=[a.to_dict() for a in self.arrows],
                    floattexts=[ft.to_dict() for ft in self.floattexts])

    def _deserialize(self,data):
        self.boxes=[Box.from_dict(d) for d in data.get("boxes",[])]
        self.arrows=[Arrow.from_dict(d) for d in data.get("arrows",[])]
        self.floattexts=[FloatText.from_dict(d) for d in data.get("floattexts",[])]
        if self.boxes: Box._id=max(b.id for b in self.boxes)
        if self.arrows: Arrow._id=max(a.id for a in self.arrows)
        if self.floattexts: FloatText._id=max(ft.id for ft in self.floattexts)

    # ═══ FILE I/O ═════════════════════════════════════════════════════════════

    def _save(self):
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("Diagram JSON","*.json"),("All","*.*")],title="Save")
        if path:
            with open(path,"w") as f: json.dump(self._serialize(),f,indent=2)
            self.status_var.set(f"Saved → {os.path.basename(path)}")

    def _load(self):
        path=filedialog.askopenfilename(filetypes=[("Diagram JSON","*.json"),("All","*.*")],title="Open")
        if path:
            with open(path) as f: data=json.load(f)
            self._push_undo(); self._deserialize(data); self._draw_all()
            self.status_var.set(f"Loaded ← {os.path.basename(path)}")

    def _export_png(self):
        try: from PIL import ImageGrab
        except ImportError:
            messagebox.showinfo("PNG Export","pip install Pillow  for PNG export\nOr use Win+Shift+S"); return
        path=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")],title="Export PNG")
        if path:
            x=self.root.winfo_rootx()+self.canvas.winfo_x()
            y=self.root.winfo_rooty()+self.canvas.winfo_y()
            w=self.canvas.winfo_width(); h=self.canvas.winfo_height()
            from PIL import ImageGrab; ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(path)
            self.status_var.set(f"PNG → {os.path.basename(path)}")

    def _export_svg(self):
        path=filedialog.asksaveasfilename(defaultextension=".svg",filetypes=[("SVG","*.svg"),("All","*.*")],title="Export SVG")
        if not path: return
        cw=self.canvas.winfo_width() or 1200; ch=self.canvas.winfo_height() or 800
        lines=[]
        lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{cw}" height="{ch}" style="background:{BG}">')
        lines.append('<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                     '<path d="M2 1L8 5L2 9" fill="none" stroke="#a0b0e0" stroke-width="1.5"/></marker></defs>')
        # Arrows
        for a in self.arrows:
            src=self._box_by_id(a.src_id); dst=self._box_by_id(a.dst_id)
            if not src or not dst: continue
            ex1,ey1=src.edge_point(*dst.center()); ex2,ey2=dst.edge_point(*src.center())
            x1,y1=self._to_canvas(ex1,ey1); x2,y2=self._to_canvas(ex2,ey2)
            dash='stroke-dasharray="6,4"' if a.line_style=="dashed" else ""
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="#a0b0e0" stroke-width="1.5" {dash} marker-end="url(#arr)"/>')
            if a.label:
                mx,my=(x1+x2)/2,(y1+y2)/2
                lines.append(f'<text x="{mx:.1f}" y="{my-8:.1f}" text-anchor="middle" '
                             f'font-family="sans-serif" font-size="11" fill="#a89ee8">{a.label}</text>')
        # Boxes
        for b in self.boxes:
            x1,y1=self._to_canvas(b.x,b.y); x2,y2=self._to_canvas(b.x+b.w,b.y+b.h)
            fill,border=BOX_COLORS.get(b.color,("#2e3a5c","#5a7ec8"))
            cx=(x1+x2)/2; cy=(y1+y2)/2; W=x2-x1; H=y2-y1
            lines.append(f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{W:.1f}" height="{H:.1f}" '
                         f'rx="4" fill="{fill}" stroke="{border}" stroke-width="1"/>')
            for i,line in enumerate(b.label.split("\n")):
                ly=y1+18+(i*14)
                esc=line.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                lines.append(f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                             f'font-family="monospace" font-size="11" fill="#e0dff5">{esc}</text>')
        # Float texts
        for ft in self.floattexts:
            cx,cy=self._to_canvas(ft.x,ft.y)
            fs="13" if ft.style=="heading" else "11"
            fw="bold" if ft.style=="heading" else "normal"
            esc=ft.text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            lines.append(f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                         f'font-family="sans-serif" font-size="{fs}" font-weight="{fw}" fill="#a89ee8">{esc}</text>')
        lines.append("</svg>")
        with open(path,"w") as f: f.write("\n".join(lines))
        self.status_var.set(f"SVG → {os.path.basename(path)}")


# ═══ ENTRY POINT ══════════════════════════════════════════════════════════════

def main():
    root=tk.Tk(); root.title("DiagramTool v4.0")
    app=DiagramApp(root)
    Box._id=Arrow._id=FloatText._id=0
    data=tpl_observer(); app._deserialize(data); app._draw_all()
    app.status_var.set(
        "DiagramTool v4  •  NEW: 🔍 Analyse Code (.py/.java) → auto class diagram  •  "
        "Rubber-band multi-select  •  Ctrl+C/V copy-paste  •  S=snap  •  O=ortho arrows  •  ✦ SVG export")
    root.mainloop()

if __name__=="__main__":
    main()
