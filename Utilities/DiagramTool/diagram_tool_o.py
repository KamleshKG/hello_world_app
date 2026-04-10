"""
DiagramTool v4.1 — ALL-IN-ONE
==============================
Single file. Zero extra files needed.

Run:   python diagram_tool.py
Needs: Python 3.x  (tkinter is built-in, no pip install)
Opt:   pip install Pillow   (PNG export)

FEATURES
  Canvas:  Box/Arrow/Text/Select/Pan modes
           12 shape palette, resize handles, snap-to-grid
           Multi-select (rubber-band + Shift+Click), group move
           Copy/Paste (Ctrl+C/V), Undo (Ctrl+Z)
           Orthogonal L-shaped arrows, Zoom + Pan
           Right-click context menu, Minimap

  Export:  Save/Load JSON, Export PNG, Export SVG

  Templates: 28 GoF Design Patterns + 5 UML diagram types

  Code Analysis:
    Python .py  — classes, imports, composition, aggregation,
                  inheritance, DI, stdlib vs local classification
    Java   .java — same + @Autowired, @Inject, JPA @OneToMany etc.
    Spring Boot  — auto-detected from pom.xml / build.gradle:
                   @RestController → Blue   (Controller layer)
                   @Service        → Purple (Service layer)
                   @Repository     → Teal   (Repository layer)
                   @Entity         → Green  (JPA Entity)
                   @Configuration  → Orange (Config / @Bean)
                   Security layer  → Red
                   Kafka/Redis/etc → Gray cylinder (Infra nodes)
"""

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import json, math, os, re, ast, copy, sys
from pathlib import Path

# ═══ CODE LAYOUT ENGINE ══════════════════════════════════════════════════

def auto_layout(class_names: list, cols: int = 4,
                col_w: int = 280, row_h: int = 220,
                start_x: int = 60, start_y: int = 80) -> dict:
    """
    Returns {class_name: (x, y)} for each name.
    Grid layout with auto column count by total size.
    """
    n = len(class_names)
    if n == 0:
        return {}
    if n <= 2:    cols = 1
    elif n <= 6:  cols = 2
    elif n <= 12: cols = 3
    elif n <= 20: cols = 4
    else:         cols = 5   # large projects: 5 columns

    positions = {}
    for i, name in enumerate(class_names):
        col = i % cols
        row = i // cols
        x = start_x + col * col_w
        y = start_y + row * row_h
        positions[name] = (x, y)


    return positions

# ═══ PYTHON / JAVA CODE ANALYSER ════════════════════════════════════════

# ── Colour mapping by role ───────────────────────────────────────────────────
COLOR_CLASS     = "Blue"
COLOR_ABSTRACT  = "Purple"
COLOR_INTERFACE = "Teal"
COLOR_ENUM      = "Orange"
COLOR_EXTERNAL  = "Gray"    # stdlib / third-party libraries
COLOR_UNKNOWN   = "Gray"

# ── Arrow styles for each relationship ──────────────────────────────────────
REL_STYLES = {
    "inherits":    ("solid",  "inheritance"),   # ──△
    "implements":  ("dashed", "inheritance"),   # - -△
    "composes":    ("solid",  "odiamond"),      # ──◆  strong composition
    "aggregates":  ("solid",  "diamond"),       # ──◇  weak / collection
    "depends":     ("dashed", "open"),          # - -▷ dependency / usage
    "injects":     ("dashed", "open"),          # - -▷ DI  (label = «inject»)
}

# ── Known stdlib / common third-party prefixes ──────────────────────────────
STDLIB_PYTHON = {
    "os","sys","re","json","math","io","abc","ast","collections","pathlib",
    "typing","dataclasses","functools","itertools","operator","copy","time",
    "datetime","threading","multiprocessing","subprocess","socket","logging",
    "unittest","pytest","argparse","configparser","enum","random","string",
    "struct","hashlib","hmac","base64","urllib","http","email","html","xml",
    "csv","sqlite3","pickle","shelve","contextlib","weakref","gc","inspect",
    "traceback","warnings","shutil","glob","fnmatch","tempfile","platform",
    "signal","queue","heapq","bisect","array","tkinter","tkinter.ttk",
}
THIRDPARTY_PYTHON = {
    "numpy","pandas","matplotlib","scipy","sklearn","tensorflow","torch",
    "keras","flask","django","fastapi","requests","aiohttp","sqlalchemy",
    "celery","redis","pymongo","psycopg2","boto3","PIL","cv2","yaml","toml",
    "pydantic","attrs","click","rich","tqdm","pytest","hypothesis",
    "selenium","playwright","bs4","lxml","paramiko","cryptography","jwt",
    "stripe","anthropic","openai","langchain","huggingface_hub","transformers",
    "yfinance","ta","pandas_ta","backtrader","zipline","aria2p",
}
STDLIB_JAVA = {
    "java","javax","sun","com.sun","org.w3c","org.xml","org.ietf",
}
THIRDPARTY_JAVA = {
    "org.springframework","com.google","org.apache","org.hibernate",
    "org.junit","org.mockito","com.fasterxml","io.netty","org.slf4j",
    "ch.qos","org.bouncycastle","com.amazonaws","org.elasticsearch",
}


def _is_external_python(module_root: str) -> bool:
    root = module_root.split(".")[0]
    return root in STDLIB_PYTHON or root in THIRDPARTY_PYTHON

def _is_external_java(pkg: str) -> bool:
    for prefix in list(STDLIB_JAVA) + list(THIRDPARTY_JAVA):
        if pkg.startswith(prefix):
            return True
    return False


# ═════════════════════════════════════════════════════════════════════════════
# PYTHON ANALYSER
# ═════════════════════════════════════════════════════════════════════════════

