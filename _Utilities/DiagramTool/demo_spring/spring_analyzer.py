"""
spring_analyzer.py  —  Spring Boot Project Scanner
====================================================
Scans an entire Spring Boot project folder and produces a
layered architecture diagram showing:

  Layers (colour-coded):
    Blue   — @RestController / @Controller / @FeignClient
    Purple — @Service / @Component (business logic)
    Teal   — @Repository / JpaRepository / CrudRepository
    Green  — @Entity / @Table  (JPA entities)
    Amber  — @Configuration / @Bean / @EnableXxx
    Red    — Security: Filter, SecurityFilterChain, @PreAuthorize
    Gray   — External infrastructure (DB, Kafka, Redis, S3, REST)

  Relationships (proper UML arrows):
    ──△  inherits          (extends JpaRepository, extends BaseEntity…)
    - -△ implements        (implements UserDetailsService…)
    ──◆  composes          (field typed as another class)
    ──◇  aggregates        (List<X>, Set<X> of another class)
    - -▷ «inject» DI       (@Autowired / constructor injection)
    - -▷ «@Transactional»  service calls
    - -▷ «@OneToMany» etc. JPA relationship annotations

  Also reads:
    application.properties / application.yml
    pom.xml / build.gradle
    to detect datasource, kafka, redis, external URLs.

Usage:
    from spring_analyzer import SpringAnalyzer
    data = SpringAnalyzer().analyze("/path/to/spring-boot-project")
    # data is ready for DiagramApp._deserialize()
"""

import os, re
from pathlib import Path

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
    r"(?:\s+extends\s+([\w<>, ]+?))?"
    r"(?:\s+implements\s+([\w<>, ]+?))?"
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

def analyze_spring(path: str) -> dict:
    """
    Analyze a Spring Boot project folder.
    Returns diagram dict for DiagramApp._deserialize().
    """
    return SpringAnalyzer().analyze(path)
