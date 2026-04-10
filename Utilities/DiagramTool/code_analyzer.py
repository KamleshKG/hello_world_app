"""
code_analyzer.py  —  DiagramTool v4 Code Analysis Engine
=========================================================
Parses Python (.py) and Java (.java) source files (or entire folders)
and extracts:
  • Classes / Interfaces / Enums
  • Imports  → Library dependency  vs  Local file dependency
  • Relationships:
      - Inheritance          (extends / class X(Y))         solid + hollow triangle
      - Interface impl       (implements / class X(Y) abc)  dashed + hollow triangle
      - Composition          (field typed as another class)  solid + filled diamond
      - Aggregation          (collection of another class)   solid + hollow diamond
      - Dependency/Usage     (method param or local var)     dashed + open arrow
      - Dependency Injection (constructor/setter injection)  dashed + open arrow [DI]

Returns a dict compatible with DiagramTool's deserialize format.
"""

import os, re, ast
from pathlib import Path

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
        from code_layout import auto_layout

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
        from code_layout import auto_layout
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

def analyze(path: str) -> dict:
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
