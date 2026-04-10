"""
DiagramTool v2.0 — Python Drawing Canvas with UML & GoF Templates
==================================================================
Usage:
  python diagram_tool_v2.py

Requirements: Python 3.x  (tkinter is built-in — no pip needed)
Optional    : pip install Pillow   (for PNG export)

ALL ORIGINAL FEATURES PRESERVED:
  Box / Arrow / Text / Select / Pan modes
  Zoom (scroll), Pan (middle-mouse), Undo (Ctrl+Z)
  Save / Load JSON, Export PNG
  Box colors, Arrow labels, Floating text, Grid

NEW — Templates menu (Templates button in toolbar):
  ┌─ UML Diagrams ──────────────────────────────────┐
  │  Class Diagram     Interface Diagram             │
  │  Sequence Diagram  Activity Diagram              │
  │  Workflow Diagram                                │
  ├─ GoF Design Patterns (all 23) ──────────────────┤
  │  CREATIONAL  : Abstract Factory, Builder,        │
  │                Factory Method, Prototype,        │
  │                Singleton                         │
  │  STRUCTURAL  : Adapter, Bridge, Composite,       │
  │                Decorator, Facade, Flyweight,     │
  │                Proxy                             │
  │  BEHAVIORAL  : Chain of Responsibility,          │
  │                Command, Interpreter, Iterator,   │
  │                Mediator, Memento, Observer,      │
  │                State, Strategy, Template Method, │
  │                Visitor                           │
  └──────────────────────────────────────────────────┘

Keyboard:
  Ctrl+S  Save    Ctrl+O  Open    Ctrl+Z  Undo
  Ctrl+A  Select all      Delete  Delete selected
  Escape  Deselect        Scroll  Zoom    Middle  Pan

Double-click any box or arrow to edit its label.
"""

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import json, math, os

# ═══════════════════════════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════════════════════════
BG          = "#1e1e2e"
SURFACE     = "#2a2a3e"
SURFACE2    = "#313145"
ACCENT      = "#7c6fcd"
ACCENT2     = "#a89ee8"
TEXT_LIGHT  = "#e0dff5"
TEXT_MUTED  = "#888aaa"
ARROW_COLOR = "#a0b0e0"
SEL_COLOR   = "#ffcc44"
GRID_COLOR  = "#252535"

BOX_COLORS = {
    "Blue":    ("#2e3a5c", "#5a7ec8"),
    "Green":   ("#1e3d2e", "#3aaa6a"),
    "Purple":  ("#3a2e5c", "#7c6fcd"),
    "Teal":    ("#1e3d3a", "#3aaaa0"),
    "Orange":  ("#4a3020", "#cc7744"),
    "Red":     ("#4a2020", "#cc4444"),
    "Gray":    ("#2e2e3e", "#666688"),
    "Yellow":  ("#3a3a1e", "#aaaa3a"),
    "Pink":    ("#3a1e3a", "#cc44cc"),
}

# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Box:
    _id = 0
    def __init__(self, x, y, w=160, h=60, label="Box", color="Blue", shape="rect"):
        Box._id += 1
        self.id    = Box._id
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.label = label
        self.color = color
        self.shape = shape   # rect | diamond | oval | note | actor | cylinder

    def center(self):
        return self.x + self.w / 2, self.y + self.h / 2

    def edge_point(self, tx, ty):
        cx, cy = self.center()
        dx, dy = tx - cx, ty - cy
        if dx == 0 and dy == 0:
            return cx, cy
        angle = math.atan2(dy, dx)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        hw, hh = self.w / 2, self.h / 2
        if self.shape == "diamond":
            # Rhombus edge
            if abs(cos_a) * hh + abs(sin_a) * hw == 0:
                return cx, cy
            scale = (hw * hh) / (abs(cos_a) * hh + abs(sin_a) * hw)
        elif self.shape == "oval":
            denom = math.hypot(cos_a / hw, sin_a / hh)
            scale = 1.0 / denom if denom else hw
        else:
            if abs(cos_a) * hh > abs(sin_a) * hw:
                scale = hw / abs(cos_a)
            else:
                scale = hh / abs(sin_a)
        return cx + cos_a * scale, cy + sin_a * scale

    def contains(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

    def to_dict(self):
        return dict(id=self.id, x=self.x, y=self.y, w=self.w, h=self.h,
                    label=self.label, color=self.color, shape=self.shape)

    @classmethod
    def from_dict(cls, d):
        b = cls(d["x"], d["y"], d["w"], d["h"],
                d["label"], d.get("color","Blue"), d.get("shape","rect"))
        b.id = d["id"]
        return b


class Arrow:
    _id = 0
    # line_style: solid | dashed | dotted
    # head_style: open | filled | empty | none | diamond | odiamond | inheritance
    def __init__(self, src_id, dst_id, label="",
                 line_style="solid", head_style="open"):
        Arrow._id += 1
        self.id         = Arrow._id
        self.src_id     = src_id
        self.dst_id     = dst_id
        self.label      = label
        self.line_style = line_style   # solid | dashed
        self.head_style = head_style   # open | filled | inheritance | diamond | odiamond | none

    def to_dict(self):
        return dict(id=self.id, src_id=self.src_id, dst_id=self.dst_id,
                    label=self.label, line_style=self.line_style,
                    head_style=self.head_style)

    @classmethod
    def from_dict(cls, d):
        a = cls(d["src_id"], d["dst_id"], d.get("label",""),
                d.get("line_style","solid"), d.get("head_style","open"))
        a.id = d["id"]
        return a


class FloatText:
    _id = 0
    def __init__(self, x, y, text="Label", style="normal"):
        FloatText._id += 1
        self.id    = FloatText._id
        self.x, self.y = x, y
        self.text  = text
        self.style = style  # normal | heading | note

    def to_dict(self):
        return dict(id=self.id, x=self.x, y=self.y, text=self.text, style=self.style)

    @classmethod
    def from_dict(cls, d):
        ft = cls(d["x"], d["y"], d["text"], d.get("style","normal"))
        ft.id = d["id"]
        return ft


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATES  — all 23 GoF patterns + 5 UML diagram types
# ═══════════════════════════════════════════════════════════════════════════════

def _b(x, y, w, h, label, color="Blue", shape="rect"):
    """Helper: create a Box dict."""
    Box._id += 1
    return dict(id=Box._id, x=x, y=y, w=w, h=h,
                label=label, color=color, shape=shape)

def _a(sid, did, label="", line_style="solid", head_style="open"):
    """Helper: create an Arrow dict referencing box ids directly."""
    Arrow._id += 1
    return dict(id=Arrow._id, src_id=sid, dst_id=did,
                label=label, line_style=line_style, head_style=head_style)

def _t(x, y, text, style="normal"):
    FloatText._id += 1
    return dict(id=FloatText._id, x=x, y=y, text=text, style=style)


# ─── Each template returns {"boxes":[], "arrows":[], "floattexts":[]} ─────────

def tpl_class_diagram():
    boxes, arrows, texts = [], [], []
    # Animal (base)
    an = _b(280, 60,  220, 100, "Animal\n──────────────\n- name: String\n- age: int\n──────────────\n+ speak(): void\n+ move(): void", "Purple")
    # Dog, Cat
    dg = _b(100, 260, 200,  90, "Dog\n──────────────\n- breed: String\n──────────────\n+ speak(): void\n+ fetch(): void", "Blue")
    ct = _b(480, 260, 200,  90, "Cat\n──────────────\n- indoor: bool\n──────────────\n+ speak(): void\n+ purr(): void", "Blue")
    # Owner
    ow = _b(280, 460, 220,  80, "Owner\n──────────────\n- name: String\n──────────────\n+ adopt(a:Animal)", "Green")
    boxes = [an, dg, ct, ow]
    arrows = [
        _a(dg["id"], an["id"], "", "solid", "inheritance"),
        _a(ct["id"], an["id"], "", "solid", "inheritance"),
        _a(ow["id"], an["id"], "owns  1..*", "solid", "open"),
    ]
    texts = [_t(390, 20, "Class Diagram — Inheritance & Association", "heading")]
    return dict(boxes=boxes, arrows=arrows, floattexts=texts)


def tpl_interface_diagram():
    boxes, arrows, texts = [], [], []
    iface  = _b(280,  60, 220, 80, "«interface»\nPaymentGateway\n──────────────\n+ charge(amount)\n+ refund(txId)", "Teal", "rect")
    cls1   = _b( 80, 240, 200, 80, "StripeGateway\n──────────────\n+ charge(amount)\n+ refund(txId)", "Blue")
    cls2   = _b(320, 240, 200, 80, "PayPalGateway\n──────────────\n+ charge(amount)\n+ refund(txId)", "Blue")
    cls3   = _b(560, 240, 200, 80, "RazorpayGateway\n──────────────\n+ charge(amount)\n+ refund(txId)", "Blue")
    client = _b(280, 420, 220, 70, "CheckoutService\n──────────────\n- gw: PaymentGateway\n+ process(cart)", "Green")
    boxes = [iface, cls1, cls2, cls3, client]
    arrows = [
        _a(cls1["id"], iface["id"], "implements", "dashed", "inheritance"),
        _a(cls2["id"], iface["id"], "implements", "dashed", "inheritance"),
        _a(cls3["id"], iface["id"], "implements", "dashed", "inheritance"),
        _a(client["id"], iface["id"], "uses", "dashed", "open"),
    ]
    texts = [_t(390, 20, "Interface Diagram — Implementation & Usage", "heading")]
    return dict(boxes=boxes, arrows=arrows, floattexts=texts)


def tpl_sequence_diagram():
    boxes, arrows, texts = [], [], []
    # Lifeline headers
    u  = _b( 60,  60, 120, 50, "User",        "Gray",   "rect")
    ui = _b(240,  60, 120, 50, "UI Layer",    "Blue",   "rect")
    svc= _b(420,  60, 120, 50, "Service",     "Purple", "rect")
    db = _b(600,  60, 120, 50, "Database",    "Teal",   "rect")
    # Lifeline bars (thin tall boxes)
    lb_u  = _b(115, 110,  10, 400, "", "Gray",   "rect")
    lb_ui = _b(295, 110,  10, 400, "", "Blue",   "rect")
    lb_s  = _b(475, 110,  10, 400, "", "Purple", "rect")
    lb_db = _b(655, 110,  10, 400, "", "Teal",   "rect")
    boxes = [u, ui, svc, db, lb_u, lb_ui, lb_s, lb_db]
    arrows = [
        _a(lb_u["id"],  lb_ui["id"], "1: login(user, pwd)",   "solid", "filled"),
        _a(lb_ui["id"], lb_s["id"],  "2: authenticate()",     "solid", "filled"),
        _a(lb_s["id"],  lb_db["id"], "3: SELECT user WHERE…", "solid", "filled"),
        _a(lb_db["id"], lb_s["id"],  "4: user record",        "dashed","open"),
        _a(lb_s["id"],  lb_ui["id"], "5: token",              "dashed","open"),
        _a(lb_ui["id"], lb_u["id"],  "6: dashboard",          "dashed","open"),
    ]
    texts = [_t(390, 20, "Sequence Diagram — Login Flow", "heading")]
    return dict(boxes=boxes, arrows=arrows, floattexts=texts)


def tpl_activity_diagram():
    boxes, arrows, texts = [], [], []
    start  = _b(300,  40,  80,  80, "Start",       "Green",  "oval")
    step1  = _b(280, 160, 200,  60, "Receive Order",    "Blue")
    dec1   = _b(290, 270, 200,  80, "In Stock?",    "Orange", "diamond")
    step2a = _b(100, 400, 200,  60, "Notify Backorder", "Red")
    step2b = _b(460, 400, 200,  60, "Pick & Pack",      "Blue")
    step3  = _b(460, 510, 200,  60, "Ship Order",       "Blue")
    step4  = _b(280, 620, 200,  60, "Send Confirmation","Teal")
    end    = _b(300, 730,  80,  80, "End",          "Gray",   "oval")
    boxes = [start, step1, dec1, step2a, step2b, step3, step4, end]
    arrows = [
        _a(start["id"],  step1["id"],  ""),
        _a(step1["id"],  dec1["id"],   ""),
        _a(dec1["id"],   step2a["id"], "No"),
        _a(dec1["id"],   step2b["id"], "Yes"),
        _a(step2a["id"], step4["id"],  ""),
        _a(step2b["id"], step3["id"],  ""),
        _a(step3["id"],  step4["id"],  ""),
        _a(step4["id"],  end["id"],    ""),
    ]
    texts = [_t(390, 10, "Activity Diagram — Order Processing", "heading")]
    return dict(boxes=boxes, arrows=arrows, floattexts=texts)


def tpl_workflow_diagram():
    boxes, arrows, texts = [], [], []
    # Swimlane labels
    texts = [
        _t(60, 120, "Customer",    "heading"),
        _t(60, 280, "Sales",       "heading"),
        _t(60, 440, "Finance",     "heading"),
        _t(60, 600, "Delivery",    "heading"),
        _t(390, 20, "Workflow Diagram — Order to Cash", "heading"),
    ]
    # Boxes per lane
    b1 = _b(160,  90, 160, 60, "Place Order",      "Blue")
    b2 = _b(380,  90, 160, 60, "Confirm Order",    "Blue")
    b3 = _b(160, 250, 160, 60, "Quote & Approve",  "Green")
    b4 = _b(380, 250, 160, 60, "Create SO",        "Green")
    b5 = _b(600, 250, 160, 60, "Notify Customer",  "Green")
    b6 = _b(160, 410, 160, 60, "Invoice",          "Orange")
    b7 = _b(380, 410, 160, 60, "Payment",          "Orange")
    b8 = _b(600, 410, 160, 60, "Receipt",          "Orange")
    b9 = _b(160, 570, 160, 60, "Dispatch",         "Teal")
    b10= _b(380, 570, 160, 60, "Transit",          "Teal")
    b11= _b(600, 570, 160, 60, "Delivered",        "Teal")
    boxes = [b1,b2,b3,b4,b5,b6,b7,b8,b9,b10,b11]
    arrows = [
        _a(b1["id"],  b2["id"],  ""),
        _a(b2["id"],  b3["id"],  ""),
        _a(b3["id"],  b4["id"],  "approved"),
        _a(b4["id"],  b5["id"],  ""),
        _a(b4["id"],  b6["id"],  ""),
        _a(b6["id"],  b7["id"],  ""),
        _a(b7["id"],  b8["id"],  ""),
        _a(b4["id"],  b9["id"],  ""),
        _a(b9["id"],  b10["id"], ""),
        _a(b10["id"], b11["id"], ""),
        _a(b5["id"],  b1["id"],  "notify"),
    ]
    return dict(boxes=boxes, arrows=arrows, floattexts=texts)


# ── GoF Patterns ───────────────────────────────────────────────────────────────

def tpl_singleton():
    b1 = _b(240, 80, 300, 130,
            "Singleton\n──────────────\n- instance: Singleton\n──────────────\n- Singleton()\n+ getInstance(): Singleton\n+ operation(): void",
            "Purple")
    note = _b(60, 60, 160, 60,
              "Only ONE instance\never created", "Gray")
    texts = [_t(390,20,"GoF Creational — Singleton","heading")]
    return dict(boxes=[b1,note], arrows=[_a(note["id"],b1["id"],"","dashed","open")], floattexts=texts)


def tpl_factory_method():
    creator  = _b(220,  60, 260, 90, "Creator\n──────────────\n+ factoryMethod(): Product\n+ operation(): void", "Purple")
    concrete = _b(220, 240, 260, 80, "ConcreteCreator\n──────────────\n+ factoryMethod(): Product", "Blue")
    product  = _b(560,  60, 200, 80, "«interface»\nProduct\n──────────────\n+ use(): void", "Teal", "rect")
    cprod    = _b(560, 240, 200, 80, "ConcreteProduct\n──────────────\n+ use(): void", "Blue")
    texts = [_t(390,20,"GoF Creational — Factory Method","heading")]
    return dict(
        boxes=[creator,concrete,product,cprod],
        arrows=[
            _a(concrete["id"], creator["id"],  "",           "solid","inheritance"),
            _a(cprod["id"],    product["id"],  "implements", "dashed","inheritance"),
            _a(creator["id"],  product["id"],  "creates",    "dashed","open"),
            _a(concrete["id"], cprod["id"],    "creates",    "dashed","open"),
        ],
        floattexts=texts)


def tpl_abstract_factory():
    af   = _b(260,  40, 260, 100, "«interface»\nAbstractFactory\n──────────────\n+ createA(): AbstractA\n+ createB(): AbstractB", "Teal","rect")
    f1   = _b( 60, 220, 240,  80, "ConcreteFactory1\n──────────────\n+ createA(): ConcreteA1\n+ createB(): ConcreteB1", "Blue")
    f2   = _b(480, 220, 240,  80, "ConcreteFactory2\n──────────────\n+ createA(): ConcreteA2\n+ createB(): ConcreteB2", "Blue")
    aa   = _b(260, 220, 180,  60, "«interface»\nAbstractA\n+ use()", "Teal","rect")
    ab   = _b(260, 320, 180,  60, "«interface»\nAbstractB\n+ use()", "Teal","rect")
    ca1  = _b( 60, 420, 180,  60, "ConcreteA1\n+ use()", "Green")
    ca2  = _b(480, 420, 180,  60, "ConcreteA2\n+ use()", "Green")
    cb1  = _b( 60, 500, 180,  60, "ConcreteB1\n+ use()", "Orange")
    cb2  = _b(480, 500, 180,  60, "ConcreteB2\n+ use()", "Orange")
    texts=[_t(390,10,"GoF Creational — Abstract Factory","heading")]
    return dict(
        boxes=[af,f1,f2,aa,ab,ca1,ca2,cb1,cb2],
        arrows=[
            _a(f1["id"],af["id"],"","solid","inheritance"),
            _a(f2["id"],af["id"],"","solid","inheritance"),
            _a(ca1["id"],aa["id"],"","solid","inheritance"),
            _a(ca2["id"],aa["id"],"","solid","inheritance"),
            _a(cb1["id"],ab["id"],"","solid","inheritance"),
            _a(cb2["id"],ab["id"],"","solid","inheritance"),
            _a(f1["id"],ca1["id"],"creates","dashed","open"),
            _a(f2["id"],ca2["id"],"creates","dashed","open"),
        ],
        floattexts=texts)


def tpl_builder():
    dir_ = _b( 60, 100, 180, 80, "Director\n──────────────\n- builder: Builder\n+ construct(): void", "Green")
    bl   = _b(320,  60, 240, 100,"«interface»\nBuilder\n──────────────\n+ buildPartA()\n+ buildPartB()\n+ getResult(): Product", "Teal","rect")
    cb   = _b(320, 240, 240,  90,"ConcreteBuilder\n──────────────\n+ buildPartA()\n+ buildPartB()\n+ getResult(): Product", "Blue")
    prod = _b(320, 390, 240,  80,"Product\n──────────────\n- partA: String\n- partB: String", "Purple")
    texts=[_t(390,10,"GoF Creational — Builder","heading")]
    return dict(
        boxes=[dir_,bl,cb,prod],
        arrows=[
            _a(dir_["id"],bl["id"],"uses","solid","open"),
            _a(cb["id"],bl["id"],"","solid","inheritance"),
            _a(cb["id"],prod["id"],"builds","dashed","open"),
        ],
        floattexts=texts)


def tpl_prototype():
    proto = _b(240, 60,  240, 90, "«interface»\nPrototype\n──────────────\n+ clone(): Prototype", "Teal","rect")
    cp1   = _b( 80, 240, 220, 80, "ConcretePrototype1\n──────────────\n+ clone(): Prototype", "Blue")
    cp2   = _b(460, 240, 220, 80, "ConcretePrototype2\n──────────────\n+ clone(): Prototype", "Blue")
    client= _b(240, 420, 240, 70, "Client\n──────────────\n+ operation(): void", "Green")
    texts=[_t(390,10,"GoF Creational — Prototype","heading")]
    return dict(
        boxes=[proto,cp1,cp2,client],
        arrows=[
            _a(cp1["id"],proto["id"],"","solid","inheritance"),
            _a(cp2["id"],proto["id"],"","solid","inheritance"),
            _a(client["id"],proto["id"],"clone()","dashed","open"),
        ],
        floattexts=texts)


def tpl_adapter():
    target  = _b(240,  60, 240, 80, "«interface»\nTarget\n──────────────\n+ request(): void", "Teal","rect")
    adapter = _b(240, 220, 240, 90, "Adapter\n──────────────\n- adaptee: Adaptee\n──────────────\n+ request(): void", "Blue")
    adaptee = _b(560, 220, 220, 80, "Adaptee\n──────────────\n+ specificRequest(): void", "Orange")
    client  = _b(240, 390, 240, 70, "Client\n──────────────\n+ doWork(t: Target)", "Green")
    texts=[_t(390,10,"GoF Structural — Adapter","heading")]
    return dict(
        boxes=[target,adapter,adaptee,client],
        arrows=[
            _a(adapter["id"],target["id"],"implements","solid","inheritance"),
            _a(adapter["id"],adaptee["id"],"delegates","solid","open"),
            _a(client["id"],target["id"],"uses","dashed","open"),
        ],
        floattexts=texts)


def tpl_bridge():
    abstr   = _b( 60,  60, 240, 90, "Abstraction\n──────────────\n- impl: Implementor\n──────────────\n+ operation()", "Purple")
    refabstr= _b( 60, 240, 240, 80, "RefinedAbstraction\n──────────────\n+ operation()", "Blue")
    impl    = _b(400,  60, 240, 90, "«interface»\nImplementor\n──────────────\n+ operationImpl()", "Teal","rect")
    ci1     = _b(320, 240, 200, 80, "ConcreteImpl1\n──────────────\n+ operationImpl()", "Green")
    ci2     = _b(540, 240, 200, 80, "ConcreteImpl2\n──────────────\n+ operationImpl()", "Green")
    texts=[_t(390,10,"GoF Structural — Bridge","heading")]
    return dict(
        boxes=[abstr,refabstr,impl,ci1,ci2],
        arrows=[
            _a(refabstr["id"],abstr["id"],"","solid","inheritance"),
            _a(ci1["id"],impl["id"],"","solid","inheritance"),
            _a(ci2["id"],impl["id"],"","solid","inheritance"),
            _a(abstr["id"],impl["id"],"uses","solid","open"),
        ],
        floattexts=texts)


def tpl_composite():
    comp = _b(240,  60, 240, 90, "«interface»\nComponent\n──────────────\n+ operation()\n+ add(c: Component)\n+ remove(c: Component)", "Teal","rect")
    leaf = _b( 60, 260, 200, 80, "Leaf\n──────────────\n+ operation()", "Blue")
    comp2= _b(480, 260, 240, 90, "Composite\n──────────────\n- children: List\n──────────────\n+ operation()\n+ add() / remove()", "Purple")
    texts=[_t(390,10,"GoF Structural — Composite","heading")]
    return dict(
        boxes=[comp,leaf,comp2],
        arrows=[
            _a(leaf["id"],comp["id"],"","solid","inheritance"),
            _a(comp2["id"],comp["id"],"","solid","inheritance"),
            _a(comp2["id"],comp["id"],"0..*","solid","diamond"),
        ],
        floattexts=texts)


def tpl_decorator():
    comp  = _b(240,  60, 220, 80, "«interface»\nComponent\n──────────────\n+ operation()", "Teal","rect")
    concr = _b( 60, 240, 220, 80, "ConcreteComponent\n──────────────\n+ operation()", "Blue")
    decr  = _b(460, 240, 240, 90, "Decorator\n──────────────\n- wrappee: Component\n──────────────\n+ operation()", "Purple")
    cd1   = _b(380, 410, 220, 80, "ConcreteDecoratorA\n──────────────\n+ operation()\n+ extraA()", "Orange")
    cd2   = _b(620, 410, 220, 80, "ConcreteDecoratorB\n──────────────\n+ operation()\n+ extraB()", "Orange")
    texts=[_t(390,10,"GoF Structural — Decorator","heading")]
    return dict(
        boxes=[comp,concr,decr,cd1,cd2],
        arrows=[
            _a(concr["id"],comp["id"],"","solid","inheritance"),
            _a(decr["id"],comp["id"],"","solid","inheritance"),
            _a(decr["id"],comp["id"],"wraps","dashed","open"),
            _a(cd1["id"],decr["id"],"","solid","inheritance"),
            _a(cd2["id"],decr["id"],"","solid","inheritance"),
        ],
        floattexts=texts)


def tpl_facade():
    facade = _b(280,  60, 220, 80, "Facade\n──────────────\n+ operationA()\n+ operationB()", "Purple")
    s1 = _b( 60, 240, 180, 70, "SubsystemA\n──────────────\n+ doThingA()", "Blue")
    s2 = _b(280, 240, 180, 70, "SubsystemB\n──────────────\n+ doThingB()", "Blue")
    s3 = _b(500, 240, 180, 70, "SubsystemC\n──────────────\n+ doThingC()", "Blue")
    client = _b(280, 400, 220, 70, "Client\n──────────────\n+ run()", "Green")
    texts=[_t(390,10,"GoF Structural — Facade","heading")]
    return dict(
        boxes=[facade,s1,s2,s3,client],
        arrows=[
            _a(facade["id"],s1["id"],"","solid","open"),
            _a(facade["id"],s2["id"],"","solid","open"),
            _a(facade["id"],s3["id"],"","solid","open"),
            _a(client["id"],facade["id"],"uses","solid","open"),
        ],
        floattexts=texts)


def tpl_flyweight():
    fwf = _b(240,  60, 260, 90, "«interface»\nFlyweight\n──────────────\n+ operation(extrinsicState)", "Teal","rect")
    cfw = _b(120, 240, 240, 80, "ConcreteFlyweight\n──────────────\n- intrinsicState\n+ operation(extState)", "Blue")
    ufw = _b(440, 240, 240, 80, "UnsharedConcreteFlyweight\n──────────────\n- allState\n+ operation(extState)", "Orange")
    fac = _b(240, 420, 260, 80, "FlyweightFactory\n──────────────\n- pool: Map\n+ getFlyweight(key)", "Purple")
    cli = _b(240, 570, 260, 70, "Client\n──────────────\n+ run()", "Green")
    texts=[_t(390,10,"GoF Structural — Flyweight","heading")]
    return dict(
        boxes=[fwf,cfw,ufw,fac,cli],
        arrows=[
            _a(cfw["id"],fwf["id"],"","solid","inheritance"),
            _a(ufw["id"],fwf["id"],"","solid","inheritance"),
            _a(fac["id"],fwf["id"],"manages","dashed","open"),
            _a(cli["id"],fac["id"],"requests","solid","open"),
        ],
        floattexts=texts)


def tpl_proxy():
    iface = _b(240,  60, 220, 80, "«interface»\nSubject\n──────────────\n+ request()", "Teal","rect")
    real  = _b( 60, 240, 220, 80, "RealSubject\n──────────────\n+ request()", "Blue")
    proxy = _b(460, 240, 220, 90, "Proxy\n──────────────\n- real: RealSubject\n──────────────\n+ request()", "Purple")
    cli   = _b(240, 420, 220, 70, "Client\n──────────────\n+ run()", "Green")
    texts=[_t(390,10,"GoF Structural — Proxy","heading")]
    return dict(
        boxes=[iface,real,proxy,cli],
        arrows=[
            _a(real["id"],iface["id"],"","solid","inheritance"),
            _a(proxy["id"],iface["id"],"","solid","inheritance"),
            _a(proxy["id"],real["id"],"delegates","solid","open"),
            _a(cli["id"],proxy["id"],"uses","solid","open"),
        ],
        floattexts=texts)


def tpl_chain_of_responsibility():
    h  = _b(240,  60, 240, 90, "«abstract»\nHandler\n──────────────\n- next: Handler\n──────────────\n+ handle(req)\n+ setNext(h)", "Purple")
    h1 = _b( 60, 260, 200, 80, "ConcreteHandler1\n──────────────\n+ handle(req)", "Blue")
    h2 = _b(300, 260, 200, 80, "ConcreteHandler2\n──────────────\n+ handle(req)", "Blue")
    h3 = _b(540, 260, 200, 80, "ConcreteHandler3\n──────────────\n+ handle(req)", "Blue")
    cli= _b(240, 430, 240, 70, "Client\n──────────────\n+ run()", "Green")
    texts=[_t(390,10,"GoF Behavioral — Chain of Responsibility","heading")]
    return dict(
        boxes=[h,h1,h2,h3,cli],
        arrows=[
            _a(h1["id"],h["id"],"","solid","inheritance"),
            _a(h2["id"],h["id"],"","solid","inheritance"),
            _a(h3["id"],h["id"],"","solid","inheritance"),
            _a(h1["id"],h2["id"],"next","solid","open"),
            _a(h2["id"],h3["id"],"next","solid","open"),
            _a(cli["id"],h1["id"],"send request","dashed","open"),
        ],
        floattexts=texts)


def tpl_command():
    inv = _b( 60,  60, 180, 90, "Invoker\n──────────────\n- cmd: Command\n──────────────\n+ invoke()", "Green")
    cmd = _b(300,  60, 220, 80, "«interface»\nCommand\n──────────────\n+ execute()\n+ undo()", "Teal","rect")
    cc  = _b(300, 230, 220, 90, "ConcreteCommand\n──────────────\n- receiver: Receiver\n──────────────\n+ execute()\n+ undo()", "Blue")
    rec = _b(580,  60, 180, 80, "Receiver\n──────────────\n+ action()\n+ undoAction()", "Orange")
    cli = _b(300, 410, 220, 70, "Client\n──────────────\n+ run()", "Purple")
    texts=[_t(390,10,"GoF Behavioral — Command","heading")]
    return dict(
        boxes=[inv,cmd,cc,rec,cli],
        arrows=[
            _a(inv["id"],cmd["id"],"uses","solid","open"),
            _a(cc["id"],cmd["id"],"","solid","inheritance"),
            _a(cc["id"],rec["id"],"calls","solid","open"),
            _a(cli["id"],cc["id"],"creates","dashed","open"),
        ],
        floattexts=texts)


def tpl_observer():
    subj = _b(240,  60, 260, 100, "Subject / Observable\n──────────────\n- observers: List\n──────────────\n+ attach(o)\n+ detach(o)\n+ notify()", "Purple")
    obs  = _b(240, 260, 260,  80, "«interface»\nObserver\n──────────────\n+ update(event)", "Teal","rect")
    co1  = _b( 60, 420, 220,  80, "ConcreteObserver1\n──────────────\n+ update(event)", "Blue")
    co2  = _b(500, 420, 220,  80, "ConcreteObserver2\n──────────────\n+ update(event)", "Blue")
    texts=[_t(390,10,"GoF Behavioral — Observer","heading")]
    return dict(
        boxes=[subj,obs,co1,co2],
        arrows=[
            _a(subj["id"],obs["id"],"notifies","solid","open"),
            _a(co1["id"],obs["id"],"","solid","inheritance"),
            _a(co2["id"],obs["id"],"","solid","inheritance"),
        ],
        floattexts=texts)


def tpl_strategy():
    ctx  = _b( 60,  60, 200, 90, "Context\n──────────────\n- strategy: Strategy\n──────────────\n+ executeStrategy()", "Purple")
    strat= _b(340,  60, 240, 80, "«interface»\nStrategy\n──────────────\n+ execute(data): Result", "Teal","rect")
    cs1  = _b(240, 240, 220, 80, "ConcreteStrategyA\n──────────────\n+ execute(data)", "Blue")
    cs2  = _b(480, 240, 220, 80, "ConcreteStrategyB\n──────────────\n+ execute(data)", "Blue")
    texts=[_t(390,10,"GoF Behavioral — Strategy","heading")]
    return dict(
        boxes=[ctx,strat,cs1,cs2],
        arrows=[
            _a(ctx["id"],strat["id"],"uses","solid","open"),
            _a(cs1["id"],strat["id"],"","solid","inheritance"),
            _a(cs2["id"],strat["id"],"","solid","inheritance"),
        ],
        floattexts=texts)


def tpl_template_method():
    abstr = _b(220,  60, 300, 120, "AbstractClass\n──────────────\n+ templateMethod()  «final»\n──────────────\n# primitiveOp1()  «abstract»\n# primitiveOp2()  «abstract»\n+ hook()", "Purple")
    c1    = _b( 80, 280, 260,  90, "ConcreteClass1\n──────────────\n# primitiveOp1()\n# primitiveOp2()", "Blue")
    c2    = _b(400, 280, 260,  90, "ConcreteClass2\n──────────────\n# primitiveOp1()\n# primitiveOp2()", "Blue")
    texts=[_t(390,10,"GoF Behavioral — Template Method","heading")]
    return dict(
        boxes=[abstr,c1,c2],
        arrows=[
            _a(c1["id"],abstr["id"],"","solid","inheritance"),
            _a(c2["id"],abstr["id"],"","solid","inheritance"),
        ],
        floattexts=texts)


def tpl_state():
    ctx   = _b( 60,  60, 200, 90, "Context\n──────────────\n- state: State\n──────────────\n+ request()\n+ setState(s)", "Purple")
    state = _b(340,  60, 220, 80, "«interface»\nState\n──────────────\n+ handle(ctx)", "Teal","rect")
    cs1   = _b(240, 240, 220, 80, "ConcreteStateA\n──────────────\n+ handle(ctx)", "Blue")
    cs2   = _b(480, 240, 220, 80, "ConcreteStateB\n──────────────\n+ handle(ctx)", "Blue")
    texts=[_t(390,10,"GoF Behavioral — State","heading")]
    return dict(
        boxes=[ctx,state,cs1,cs2],
        arrows=[
            _a(ctx["id"],state["id"],"uses","solid","open"),
            _a(cs1["id"],state["id"],"","solid","inheritance"),
            _a(cs2["id"],state["id"],"","solid","inheritance"),
            _a(cs1["id"],cs2["id"],"transition","dashed","open"),
        ],
        floattexts=texts)


def tpl_iterator():
    agg  = _b(240,  60, 240, 80, "«interface»\nAggregate\n──────────────\n+ createIterator()", "Teal","rect")
    it   = _b(240, 240, 240, 90, "«interface»\nIterator\n──────────────\n+ hasNext(): bool\n+ next(): Object\n+ reset()", "Teal","rect")
    ca   = _b( 40, 420, 240, 80, "ConcreteAggregate\n──────────────\n+ createIterator()", "Blue")
    ci   = _b(440, 420, 240, 80, "ConcreteIterator\n──────────────\n+ hasNext()\n+ next()", "Blue")
    cli  = _b(580,  60, 180, 70, "Client\n──────────────\n+ run()", "Green")
    texts=[_t(390,10,"GoF Behavioral — Iterator","heading")]
    return dict(
        boxes=[agg,it,ca,ci,cli],
        arrows=[
            _a(ca["id"],agg["id"],"","solid","inheritance"),
            _a(ci["id"],it["id"],"","solid","inheritance"),
            _a(ca["id"],ci["id"],"creates","dashed","open"),
            _a(cli["id"],agg["id"],"uses","solid","open"),
            _a(cli["id"],it["id"],"uses","solid","open"),
        ],
        floattexts=texts)


def tpl_mediator():
    med  = _b(240,  60, 240, 80, "«interface»\nMediator\n──────────────\n+ notify(sender, event)", "Teal","rect")
    cmed = _b(240, 220, 240, 80, "ConcreteMediator\n──────────────\n+ notify(sender, event)", "Purple")
    c1   = _b( 40, 400, 200, 80, "ComponentA\n──────────────\n- mediator: Mediator\n+ operationA()", "Blue")
    c2   = _b(260, 400, 200, 80, "ComponentB\n──────────────\n- mediator: Mediator\n+ operationB()", "Blue")
    c3   = _b(480, 400, 200, 80, "ComponentC\n──────────────\n- mediator: Mediator\n+ operationC()", "Blue")
    texts=[_t(390,10,"GoF Behavioral — Mediator","heading")]
    return dict(
        boxes=[med,cmed,c1,c2,c3],
        arrows=[
            _a(cmed["id"],med["id"],"","solid","inheritance"),
            _a(c1["id"],med["id"],"notifies","dashed","open"),
            _a(c2["id"],med["id"],"notifies","dashed","open"),
            _a(c3["id"],med["id"],"notifies","dashed","open"),
            _a(cmed["id"],c1["id"],"coordinates","solid","open"),
            _a(cmed["id"],c2["id"],"coordinates","solid","open"),
            _a(cmed["id"],c3["id"],"coordinates","solid","open"),
        ],
        floattexts=texts)


def tpl_memento():
    orig = _b( 60,  60, 220, 90, "Originator\n──────────────\n- state: State\n──────────────\n+ save(): Memento\n+ restore(m)", "Purple")
    mem  = _b(360,  60, 220, 90, "Memento\n──────────────\n- state: State\n──────────────\n+ getState(): State", "Blue")
    car  = _b(360, 240, 220, 90, "Caretaker\n──────────────\n- history: List<Memento>\n──────────────\n+ backup()\n+ undo()", "Green")
    texts=[_t(390,10,"GoF Behavioral — Memento","heading")]
    return dict(
        boxes=[orig,mem,car],
        arrows=[
            _a(orig["id"],mem["id"],"creates","solid","open"),
            _a(car["id"],mem["id"],"stores","solid","odiamond"),
            _a(car["id"],orig["id"],"restores via","dashed","open"),
        ],
        floattexts=texts)


def tpl_interpreter():
    expr  = _b(220,  60, 260, 80, "«interface»\nExpression\n──────────────\n+ interpret(ctx): bool", "Teal","rect")
    term  = _b( 60, 240, 240, 80, "TerminalExpression\n──────────────\n+ interpret(ctx): bool", "Blue")
    nterm = _b(460, 240, 240, 90, "NonterminalExpression\n──────────────\n- exprs: List\n──────────────\n+ interpret(ctx): bool", "Blue")
    ctx   = _b(220, 400, 260, 80, "Context\n──────────────\n+ lookup(name)\n+ assign(name, val)", "Purple")
    cli   = _b(580, 400, 180, 70, "Client\n──────────────\n+ run()", "Green")
    texts=[_t(390,10,"GoF Behavioral — Interpreter","heading")]
    return dict(
        boxes=[expr,term,nterm,ctx,cli],
        arrows=[
            _a(term["id"],expr["id"],"","solid","inheritance"),
            _a(nterm["id"],expr["id"],"","solid","inheritance"),
            _a(nterm["id"],expr["id"],"0..*","solid","diamond"),
            _a(cli["id"],ctx["id"],"creates","dashed","open"),
            _a(cli["id"],expr["id"],"uses","dashed","open"),
        ],
        floattexts=texts)


def tpl_visitor():
    vis  = _b(240,  60, 260, 90, "«interface»\nVisitor\n──────────────\n+ visitA(e: ConcreteA)\n+ visitB(e: ConcreteB)", "Teal","rect")
    cv1  = _b( 60, 240, 240, 80, "ConcreteVisitor1\n──────────────\n+ visitA()\n+ visitB()", "Blue")
    cv2  = _b(480, 240, 240, 80, "ConcreteVisitor2\n──────────────\n+ visitA()\n+ visitB()", "Blue")
    elem = _b(240, 420, 260, 80, "«interface»\nElement\n──────────────\n+ accept(v: Visitor)", "Teal","rect")
    ea   = _b( 60, 580, 240, 80, "ConcreteElementA\n──────────────\n+ accept(v: Visitor)", "Green")
    eb   = _b(480, 580, 240, 80, "ConcreteElementB\n──────────────\n+ accept(v: Visitor)", "Green")
    texts=[_t(390,10,"GoF Behavioral — Visitor","heading")]
    return dict(
        boxes=[vis,cv1,cv2,elem,ea,eb],
        arrows=[
            _a(cv1["id"],vis["id"],"","solid","inheritance"),
            _a(cv2["id"],vis["id"],"","solid","inheritance"),
            _a(ea["id"],elem["id"],"","solid","inheritance"),
            _a(eb["id"],elem["id"],"","solid","inheritance"),
            _a(elem["id"],vis["id"],"accepts","dashed","open"),
        ],
        floattexts=texts)


# ─── Template registry ──────────────────────────────────────────────────────
TEMPLATES = {
    "UML Diagrams": {
        "Class Diagram":     tpl_class_diagram,
        "Interface Diagram": tpl_interface_diagram,
        "Sequence Diagram":  tpl_sequence_diagram,
        "Activity Diagram":  tpl_activity_diagram,
        "Workflow Diagram":  tpl_workflow_diagram,
    },
    "GoF — Creational": {
        "Singleton":         tpl_singleton,
        "Factory Method":    tpl_factory_method,
        "Abstract Factory":  tpl_abstract_factory,
        "Builder":           tpl_builder,
        "Prototype":         tpl_prototype,
    },
    "GoF — Structural": {
        "Adapter":   tpl_adapter,
        "Bridge":    tpl_bridge,
        "Composite": tpl_composite,
        "Decorator": tpl_decorator,
        "Facade":    tpl_facade,
        "Flyweight": tpl_flyweight,
        "Proxy":     tpl_proxy,
    },
    "GoF — Behavioral": {
        "Chain of Responsibility": tpl_chain_of_responsibility,
        "Command":                 tpl_command,
        "Interpreter":             tpl_interpreter,
        "Iterator":                tpl_iterator,
        "Mediator":                tpl_mediator,
        "Memento":                 tpl_memento,
        "Observer":                tpl_observer,
        "State":                   tpl_state,
        "Strategy":                tpl_strategy,
        "Template Method":         tpl_template_method,
        "Visitor":                 tpl_visitor,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class DiagramApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DiagramTool v2.0 — UML & GoF Patterns")
        self.root.configure(bg=BG)
        self.root.geometry("1400x860")

        self.boxes      = []
        self.arrows     = []
        self.floattexts = []
        self.selected   = None
        self.mode       = "select"
        self.arrow_src  = None
        self.undo_stack = []

        self.offset_x   = 40
        self.offset_y   = 40
        self.zoom       = 1.0
        self._drag_start= None
        self._drag_obj  = None
        self._drag_origin = None
        self._pan_start = None

        # Arrow style for new arrows
        self.new_line_style = tk.StringVar(value="solid")
        self.new_head_style = tk.StringVar(value="open")

        self._build_ui()
        self._bind_events()
        self._draw_all()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top toolbar ──
        tb = tk.Frame(self.root, bg=SURFACE, height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        self.mode_btns = {}
        modes = [
            ("☰ Select", "select"),
            ("⬜ Box",   "box"),
            ("➜ Arrow",  "arrow"),
            ("T Text",   "text"),
            ("✥ Pan",    "pan"),
        ]
        for label, key in modes:
            btn = tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                            activebackground=ACCENT, activeforeground="white",
                            relief="flat", padx=11, pady=8, cursor="hand2",
                            font=("Segoe UI", 10),
                            command=lambda k=key: self.set_mode(k))
            btn.pack(side="left", padx=2, pady=6)
            self.mode_btns[key] = btn

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        # Arrow style pickers (shown when in arrow mode)
        self.arrow_opts_frame = tk.Frame(tb, bg=SURFACE)
        self.arrow_opts_frame.pack(side="left", padx=4)
        tk.Label(self.arrow_opts_frame, text="Line:", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        for v, lbl in [("solid","──"), ("dashed","- -")]:
            tk.Radiobutton(self.arrow_opts_frame, text=lbl, variable=self.new_line_style,
                           value=v, bg=SURFACE, fg=TEXT_LIGHT, selectcolor=ACCENT,
                           activebackground=SURFACE, font=("Segoe UI", 9)
                           ).pack(side="left", padx=2)
        tk.Label(self.arrow_opts_frame, text=" Head:", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8,0))
        for v, lbl in [("open","▷"),("filled","▶"),("inheritance","△"),
                        ("diamond","◇"),("odiamond","◆"),("none","—")]:
            tk.Radiobutton(self.arrow_opts_frame, text=lbl, variable=self.new_head_style,
                           value=v, bg=SURFACE, fg=TEXT_LIGHT, selectcolor=ACCENT,
                           activebackground=SURFACE, font=("Segoe UI", 10)
                           ).pack(side="left", padx=1)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        actions = [
            ("🗑 Delete", self._delete_selected),
            ("✏ Edit",   self._edit_selected),
            ("🎨 Color",  self._change_color),
            ("◈ Shape",   self._change_shape),
        ]
        for label, cmd in actions:
            tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                      activebackground="#555577", relief="flat",
                      padx=9, pady=8, cursor="hand2",
                      font=("Segoe UI", 10), command=cmd).pack(side="left", padx=2, pady=6)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        # Templates button
        tk.Button(tb, text="📐 Templates", bg=ACCENT, fg="white",
                  activebackground=ACCENT2, relief="flat",
                  padx=12, pady=8, cursor="hand2",
                  font=("Segoe UI", 10, "bold"),
                  command=self._show_template_panel).pack(side="left", padx=4, pady=6)

        tk.Frame(tb, bg=SURFACE2, width=1).pack(side="left", fill="y", padx=3)

        file_actions = [
            ("💾 Save",       self._save),
            ("📂 Open",       self._load),
            ("🖼 Export PNG", self._export_png),
            ("🧹 Clear",      self._clear),
        ]
        for label, cmd in file_actions:
            tk.Button(tb, text=label, bg=SURFACE2, fg=TEXT_LIGHT,
                      activebackground="#555577", relief="flat",
                      padx=9, pady=8, cursor="hand2",
                      font=("Segoe UI", 10), command=cmd).pack(side="left", padx=2, pady=6)

        self.zoom_var = tk.StringVar(value="100%")
        tk.Button(tb, text="⟳ Reset", bg=SURFACE2, fg=TEXT_MUTED,
                  relief="flat", padx=8, pady=8, cursor="hand2",
                  font=("Segoe UI", 9), command=self._reset_view).pack(side="right", padx=4, pady=6)
        tk.Label(tb, textvariable=self.zoom_var, bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 10)).pack(side="right", padx=6)

        # ── Status bar ──
        self.status_var = tk.StringVar(value="Ready  •  Select a tool from the toolbar  •  📐 Templates for UML & GoF patterns")
        tk.Label(self.root, textvariable=self.status_var,
                 bg=SURFACE, fg=TEXT_MUTED, font=("Segoe UI", 9),
                 anchor="w", padx=12, pady=4).pack(fill="x", side="bottom")

        # ── Right panel ──
        right = tk.Frame(self.root, bg=SURFACE, width=190)
        right.pack(fill="y", side="right")
        right.pack_propagate(False)

        tk.Label(right, text="SHORTCUTS", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold"), pady=10).pack()
        for key, desc in [("Ctrl+S","Save"),("Ctrl+O","Open"),("Ctrl+Z","Undo"),
                           ("Ctrl+A","Select all"),("Del","Delete"),("Esc","Deselect"),
                           ("Scroll","Zoom"),("Middle","Pan"),("Dbl-click","Edit label")]:
            row = tk.Frame(right, bg=SURFACE)
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(row, text=key, bg=SURFACE2, fg=ACCENT2,
                     font=("Consolas", 9), padx=4, width=10).pack(side="left")
            tk.Label(row, text=desc, bg=SURFACE, fg=TEXT_MUTED,
                     font=("Segoe UI", 9), padx=4).pack(side="left")

        tk.Frame(right, bg=SURFACE2, height=1).pack(fill="x", pady=8, padx=6)
        tk.Label(right, text="ARROW TYPES", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack()
        for sym, desc in [("──▷","Association"),("- -▷","Dependency"),
                           ("──△","Inheritance"),("──◇","Aggregation"),
                           ("──◆","Composition"),("- -△","Realization")]:
            row = tk.Frame(right, bg=SURFACE)
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(row, text=sym, bg=SURFACE, fg=ACCENT2,
                     font=("Consolas", 9), width=8).pack(side="left")
            tk.Label(row, text=desc, bg=SURFACE, fg=TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(side="left")

        tk.Frame(right, bg=SURFACE2, height=1).pack(fill="x", pady=8, padx=6)
        tk.Label(right, text="SHAPES", bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack()
        for sym, desc in [("▭","rect (default)"),("◇","diamond"),("⬭","oval"),
                           ("📄","note"),("👤","actor"),("🥫","cylinder")]:
            row = tk.Frame(right, bg=SURFACE)
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(row, text=sym, bg=SURFACE, fg=ACCENT2,
                     font=("Segoe UI", 10), width=3).pack(side="left")
            tk.Label(row, text=desc, bg=SURFACE, fg=TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(side="left")

        # ── Canvas ──
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.set_mode("select")

    # ─── Template Panel ──────────────────────────────────────────────────────

    def _show_template_panel(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("📐 Templates — UML & GoF Patterns")
        dlg.configure(bg=BG)
        dlg.geometry("760x580")
        dlg.resizable(True, True)
        dlg.grab_set()

        tk.Label(dlg, text="Choose a Template", bg=BG, fg=TEXT_LIGHT,
                 font=("Segoe UI", 14, "bold"), pady=12).pack()
        tk.Label(dlg, text="Templates are pre-loaded onto the canvas. You can then edit all boxes, arrows and labels freely.",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 9), wraplength=700).pack(pady=(0,8))

        # Notebook for categories
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE2, foreground=TEXT_MUTED,
                         padding=[14, 6], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.configure("TFrame", background=BG)

        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=16, pady=4)

        for category, patterns in TEMPLATES.items():
            frame = ttk.Frame(nb)
            nb.add(frame, text=category)

            canvas_f = tk.Canvas(frame, bg=BG, highlightthickness=0)
            scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas_f.yview)
            canvas_f.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            canvas_f.pack(side="left", fill="both", expand=True)

            inner = tk.Frame(canvas_f, bg=BG)
            canvas_f.create_window((0,0), window=inner, anchor="nw")

            col = 0
            for name, fn in patterns.items():
                card = tk.Frame(inner, bg=SURFACE, relief="flat",
                                padx=12, pady=10, cursor="hand2")
                card.grid(row=col // 2, column=col % 2,
                          padx=10, pady=8, sticky="nsew")

                # Category badge color
                cat_colors = {
                    "UML Diagrams":    ("#3aaaa0","#1e3d3a"),
                    "GoF — Creational":("#7c6fcd","#3a2e5c"),
                    "GoF — Structural":("#3aaa6a","#1e3d2e"),
                    "GoF — Behavioral":("#cc7744","#4a3020"),
                }
                badge_fg, badge_bg = cat_colors.get(category, (ACCENT2, SURFACE2))
                tk.Label(card, text=category.upper(), bg=badge_bg, fg=badge_fg,
                         font=("Segoe UI", 7, "bold"), padx=6, pady=2,
                         ).pack(anchor="w")
                tk.Label(card, text=name, bg=SURFACE, fg=TEXT_LIGHT,
                         font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(4,2))

                # Short descriptions
                descs = {
                    "Class Diagram":     "Classes, attributes, methods,\nrelationships & inheritance",
                    "Interface Diagram": "Interfaces, implementations\n& client usage",
                    "Sequence Diagram":  "Lifelines, messages &\nreturn flows over time",
                    "Activity Diagram":  "Control flow, decisions\n& parallel activities",
                    "Workflow Diagram":  "Swimlane business process\nwith roles & handoffs",
                    "Singleton":         "Ensures only one instance\nexists globally",
                    "Factory Method":    "Subclasses decide which\nobject to instantiate",
                    "Abstract Factory":  "Family of related objects\nwithout specifying classes",
                    "Builder":           "Step-by-step construction\nof complex objects",
                    "Prototype":         "Clone existing objects\ninstead of creating new",
                    "Adapter":           "Convert incompatible\ninterfaces to work together",
                    "Bridge":            "Separate abstraction\nfrom implementation",
                    "Composite":         "Tree structure for\npart-whole hierarchies",
                    "Decorator":         "Add behaviour to objects\ndynamically at runtime",
                    "Facade":            "Simplified interface to\na complex subsystem",
                    "Flyweight":         "Share common state to\nsupport many fine objects",
                    "Proxy":             "Control access to\nanother object",
                    "Chain of Responsibility": "Pass request along\na chain of handlers",
                    "Command":           "Encapsulate requests\nas objects (undo/redo)",
                    "Interpreter":       "Grammar interpreter for\na simple language",
                    "Iterator":          "Sequential access without\nexposing structure",
                    "Mediator":          "Centralise communication\nbetween components",
                    "Memento":           "Capture & restore object\nstate (undo history)",
                    "Observer":          "Notify dependents when\nobject state changes",
                    "State":             "Alter behaviour when\ninternal state changes",
                    "Strategy":          "Swap algorithms\nat runtime",
                    "Template Method":   "Skeleton algorithm with\nsteps in subclasses",
                    "Visitor":           "Add operations without\nchanging element classes",
                }
                tk.Label(card, text=descs.get(name,""), bg=SURFACE, fg=TEXT_MUTED,
                         font=("Segoe UI", 8), justify="left").pack(anchor="w")

                load_btn = tk.Button(
                    card, text="Load →", bg=ACCENT, fg="white",
                    relief="flat", padx=10, pady=4, cursor="hand2",
                    font=("Segoe UI", 9, "bold"),
                    command=lambda f=fn, d=dlg: self._load_template(f, d))
                load_btn.pack(anchor="e", pady=(8,0))

                col += 1

            inner.update_idletasks()
            canvas_f.configure(scrollregion=canvas_f.bbox("all"))
            inner.columnconfigure(0, weight=1)
            inner.columnconfigure(1, weight=1)

        tk.Button(dlg, text="Close", bg=SURFACE2, fg=TEXT_LIGHT,
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=dlg.destroy).pack(pady=10)

    def _load_template(self, fn, dlg):
        if self.boxes or self.arrows or self.floattexts:
            if not messagebox.askyesno(
                    "Load Template",
                    "This will replace the current canvas.\nContinue?",
                    parent=dlg):
                return
        self._push_undo()
        # Reset id counters so template ids are clean
        Box._id = 0
        Arrow._id = 0
        FloatText._id = 0
        data = fn()
        self._deserialize(data)
        self.offset_x = 40
        self.offset_y = 40
        self.zoom = 1.0
        self.zoom_var.set("100%")
        self._draw_all()
        dlg.destroy()
        self.status_var.set(f"Template loaded  •  All elements are editable — double-click to edit labels")

    # ─── Mode ────────────────────────────────────────────────────────────────

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
        msgs = {
            "select": "Select  •  Click to select · drag to move · double-click to edit",
            "box":    "Box  •  Click on canvas to place a new box",
            "arrow":  "Arrow  •  Click SOURCE box, then click TARGET box",
            "text":   "Text  •  Click anywhere to drop a floating label",
            "pan":    "Pan  •  Drag the canvas to scroll around",
        }
        self.status_var.set(msgs.get(mode,""))
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
            dx, dy  = x2-x1, y2-y1
            length  = math.hypot(dx, dy)
            if length == 0:
                continue
            t  = max(0, min(1, ((wx-x1)*dx+(wy-y1)*dy)/length**2))
            px, py = x1+t*dx, y1+t*dy
            if math.hypot(wx-px, wy-py) < tol/self.zoom:
                return a
        return None

    def _floattext_at(self, wx, wy, tol=20):
        for ft in reversed(self.floattexts):
            if abs(ft.x-wx) < tol and abs(ft.y-wy) < tol:
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
            b = Box(wx-80, wy-30, label="Box")
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
            hit = self._box_at(wx, wy)
            if hit:
                if self.arrow_src is None:
                    self.arrow_src = hit
                    self.selected  = hit
                    self.status_var.set(f"Arrow  •  Now click TARGET box  (source: {hit.label[:30]})")
                    self._draw_all()
                else:
                    if hit.id != self.arrow_src.id:
                        self._push_undo()
                        a = Arrow(self.arrow_src.id, hit.id, "",
                                  self.new_line_style.get(),
                                  self.new_head_style.get())
                        self.arrows.append(a)
                    self.arrow_src = None
                    self.selected  = None
                    self.status_var.set("Arrow  •  Click SOURCE box, then TARGET box")
                    self._draw_all()
            return

        if self.mode == "select":
            hit = (self._box_at(wx, wy)
                   or self._arrow_at(wx, wy)
                   or self._floattext_at(wx, wy))
            self.selected = hit
            if hit:
                self._drag_start = (wx, wy)
                self._drag_obj   = hit
                self._drag_origin = (
                    (hit.x, hit.y) if isinstance(hit, (Box, FloatText)) else None)
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
            if isinstance(obj, (Box, FloatText)):
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
        hit = (self._box_at(wx, wy)
               or self._arrow_at(wx, wy)
               or self._floattext_at(wx, wy))
        if isinstance(hit, Box):
            self._edit_box_label(hit)
        elif isinstance(hit, Arrow):
            self._edit_arrow_label(hit)
        elif isinstance(hit, FloatText):
            self._edit_floattext(hit)

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
        self.zoom = max(0.15, min(6.0, self.zoom * factor))
        if event:
            cx, cy = event.x, event.y
            self.offset_x = cx - (cx - self.offset_x) * (self.zoom / old)
            self.offset_y = cy - (cy - self.offset_y) * (self.zoom / old)
        self.zoom_var.set(f"{int(self.zoom*100)}%")
        self._draw_all()

    def _escape(self):
        self.arrow_src = None
        self.selected  = None
        self._draw_all()

    def _bind_events(self):
        c = self.canvas
        c.bind("<Button-1>",        self._on_click)
        c.bind("<B1-Motion>",       self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", self._on_dblclick)
        c.bind("<Button-2>",        self._on_pan_start)
        c.bind("<B2-Motion>",       self._on_pan)
        c.bind("<Button-4>",        lambda e: self._zoom(1.1, e))
        c.bind("<Button-5>",        lambda e: self._zoom(0.9, e))
        c.bind("<MouseWheel>",      self._on_mousewheel)
        self.root.bind("<Control-s>", lambda e: self._save())
        self.root.bind("<Control-o>", lambda e: self._load())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-a>", lambda e: self._select_all())
        self.root.bind("<Delete>",    lambda e: self._delete_selected())
        self.root.bind("<Escape>",    lambda e: self._escape())

    # ─── Drawing ─────────────────────────────────────────────────────────────

    def _draw_all(self):
        c = self.canvas
        c.delete("all")
        self._draw_grid()
        for a in self.arrows:
            self._draw_arrow(a)
        for b in self.boxes:
            self._draw_box(b)
        for ft in self.floattexts:
            self._draw_floattext(ft)
        if self.mode == "arrow" and self.arrow_src:
            cx, cy = self._to_canvas(*self.arrow_src.center())
            c.create_oval(cx-7, cy-7, cx+7, cy+7, fill=SEL_COLOR, outline="")

    def _draw_grid(self):
        c = self.canvas
        w = c.winfo_width() or 1400
        h = c.winfo_height() or 800
        sp = 40 * self.zoom
        ox = self.offset_x % sp
        oy = self.offset_y % sp
        x = ox
        while x < w:
            c.create_line(x, 0, x, h, fill=GRID_COLOR, width=1)
            x += sp
        y = oy
        while y < h:
            c.create_line(0, y, w, y, fill=GRID_COLOR, width=1)
            y += sp

    def _draw_box(self, box):
        c = self.canvas
        x1, y1 = self._to_canvas(box.x, box.y)
        x2, y2 = self._to_canvas(box.x+box.w, box.y+box.h)
        fill, border = BOX_COLORS.get(box.color, ("#2e3a5c","#5a7ec8"))
        is_sel = (self.selected is box) or (self.mode == "arrow" and self.arrow_src is box)
        border_c = SEL_COLOR if is_sel else border
        lw = 2 if is_sel else 1

        shape = getattr(box, "shape", "rect")

        if shape == "diamond":
            cx = (x1+x2)/2; cy = (y1+y2)/2
            pts = [cx, y1, x2, cy, cx, y2, x1, cy]
            c.create_polygon(pts, fill=fill, outline=border_c, width=lw)
            c.create_text(cx, cy, text=box.label, fill=TEXT_LIGHT,
                          font=("Segoe UI", max(7,int(10*self.zoom))),
                          anchor="center", width=(x2-x1-8))
        elif shape == "oval":
            c.create_oval(x1, y1, x2, y2, fill=fill, outline=border_c, width=lw)
            cx=(x1+x2)/2; cy=(y1+y2)/2
            c.create_text(cx, cy, text=box.label, fill=TEXT_LIGHT,
                          font=("Segoe UI", max(7,int(10*self.zoom))),
                          anchor="center", width=(x2-x1-12))
        elif shape == "note":
            fold = min(16*self.zoom, (x2-x1)*0.2)
            pts = [x1,y1, x2-fold,y1, x2,y1+fold, x2,y2, x1,y2]
            c.create_polygon(pts, fill=fill, outline=border_c, width=lw)
            c.create_line(x2-fold,y1, x2-fold,y1+fold, x2,y1+fold,
                          fill=border_c, width=lw)
            c.create_text((x1+x2)/2, (y1+y2)/2, text=box.label, fill=TEXT_LIGHT,
                          font=("Segoe UI", max(7,int(10*self.zoom))),
                          anchor="center", width=(x2-x1-16))
        elif shape == "actor":
            # Stick figure
            cx=(x1+x2)/2; r=min((x2-x1),(y2-y1))*0.18
            head_y = y1+r*2
            c.create_oval(cx-r,y1,cx+r,head_y, fill=fill, outline=border_c, width=lw)
            body_y = head_y+(y2-y1)*0.25
            c.create_line(cx,head_y,cx,body_y, fill=border_c, width=lw)
            c.create_line(x1+4,head_y+(y2-y1)*0.1,x2-4,head_y+(y2-y1)*0.1,
                          fill=border_c, width=lw)
            c.create_line(cx,body_y,x1+4,y2-4, fill=border_c, width=lw)
            c.create_line(cx,body_y,x2-4,y2-4, fill=border_c, width=lw)
            c.create_text(cx,(y1+y2)/2+r*2, text=box.label, fill=TEXT_LIGHT,
                          font=("Segoe UI", max(7,int(9*self.zoom))),
                          anchor="n", width=(x2-x1))
        elif shape == "cylinder":
            rx = (x2-x1)/2; ry = min(14*self.zoom, (y2-y1)*0.2)
            cx = (x1+x2)/2
            c.create_rectangle(x1,y1+ry,x2,y2-ry, fill=fill, outline="")
            c.create_oval(x1,y1,x2,y1+ry*2, fill=fill, outline=border_c, width=lw)
            c.create_oval(x1,y2-ry*2,x2,y2, fill=fill, outline=border_c, width=lw)
            c.create_line(x1,y1+ry,x1,y2-ry, fill=border_c, width=lw)
            c.create_line(x2,y1+ry,x2,y2-ry, fill=border_c, width=lw)
            c.create_text(cx,(y1+y2)/2, text=box.label, fill=TEXT_LIGHT,
                          font=("Segoe UI", max(7,int(10*self.zoom))),
                          anchor="center", width=(x2-x1-8))
        else:  # rect
            # Shadow
            c.create_rectangle(x1+3,y1+3,x2+3,y2+3, fill="#111122", outline="")
            # Body
            c.create_rectangle(x1,y1,x2,y2, fill=fill, outline="")
            # Top accent bar
            bar = max(3,(y2-y1)*0.06)
            c.create_rectangle(x1,y1,x2,y1+bar, fill=border, outline="")
            # Border
            c.create_rectangle(x1,y1,x2,y2, fill="", outline=border_c, width=lw)
            # Label (supports multi-line with \n)
            fs = max(7, int(11*self.zoom))
            c.create_text((x1+x2)/2,(y1+y2)/2, text=box.label,
                          fill=TEXT_LIGHT, font=("Consolas", fs),
                          anchor="center", width=(x2-x1-10), justify="center")

    def _draw_arrow(self, arrow):
        c = self.canvas
        src = self._box_by_id(arrow.src_id)
        dst = self._box_by_id(arrow.dst_id)
        if not src or not dst:
            return

        tx, ty = dst.center()
        sx, sy = src.center()
        ex1, ey1 = src.edge_point(tx, ty)
        ex2, ey2 = dst.edge_point(sx, sy)
        cx1, cy1 = self._to_canvas(ex1, ey1)
        cx2, cy2 = self._to_canvas(ex2, ey2)

        is_sel = (self.selected is arrow)
        color  = SEL_COLOR if is_sel else ARROW_COLOR
        lw     = 2 if is_sel else 1.5
        dash   = (6, 4) if getattr(arrow,"line_style","solid") == "dashed" else ()

        head = getattr(arrow, "head_style", "open")
        as_ = (10*self.zoom, 14*self.zoom, 4*self.zoom)

        if head == "none":
            c.create_line(cx1,cy1,cx2,cy2, fill=color, width=lw, dash=dash)
        elif head == "inheritance":
            # Hollow triangle
            c.create_line(cx1,cy1,cx2,cy2, fill=color, width=lw, dash=dash)
            self._draw_triangle_head(c, cx1,cy1,cx2,cy2, color, filled=False)
        elif head == "filled":
            c.create_line(cx1,cy1,cx2,cy2, fill=color, width=lw, dash=dash,
                          arrow=tk.LAST,
                          arrowshape=(12*self.zoom,14*self.zoom,5*self.zoom))
        elif head in ("diamond","odiamond"):
            c.create_line(cx1,cy1,cx2,cy2, fill=color, width=lw, dash=dash)
            self._draw_diamond_head(c, cx1,cy1,cx2,cy2, color, head=="odiamond")
        else:  # open
            c.create_line(cx1,cy1,cx2,cy2, fill=color, width=lw, dash=dash,
                          arrow=tk.LAST,
                          arrowshape=(10*self.zoom,12*self.zoom,4*self.zoom))

        if arrow.label:
            mx = (cx1+cx2)/2
            my = (cy1+cy2)/2
            fs = max(6, int(9*self.zoom))
            c.create_text(mx, my-10*self.zoom, text=arrow.label,
                          fill=ACCENT2, font=("Segoe UI", fs))

    def _draw_triangle_head(self, c, x1,y1,x2,y2, color, filled):
        angle = math.atan2(y2-y1, x2-x1)
        size  = 14 * self.zoom
        spread= math.radians(25)
        p1x = x2 - size*math.cos(angle-spread)
        p1y = y2 - size*math.sin(angle-spread)
        p2x = x2 - size*math.cos(angle+spread)
        p2y = y2 - size*math.sin(angle+spread)
        fill = color if filled else BG
        c.create_polygon(x2,y2,p1x,p1y,p2x,p2y,
                         fill=fill, outline=color, width=1.5)

    def _draw_diamond_head(self, c, x1,y1,x2,y2, color, open_):
        angle = math.atan2(y2-y1, x2-x1)
        s = 14*self.zoom
        tip_x  = x2
        tip_y  = y2
        back_x = tip_x - s*math.cos(angle)
        back_y = tip_y - s*math.sin(angle)
        side_x = tip_x - (s/2)*math.cos(angle)
        side_y = tip_y - (s/2)*math.sin(angle)
        perp = angle + math.pi/2
        w = s*0.45
        l_x = side_x + w*math.cos(perp)
        l_y = side_y + w*math.sin(perp)
        r_x = side_x - w*math.cos(perp)
        r_y = side_y - w*math.sin(perp)
        fill = BG if open_ else color
        c.create_polygon(tip_x,tip_y,l_x,l_y,back_x,back_y,r_x,r_y,
                         fill=fill, outline=color, width=1.5)

    def _draw_floattext(self, ft):
        c = self.canvas
        cx, cy = self._to_canvas(ft.x, ft.y)
        is_sel = (self.selected is ft)
        fs  = max(8, int(12*self.zoom))
        styles = {
            "heading": ("Segoe UI", fs+2, "bold"),
            "note":    ("Segoe UI", fs, "italic"),
            "normal":  ("Segoe UI", fs),
        }
        font = styles.get(getattr(ft,"style","normal"), ("Segoe UI", fs))
        col  = SEL_COLOR if is_sel else ACCENT2
        c.create_text(cx, cy, text=ft.text, fill=col, font=font, anchor="center")
        if is_sel:
            c.create_oval(cx-8,cy-8,cx+8,cy+8, outline=SEL_COLOR, width=1, fill="")

    # ─── Edit helpers ─────────────────────────────────────────────────────────

    def _edit_box_label(self, box):
        # Multi-line dialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Box Label")
        dlg.configure(bg=SURFACE)
        dlg.geometry("420x260")
        dlg.resizable(True, True)
        dlg.grab_set()
        tk.Label(dlg, text="Edit label (use \\n for new lines):",
                 bg=SURFACE, fg=TEXT_LIGHT, font=("Segoe UI",10), pady=8).pack()
        txt = tk.Text(dlg, bg=BG, fg=TEXT_LIGHT, font=("Consolas",10),
                      insertbackground=TEXT_LIGHT, wrap="word",
                      height=8, padx=8, pady=6)
        txt.pack(fill="both", expand=True, padx=12)
        txt.insert("1.0", box.label)
        txt.focus_set()
        def apply():
            box.label = txt.get("1.0","end-1c")
            self._draw_all()
            dlg.destroy()
        tk.Button(dlg, text="Apply  (Ctrl+Enter)", bg=ACCENT, fg="white",
                  relief="flat", padx=16, pady=6, cursor="hand2",
                  command=apply).pack(pady=8)
        dlg.bind("<Control-Return>", lambda e: apply())

    def _edit_arrow_label(self, arrow):
        new = simpledialog.askstring("Edit Arrow Label",
                                     "Arrow label:", initialvalue=arrow.label,
                                     parent=self.root)
        if new is not None:
            arrow.label = new
            self._draw_all()

    def _edit_floattext(self, ft):
        new = simpledialog.askstring("Edit Text", "Text:",
                                     initialvalue=ft.text, parent=self.root)
        if new is not None:
            ft.text = new
            self._draw_all()

    def _edit_selected(self):
        if isinstance(self.selected, Box):
            self._edit_box_label(self.selected)
        elif isinstance(self.selected, Arrow):
            self._edit_arrow_label(self.selected)
        elif isinstance(self.selected, FloatText):
            self._edit_floattext(self.selected)

    def _change_color(self):
        if not isinstance(self.selected, Box):
            self.status_var.set("Select a box first, then click Color")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Box Color")
        dlg.configure(bg=SURFACE)
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="Box color:", bg=SURFACE, fg=TEXT_LIGHT,
                 font=("Segoe UI",10), pady=10, padx=16).pack()
        chosen = tk.StringVar(value=self.selected.color)
        for name,(fill,border) in BOX_COLORS.items():
            row = tk.Frame(dlg, bg=SURFACE)
            row.pack(fill="x", padx=16, pady=2)
            tk.Radiobutton(row, text=name, variable=chosen, value=name,
                           bg=SURFACE, fg=TEXT_LIGHT, selectcolor=fill,
                           activebackground=SURFACE,
                           font=("Segoe UI",10)).pack(side="left")
            tk.Frame(row, bg=fill, width=40, height=14).pack(side="right", padx=4)
        def apply():
            self.selected.color = chosen.get()
            self._draw_all()
            dlg.destroy()
        tk.Button(dlg, text="Apply", bg=ACCENT, fg="white", relief="flat",
                  padx=20, pady=6, cursor="hand2", command=apply).pack(pady=10)

    def _change_shape(self):
        if not isinstance(self.selected, Box):
            self.status_var.set("Select a box first, then click Shape")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Box Shape")
        dlg.configure(bg=SURFACE)
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="Box shape:", bg=SURFACE, fg=TEXT_LIGHT,
                 font=("Segoe UI",10), pady=10, padx=16).pack()
        chosen = tk.StringVar(value=getattr(self.selected,"shape","rect"))
        for name, desc in [("rect","Rectangle (default)"),("diamond","Diamond (decision)"),
                            ("oval","Oval (start/end)"),("note","Note (corner fold)"),
                            ("actor","Actor (stick figure)"),("cylinder","Cylinder (database)")]:
            tk.Radiobutton(dlg, text=f"{name}  —  {desc}", variable=chosen, value=name,
                           bg=SURFACE, fg=TEXT_LIGHT, selectcolor=ACCENT,
                           activebackground=SURFACE, font=("Segoe UI",10),
                           anchor="w").pack(fill="x", padx=16, pady=2)
        def apply():
            self.selected.shape = chosen.get()
            self._draw_all()
            dlg.destroy()
        tk.Button(dlg, text="Apply", bg=ACCENT, fg="white", relief="flat",
                  padx=20, pady=6, cursor="hand2", command=apply).pack(pady=10)

    # ─── Undo ─────────────────────────────────────────────────────────────────

    def _push_undo(self):
        self.undo_stack.append(self._serialize())
        if len(self.undo_stack) > 60:
            self.undo_stack.pop(0)

    def _undo(self):
        if not self.undo_stack:
            self.status_var.set("Nothing to undo")
            return
        self._deserialize(self.undo_stack.pop())
        self._draw_all()
        self.status_var.set("Undone")

    # ─── Delete / misc ────────────────────────────────────────────────────────

    def _delete_selected(self):
        if not self.selected:
            return
        self._push_undo()
        if isinstance(self.selected, Box):
            bid = self.selected.id
            self.boxes  = [b for b in self.boxes  if b.id != bid]
            self.arrows = [a for a in self.arrows
                           if a.src_id != bid and a.dst_id != bid]
        elif isinstance(self.selected, Arrow):
            self.arrows = [a for a in self.arrows if a.id != self.selected.id]
        elif isinstance(self.selected, FloatText):
            self.floattexts = [ft for ft in self.floattexts if ft.id != self.selected.id]
        self.selected = None
        self._draw_all()

    def _select_all(self):
        self.status_var.set(f"Canvas has {len(self.boxes)} boxes · "
                            f"{len(self.arrows)} arrows · "
                            f"{len(self.floattexts)} texts")

    def _clear(self):
        if messagebox.askyesno("Clear Canvas","Delete everything on the canvas?"):
            self._push_undo()
            self.boxes.clear(); self.arrows.clear(); self.floattexts.clear()
            self.selected = None
            self._draw_all()

    def _reset_view(self):
        self.offset_x = 40; self.offset_y = 40
        self.zoom = 1.0; self.zoom_var.set("100%")
        self._draw_all()

    # ─── Serialise ────────────────────────────────────────────────────────────

    def _serialize(self):
        return dict(
            boxes      = [b.to_dict()  for b in self.boxes],
            arrows     = [a.to_dict()  for a in self.arrows],
            floattexts = [ft.to_dict() for ft in self.floattexts],
        )

    def _deserialize(self, data):
        self.boxes      = [Box.from_dict(d)       for d in data.get("boxes", [])]
        self.arrows     = [Arrow.from_dict(d)     for d in data.get("arrows", [])]
        self.floattexts = [FloatText.from_dict(d) for d in data.get("floattexts", [])]
        if self.boxes:       Box._id       = max(b.id  for b in self.boxes)
        if self.arrows:      Arrow._id     = max(a.id  for a in self.arrows)
        if self.floattexts:  FloatText._id = max(ft.id for ft in self.floattexts)

    # ─── File I/O ─────────────────────────────────────────────────────────────

    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Diagram JSON","*.json"),("All","*.*")],
            title="Save Diagram")
        if path:
            with open(path,"w") as f:
                json.dump(self._serialize(), f, indent=2)
            self.status_var.set(f"Saved → {os.path.basename(path)}")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Diagram JSON","*.json"),("All","*.*")],
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
            messagebox.showinfo("Export PNG",
                "Install Pillow for PNG export:\n  pip install Pillow\n\n"
                "Or use Windows Snipping Tool (Win+Shift+S) to capture the canvas.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG","*.png")], title="Export PNG")
        if path:
            x = self.root.winfo_rootx() + self.canvas.winfo_x()
            y = self.root.winfo_rooty() + self.canvas.winfo_y()
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(path)
            self.status_var.set(f"Exported → {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    root.title("DiagramTool v2.0")
    app = DiagramApp(root)

    # Welcome demo — shows capability on launch
    Box._id = 0; Arrow._id = 0; FloatText._id = 0
    data = tpl_observer()   # show Observer pattern as default
    app._deserialize(data)
    app._draw_all()
    app.status_var.set(
        "Welcome!  •  Showing GoF Observer pattern  •  "
        "Click 📐 Templates for all 23 GoF patterns + 5 UML diagrams")
    root.mainloop()


if __name__ == "__main__":
    main()