class PythonAnalyzer:
    """Parse one or more .py files using the ast module."""

    def __init__(self):
        self.classes   = {}   # name -> ClassInfo dict
        self.imports   = {}   # alias -> (full_module, is_external)
        self.local_files = set()

    # ── Public entry ─────────────────────────────────────────────────────────

    def analyze_path(self, path: str):
        p = Path(path)
        if p.is_file() and p.suffix == ".py":
            self._analyze_file(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                self._analyze_file(f)
        return self._build_diagram()

    # ── File level ───────────────────────────────────────────────────────────

    def _analyze_file(self, path: Path):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            return

        # Collect local module names (filename stems)
        self.local_files.add(path.stem)

        # Collect imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    ext  = _is_external_python(alias.name)
                    self.imports[name] = (alias.name, ext)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                ext = _is_external_python(mod)
                for alias in node.names:
                    name = alias.asname or alias.name
                    self.imports[name] = (f"{mod}.{alias.name}", ext)

        # Collect classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._analyze_class(node, path.stem)

    def _analyze_class(self, node: ast.ClassDef, module: str):
        info = {
            "name":       node.name,
            "module":     module,
            "kind":       "class",      # class | abstract | interface | enum
            "bases":      [],
            "fields":     [],           # [(name, type_hint)]
            "methods":    [],           # [(name, params, return_type)]
            "ctor_params":[],           # constructor param type hints
            "relations":  [],           # [(rel_type, target_name, label)]
        }

        # Detect abstract / interface via ABC
        base_names = []
        for b in node.bases:
            bn = self._name_of(b)
            if bn:
                base_names.append(bn)
                if bn in ("ABC", "ABCMeta"):
                    info["kind"] = "abstract"
                elif bn == "Enum":
                    info["kind"] = "enum"
                else:
                    rel = "implements" if info["kind"] == "abstract" else "inherits"
                    info["relations"].append((rel, bn, ""))

        info["bases"] = base_names

        # Analyse body
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._analyze_method(item, info)
            elif isinstance(item, ast.AnnAssign):
                # field: Type  or  field: Type = ...
                fname = self._name_of(item.target)
                ftype = self._annotation_str(item.annotation)
                if fname and ftype:
                    info["fields"].append((fname, ftype))
                    self._classify_field_rel(fname, ftype, info)

        self.classes[node.name] = info

    def _analyze_method(self, node: ast.FunctionDef, info: dict):
        params = []
        ret    = ""
        if node.returns:
            ret = self._annotation_str(node.returns)

        for arg in node.args.args:
            if arg.arg == "self":
                continue
            atype = self._annotation_str(arg.annotation) if arg.annotation else ""
            params.append((arg.arg, atype))

        info["methods"].append((node.name, params, ret))

        # Constructor: injected dependencies
        if node.name == "__init__":
            for argname, atype in params:
                if atype:
                    info["ctor_params"].append(atype)
                    # Check if it's a known local class → DI
                    base = atype.split("[")[0].strip()
                    info["relations"].append(("injects", base, "«inject»"))

            # Also scan body for self.x = param assignments
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if (isinstance(t, ast.Attribute) and
                                isinstance(t.value, ast.Name) and
                                t.value.id == "self"):
                            if isinstance(stmt.value, ast.Name):
                                val = stmt.value.id
                                if any(val == p[0] for p in params):
                                    # self.x = injected_param → strong composition
                                    ptype = next((p[1] for p in params if p[0]==val),"")
                                    if ptype:
                                        base = ptype.split("[")[0].strip()
                                        info["relations"].append(("composes", base, ""))

        # Other methods: detect usage of other classes as params
        else:
            for argname, atype in params:
                if atype:
                    base = atype.split("[")[0].strip()
                    if base not in ("str","int","float","bool","None","Any",
                                   "list","dict","tuple","set","bytes"):
                        info["relations"].append(("depends", base, ""))

    def _classify_field_rel(self, fname: str, ftype: str, info: dict):
        """Turn field type hints into composition / aggregation."""
        # List[X], Set[X], Sequence[X] → aggregation
        m = re.match(r"(?:List|Set|Sequence|Tuple|Iterable|Collection)\[(.+)\]", ftype)
        if m:
            inner = m.group(1).split(",")[0].strip()
            if inner not in ("str","int","float","bool","Any"):
                info["relations"].append(("aggregates", inner, f"0..*"))
            return
        # Optional[X] → weak dependency
        m = re.match(r"Optional\[(.+)\]", ftype)
        if m:
            inner = m.group(1).strip()
            if inner not in ("str","int","float","bool","None","Any"):
                info["relations"].append(("aggregates", inner, "0..1"))
            return
        # Dict[K, V] — check V
        m = re.match(r"Dict\[.+?,\s*(.+)\]", ftype)
        if m:
            vtype = m.group(1).strip()
            if vtype not in ("str","int","float","bool","Any"):
                info["relations"].append(("aggregates", vtype, ""))
            return
        # Plain class reference → composition
        primitives = {"str","int","float","bool","None","Any","bytes",
                      "object","type","callable","Callable"}
        clean = ftype.replace("'","").strip()
        if clean and clean[0].isupper() and clean not in primitives:
            info["relations"].append(("composes", clean, ""))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _name_of(self, node) -> str:
        if isinstance(node, ast.Name):      return node.id
        if isinstance(node, ast.Attribute): return node.attr
        return ""

    def _annotation_str(self, node) -> str:
        if node is None: return ""
        if isinstance(node, ast.Name):      return node.id
        if isinstance(node, ast.Attribute): return f"{self._annotation_str(node.value)}.{node.attr}"
        if isinstance(node, ast.Subscript):
            return f"{self._annotation_str(node.value)}[{self._annotation_str(node.slice)}]"
        if isinstance(node, ast.Tuple):
            return ", ".join(self._annotation_str(e) for e in node.elts)
        if isinstance(node, ast.Constant):  return str(node.value)
        if isinstance(node, ast.BinOp):     # X | Y (Python 3.10+)
            return f"{self._annotation_str(node.left)} | {self._annotation_str(node.right)}"
        return ""

    # ── Build diagram dict ────────────────────────────────────────────────────

    def _build_diagram(self):

        boxes, arrows, floattexts = [], [], []
        box_id = {}   # class_name -> box id

        _bid = [0]
        _aid = [0]
        _tid = [0]

        def new_box(x,y,w,h,label,color,shape="rect"):
            _bid[0]+=1
            b=dict(id=_bid[0],x=x,y=y,w=w,h=h,label=label,color=color,shape=shape)
            boxes.append(b); return b

        def new_arrow(sid,did,label,ls,hs):
            _aid[0]+=1
            arrows.append(dict(id=_aid[0],src_id=sid,dst_id=did,
                               label=label,line_style=ls,head_style=hs))

        def new_text(x,y,text,style="normal"):
            _tid[0]+=1
            floattexts.append(dict(id=_tid[0],x=x,y=y,text=text,style=style))

        # Collect external libraries referenced
        external_libs = {}  # lib_name -> box_id

        # Place class boxes
        positions = auto_layout(list(self.classes.keys()))
        for cname, (cx, cy) in positions.items():
            info  = self.classes[cname]
            kind  = info["kind"]
            color = {"class":COLOR_CLASS,"abstract":COLOR_ABSTRACT,
                     "interface":COLOR_INTERFACE,"enum":COLOR_ENUM}.get(kind, COLOR_CLASS)

            # Build label
            header = cname
            if kind != "class":
                header = f"«{kind}»\n{cname}"
            sep = "──────────────"
            field_lines = "\n".join(f"  {f}: {t}" for f,t in info["fields"][:6])
            method_lines= "\n".join(
                f"  +{m[0]}({', '.join(a+':'+t if t else a for a,t in m[1][:3])})"
                for m in info["methods"][:6]
            )
            parts = [header]
            if field_lines:   parts += [sep, field_lines]
            if method_lines:  parts += [sep, method_lines]
            label = "\n".join(parts)

            w = max(180, 12*max((len(l) for l in label.split("\n")), default=10))
            h = max(60,  18*len(label.split("\n")))
            b = new_box(cx, cy, w, h, label, color)
            box_id[cname] = b["id"]

        # Arrows
        seen_rels = set()
        for cname, info in self.classes.items():
            src_id = box_id.get(cname)
            if not src_id: continue

            for (rel, target, lbl) in info["relations"]:
                ls, hs = REL_STYLES.get(rel, ("solid","open"))

                if target in box_id:
                    key = (src_id, box_id[target], rel)
                    if key in seen_rels: continue
                    seen_rels.add(key)
                    new_arrow(src_id, box_id[target], lbl, ls, hs)

                else:
                    # External library or unknown
                    # Check if it came from an import
                    import_info = self.imports.get(target)
                    if import_info:
                        full_mod, is_ext = import_info
                        lib_label = target if is_ext else full_mod
                    else:
                        lib_label = target
                        is_ext    = False

                    if lib_label not in external_libs:
                        # Place external box off to the right
                        ex = 900 + len(external_libs)*10
                        ey = 80  + len(external_libs)*90
                        color = COLOR_EXTERNAL
                        shape = "rect"
                        eb = new_box(ex, ey, 160, 50, lib_label, color, shape)
                        external_libs[lib_label] = eb["id"]

                    key = (src_id, external_libs[lib_label], rel)
                    if key in seen_rels: continue
                    seen_rels.add(key)
                    new_arrow(src_id, external_libs[lib_label], lbl, ls, hs)

        new_text(400, 20,
                 f"Code Analysis — Python  ({len(self.classes)} classes, "
                 f"{len(self.imports)} imports)", "heading")

        # Legend
        new_text(50, 20, "──△ inherits  - -△ implements  ──◆ composes  ──◇ aggregates  - -▷ depends  «inject»=DI", "normal")

        return dict(boxes=boxes, arrows=arrows, floattexts=floattexts)


# ═════════════════════════════════════════════════════════════════════════════
# JAVA ANALYSER
# ═════════════════════════════════════════════════════════════════════════════

class JavaAnalyzer:
    """Parse .java files with regex (no external parser needed)."""

    # Patterns
    _P_IMPORT  = re.compile(r"^\s*import\s+(static\s+)?([^\s;]+);", re.M)
    _P_CLASS   = re.compile(
        r"(?:public\s+|private\s+|protected\s+|abstract\s+|final\s+)*"
        r"(class|interface|enum|@interface)\s+(\w+)"
        r"(?:\s*<[^>]*>)?"                           # generics
        r"(?:\s+extends\s+([\w,\s<>]+?))??"
        r"(?:\s+implements\s+([\w,\s<>]+?))?"
        r"\s*\{", re.M)
    _P_FIELD   = re.compile(
        r"^\s*(?:private|protected|public)?\s*(?:final\s+|static\s+)*"
        r"([\w<>\[\],\s]+?)\s+(\w+)\s*(?:=|;)", re.M)
    _P_METHOD  = re.compile(
        r"^\s*(?:public|private|protected|abstract|static|final|synchronized|@Override\s+)*\s+"
        r"(?:<[^>]*>\s+)?([\w<>\[\],\s]+?)\s+(\w+)\s*\(([^)]*)\)", re.M)
    _P_ANNOT   = re.compile(r"@(\w+)")
    _P_INJECT  = re.compile(r"@(?:Autowired|Inject|Resource|Value)")
    _PRIMITIVES= {"void","int","long","double","float","boolean","char","byte",
                  "short","String","Integer","Long","Double","Float","Boolean",
                  "Object","Number","Comparable","Serializable","Iterable",
                  "var","T","E","K","V","R","U"}
    _COLLECT   = {"List","Set","Map","Collection","Queue","Deque","ArrayList",
                  "LinkedList","HashSet","HashMap","Optional","Stream","Iterable"}

    def __init__(self):
        self.classes = {}
        self.imports = {}

    def analyze_path(self, path: str):
        p = Path(path)
        if p.is_file() and p.suffix == ".java":
            self._analyze_file(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*.java")):
                self._analyze_file(f)
        return self._build_diagram()

    def _analyze_file(self, path: Path):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        # Imports
        file_imports = {}
        for m in self._P_IMPORT.finditer(src):
            full = m.group(2).strip()
            simple = full.split(".")[-1]
            ext = _is_external_java(full)
            file_imports[simple] = (full, ext)
            self.imports[simple] = (full, ext)

        # Classes
        for m in self._P_CLASS.finditer(src):
            kind_kw = m.group(1)   # class|interface|enum|@interface
            cname   = m.group(2)
            extends = [x.strip().split("<")[0]
                       for x in (m.group(3) or "").split(",") if x.strip()]
            implements = [x.strip().split("<")[0]
                          for x in (m.group(4) or "").split(",") if x.strip()]

            kind = {"interface":"interface","enum":"enum",
                    "@interface":"interface"}.get(kind_kw,"class")

            # Try to detect abstract
            start = max(0, m.start()-80)
            preceding = src[start:m.start()]
            if "abstract" in preceding:
                kind = "abstract"

            info = {
                "name":      cname,
                "kind":      kind,
                "fields":    [],
                "methods":   [],
                "relations": [],
            }

            # Extends → inherits
            for base in extends:
                if base:
                    info["relations"].append(("inherits", base, ""))

            # Implements → implements
            for iface in implements:
                if iface:
                    info["relations"].append(("implements", iface, ""))

            # Get class body (heuristic: find matching brace)
            body = self._extract_body(src, m.end()-1)

            # Fields
            for fm in self._P_FIELD.finditer(body):
                ftype = fm.group(1).strip()
                fname = fm.group(2).strip()
                if fname in ("class","return","new","if","for","while",
                             "else","throw","catch"): continue
                info["fields"].append((fname, ftype))

                # Determine relationship type from field type
                col_m = re.match(r"(\w+)\s*<\s*([\w<>]+)", ftype)
                if col_m:
                    container = col_m.group(1)
                    inner     = col_m.group(2).split("<")[0]
                    if container in self._COLLECT and inner not in self._PRIMITIVES:
                        info["relations"].append(("aggregates", inner, "0..*"))
                else:
                    clean = ftype.split("<")[0].strip().split("[")[0].strip()
                    if clean and clean not in self._PRIMITIVES and clean[0].isupper():
                        # Check if @Autowired / @Inject precedes field
                        fpos = src.find(ftype, m.end())
                        pre  = src[max(0,fpos-100):fpos]
                        if self._P_INJECT.search(pre):
                            info["relations"].append(("injects", clean, "«inject»"))
                        else:
                            info["relations"].append(("composes", clean, ""))

            # Methods
            for mm in self._P_METHOD.finditer(body):
                ret    = mm.group(1).strip()
                mname  = mm.group(2).strip()
                params = mm.group(3).strip()
                if mname in ("if","while","for","catch","switch"): continue
                param_list = []
                if params:
                    for p in params.split(","):
                        parts = p.strip().split()
                        if len(parts)>=2:
                            ptype = parts[-2].split("<")[0]
                            pname = parts[-1]
                            param_list.append((pname, ptype))
                            if (ptype not in self._PRIMITIVES and
                                    ptype[0:1].isupper()):
                                info["relations"].append(("depends", ptype, ""))
                info["methods"].append((mname, param_list, ret))

            # Constructor injection detection
            ctor_pattern = re.compile(
                rf"(?:public|protected)\s+{re.escape(cname)}\s*\(([^)]*)\)", re.M)
            for cm in ctor_pattern.finditer(body):
                params_raw = cm.group(1)
                for p in params_raw.split(","):
                    parts = p.strip().split()
                    if len(parts)>=2:
                        ptype = parts[-2].split("<")[0]
                        if (ptype not in self._PRIMITIVES and
                                ptype[0:1].isupper()):
                            info["relations"].append(("injects", ptype, "«inject»"))

            self.classes[cname] = info

    def _extract_body(self, src: str, start: int) -> str:
        """Extract content between matching braces starting at `start`."""
        depth=0; i=start
        begin=-1
        while i < len(src):
            if src[i]=="{":
                depth+=1
                if begin==-1: begin=i
            elif src[i]=="}":
                depth-=1
                if depth==0:
                    return src[begin+1:i]
            i+=1
        return src[begin+1:] if begin>=0 else ""

    def _build_diagram(self):
        boxes, arrows, floattexts = [], [], []
        box_id = {}

        _bid=[0]; _aid=[0]; _tid=[0]

        def new_box(x,y,w,h,label,color,shape="rect"):
            _bid[0]+=1
            b=dict(id=_bid[0],x=x,y=y,w=w,h=h,label=label,color=color,shape=shape)
            boxes.append(b); return b

        def new_arrow(sid,did,label,ls,hs):
            _aid[0]+=1
            arrows.append(dict(id=_aid[0],src_id=sid,dst_id=did,
                               label=label,line_style=ls,head_style=hs))

        def new_text(x,y,text,style="normal"):
            _tid[0]+=1
            floattexts.append(dict(id=_tid[0],x=x,y=y,text=text,style=style))

        external_libs = {}
        positions = auto_layout(list(self.classes.keys()))

        for cname,(cx,cy) in positions.items():
            info  = self.classes[cname]
            kind  = info["kind"]
            color = {"class":COLOR_CLASS,"abstract":COLOR_ABSTRACT,
                     "interface":COLOR_INTERFACE,"enum":COLOR_ENUM}.get(kind,COLOR_CLASS)

            header = f"«{kind}»\n{cname}" if kind != "class" else cname
            sep = "──────────────"
            field_lines  = "\n".join(f"  -{f}: {t}" for f,t in info["fields"][:5])
            method_lines = "\n".join(
                f"  +{m[0]}({', '.join(a+':'+t for a,t in m[1][:2])}): {m[2][:15]}"
                for m in info["methods"][:5])
            parts=[header]
            if field_lines:  parts+=[sep,field_lines]
            if method_lines: parts+=[sep,method_lines]
            label="\n".join(parts)

            w=max(190,11*max((len(l) for l in label.split("\n")),default=10))
            h=max(60, 17*len(label.split("\n")))
            b=new_box(cx,cy,w,h,label,color)
            box_id[cname]=b["id"]

        seen=set()
        for cname,info in self.classes.items():
            sid=box_id.get(cname)
            if not sid: continue
            for (rel,target,lbl) in info["relations"]:
                ls,hs=REL_STYLES.get(rel,("solid","open"))
                if target in box_id:
                    key=(sid,box_id[target],rel)
                    if key in seen: continue
                    seen.add(key)
                    new_arrow(sid,box_id[target],lbl,ls,hs)
                else:
                    imp=self.imports.get(target)
                    lib_label=target
                    if imp:
                        full,is_ext=imp
                        lib_label=target
                    if lib_label not in external_libs:
                        ex=900+len(external_libs)*10
                        ey=80+len(external_libs)*90
                        eb=new_box(ex,ey,160,50,lib_label,COLOR_EXTERNAL)
                        external_libs[lib_label]=eb["id"]
                    key=(sid,external_libs[lib_label],rel)
                    if key in seen: continue
                    seen.add(key)
                    new_arrow(sid,external_libs[lib_label],lbl,ls,hs)

        new_text(400,20,
                 f"Code Analysis — Java  ({len(self.classes)} classes, "
                 f"{len(self.imports)} imports)", "heading")
        new_text(50,20,
                 "──△ inherits  - -△ implements  ──◆ composes  ──◇ aggregates  - -▷ depends  «inject»=DI",
                 "normal")

        return dict(boxes=boxes,arrows=arrows,floattexts=floattexts)


# ═════════════════════════════════════════════════════════════════════════════
# UNIFIED ENTRY
# ═════════════════════════════════════════════════════════════════════════════

def _analyze_code_files(path: str) -> dict:
    """
    Analyze a file or directory of Python / Java source code.
    Returns a diagram dict ready for DiagramApp._deserialize().
    """
    p = Path(path)
    # Decide language
    if p.is_file():
        if p.suffix == ".py":
            return PythonAnalyzer().analyze_path(path)
        elif p.suffix == ".java":
            return JavaAnalyzer().analyze_path(path)
        else:
            raise ValueError(f"Unsupported file type: {p.suffix}")
    elif p.is_dir():
        # Mixed folder: run both
        py_files  = list(p.rglob("*.py"))
        java_files = list(p.rglob("*.java"))
        if py_files and not java_files:
            return PythonAnalyzer().analyze_path(path)
        elif java_files and not py_files:
            return JavaAnalyzer().analyze_path(path)
        elif py_files and java_files:
            # Prefer Python if more .py files
            if len(py_files) >= len(java_files):
                return PythonAnalyzer().analyze_path(path)
            else:
                return JavaAnalyzer().analyze_path(path)
        else:
            raise ValueError("No .py or .java files found in directory.")
    else:
        raise FileNotFoundError(path)

# ═══ SPRING BOOT PROJECT ANALYSER ═══════════════════════════════════════

# ── Colour per stereotype ────────────────────────────────────────────────────
LAYER_COLOR = {
    "controller": "Blue",
    "service":    "Purple",
    "repository": "Teal",
    "entity":     "Green",
    "config":     "Orange",
    "security":   "Red",
    "component":  "Purple",
    "feign":      "Blue",
    "external":   "Gray",
    "unknown":    "Gray",
}

# ── Arrow styles ─────────────────────────────────────────────────────────────
REL = {
    "inherits":   ("solid",  "inheritance"),
    "implements": ("dashed", "inheritance"),
    "composes":   ("solid",  "odiamond"),
    "aggregates": ("solid",  "diamond"),
    "injects":    ("dashed", "open"),
    "depends":    ("dashed", "open"),
}

# ── Spring stereotype annotation patterns ────────────────────────────────────
STEREO_PATTERNS = [
    ("controller", re.compile(r"@(?:Rest)?Controller\b")),
    ("feign",      re.compile(r"@FeignClient\b")),
    ("service",    re.compile(r"@Service\b")),
    ("repository", re.compile(r"@(?:Repository|RepositoryRestResource)\b")),
    ("entity",     re.compile(r"@(?:Entity|Table)\b")),
    ("config",     re.compile(r"@(?:Configuration|SpringBootApplication|EnableJpaRepositories|EnableCaching|EnableScheduling|EnableWebSecurity|EnableAsync|EnableTransactionManagement)\b")),
    ("security",   re.compile(r"@(?:PreAuthorize|PostAuthorize|Secured|RolesAllowed)\b|SecurityFilterChain|extends\s+(?:WebSecurityConfigurerAdapter|OncePerRequestFilter|BasicAuthenticationFilter)")),
    ("component",  re.compile(r"@Component\b")),
]

# ── JPA relationship annotations ─────────────────────────────────────────────
JPA_REL_PATTERNS = [
    re.compile(r"@OneToMany.*?(?:targetEntity\s*=\s*(\w+)\.class)?"),
    re.compile(r"@ManyToOne.*?(?:targetEntity\s*=\s*(\w+)\.class)?"),
    re.compile(r"@OneToOne.*?(?:targetEntity\s*=\s*(\w+)\.class)?"),
    re.compile(r"@ManyToMany.*?(?:targetEntity\s*=\s*(\w+)\.class)?"),
]
JPA_ANNO_RE  = re.compile(r"@(OneToMany|ManyToOne|OneToOne|ManyToMany)")
FIELD_TYPE_RE= re.compile(
    r"(?:private|protected|public)\s+(?:final\s+)?"
    r"([\w<>\[\],\s]+?)\s+(\w+)\s*(?:;|=)")
COLLECTION_RE= re.compile(r"(?:List|Set|Collection|Iterable|Page)\s*<\s*(\w+)\s*>")
IMPORT_RE    = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+);", re.M)
CLASS_RE     = re.compile(
    r"(?:public\s+|abstract\s+|final\s+)*(?:class|interface|enum)\s+(\w+)"
    r"(?:<[^>]*>)?"
    r"(?:\s+extends\s+([\w.<>, ]+?))?"
    r"(?:\s+implements\s+([\w.<>, ]+?))?"
    r"\s*\{", re.M)
CTOR_RE_TMPL = r"(?:public|protected)\s+{}\s*\(([^)]*)\)"
AUTOWIRED_RE = re.compile(r"@(?:Autowired|Inject|Resource)")
BEAN_RE      = re.compile(r"@Bean\b")
REQUEST_MAP  = re.compile(r"@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)"
                           r"(?:\([^)]*value\s*=\s*\"([^\"]*)\"|"
                           r"\(\"([^\"]*)\"|"
                           r"\([^)]*path\s*=\s*\"([^\"]*)\")?"
                           r"\s*\)?", re.M)
TRANSACT_RE  = re.compile(r"@Transactional\b")
FEIGN_URL    = re.compile(r"@FeignClient\s*\([^)]*(?:url|name)\s*=\s*['\"]([^'\"]+)['\"]")

# Known external infra identifiers from imports / property keys
EXTERNAL_IMPORTS = {
    "kafka":     ["KafkaTemplate","KafkaListener","ProducerFactory","ConsumerFactory",
                  "org.apache.kafka","spring.kafka"],
    "redis":     ["RedisTemplate","StringRedisTemplate","RedisRepository",
                  "spring.redis","org.springframework.data.redis"],
    "rabbit":    ["RabbitTemplate","RabbitListener","AmqpTemplate","spring.rabbitmq"],
    "s3":        ["AmazonS3","S3Client","S3Template","software.amazon.awssdk.services.s3"],
    "mail":      ["JavaMailSender","MailSender","spring.mail"],
    "elastic":   ["ElasticsearchClient","ElasticsearchOperations","spring.elasticsearch"],
    "mongo":     ["MongoTemplate","MongoRepository","spring.data.mongodb"],
    "jpa":       ["JpaRepository","CrudRepository","PagingAndSortingRepository"],
}

PRIMITIVES = {
    "void","int","long","double","float","boolean","char","byte","short",
    "String","Integer","Long","Double","Float","Boolean","Object","Number",
    "var","T","E","K","V","R","U","Optional","ResponseEntity","HttpStatus",
    "ModelAndView","HttpServletRequest","HttpServletResponse","Model",
    "Principal","Authentication","SecurityContext",
}


# ═════════════════════════════════════════════════════════════════════════════
class SpringAnalyzer:

    def __init__(self):
        self.classes    = {}   # name -> ClassInfo
        self.infra_nodes= {}   # label -> infra box dict
        self.prop_lines = []   # lines from application.properties/yml

    # ── Public ────────────────────────────────────────────────────────────────

    def analyze(self, root: str) -> dict:
        root = Path(root)
        self._scan_properties(root)
        self._scan_java_files(root)
        self._scan_pom_gradle(root)
        return self._build_diagram()

    # ── Scanning ──────────────────────────────────────────────────────────────

    def _scan_properties(self, root: Path):
        for pat in ("application.properties","application.yml",
                    "application-*.properties","application-*.yml"):
            for f in root.rglob(pat):
                try:
                    self.prop_lines += f.read_text(encoding="utf-8",errors="replace").splitlines()
                except Exception:
                    pass

    def _scan_pom_gradle(self, root: Path):
        for f in list(root.rglob("pom.xml"))[:1] + list(root.rglob("build.gradle"))[:1]:
            try:
                content = f.read_text(encoding="utf-8",errors="replace")
                # detect kafka, redis etc from dependency declarations
                for infra_key in ("kafka","redis","rabbit","s3","mail","elastic","mongo"):
                    if infra_key in content.lower():
                        self._ensure_infra(infra_key)
            except Exception:
                pass

    def _scan_java_files(self, root: Path):
        for f in sorted(root.rglob("*.java")):
            try:
                self._parse_java(f)
            except Exception:
                pass

    def _parse_java(self, path: Path):
        src = path.read_text(encoding="utf-8", errors="replace")

        # Collect imports
        imports = {m.group(1).split(".")[-1]: m.group(1)
                   for m in IMPORT_RE.finditer(src)}

        # Detect infra usage from imports
        for infra_key, markers in EXTERNAL_IMPORTS.items():
            for marker in markers:
                if marker in src:
                    self._ensure_infra(infra_key)

        # Detect infra from properties
        for line in self.prop_lines:
            for infra_key in ("kafka","redis","rabbit","s3","mail","elastic","mongo"):
                if infra_key in line.lower():
                    self._ensure_infra(infra_key)

        # Parse classes
        for m in CLASS_RE.finditer(src):
            cname = m.group(1)
            # grab preceding ~300 chars for annotations
            pre_start = max(0, m.start() - 300)
            pre = src[pre_start:m.start()]
            full_block = src[m.start():m.start()+1]  # minimal, body extracted below

            stereo = self._detect_stereo(pre, src, cname)
            extends_raw = m.group(2) or ""
            implements_raw = m.group(3) or ""

            info = {
                "name":      cname,
                "stereo":    stereo,
                "color":     LAYER_COLOR.get(stereo, "Gray"),
                "file":      path.stem,
                "relations": [],
                "endpoints": [],
                "beans":     [],
                "transactional": TRANSACT_RE.search(pre) is not None,
            }

            # Inheritance
            for base in [x.strip().split("<")[0] for x in extends_raw.split(",") if x.strip()]:
                info["relations"].append(("inherits", base, ""))

            # Implementation
            for iface in [x.strip().split("<")[0] for x in implements_raw.split(",") if x.strip()]:
                if iface:
                    info["relations"].append(("implements", iface, ""))

            # Extract body
            body = self._extract_body(src, m.end() - 1)

            # Endpoints
            for em in REQUEST_MAP.finditer(pre + body):
                path_val = em.group(1) or em.group(2) or em.group(3) or ""
                if path_val:
                    info["endpoints"].append(path_val)

            # @Bean methods
            if stereo == "config":
                bean_types = re.findall(r"@Bean\s+(?:public\s+)?(\w+)\s+\w+\s*\(", body)
                info["beans"] = bean_types

            # Fields → composition / aggregation / JPA
            self._parse_fields(body, info, imports)

            # Constructor injection
            self._parse_ctor_injection(body, cname, info, imports)

            # @Autowired field injection
            self._parse_autowired(body, info, imports)

            # FeignClient URL
            fm = FEIGN_URL.search(pre)
            if fm:
                info["feign_url"] = fm.group(1)

            self.classes[cname] = info

    def _detect_stereo(self, pre: str, src: str, cname: str) -> str:
        for stereo, pat in STEREO_PATTERNS:
            if pat.search(pre):
                return stereo
        # Heuristic from class name suffix
        name_lower = cname.lower()
        for suffix, stereo in [
            ("controller","controller"),("resource","controller"),
            ("service","service"),("serviceimpl","service"),
            ("repository","repository"),("repo","repository"),("dao","repository"),
            ("entity","entity"),("model","entity"),
            ("config","config"),("configuration","config"),
            ("filter","security"),("interceptor","security"),
            ("component","component"),
        ]:
            if name_lower.endswith(suffix):
                return stereo
        return "unknown"

    def _parse_fields(self, body: str, info: dict, imports: dict):
        # JPA annotation → relationship type
        jpa_anno_map = {
            "OneToMany":  "aggregates",
            "ManyToMany": "aggregates",
            "ManyToOne":  "composes",
            "OneToOne":   "composes",
        }
        # Split by semicolons to get field declarations
        for m in FIELD_TYPE_RE.finditer(body):
            ftype_raw = m.group(1).strip()
            fname     = m.group(2).strip()
            if fname in ("class","return","new","if","for","while","else",
                         "throw","catch","try","final","static","void"): continue

            # Check JPA annotation immediately before this field
            fpos = m.start()
            pre_field = body[max(0,fpos-150):fpos]
            jpa_match = JPA_ANNO_RE.search(pre_field)
            jpa_rel   = jpa_anno_map.get(jpa_match.group(1)) if jpa_match else None

            # Collection field
            col_m = COLLECTION_RE.match(ftype_raw)
            if col_m:
                inner = col_m.group(1)
                if inner not in PRIMITIVES:
                    rel = jpa_rel or "aggregates"
                    label = f"@{jpa_match.group(1)}" if jpa_match else "0..*"
                    info["relations"].append((rel, inner, label))
                continue

            # Generic single type
            clean = ftype_raw.split("<")[0].split("[")[0].strip()
            if clean and clean not in PRIMITIVES and clean[0].isupper():
                rel = jpa_rel or "composes"
                label = f"@{jpa_match.group(1)}" if jpa_match else ""
                info["relations"].append((rel, clean, label))

    def _parse_ctor_injection(self, body: str, cname: str, info: dict, imports: dict):
        ctor_pat = re.compile(
            CTOR_RE_TMPL.format(re.escape(cname)), re.M)
        for m in ctor_pat.finditer(body):
            params_raw = m.group(1)
            for p in params_raw.split(","):
                parts = p.strip().split()
                if len(parts) >= 2:
                    ptype = parts[-2].split("<")[0]
                    if ptype not in PRIMITIVES and ptype[0:1].isupper():
                        info["relations"].append(("injects", ptype, "«inject»"))

    def _parse_autowired(self, body: str, info: dict, imports: dict):
        # Find @Autowired / @Inject preceded field declarations
        for am in AUTOWIRED_RE.finditer(body):
            after = body[am.end():am.end()+150]
            fm = FIELD_TYPE_RE.search(after)
            if fm:
                ftype = fm.group(1).strip().split("<")[0].split("[")[0]
                if ftype not in PRIMITIVES and ftype[0:1].isupper():
                    info["relations"].append(("injects", ftype, "«inject»"))

    def _extract_body(self, src: str, start: int) -> str:
        depth = 0; i = start; begin = -1
        while i < len(src):
            if src[i] == "{":
                depth += 1
                if begin == -1: begin = i
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    return src[begin+1:i]
            i += 1
        return src[begin+1:] if begin >= 0 else ""

    def _ensure_infra(self, key: str):
        labels = {
            "kafka":   "Kafka\n(Message Broker)",
            "redis":   "Redis\n(Cache / Session)",
            "rabbit":  "RabbitMQ\n(Message Broker)",
            "s3":      "AWS S3\n(Object Storage)",
            "mail":    "SMTP\n(Email Server)",
            "elastic": "Elasticsearch\n(Search Engine)",
            "mongo":   "MongoDB\n(NoSQL DB)",
            "jpa":     "RDBMS\n(via JPA/Hibernate)",
        }
        if key not in self.infra_nodes:
            self.infra_nodes[key] = labels.get(key, key)

    # ── Diagram build ─────────────────────────────────────────────────────────

    def _build_diagram(self) -> dict:
        # Also detect datasource (JPA always means a DB)
        if any(info["stereo"] == "repository" for info in self.classes.values()):
            self._ensure_infra("jpa")
        # Check properties for datasource
        for line in self.prop_lines:
            if "spring.datasource" in line or "datasource.url" in line:
                self._ensure_infra("jpa")
                break

        # ── Layout strategy: layer rows ───────────────────────────────────────
        # Group by stereo
        layer_order = ["controller","feign","security","service",
                       "component","repository","entity","config","unknown"]
        layers = {l: [] for l in layer_order}
        for cname, info in self.classes.items():
            s = info["stereo"]
            if s not in layers: s = "unknown"
            layers[s].append(cname)

        # Remove empty
        layers = {k: v for k, v in layers.items() if v}

        BOX_W   = 190
        BOX_H   = 70
        COL_GAP = 20
        ROW_GAP = 50
        START_X = 40
        START_Y = 80

        positions = {}  # cname -> (x, y, w, h)
        y_cursor  = START_Y

        for stereo, names in layers.items():
            cols = min(4, len(names))
            for i, name in enumerate(names):
                col = i % cols
                row = i // cols
                x = START_X + col * (BOX_W + COL_GAP)
                y = y_cursor + row * (BOX_H + ROW_GAP // 2)
                # Adjust height for multi-line labels
                info = self.classes[name]
                label = self._make_label(info)
                lines = label.count("\n") + 1
                h = max(BOX_H, 16 * lines + 16)
                positions[name] = (x, y, BOX_W, h)
            # Advance cursor past this layer
            rows_in_layer = (len(names) - 1) // cols + 1
            max_h = max((positions[n][3] for n in names), default=BOX_H)
            y_cursor += rows_in_layer * (max_h + ROW_GAP // 2) + ROW_GAP

        # Infra nodes — stacked on the right
        infra_x = START_X + 4 * (BOX_W + COL_GAP) + 20
        infra_y = START_Y
        infra_positions = {}
        for key, label in self.infra_nodes.items():
            infra_positions[key] = (infra_x, infra_y, 160, 60)
            infra_y += 80

        # ── Emit boxes & arrows ───────────────────────────────────────────────
        boxes, arrows, floattexts = [], [], []
        box_id    = {}
        _bid = [0]; _aid = [0]; _tid = [0]

        def new_box(x, y, w, h, label, color, shape="rect"):
            _bid[0] += 1
            b = dict(id=_bid[0], x=x, y=y, w=w, h=h,
                     label=label, color=color, shape=shape)
            boxes.append(b); return b

        def new_arrow(sid, did, label, ls, hs):
            _aid[0] += 1
            arrows.append(dict(id=_aid[0], src_id=sid, dst_id=did,
                               label=label, line_style=ls, head_style=hs,
                               orthogonal=False))

        def new_text(x, y, text, style="normal"):
            _tid[0] += 1
            floattexts.append(dict(id=_tid[0], x=x, y=y, text=text, style=style))

        # Layer headers
        y_header = START_Y - 24
        for stereo, names in layers.items():
            if not names: continue
            first_x = positions[names[0]][0]
            last_x, last_w = positions[names[-1]][0], positions[names[-1]][2]
            mid_x = (first_x + last_x + last_w) / 2
            label_map = {
                "controller": "@RestController / @Controller",
                "feign":      "@FeignClient",
                "security":   "Security / Filter",
                "service":    "@Service",
                "component":  "@Component",
                "repository": "@Repository / JpaRepository",
                "entity":     "@Entity (JPA)",
                "config":     "@Configuration / @Bean",
                "unknown":    "Other classes",
            }
            new_text(mid_x, y_header, label_map.get(stereo, stereo), "note")
            # update header y for next layer
            y_header = max(positions[n][1] + positions[n][3] for n in names) + 26

        # Class boxes
        for cname, (x, y, w, h) in positions.items():
            info  = self.classes[cname]
            label = self._make_label(info)
            color = info["color"]
            b = new_box(x, y, w, h, label, color)
            box_id[cname] = b["id"]

        # Infra boxes
        infra_ids = {}
        for key, (x, y, w, h) in infra_positions.items():
            label = self.infra_nodes[key]
            b = new_box(x, y, w, h, label, "Gray", "cylinder" if "DB" in label or "SQL" in label or "Mongo" in label else "rect")
            infra_ids[key] = b["id"]

        # Arrows between classes
        seen = set()
        for cname, info in self.classes.items():
            sid = box_id.get(cname)
            if not sid: continue
            for (rel, target, lbl) in info["relations"]:
                ls, hs = REL.get(rel, ("dashed", "open"))
                if target in box_id:
                    key = (sid, box_id[target], rel)
                    if key in seen: continue
                    seen.add(key)
                    new_arrow(sid, box_id[target], lbl, ls, hs)
                else:
                    # Try infra
                    for infra_key, markers in EXTERNAL_IMPORTS.items():
                        if target in markers and infra_key in infra_ids:
                            key = (sid, infra_ids[infra_key], "depends")
                            if key not in seen:
                                seen.add(key)
                                new_arrow(sid, infra_ids[infra_key], "", "dashed", "open")

        # Service → infra arrows (from field types like KafkaTemplate, RedisTemplate)
        for cname, info in self.classes.items():
            sid = box_id.get(cname)
            if not sid: continue
            for (rel, target, lbl) in info["relations"]:
                for infra_key, markers in EXTERNAL_IMPORTS.items():
                    if target in markers and infra_key in infra_ids:
                        key = (sid, infra_ids[infra_key], rel)
                        if key not in seen:
                            seen.add(key)
                            new_arrow(sid, infra_ids[infra_key], "", "dashed", "open")

        # Title
        n_cls  = len(self.classes)
        n_rel  = len(arrows)
        n_inf  = len(self.infra_nodes)
        new_text(340, 30,
                 f"Spring Boot Architecture  —  {n_cls} classes · {n_rel} relationships · {n_inf} infra nodes",
                 "heading")

        # Legend
        new_text(40, 20,
                 "──△ inherits  - -△ implements  ──◆ composes  ──◇ aggregates  - -▷ «inject» DI",
                 "normal")

        return dict(boxes=boxes, arrows=arrows, floattexts=floattexts)

    def _make_label(self, info: dict) -> str:
        name  = info["name"]
        stereo = info["stereo"]
        sep   = "──────────────"

        # Stereotype header
        stereo_display = {
            "controller": "«controller»",
            "feign":      "«feign client»",
            "service":    "«service»",
            "repository": "«repository»",
            "entity":     "«entity»",
            "config":     "«configuration»",
            "security":   "«security»",
            "component":  "«component»",
        }
        header = stereo_display.get(stereo, "")
        lines  = []
        if header:
            lines.append(header)
        lines.append(name)

        # Endpoints (max 3)
        eps = info.get("endpoints", [])[:3]
        if eps:
            lines.append(sep)
            for ep in eps:
                lines.append(f"  {ep}")

        # Beans (max 3)
        beans = info.get("beans", [])[:3]
        if beans:
            lines.append(sep)
            for b in beans:
                lines.append(f"  @Bean {b}")

        # Transactional note
        if info.get("transactional"):
            if sep not in lines: lines.append(sep)
            lines.append("  @Transactional")

        return "\n".join(lines)


# ── Unified entry (called from code_analyzer.py or directly) ─────────────────

def _analyze_spring_project(path: str) -> dict:
    """
    Analyze a Spring Boot project folder.
    Returns diagram dict for DiagramApp._deserialize().
    """
    return SpringAnalyzer().analyze(path)

# ═══ DIAGRAM TOOL — MAIN APPLICATION ════════════════════════════════════

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

        tk.Button(tb, text="✍ Text to Diagram", bg="#5c3a1e", fg="white",
                  relief="flat", padx=10, pady=8, cursor="hand2",
                  font=("Segoe UI",10,"bold"),
                  command=self._show_text_diagram).pack(side="left",padx=3,pady=6)

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
        """Show a clean picker dialog — Python file, Java file, or Spring Boot folder."""
        dlg = tk.Toplevel(self.root)
        dlg.title("🔍 Analyse Code")
        dlg.configure(bg=BG)
        dlg.geometry("560x400")
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Analyse Code → Generate Class Diagram",
                 bg=BG, fg=TEXT_LIGHT, font=("Segoe UI",13,"bold"), pady=14).pack()
        tk.Label(dlg, text="Choose what you want to analyse:",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI",10)).pack(pady=(0,10))

        chosen_path = [None]
        chosen_mode = [None]

        def pick_and_run(mode):
            chosen_mode[0] = mode
            if mode == "python":
                path = filedialog.askopenfilename(
                    parent=dlg, title="Select Python file or folder",
                    filetypes=[("Python files","*.py"),("All files","*.*")])
                if not path:
                    path = filedialog.askdirectory(
                        parent=dlg, title="Or select a Python project folder")
            elif mode == "java":
                path = filedialog.askopenfilename(
                    parent=dlg, title="Select Java file or folder",
                    filetypes=[("Java files","*.java"),("All files","*.*")])
                if not path:
                    path = filedialog.askdirectory(
                        parent=dlg, title="Or select a Java project folder")
            elif mode == "spring":
                path = filedialog.askdirectory(
                    parent=dlg,
                    title="Select Spring Boot project ROOT folder (contains pom.xml / build.gradle)")
            else:
                return

            if not path:
                return

            chosen_path[0] = path
            dlg.destroy()
            self._run_analysis(path, mode)

        # ── Three big option cards ──────────────────────────────────────────
        cards_frame = tk.Frame(dlg, bg=BG)
        cards_frame.pack(fill="both", expand=True, padx=20, pady=5)

        options = [
            ("python", "🐍  Python",
             ".py file or project folder",
             "Detects classes, inheritance,\ncomposition, aggregation, DI",
             "#1e3d2e", "#3aaa6a"),
            ("java",   "☕  Java",
             ".java file or project folder",
             "Detects classes, interfaces,\n@Autowired, JPA annotations",
             "#2e3a5c", "#5a7ec8"),
            ("spring", "🍃  Spring Boot",
             "Project root folder (has pom.xml)",
             "Scans all layers:\nController → Service → Repository → Entity",
             "#3a2e5c", "#7c6fcd"),
        ]

        for col, (mode, title, subtitle, desc, fill, border) in enumerate(options):
            card = tk.Frame(cards_frame, bg=fill, cursor="hand2",
                           relief="flat", padx=12, pady=14)
            card.grid(row=0, column=col, padx=8, pady=4, sticky="nsew")
            cards_frame.columnconfigure(col, weight=1)

            tk.Label(card, text=title, bg=fill, fg="white",
                     font=("Segoe UI",13,"bold")).pack(anchor="w")
            tk.Label(card, text=subtitle, bg=fill, fg="#ccddcc",
                     font=("Segoe UI",8)).pack(anchor="w", pady=(2,6))
            tk.Label(card, text=desc, bg=fill, fg="#aaccaa",
                     font=("Segoe UI",8), justify="left").pack(anchor="w", pady=(0,10))

            btn = tk.Button(card, text="Browse & Analyse →",
                           bg=border, fg="white", relief="flat",
                           padx=10, pady=5, cursor="hand2",
                           font=("Segoe UI",9,"bold"),
                           command=lambda m=mode: pick_and_run(m))
            btn.pack(anchor="s", fill="x")

            # Make whole card clickable
            for w in (card,):
                w.bind("<Button-1>", lambda e, m=mode: pick_and_run(m))

        tk.Frame(dlg, bg=SURFACE2, height=1).pack(fill="x", pady=10, padx=20)
        tk.Label(dlg,
                 text="UML arrows: ──△ inherits  - -△ implements  ──◆ composes  ──◇ aggregates  - -▷ «inject» DI",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI",8)).pack()
        tk.Button(dlg, text="Cancel", bg=SURFACE2, fg=TEXT_MUTED,
                  relief="flat", padx=16, pady=4, cursor="hand2",
                  command=dlg.destroy).pack(pady=8)

    def _run_analysis(self, path, mode):
        """Actually run the chosen analyser and load result onto canvas."""
        try:
            self.status_var.set(f"Analysing {mode}: {os.path.basename(path)} …")
            self.root.update()

            if mode == "spring":
                data = _analyze_spring_project(path)
            elif mode in ("python", "java"):
                data = _analyze_code_files(path)
            else:
                data = _analyze_code_files(path)

        except Exception as e:
            messagebox.showerror("Analysis Error",
                f"Could not analyse:\n\n{e}\n\n"
                "Check the file/folder is a valid Python or Java project.")
            return

        if not data.get("boxes"):
            messagebox.showinfo("No Classes Found",
                "No classes were detected.\n"
                "Make sure the file/folder contains class definitions.")
            return

        if (self.boxes or self.arrows) and not messagebox.askyesno(
                "Load Analysis", "Replace current canvas with analysis result?"):
            return

        self._push_undo()
        Box._id = Arrow._id = FloatText._id = 0
        self._deserialize(data)
        self.offset_x = 30; self.offset_y = 50
        # Auto-zoom: smaller zoom for larger diagrams
        n_boxes = len(data.get("boxes", []))
        if n_boxes > 25:   z = 0.5
        elif n_boxes > 15: z = 0.65
        elif n_boxes > 8:  z = 0.8
        else:              z = 0.9
        self.zoom = z; self.zoom_var.set(f"{int(z*100)}%")
        self._draw_all()
        n_cls = len(self.boxes); n_rel = len(self.arrows)
        self.status_var.set(
            f"Analysis complete  •  {n_cls} classes · {n_rel} relationships  •  "
            f"Scroll to zoom · Drag to pan · Double-click to edit")


    # ═══ TEXT TO DIAGRAM ══════════════════════════════════════════════════════

    def _show_text_diagram(self):
        """
        Text-to-Diagram panel.
        Type plain English or DSL syntax — diagram draws live as you type.

        DSL Syntax:
          # comment
          NodeType: Node Name [color: blue] [label: optional badge]
          Node A -> Node B [label: arrow label]
          Node A --> Node B   (dashed arrow)
          Node A <-> Node B   (bidirectional)

        Node types (set colour automatically):
          Actor   System   Database   Queue   Cloud
          Service   UI   API

        Colours: blue green purple teal orange red gray yellow pink

        Export: Click "Load to Canvas" to push the diagram onto the main canvas.
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("✍ Text to Diagram")
        dlg.configure(bg=BG)
        dlg.geometry("1100x680")
        dlg.resizable(True, True)

        # ── Colour tables ──────────────────────────────────────────────────
        NODE_FILLS = {
            "actor":    ("Gray",   "#2e2e3e","#666688"),
            "system":   ("Blue",   "#2e3a5c","#5a7ec8"),
            "database": ("Teal",   "#1e3d3a","#3aaaa0"),
            "queue":    ("Orange", "#4a3020","#cc7744"),
            "cloud":    ("Green",  "#1e3d2e","#3aaa6a"),
            "service":  ("Purple", "#3a2e5c","#7c6fcd"),
            "ui":       ("Pink",   "#3a1e3a","#cc44cc"),
            "api":      ("Yellow", "#3a3a1e","#aaaa3a"),
            "default":  ("Blue",   "#2e3a5c","#5a7ec8"),
        }
        COLOR_MAP = {
            "blue":   ("#2e3a5c","#5a7ec8"), "green":  ("#1e3d2e","#3aaa6a"),
            "purple": ("#3a2e5c","#7c6fcd"), "teal":   ("#1e3d3a","#3aaaa0"),
            "orange": ("#4a3020","#cc7744"), "red":    ("#4a2020","#cc4444"),
            "gray":   ("#2e2e3e","#666688"), "yellow": ("#3a3a1e","#aaaa3a"),
            "pink":   ("#3a1e3a","#cc44cc"),
        }
        DIAGRAM_COLOR_MAP = {
            "blue":"Blue","green":"Green","purple":"Purple","teal":"Teal",
            "orange":"Orange","red":"Red","gray":"Gray","yellow":"Yellow","pink":"Pink",
        }
        TYPE_COLOR_MAP = {
            "actor":"Gray","system":"Blue","database":"Teal","queue":"Orange",
            "cloud":"Green","service":"Purple","ui":"Pink","api":"Yellow",
        }

        # ── State ─────────────────────────────────────────────────────────
        parsed_nodes = {}   # name -> {type, color, fill, stroke}
        parsed_edges = []   # {src, dst, op, lbl}

        # ── Parse ──────────────────────────────────────────────────────────
        import re as _re
        TYPE_RE  = _re.compile(r"^(Actor|System|Database|Queue|Cloud|Service|UI|API|DB):\s*(.+)", _re.I)
        EDGE_RE  = _re.compile(r"^(.+?)\s*(<->|-->|->)\s*(.+)")
        LBL_RE   = _re.compile(r"\[label:\s*([^\]]+)\]")
        COL_RE   = _re.compile(r"\[color:\s*(\w+)\]")

        def clean(s): return _re.sub(r"\[.*?\]","",s).strip()
        def get_lbl(s):
            m=LBL_RE.search(s); return m.group(1).strip() if m else ""
        def get_col(s):
            m=COL_RE.search(s); return m.group(1).lower() if m else None

        def do_parse(text):
            parsed_nodes.clear(); parsed_edges.clear()
            for raw in text.split("\n"):
                line=raw.strip()
                if not line or line.startswith("#"): continue
                tm=TYPE_RE.match(line)
                if tm:
                    typ=tm.group(1).lower(); rest=tm.group(2)
                    nm=clean(rest); col=get_col(rest)
                    base=NODE_FILLS.get(typ,NODE_FILLS["default"])
                    if col and col in COLOR_MAP:
                        fill,stroke=COLOR_MAP[col]
                        dcolor=DIAGRAM_COLOR_MAP.get(col,"Blue")
                    else:
                        dcolor,fill,stroke=base
                    parsed_nodes[nm]={"type":typ,"color":dcolor,"fill":fill,"stroke":stroke}
                    continue
                em=EDGE_RE.match(line)
                if em:
                    src=clean(em.group(1)); op=em.group(2); rest2=em.group(3)
                    dst=clean(rest2); lbl=get_lbl(rest2) or get_lbl(em.group(1))
                    for nm in (src,dst):
                        if nm not in parsed_nodes:
                            parsed_nodes[nm]={"type":"default","color":"Blue",
                                              "fill":"#2e3a5c","stroke":"#5a7ec8"}
                    parsed_edges.append({"src":src,"dst":dst,"op":op,"lbl":lbl})

        # ── Layout ─────────────────────────────────────────────────────────
        def do_layout(node_positions=None):
            names=list(parsed_nodes.keys()); n=len(names)
            if not n: return {}
            in_deg={nm:0 for nm in names}
            for e in parsed_edges: in_deg[e["dst"]]=in_deg.get(e["dst"],0)+1
            roots=[nm for nm in names if in_deg.get(nm,0)==0] or [names[0]]
            layers=[]; placed=set()
            layer=roots[:]
            while layer and len(placed)<n:
                layer=[nm for nm in layer if nm not in placed]
                if not layer: break
                layers.append(layer); placed.update(layer)
                nxt=set()
                for src in layer:
                    for e in parsed_edges:
                        if e["src"]==src and e["dst"] not in placed:
                            nxt.add(e["dst"])
                layer=list(nxt)
            remain=[nm for nm in names if nm not in placed]
            if remain: layers.append(remain)
            CW,RH,SX,SY=200,110,40,40
            pos={}
            for li,lay in enumerate(layers):
                for ci,nm in enumerate(lay):
                    pos[nm]=(SX+ci*(CW+20), SY+li*(RH+20))
            return pos

        # ── Canvas draw ────────────────────────────────────────────────────
        pos_cache={}

        def draw_canvas():
            c=preview_canvas; c.delete("all")
            W=c.winfo_width() or 800; H=c.winfo_height() or 500
            # Grid
            for x in range(0,W,40): c.create_line(x,0,x,H,fill="#252535",width=1)
            for y in range(0,H,40): c.create_line(0,y,W,y,fill="#252535",width=1)
            if not parsed_nodes: return
            pos=do_layout()
            pos_cache.update(pos)
            BOX_W,BOX_H=160,52
            # Edges first
            for e in parsed_edges:
                sp=pos.get(e["src"]); dp=pos.get(e["dst"])
                if not sp or not dp: continue
                x1=sp[0]+BOX_W//2; y1=sp[1]+BOX_H//2
                x2=dp[0]+BOX_W//2; y2=dp[1]+BOX_H//2
                dash=(6,4) if e["op"]=="-->" else ()
                c.create_line(x1,y1,x2,y2,fill="#6878a8",width=1.5,dash=dash,
                              arrow=tk.LAST,arrowshape=(10,12,4))
                if e["op"]=="<->":
                    c.create_line(x1,y1,x2,y2,fill="#6878a8",width=1.5,
                                  arrow=tk.FIRST,arrowshape=(10,12,4))
                if e["lbl"]:
                    mx,my=(x1+x2)//2,(y1+y2)//2
                    c.create_rectangle(mx-40,my-10,mx+40,my+10,fill="#1a1a2e",outline="")
                    c.create_text(mx,my,text=e["lbl"],fill="#a89ee8",
                                  font=("Segoe UI",9))
            # Nodes
            for nm,nd in parsed_nodes.items():
                p=pos.get(nm)
                if not p: continue
                x,y=p; fill=nd["fill"]; stroke=nd["stroke"]; typ=nd["type"]
                if typ=="actor":
                    # Stick figure
                    cx=x+BOX_W//2; r=10; hy=y+r+4
                    c.create_oval(cx-r,y,cx+r,y+r*2,fill=fill,outline=stroke)
                    c.create_line(cx,y+r*2,cx,y+r*2+20,fill=stroke,width=1.5)
                    c.create_line(cx-15,y+r*3+2,cx+15,y+r*3+2,fill=stroke,width=1.5)
                    c.create_line(cx,y+r*2+20,cx-12,y+r*2+34,fill=stroke,width=1.5)
                    c.create_line(cx,y+r*2+20,cx+12,y+r*2+34,fill=stroke,width=1.5)
                    c.create_text(cx,y+BOX_H,text=nm,fill="#e0dff5",
                                  font=("Segoe UI",10,"bold"))
                elif typ=="database":
                    ry=8; cx=x+BOX_W//2
                    c.create_oval(x,y,x+BOX_W,y+ry*2,fill=fill,outline=stroke)
                    c.create_rectangle(x,y+ry,x+BOX_W,y+BOX_H-ry,fill=fill,outline="")
                    c.create_oval(x,y+BOX_H-ry*2,x+BOX_W,y+BOX_H,fill=fill,outline=stroke)
                    c.create_line(x,y+ry,x,y+BOX_H-ry,fill=stroke)
                    c.create_line(x+BOX_W,y+ry,x+BOX_W,y+BOX_H-ry,fill=stroke)
                    c.create_text(cx,y+BOX_H//2,text=nm,fill="#e0dff5",
                                  font=("Segoe UI",10,"bold"))
                elif typ=="queue":
                    rx=BOX_H//2; cx=x+BOX_W//2
                    pts=[x+rx,y, x+BOX_W-rx,y]
                    c.create_arc(x+BOX_W-rx*2,y,x+BOX_W,y+BOX_H,start=270,extent=180,
                                 fill=fill,outline=stroke)
                    c.create_arc(x,y,x+rx*2,y+BOX_H,start=90,extent=180,
                                 fill=fill,outline=stroke)
                    c.create_rectangle(x+rx,y,x+BOX_W-rx,y+BOX_H,fill=fill,outline="")
                    c.create_line(x+rx,y,x+BOX_W-rx,y,fill=stroke)
                    c.create_line(x+rx,y+BOX_H,x+BOX_W-rx,y+BOX_H,fill=stroke)
                    c.create_text(cx,y+BOX_H//2,text=nm,fill="#e0dff5",
                                  font=("Segoe UI",10,"bold"))
                else:
                    # Standard rect with accent bar
                    c.create_rectangle(x+3,y+3,x+BOX_W+3,y+BOX_H+3,fill="#111122",outline="")
                    c.create_rectangle(x,y,x+BOX_W,y+BOX_H,fill=fill,outline=stroke)
                    c.create_rectangle(x,y,x+BOX_W,y+5,fill=stroke,outline="")
                    # Type badge
                    badge=typ.upper() if typ!="default" else ""
                    cx_nm=x+BOX_W//2
                    if badge:
                        c.create_text(cx_nm,y+16,text=badge,fill="#888aaa",
                                      font=("Segoe UI",8))
                        c.create_text(cx_nm,y+34,text=nm,fill="#e0dff5",
                                      font=("Segoe UI",10,"bold"))
                    else:
                        c.create_text(cx_nm,y+BOX_H//2,text=nm,fill="#e0dff5",
                                      font=("Segoe UI",10,"bold"))
            # Stats
            c.create_text(8,8,anchor="nw",
                          text=f"{len(parsed_nodes)} nodes  {len(parsed_edges)} edges",
                          fill="#555577",font=("Segoe UI",8))

        # ── Build UI ───────────────────────────────────────────────────────
        # Top row: quick-insert buttons
        top = tk.Frame(dlg, bg=SURFACE); top.pack(fill="x", padx=0)
        tk.Label(top, text="✍ Text to Diagram", bg=SURFACE, fg=TEXT_LIGHT,
                 font=("Segoe UI",12,"bold"), pady=8, padx=12).pack(side="left")

        # Snippet buttons
        snip_frame = tk.Frame(top, bg=SURFACE); snip_frame.pack(side="left", padx=8)
        snippets=[
            ("+ Actor",   "Actor: "),("+ System",  "System: "),
            ("+ DB",      "Database: "),("+ Queue", "Queue: "),
            ("+ Service", "Service: "),("+ API",    "API: "),
            ("→ arrow",   " -> "),("- -> dashed"," --> "),
            ("↔ both",   " <-> "),
        ]
        for label, txt in snippets:
            def make_insert(t):
                def do():
                    editor.insert(tk.INSERT, t); on_change()
                return do
            tk.Button(snip_frame, text=label, bg=SURFACE2, fg=ACCENT2,
                      relief="flat", padx=6, pady=3, cursor="hand2",
                      font=("Segoe UI",8), command=make_insert(txt)
                      ).pack(side="left", padx=2, pady=4)

        # Example buttons — scrollable categorised panel
        ex_outer = tk.Frame(dlg, bg=SURFACE2, height=70)
        ex_outer.pack(fill="x"); ex_outer.pack_propagate(False)
        ex_cv = tk.Canvas(ex_outer, bg=SURFACE2, height=66, highlightthickness=0)
        ex_sb = tk.Scrollbar(ex_outer, orient="horizontal", command=ex_cv.xview)
        ex_cv.configure(xscrollcommand=ex_sb.set)
        ex_sb.pack(side="bottom", fill="x")
        ex_cv.pack(fill="both", expand=True)
        ex_inner = tk.Frame(ex_cv, bg=SURFACE2)
        ex_cv.create_window((0,0), window=ex_inner, anchor="nw")

        EXAMPLES_TXT = {
            "CI/CD Pipeline": """# CI/CD Pipeline  (GitHub Actions / Jenkins)
Actor: Developer
System: GitHub [color: gray]
System: GitHub Actions [color: blue]
System: SonarQube [color: teal]
System: Trivy Scanner [color: red]
System: Docker Registry [color: purple]
System: Kubernetes Dev [color: teal]
System: Kubernetes Prod [color: green]
System: Prometheus [color: orange]
System: Slack [color: gray]

Developer -> GitHub [label: git push / PR]
GitHub -> GitHub Actions [label: webhook trigger]
GitHub Actions -> SonarQube [label: code quality scan]
GitHub Actions -> Trivy Scanner [label: image security scan]
GitHub Actions -> Docker Registry [label: push image]
Docker Registry -> Kubernetes Dev [label: deploy to dev]
Kubernetes Dev --> GitHub Actions [label: health check OK]
GitHub Actions -> Kubernetes Prod [label: promote to prod]
Kubernetes Dev -> Prometheus [label: metrics]
Kubernetes Prod -> Prometheus [label: metrics]
GitHub Actions -> Slack [label: notify team]""",
            "Spring Boot App": """# Spring Boot Application Architecture
Actor: Client
API: API Gateway [color: blue]
Service: ProductController [color: blue]
Service: OrderController [color: blue]
Service: ProductService [color: purple]
Service: OrderService [color: purple]
Service: NotificationService [color: purple]
Database: PostgreSQL [color: teal]
Queue: Kafka [color: orange]
System: Redis Cache [color: red]
System: Email SMTP [color: gray]
System: Feign Client [color: yellow]

Client -> API Gateway [label: HTTPS]
API Gateway -> ProductController [label: /api/products]
API Gateway -> OrderController [label: /api/orders]
ProductController -> ProductService [label: delegate]
OrderController -> OrderService [label: delegate]
ProductService -> Redis Cache [label: @Cacheable]
ProductService -> PostgreSQL [label: JPA query]
OrderService -> PostgreSQL [label: @Transactional]
OrderService -> Kafka [label: order.placed event]
Kafka -> NotificationService [label: @KafkaListener]
NotificationService -> Email SMTP [label: send email]
OrderService -> Feign Client [label: call payment API]""",
            "Microservices": """# Microservices Architecture  (E-Commerce)
Actor: Client Browser
Actor: Mobile App
API: API Gateway / Load Balancer [color: blue]
Service: Auth Service [color: purple]
Service: Product Service [color: purple]
Service: Order Service [color: purple]
Service: Payment Service [color: orange]
Service: Inventory Service [color: teal]
Service: Notification Service [color: gray]
Queue: Kafka Message Bus [color: yellow]
Database: Auth DB [color: green]
Database: Product DB [color: green]
Database: Order DB [color: green]
System: Redis Session Store [color: red]
System: Elasticsearch [color: blue]
System: Payment Gateway [color: orange]

Client Browser -> API Gateway / Load Balancer [label: HTTPS]
Mobile App -> API Gateway / Load Balancer [label: HTTPS]
API Gateway / Load Balancer -> Auth Service [label: JWT validate]
API Gateway / Load Balancer -> Product Service
API Gateway / Load Balancer -> Order Service
Auth Service -> Auth DB
Auth Service -> Redis Session Store [label: cache token]
Product Service -> Product DB
Product Service -> Elasticsearch [label: full-text search]
Order Service -> Order DB
Order Service -> Kafka Message Bus [label: order.placed]
Order Service -> Payment Service [label: charge request]
Payment Service -> Payment Gateway [label: Razorpay/Stripe]
Kafka Message Bus -> Inventory Service [label: reserve stock]
Kafka Message Bus -> Notification Service [label: send email/SMS]""",
            "DevSecOps": """# DevSecOps Pipeline  (Enterprise)
Actor: Developer
Actor: Security Team
System: GitLab [color: orange]
System: GitLab CI [color: orange]
System: SonarQube [color: blue]
System: OWASP ZAP [color: red]
System: Trivy [color: red]
System: Checkov IaC [color: red]
System: Nexus Artifactory [color: purple]
System: Kubernetes Dev [color: teal]
System: Kubernetes Staging [color: yellow]
System: Kubernetes Prod [color: green]
System: Prometheus + Grafana [color: orange]
System: PagerDuty [color: gray]

Developer -> GitLab [label: git push]
GitLab -> GitLab CI [label: pipeline trigger]
GitLab CI -> SonarQube [label: SAST scan]
GitLab CI -> OWASP ZAP [label: DAST scan]
GitLab CI -> Trivy [label: container scan]
GitLab CI -> Checkov IaC [label: IaC policy check]
GitLab CI -> Nexus Artifactory [label: publish artifact]
Nexus Artifactory -> Kubernetes Dev [label: deploy]
Kubernetes Dev --> GitLab CI [label: smoke tests]
GitLab CI -> Kubernetes Staging [label: promote]
GitLab CI -> Kubernetes Prod [label: blue-green deploy]
Kubernetes Prod -> Prometheus + Grafana [label: metrics]""",
            "Kubernetes": """# Kubernetes Cluster Architecture
Actor: Developer
Actor: End User
System: kubectl / Helm [color: gray]
System: Ingress Controller [color: blue]
Service: Auth Pod x3 [color: purple]
Service: API Pod x5 [color: purple]
Service: Worker Pod x3 [color: teal]
System: HorizontalPodAutoscaler [color: orange]
System: ConfigMap + Secret [color: gray]
Database: PostgreSQL StatefulSet [color: green]
Queue: Kafka StatefulSet [color: orange]
System: Persistent Volume [color: teal]
System: Prometheus [color: orange]
System: Grafana [color: yellow]
Cloud: Container Registry [color: blue]

Developer -> kubectl / Helm [label: apply manifests]
kubectl / Helm -> Container Registry [label: pull images]
End User -> Ingress Controller [label: HTTPS request]
Ingress Controller -> Auth Pod x3 [label: /auth/*]
Ingress Controller -> API Pod x5 [label: /api/*]
API Pod x5 -> PostgreSQL StatefulSet [label: queries]
API Pod x5 -> Kafka StatefulSet [label: publish events]
Kafka StatefulSet -> Worker Pod x3 [label: consume]
Worker Pod x3 -> PostgreSQL StatefulSet [label: write]
PostgreSQL StatefulSet -> Persistent Volume [label: data]
HorizontalPodAutoscaler -> API Pod x5 [label: scale 2-10]
Prometheus -> API Pod x5 [label: scrape /metrics]
Prometheus -> Grafana [label: datasource]""",
            "AWS Architecture": """# AWS 3-Tier Web Architecture
Actor: User
Cloud: CloudFront CDN [color: orange]
Cloud: Route 53 DNS [color: gray]
Cloud: WAF [color: red]
Cloud: ALB Load Balancer [color: blue]
Service: EC2 Auto Scaling Group [color: blue]
Cloud: RDS PostgreSQL Multi-AZ [color: green]
Cloud: ElastiCache Redis [color: red]
Cloud: S3 Static Assets [color: orange]
Cloud: SQS Queue [color: yellow]
Cloud: Lambda Functions [color: purple]
Cloud: SNS Notifications [color: gray]
Cloud: CloudWatch [color: orange]
Cloud: Secrets Manager [color: red]

User -> Route 53 DNS [label: DNS resolve]
Route 53 DNS -> CloudFront CDN [label: edge cache]
CloudFront CDN -> WAF [label: filter traffic]
CloudFront CDN -> S3 Static Assets [label: static files]
WAF -> ALB Load Balancer [label: clean traffic]
ALB Load Balancer -> EC2 Auto Scaling Group [label: distribute]
EC2 Auto Scaling Group -> RDS PostgreSQL Multi-AZ [label: read/write]
EC2 Auto Scaling Group -> ElastiCache Redis [label: cache]
EC2 Auto Scaling Group -> SQS Queue [label: async jobs]
SQS Queue -> Lambda Functions [label: trigger]
Lambda Functions -> SNS Notifications [label: notify]
EC2 Auto Scaling Group -> CloudWatch [label: logs/metrics]""",
            "Azure Architecture": """# Azure Cloud Architecture
Actor: User
Cloud: Azure Front Door [color: blue]
Cloud: Azure API Management [color: purple]
Service: App Service Plan [color: blue]
Service: Azure Functions [color: purple]
Cloud: Azure Service Bus [color: orange]
Database: Azure SQL Managed [color: green]
Database: Cosmos DB [color: teal]
Cloud: Azure Redis Cache [color: red]
Cloud: Azure Blob Storage [color: gray]
Cloud: Azure AD B2C [color: blue]
Cloud: Azure Key Vault [color: red]
Cloud: Azure Monitor [color: orange]
Cloud: Logic Apps [color: yellow]

User -> Azure Front Door [label: global routing]
Azure Front Door -> Azure API Management [label: API facade]
Azure API Management -> Azure AD B2C [label: auth/OAuth2]
Azure API Management -> App Service Plan [label: REST calls]
App Service Plan -> Azure SQL Managed [label: OLTP data]
App Service Plan -> Cosmos DB [label: NoSQL/JSON]
App Service Plan -> Azure Redis Cache [label: session cache]
App Service Plan -> Azure Service Bus [label: async events]
Azure Service Bus -> Azure Functions [label: trigger]
Azure Functions -> Azure Blob Storage [label: file ops]
Azure Functions -> Logic Apps [label: workflow]
Azure Monitor -> App Service Plan [label: telemetry]""",
            "GCP Architecture": """# Google Cloud Platform Architecture
Actor: User
Cloud: Cloud Armor WAF [color: red]
Cloud: Cloud Load Balancing [color: blue]
Cloud: Cloud CDN [color: orange]
Service: GKE Autopilot [color: teal]
Cloud: Cloud Pub/Sub [color: yellow]
Cloud: Cloud Functions [color: purple]
Database: Cloud Spanner [color: green]
Database: BigQuery [color: blue]
Cloud: Memorystore Redis [color: red]
Cloud: Cloud Storage GCS [color: gray]
Cloud: Vertex AI [color: purple]
Cloud: Cloud Monitoring [color: orange]

User -> Cloud Armor WAF [label: filter DDoS]
Cloud Armor WAF -> Cloud Load Balancing [label: clean traffic]
Cloud Load Balancing -> Cloud CDN [label: cache]
Cloud Load Balancing -> GKE Autopilot [label: route]
GKE Autopilot -> Cloud Spanner [label: global DB]
GKE Autopilot -> Memorystore Redis [label: cache]
GKE Autopilot -> Cloud Pub/Sub [label: publish event]
Cloud Pub/Sub -> Cloud Functions [label: subscribe]
Cloud Functions -> Cloud Storage GCS [label: store]
Cloud Functions -> BigQuery [label: analytics ingest]
GKE Autopilot -> Vertex AI [label: ML inference]
Cloud Monitoring -> GKE Autopilot [label: observe]""",
            "RAG System": """# RAG — Retrieval Augmented Generation
Actor: User
UI: Chat Interface [color: blue]
Service: API Server [color: purple]
Service: Query Processor [color: purple]
Service: Embedding Service [color: teal]
Database: Vector Store [color: teal]
Service: Retriever [color: teal]
Service: Reranker [color: orange]
Service: Context Builder [color: orange]
Service: LLM Backend [color: purple]
Service: Response Generator [color: purple]
Database: Document Store [color: green]
Service: Document Ingestion [color: gray]
Service: Chunker + Splitter [color: gray]

User -> Chat Interface [label: question]
Chat Interface -> API Server [label: POST /chat]
API Server -> Query Processor [label: preprocess]
Query Processor -> Embedding Service [label: embed query]
Embedding Service -> Vector Store [label: similarity search]
Vector Store --> Retriever [label: top-K chunks]
Retriever -> Reranker [label: re-rank results]
Reranker -> Context Builder [label: top chunks]
Context Builder -> LLM Backend [label: prompt + context]
LLM Backend --> Response Generator [label: completion]
Response Generator --> Chat Interface [label: streamed answer]
Document Ingestion -> Document Store [label: raw docs]
Document Ingestion -> Chunker + Splitter [label: split text]
Chunker + Splitter -> Embedding Service [label: embed chunks]
Embedding Service -> Vector Store [label: upsert vectors]""",
            "AI Agents": """# Agentic AI System  (Multi-Agent)
Actor: User
UI: Agent UI [color: blue]
Service: Orchestrator Agent [color: purple]
Service: Planner Agent [color: purple]
Service: Executor Agent [color: orange]
Service: Critic Agent [color: red]
Service: Memory Manager [color: teal]
Database: Short-Term Memory [color: teal]
Database: Long-Term Memory [color: teal]
Service: Tool Registry [color: gray]
Service: Web Search Tool [color: blue]
Service: Code Executor Tool [color: orange]
Service: API Caller Tool [color: yellow]
Service: LLM Backend [color: purple]

User -> Agent UI [label: goal / task]
Agent UI -> Orchestrator Agent [label: dispatch]
Orchestrator Agent -> Planner Agent [label: plan steps]
Planner Agent -> LLM Backend [label: reason + plan]
LLM Backend --> Planner Agent [label: action list]
Planner Agent -> Executor Agent [label: execute step]
Executor Agent -> Tool Registry [label: select tool]
Tool Registry -> Web Search Tool [label: search]
Tool Registry -> Code Executor Tool [label: run code]
Tool Registry -> API Caller Tool [label: HTTP call]
Executor Agent --> Critic Agent [label: output]
Critic Agent --> Orchestrator Agent [label: pass/retry]
Executor Agent -> Memory Manager [label: store result]
Memory Manager -> Short-Term Memory [label: session]
Memory Manager -> Long-Term Memory [label: persist]
Orchestrator Agent --> Agent UI [label: final answer]""",
            "LLM Platform": """# LLM Production Platform
Actor: Developer
Actor: End User
API: API Gateway [color: blue]
Service: Auth + Rate Limiter [color: red]
Service: Request Router [color: purple]
Service: Prompt Manager [color: orange]
Service: LLM Proxy [color: purple]
System: OpenAI GPT-4 [color: green]
System: Anthropic Claude [color: teal]
System: Llama Local [color: gray]
Service: Response Streamer [color: blue]
Service: Usage Tracker [color: orange]
Database: Usage DB [color: green]
Database: Prompt Templates DB [color: teal]
System: Redis Cache [color: red]
System: Observability [color: gray]

Developer -> API Gateway [label: API key]
End User -> API Gateway [label: chat request]
API Gateway -> Auth + Rate Limiter [label: validate + throttle]
Auth + Rate Limiter -> Request Router [label: route by model]
Request Router -> Prompt Manager [label: load template]
Request Router -> LLM Proxy [label: forward]
LLM Proxy -> Redis Cache [label: cache check]
LLM Proxy -> OpenAI GPT-4 [label: gpt-4 calls]
LLM Proxy -> Anthropic Claude [label: claude calls]
LLM Proxy -> Llama Local [label: local inference]
LLM Proxy -> Response Streamer [label: stream tokens]
Response Streamer --> End User [label: SSE stream]
LLM Proxy -> Usage Tracker [label: log tokens]
Usage Tracker -> Usage DB""",
            "Agentic AI (LangChain)": """# Agentic AI with LangChain / LangGraph
Actor: User
Service: LangGraph Workflow [color: purple]
Service: Supervisor Node [color: purple]
Service: Research Agent [color: blue]
Service: Analysis Agent [color: teal]
Service: Writer Agent [color: orange]
Service: Reviewer Agent [color: red]
Service: LLM Backend [color: purple]
Service: Tavily Web Search [color: blue]
Service: Code Interpreter [color: orange]
Database: Chroma Vector DB [color: teal]
Service: LangSmith Tracer [color: gray]
Database: Checkpoint Store [color: green]
Service: Human-in-Loop [color: yellow]

User -> LangGraph Workflow [label: task input]
LangGraph Workflow -> Supervisor Node [label: route]
Supervisor Node -> Research Agent [label: gather info]
Supervisor Node -> Analysis Agent [label: analyse data]
Supervisor Node -> Writer Agent [label: draft output]
Supervisor Node -> Reviewer Agent [label: review]
Research Agent -> Tavily Web Search [label: search web]
Research Agent -> Chroma Vector DB [label: retrieve docs]
Analysis Agent -> Code Interpreter [label: run analysis]
Research Agent -> LLM Backend [label: reason]
Writer Agent -> LLM Backend [label: generate]
Reviewer Agent -> LLM Backend [label: critique]
Reviewer Agent -> Human-in-Loop [label: approve?]
LangGraph Workflow -> Checkpoint Store [label: save state]
LangGraph Workflow -> LangSmith Tracer [label: trace]""",
            "Event-Driven": """# Event-Driven Architecture
Actor: Producer Systems
Actor: Consumer Systems
Queue: Kafka Cluster [color: orange]
Service: Schema Registry [color: gray]
Service: Event Producer A [color: blue]
Service: Event Producer B [color: blue]
Service: Event Consumer X [color: teal]
Service: Event Consumer Y [color: teal]
Service: Stream Processor Flink [color: orange]
Database: Event Store [color: orange]
Database: Read Model DB [color: green]
Service: Dead Letter Handler [color: red]

Producer Systems -> Event Producer A
Producer Systems -> Event Producer B
Event Producer A -> Schema Registry [label: validate]
Event Producer A -> Kafka Cluster [label: publish]
Event Producer B -> Kafka Cluster [label: publish]
Kafka Cluster -> Event Store [label: persist]
Kafka Cluster -> Event Consumer X [label: subscribe]
Kafka Cluster -> Event Consumer Y [label: subscribe]
Kafka Cluster -> Stream Processor Flink [label: stream]
Stream Processor Flink -> Event Consumer X [label: enriched]
Event Consumer X -> Read Model DB [label: CQRS write]
Event Consumer Y -> Consumer Systems [label: notify]
Kafka Cluster -> Dead Letter Handler [label: failed events]""",
            "CQRS + Event Sourcing": """# CQRS + Event Sourcing Pattern
Actor: Client
API: Command API [color: blue]
API: Query API [color: teal]
Service: Command Handler [color: purple]
Service: Domain Aggregate [color: purple]
Database: Event Store [color: orange]
Service: Event Bus [color: orange]
Service: Projection Handler [color: teal]
Database: Read Model PostgreSQL [color: green]
Database: Read Model Elasticsearch [color: blue]
Service: Saga Orchestrator [color: red]
Service: Snapshot Service [color: gray]

Client -> Command API [label: write command]
Client -> Query API [label: read query]
Command API -> Command Handler [label: validate + dispatch]
Command Handler -> Domain Aggregate [label: apply rules]
Domain Aggregate -> Event Store [label: append event]
Event Store -> Event Bus [label: publish event]
Event Bus -> Projection Handler [label: subscribe]
Event Bus -> Saga Orchestrator [label: long transaction]
Projection Handler -> Read Model PostgreSQL [label: OLTP view]
Projection Handler -> Read Model Elasticsearch [label: search view]
Query API -> Read Model PostgreSQL [label: simple queries]
Query API -> Read Model Elasticsearch [label: search]
Event Store -> Snapshot Service [label: periodic snapshot]""",
            "Service Mesh": """# Service Mesh (Istio on Kubernetes)
Actor: External Client
System: Ingress Gateway [color: blue]
Service: Service A + Sidecar [color: purple]
Service: Service B + Sidecar [color: purple]
Service: Service C + Sidecar [color: teal]
System: Istiod Control Plane [color: orange]
System: Pilot Config [color: orange]
System: Citadel mTLS [color: red]
System: Kiali Dashboard [color: blue]
System: Jaeger Tracing [color: yellow]
System: Prometheus [color: orange]

External Client -> Ingress Gateway [label: HTTPS]
Ingress Gateway -> Service A + Sidecar [label: route]
Service A + Sidecar -> Service B + Sidecar [label: mTLS]
Service A + Sidecar -> Service C + Sidecar [label: mTLS]
Istiod Control Plane -> Pilot Config [label: config]
Istiod Control Plane -> Citadel mTLS [label: certs]
Pilot Config -> Service A + Sidecar [label: push config]
Citadel mTLS -> Service B + Sidecar [label: cert rotation]
Service A + Sidecar -> Jaeger Tracing [label: spans]
Prometheus -> Service A + Sidecar [label: scrape]
Kiali Dashboard -> Prometheus [label: visualise]""",
            "Data Pipeline": """# Modern Data Pipeline  (Lakehouse)
Actor: Data Sources
Service: Kafka Ingestion [color: orange]
Service: Spark Streaming [color: orange]
Service: dbt Transform [color: teal]
Cloud: Data Lake S3 / GCS [color: blue]
Database: Bronze Layer Raw [color: gray]
Database: Silver Layer Cleaned [color: teal]
Database: Gold Layer Aggregated [color: green]
Service: Delta Lake / Iceberg [color: blue]
Database: Data Warehouse Snowflake [color: blue]
Service: Airflow Orchestrator [color: purple]
Service: Great Expectations [color: red]
Service: Metabase / Superset [color: yellow]
Actor: Data Analysts
Actor: ML Engineers

Data Sources -> Kafka Ingestion [label: real-time events]
Data Sources -> Data Lake S3 / GCS [label: batch upload]
Kafka Ingestion -> Spark Streaming [label: consume]
Spark Streaming -> Bronze Layer Raw [label: raw ingest]
Airflow Orchestrator -> dbt Transform [label: schedule]
Bronze Layer Raw -> dbt Transform [label: clean]
dbt Transform -> Great Expectations [label: validate]
dbt Transform -> Silver Layer Cleaned [label: write]
Silver Layer Cleaned -> Gold Layer Aggregated [label: aggregate]
Gold Layer Aggregated -> Delta Lake / Iceberg [label: ACID ops]
Delta Lake / Iceberg -> Data Warehouse Snowflake [label: sync]
Data Warehouse Snowflake -> Metabase / Superset [label: BI queries]
Metabase / Superset -> Data Analysts [label: dashboards]
Data Warehouse Snowflake -> ML Engineers [label: features]""",
            "Zero Trust Security": """# Zero Trust Security Architecture
Actor: Remote User
Actor: Internal User
System: Identity Provider Okta [color: blue]
System: MFA Gateway [color: red]
System: ZTNA Proxy [color: red]
System: Device Trust Check [color: orange]
API: API Gateway [color: blue]
System: WAF + DDoS Shield [color: red]
Service: Service A [color: teal]
Service: Service B [color: teal]
Database: Secrets Vault [color: red]
System: SIEM Splunk [color: gray]
System: Policy Engine OPA [color: orange]

Remote User -> MFA Gateway [label: MFA challenge]
Internal User -> MFA Gateway [label: MFA challenge]
MFA Gateway -> Identity Provider Okta [label: verify identity]
Identity Provider Okta --> ZTNA Proxy [label: token issued]
ZTNA Proxy -> Device Trust Check [label: posture check]
Device Trust Check -> Policy Engine OPA [label: enforce policy]
Policy Engine OPA --> API Gateway [label: allow/deny]
API Gateway -> WAF + DDoS Shield [label: inspect]
WAF + DDoS Shield -> Service A [label: clean request]
WAF + DDoS Shield -> Service B [label: clean request]
Service A -> Secrets Vault [label: fetch secret]
Service B -> Secrets Vault [label: fetch secret]
SIEM Splunk -> API Gateway [label: collect logs]""",
        }


        CATEGORIES = [
            ("DevOps / Cloud",  ["CI/CD Pipeline","Spring Boot App","Microservices",
                                  "DevSecOps","Kubernetes"]),
            ("Cloud Providers", ["AWS Architecture","Azure Architecture","GCP Architecture"]),
            ("AI / ML",         ["RAG System","AI Agents","LLM Platform",
                                  "Agentic AI (LangChain)"]),
            ("Architecture",    ["Event-Driven","CQRS + Event Sourcing","Service Mesh",
                                  "Data Pipeline","Zero Trust Security"]),
        ]
        cat_colors_map = {
            "DevOps / Cloud":  ("#1e3d3a","#3aaaa0"),
            "Cloud Providers": ("#2e3a5c","#5a7ec8"),
            "AI / ML":         ("#3a2e5c","#7c6fcd"),
            "Architecture":    ("#4a3020","#cc7744"),
        }
        for cat_name, names in CATEGORIES:
            col = tk.Frame(ex_inner, bg=SURFACE2)
            col.pack(side="left", padx=4, pady=2)
            tk.Label(col, text=cat_name.upper(), bg=SURFACE2, fg=TEXT_MUTED,
                     font=("Segoe UI",7,"bold"), pady=1).pack(anchor="w")
            btn_row = tk.Frame(col, bg=SURFACE2); btn_row.pack()
            bg_c, fg_c = cat_colors_map.get(cat_name, (SURFACE2, ACCENT2))
            for name in names:
                txt = EXAMPLES_TXT.get(name,"")
                def load_ex(t=txt):
                    editor.delete("1.0", tk.END); editor.insert("1.0", t); on_change()
                tk.Button(btn_row, text=name, bg=bg_c, fg=fg_c,
                          relief="flat", padx=6, pady=2, cursor="hand2",
                          font=("Segoe UI",8), command=load_ex
                          ).pack(side="left", padx=2)
        ex_inner.update_idletasks()
        ex_cv.configure(scrollregion=ex_cv.bbox("all"))
        ex_cv.bind("<MouseWheel>", lambda e: ex_cv.xview_scroll(-1 if e.delta>0 else 1,"units"))

        # ── Main pane: editor | preview ────────────────────────────────────
        pane = tk.Frame(dlg, bg=BG); pane.pack(fill="both", expand=True)

        # Left: editor
        left = tk.Frame(pane, bg=BG, width=400); left.pack(side="left", fill="both")
        left.pack_propagate(False)

        tk.Label(left, text="DSL  (edits update diagram live)",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI",8), pady=4).pack()

        editor = tk.Text(left, bg="#0e0e1a", fg="#c8c8e8",
                         font=("Consolas",11), insertbackground=ACCENT2,
                         wrap="word", padx=10, pady=8,
                         selectbackground=ACCENT, relief="flat")
        editor.pack(fill="both", expand=True, padx=4, pady=(0,4))

        # Syntax colour tags
        editor.tag_configure("comment", foreground="#555577")
        editor.tag_configure("type_kw", foreground="#3aaaa0")
        editor.tag_configure("arrow",   foreground="#cc7744")
        editor.tag_configure("bracket", foreground="#a89ee8")

        # Right: preview canvas
        right = tk.Frame(pane, bg=BG); right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Live preview  (drag nodes to rearrange)",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI",8), pady=4).pack()

        preview_canvas = tk.Canvas(right, bg="#1e1e2e", highlightthickness=0)
        preview_canvas.pack(fill="both", expand=True, padx=4, pady=(0,4))

        # ── Syntax highlighting ────────────────────────────────────────────
        def highlight():
            editor.tag_remove("comment","1.0",tk.END)
            editor.tag_remove("type_kw","1.0",tk.END)
            editor.tag_remove("arrow",  "1.0",tk.END)
            editor.tag_remove("bracket","1.0",tk.END)
            for i,line in enumerate(editor.get("1.0",tk.END).split("\n"),1):
                ln=f"{i}.0"; le=f"{i}.end"
                s=line.strip()
                if s.startswith("#"):
                    editor.tag_add("comment",ln,le)
                elif _re.match(r"(Actor|System|Database|Queue|Cloud|Service|UI|API|DB):",s,_re.I):
                    kend=s.index(":")+1
                    editor.tag_add("type_kw",ln,f"{i}.{kend}")
                if "->" in line or "-->" in line or "<->" in line:
                    for kw in ["->","-->","<->"]:
                        start="1.0"
                        while True:
                            idx=editor.search(kw,f"{i}.0",f"{i}.end")
                            if not idx: break
                            editor.tag_add("arrow",idx,f"{idx}+{len(kw)}c")
                            start=f"{idx}+{len(kw)}c"
                            break
                for m in _re.finditer(r"\[.*?\]",line):
                    editor.tag_add("bracket",f"{i}.{m.start()}",f"{i}.{m.end()}")

        def on_change(event=None):
            do_parse(editor.get("1.0",tk.END))
            draw_canvas()
            highlight()

        editor.bind("<KeyRelease>", on_change)

        # ── Node drag on preview ───────────────────────────────────────────
        drag_state={"node":None,"ox":0,"oy":0}
        BOX_W,BOX_H=160,52

        def pc_click(e):
            for nm,p in pos_cache.items():
                if p[0]<=e.x<=p[0]+BOX_W and p[1]<=e.y<=p[1]+BOX_H:
                    drag_state.update({"node":nm,"ox":e.x-p[0],"oy":e.y-p[1]})
                    return
        def pc_drag(e):
            nm=drag_state["node"]
            if nm:
                pos_cache[nm]=(e.x-drag_state["ox"],e.y-drag_state["oy"])
                draw_canvas_with_positions()
        def pc_release(e): drag_state["node"]=None

        def draw_canvas_with_positions():
            """Redraw using cached (possibly manually moved) positions."""
            c=preview_canvas; c.delete("all")
            W=c.winfo_width() or 800; H=c.winfo_height() or 500
            for x in range(0,W,40): c.create_line(x,0,x,H,fill="#252535",width=1)
            for y in range(0,H,40): c.create_line(0,y,W,y,fill="#252535",width=1)
            # Edges
            for e in parsed_edges:
                sp=pos_cache.get(e["src"]); dp=pos_cache.get(e["dst"])
                if not sp or not dp: continue
                x1=sp[0]+BOX_W//2; y1=sp[1]+BOX_H//2
                x2=dp[0]+BOX_W//2; y2=dp[1]+BOX_H//2
                dash=(6,4) if e["op"]=="-->" else ()
                c.create_line(x1,y1,x2,y2,fill="#6878a8",width=1.5,dash=dash,
                              arrow=tk.LAST,arrowshape=(10,12,4))
                if e["op"]=="<->":
                    c.create_line(x1,y1,x2,y2,fill="#6878a8",width=1.5,
                                  arrow=tk.FIRST,arrowshape=(10,12,4))
                if e["lbl"]:
                    mx,my=(x1+x2)//2,(y1+y2)//2
                    c.create_rectangle(mx-40,my-10,mx+40,my+10,fill="#1a1a2e",outline="")
                    c.create_text(mx,my,text=e["lbl"],fill="#a89ee8",font=("Segoe UI",9))
            # Nodes
            for nm,nd in parsed_nodes.items():
                p=pos_cache.get(nm)
                if not p: continue
                x,y=p; fill=nd["fill"]; stroke=nd["stroke"]; typ=nd["type"]
                if typ=="actor":
                    cx=x+BOX_W//2; r=10
                    c.create_oval(cx-r,y,cx+r,y+r*2,fill=fill,outline=stroke)
                    c.create_line(cx,y+r*2,cx,y+r*2+20,fill=stroke,width=1.5)
                    c.create_line(cx-15,y+r*3+2,cx+15,y+r*3+2,fill=stroke,width=1.5)
                    c.create_line(cx,y+r*2+20,cx-12,y+r*2+34,fill=stroke,width=1.5)
                    c.create_line(cx,y+r*2+20,cx+12,y+r*2+34,fill=stroke,width=1.5)
                    c.create_text(cx,y+BOX_H,text=nm,fill="#e0dff5",font=("Segoe UI",10,"bold"))
                elif typ=="database":
                    ry=8; cx=x+BOX_W//2
                    c.create_oval(x,y,x+BOX_W,y+ry*2,fill=fill,outline=stroke)
                    c.create_rectangle(x,y+ry,x+BOX_W,y+BOX_H-ry,fill=fill,outline="")
                    c.create_oval(x,y+BOX_H-ry*2,x+BOX_W,y+BOX_H,fill=fill,outline=stroke)
                    c.create_line(x,y+ry,x,y+BOX_H-ry,fill=stroke)
                    c.create_line(x+BOX_W,y+ry,x+BOX_W,y+BOX_H-ry,fill=stroke)
                    c.create_text(cx,y+BOX_H//2+4,text=nm,fill="#e0dff5",font=("Segoe UI",10,"bold"))
                elif typ=="queue":
                    cx=x+BOX_W//2
                    c.create_rectangle(x,y,x+BOX_W,y+BOX_H,fill=fill,outline=stroke)
                    c.create_line(x+8,y+4,x+8,y+BOX_H-4,fill=stroke,width=2)
                    c.create_line(x+BOX_W-8,y+4,x+BOX_W-8,y+BOX_H-4,fill=stroke,width=2)
                    c.create_text(cx,y+BOX_H//2,text=nm,fill="#e0dff5",font=("Segoe UI",10,"bold"))
                else:
                    c.create_rectangle(x+3,y+3,x+BOX_W+3,y+BOX_H+3,fill="#111122",outline="")
                    c.create_rectangle(x,y,x+BOX_W,y+BOX_H,fill=fill,outline=stroke)
                    c.create_rectangle(x,y,x+BOX_W,y+5,fill=stroke,outline="")
                    badge=typ.upper() if typ!="default" else ""
                    cx_nm=x+BOX_W//2
                    if badge:
                        c.create_text(cx_nm,y+16,text=badge,fill="#888aaa",font=("Segoe UI",8))
                        c.create_text(cx_nm,y+34,text=nm,fill="#e0dff5",font=("Segoe UI",10,"bold"))
                    else:
                        c.create_text(cx_nm,y+BOX_H//2,text=nm,fill="#e0dff5",font=("Segoe UI",10,"bold"))
            c.create_text(8,8,anchor="nw",
                          text=f"{len(parsed_nodes)} nodes  {len(parsed_edges)} edges",
                          fill="#555577",font=("Segoe UI",8))

        preview_canvas.bind("<ButtonPress-1>",   pc_click)
        preview_canvas.bind("<B1-Motion>",        pc_drag)
        preview_canvas.bind("<ButtonRelease-1>",  pc_release)
        preview_canvas.bind("<Configure>",        lambda e: on_change())

        # ── Bottom buttons ─────────────────────────────────────────────────
        bot = tk.Frame(dlg, bg=SURFACE); bot.pack(fill="x", pady=6)

        def load_to_canvas():
            """Convert parsed DSL nodes/edges to DiagramTool Box/Arrow objects."""
            if not parsed_nodes:
                messagebox.showinfo("Nothing to load",
                    "Type some nodes and arrows first.", parent=dlg)
                return
            if (self.boxes or self.arrows) and not messagebox.askyesno(
                    "Load to Canvas",
                    "Replace current canvas with this diagram?", parent=dlg):
                return
            self._push_undo()
            Box._id = Arrow._id = FloatText._id = 0
            self.boxes.clear(); self.arrows.clear(); self.floattexts.clear()

            pos = do_layout()
            id_map = {}  # name -> Box id
            for nm, nd in parsed_nodes.items():
                Box._id += 1
                p = pos.get(nm, (100, 100))
                color = DIAGRAM_COLOR_MAP.get(nd.get("color","blue").lower(),"Blue")
                tc = TYPE_COLOR_MAP.get(nd["type"], "Blue")
                final_color = color if color != "Blue" or nd["type"]=="default" else tc
                b = Box(p[0], p[1], 160, 52,
                        nd["type"].upper() + "\n" + nm if nd["type"] != "default" else nm,
                        final_color, "actor" if nd["type"]=="actor" else
                                     "cylinder" if nd["type"]=="database" else "rect")
                b.id = Box._id
                self.boxes.append(b)
                id_map[nm] = b.id
            for e in parsed_edges:
                Arrow._id += 1
                sid = id_map.get(e["src"]); did = id_map.get(e["dst"])
                if not sid or not did: continue
                ls = "dashed" if e["op"]=="-->" else "solid"
                hs = "open"
                a = Arrow(sid, did, e["lbl"], ls, hs)
                a.id = Arrow._id
                self.arrows.append(a)

            self.offset_x = 40; self.offset_y = 40
            self.zoom = 1.0; self.zoom_var.set("100%")
            self._draw_all()
            self.status_var.set(
                f"Loaded from Text-to-Diagram  •  {len(self.boxes)} nodes · "
                f"{len(self.arrows)} edges  •  You can now edit, resize and rearrange")
            dlg.destroy()

        def save_dsl():
            path = filedialog.asksaveasfilename(
                parent=dlg, defaultextension=".dsl",
                filetypes=[("Diagram DSL","*.dsl"),("Text","*.txt"),("All","*.*")],
                title="Save DSL")
            if path:
                with open(path,"w") as f: f.write(editor.get("1.0",tk.END))

        def load_dsl():
            path = filedialog.askopenfilename(
                parent=dlg, filetypes=[("Diagram DSL","*.dsl"),("Text","*.txt"),("All","*.*")],
                title="Open DSL")
            if path:
                editor.delete("1.0",tk.END)
                editor.insert("1.0", open(path).read())
                on_change()

        tk.Button(bot, text="✅ Load to Canvas", bg="#2a5c2a", fg="white",
                  relief="flat", padx=16, pady=6, cursor="hand2",
                  font=("Segoe UI",10,"bold"),
                  command=load_to_canvas).pack(side="left", padx=8)
        tk.Button(bot, text="💾 Save DSL", bg=SURFACE2, fg=TEXT_LIGHT,
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  font=("Segoe UI",10), command=save_dsl).pack(side="left", padx=4)
        tk.Button(bot, text="📂 Load DSL", bg=SURFACE2, fg=TEXT_LIGHT,
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  font=("Segoe UI",10), command=load_dsl).pack(side="left", padx=4)
        tk.Button(bot, text="Close", bg=SURFACE2, fg=TEXT_MUTED,
                  relief="flat", padx=12, pady=6, cursor="hand2",
                  command=dlg.destroy).pack(side="right", padx=8)

        # ── DSL reference label ────────────────────────────────────────────
        ref = (
            "Syntax:  NodeType: Name [color: blue]   |   "
            "A -> B [label: text]   A --> B (dashed)   A <-> B (both ways)   |   "
            "Types: Actor  System  Database  Queue  Cloud  Service  UI  API"
        )
        tk.Label(bot, text=ref, bg=SURFACE, fg=TEXT_MUTED,
                 font=("Segoe UI",8)).pack(side="left", padx=12)

        # ── Load default example ───────────────────────────────────────────
        default_dsl = """# CI/CD Pipeline
Actor: Developer
System: Git Repository
System: Build Tool [color: blue]
System: Test Suite [color: teal]
System: Artifact Registry [color: purple]
System: Dev Server [color: green]
System: Prod Server [color: green]

Developer -> Git Repository [label: push code]
Git Repository -> Build Tool [label: webhook trigger]
Build Tool -> Test Suite [label: run tests]
Test Suite --> Build Tool [label: results]
Build Tool -> Artifact Registry [label: publish]
Artifact Registry -> Dev Server [label: deploy dev]
Artifact Registry -> Prod Server [label: release]
Dev Server --> Developer [label: notify]"""
        editor.insert("1.0", default_dsl)
        dlg.after(200, on_change)


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
