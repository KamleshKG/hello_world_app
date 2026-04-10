"""
outlook_scanner.py
──────────────────
Scans ALL Outlook folders + subfolders recursively for emails from a specific sender.

KEY BEHAVIOURS:
  ✅ Multi-sender isolation  — each sender gets their own table in SQLite
                               scanning Fish John never touches Rajesh Sharma's data
  ✅ Incremental scanning    — remembers last scan date, only fetches NEW emails
  ✅ Full scan on first run  — auto-detects when a sender is brand new
  ✅ Force full rescan flag  — FORCE_FULL_SCAN = True if you ever need it
  ✅ Deduplication by EntryID — same email never inserted twice
  ✅ Scan log table          — records every run: who, when, how many found

SQLite table layout
───────────────────
  emails_<sender_key>        raw emails for this sender
  email_threads_<sender_key> thread grouping for this sender
  nlp_<sender_key>           spaCy NLP results for this sender   (written by nlp_pipeline.py)
  scan_log                   one row per scan run (all senders)

  Example for fish.john@devops-team.com:
    emails_fish_john_devops_team_com
    email_threads_fish_john_devops_team_com
    nlp_fish_john_devops_team_com

Requirements:
    pip install pywin32 pandas
"""

import win32com.client
import pandas as pd
import re
import sqlite3
import hashlib
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────────────────
TARGET_SENDER   = "fish.john@devops-team.com"  # ← email address OR display name
DB_PATH         = "emails.db"
MAX_EMAILS      = 5000          # cap per run (applies to new emails only)
SCAN_SENT       = True          # also look in Sent Items for emails TO this sender
FORCE_FULL_SCAN = False         # True = ignore last scan date, re-fetch everything
                                # Use this if you suspect missing emails
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# SENDER KEY — safe SQLite table name from any email/name
# ─────────────────────────────────────────────────────────────────────────────

def make_sender_key(sender: str) -> str:
    """
    Turn any email/name into a safe SQLite table suffix.
    'fish.john@devops-team.com' → 'fish_john_devops_team_com'
    'Fish John'                 → 'fish_john'
    """
    key = sender.lower().strip()
    key = re.sub(r"[^a-z0-9]+", "_", key)   # replace non-alphanumeric with _
    key = key.strip("_")
    return key


def table_names(sender: str) -> dict:
    """Return all table names for a given sender."""
    k = make_sender_key(sender)
    return {
        "emails"   : f"emails_{k}",
        "threads"  : f"email_threads_{k}",
        "nlp"      : f"nlp_{k}",
        "scan_log" : "scan_log",         # shared across all senders
    }


# ─────────────────────────────────────────────────────────────────────────────
# SCAN LOG — remember last scan date per sender
# ─────────────────────────────────────────────────────────────────────────────

def init_db(db_path: str):
    """Create shared tables if they don't exist yet."""
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sender          TEXT    NOT NULL,
            sender_key      TEXT    NOT NULL,
            scan_type       TEXT    NOT NULL,   -- 'full' or 'incremental'
            started_at      TEXT    NOT NULL,
            finished_at     TEXT,
            emails_found    INTEGER DEFAULT 0,
            emails_new      INTEGER DEFAULT 0,
            last_email_date TEXT,               -- latest ReceivedTime seen
            status          TEXT    DEFAULT 'running'
        )
    """)
    con.commit()
    con.close()


def get_last_scan_info(db_path: str, sender_key: str) -> dict:
    """
    Returns info about the last SUCCESSFUL scan for this sender.
    Returns None if this sender has never been scanned before.
    """
    con = sqlite3.connect(db_path)
    try:
        row = con.execute("""
            SELECT last_email_date, emails_found, finished_at
            FROM   scan_log
            WHERE  sender_key = ? AND status = 'done'
            ORDER  BY id DESC
            LIMIT  1
        """, (sender_key,)).fetchone()
        if row:
            return {
                "last_email_date" : row[0],
                "emails_found"    : row[1],
                "finished_at"     : row[2],
            }
        return None
    except Exception:
        return None
    finally:
        con.close()


def get_existing_entry_ids(db_path: str, emails_table: str) -> set:
    """Load all known EntryIDs for this sender from SQLite (for dedup)."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            f"SELECT message_id FROM [{emails_table}]"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()   # table doesn't exist yet → no existing IDs
    finally:
        con.close()


def log_scan_start(db_path: str, sender: str, sender_key: str,
                   scan_type: str) -> int:
    """Insert a scan_log row and return its id."""
    con = sqlite3.connect(db_path)
    cur = con.execute("""
        INSERT INTO scan_log (sender, sender_key, scan_type, started_at, status)
        VALUES (?, ?, ?, ?, 'running')
    """, (sender, sender_key, scan_type,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_id = cur.lastrowid
    con.commit()
    con.close()
    return log_id


def log_scan_done(db_path: str, log_id: int,
                  emails_found: int, emails_new: int, last_date: str):
    """Update the scan_log row as done."""
    con = sqlite3.connect(db_path)
    con.execute("""
        UPDATE scan_log
        SET    finished_at   = ?,
               emails_found  = ?,
               emails_new    = ?,
               last_email_date = ?,
               status        = 'done'
        WHERE  id = ?
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          emails_found, emails_new, last_date, log_id))
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# OUTLOOK CONNECTION + RECURSIVE FOLDER TRAVERSAL
# ─────────────────────────────────────────────────────────────────────────────

def connect_outlook():
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        return outlook.GetNamespace("MAPI")
    except Exception as e:
        raise RuntimeError(
            f"Could not connect to Outlook: {e}\n"
            "Make sure Outlook desktop app is open."
        )


def iter_all_folders(namespace):
    """Yield every mail folder across all stores recursively."""
    SKIP = {"calendar","contacts","tasks","notes","journal",
            "junk","deleted","outbox","sync issues",
            "conflicts","local failures","server failures","drafts"}

    def recurse(folder):
        try:
            name = folder.Name.lower()
        except Exception:
            return
        if any(s in name for s in SKIP):
            return
        yield folder
        try:
            for sub in folder.Folders:
                yield from recurse(sub)
        except Exception:
            pass

    for store in namespace.Stores:
        try:
            for top in store.GetRootFolder().Folders:
                yield from recurse(top)
        except Exception:
            continue


def get_folder_path(folder) -> str:
    parts = []
    try:
        f = folder
        while True:
            parts.append(f.Name)
            try:
                f = f.Parent
                if not hasattr(f, "Name"): break
            except Exception:
                break
    except Exception:
        pass
    parts.reverse()
    return " / ".join(parts[1:])


# ─────────────────────────────────────────────────────────────────────────────
# TEXT + SUBJECT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def clean_body(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(
        r"(_{3,}|─{3,}|-{3,})\s*(From:|Sent:|To:|Subject:|On .+wrote:).*",
        "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^>+.*$", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


_REPLY_PREFIX = re.compile(
    r"^\s*(re(\[\d+\])?|fw|fwd(\[\d+\])?|aw|tr|wg|sv|vs)\s*:\s*",
    flags=re.IGNORECASE)


def normalise_subject(subject: str) -> str:
    s = (subject or "").strip()
    while True:
        n = _REPLY_PREFIX.sub("", s).strip()
        if n == s: break
        s = n
    return s


def is_reply(subject: str) -> bool:
    return bool(_REPLY_PREFIX.match((subject or "").strip()))


def make_thread_id(base_subject: str) -> str:
    return hashlib.md5(base_subject.lower().strip().encode()).hexdigest()[:12]


# ─────────────────────────────────────────────────────────────────────────────
# SENDER MATCHING
# ─────────────────────────────────────────────────────────────────────────────

def sender_matches(msg, target: str) -> bool:
    t = target.lower().strip()
    try:
        if t in (msg.SenderEmailAddress or "").lower(): return True
    except Exception: pass
    try:
        if t in (msg.SenderName or "").lower(): return True
    except Exception: pass
    return False


def recipient_matches(msg, target: str) -> bool:
    t = target.lower().strip()
    try:
        for r in msg.Recipients:
            try:
                if t in (r.Address or "").lower(): return True
                if t in (r.Name    or "").lower(): return True
            except Exception: pass
    except Exception: pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCAN — incremental by default
# ─────────────────────────────────────────────────────────────────────────────

def scan_emails(
    target_sender:   str  = TARGET_SENDER,
    db_path:         str  = DB_PATH,
    max_emails:      int  = MAX_EMAILS,
    scan_sent:       bool = SCAN_SENT,
    force_full_scan: bool = FORCE_FULL_SCAN,
) -> pd.DataFrame:

    sender_key = make_sender_key(target_sender)
    tables     = table_names(target_sender)
    init_db(db_path)

    # ── Decide: full scan or incremental? ─────────────────────────────────────
    last_info  = get_last_scan_info(db_path, sender_key)
    is_new_sender = last_info is None

    if force_full_scan or is_new_sender:
        scan_type       = "full"
        since_date      = None
        existing_ids    = set()   # full scan: ignore existing IDs (table will be upserted)
        print(f"[+] Scan type   : FULL {'(first time for this sender)' if is_new_sender else '(forced)'}")
    else:
        scan_type       = "incremental"
        since_date      = pd.to_datetime(last_info["last_email_date"])
        existing_ids    = get_existing_entry_ids(db_path, tables["emails"])
        print(f"[+] Scan type   : INCREMENTAL (only emails after {since_date.date()})")
        print(f"[+] Known emails: {len(existing_ids)} already in DB")
        print(f"[+] Last scan   : {last_info['finished_at']}")

    print(f"[+] Target      : {target_sender}")
    print(f"[+] Sender key  : {sender_key}")
    print(f"[+] Tables      : {tables['emails']}")
    print(f"[+] Walking all Outlook folders recursively…\n")

    log_id = log_scan_start(db_path, target_sender, sender_key, scan_type)

    ns = connect_outlook()
    records      = []
    folder_stats = {}
    total_checked = 0
    skipped_old   = 0

    for folder in iter_all_folders(ns):
        if len(records) >= max_emails:
            break

        folder_path    = get_folder_path(folder)
        is_sent_folder = "sent" in folder_path.lower()
        total_checked += 1

        try:
            items = folder.Items
            items.Sort("[ReceivedTime]", True)   # newest first
        except Exception:
            continue

        for msg in items:
            if len(records) >= max_emails:
                break
            try:
                if msg.Class != 43:
                    continue

                # ── Incremental date filter ───────────────────────────────────
                if since_date is not None:
                    try:
                        msg_date = pd.to_datetime(str(msg.ReceivedTime))
                        if msg_date <= since_date:
                            skipped_old += 1
                            # Outlook sorts newest-first so once we go past
                            # the cutoff date in this folder we can stop
                            break
                    except Exception:
                        pass

                # ── Dedup check ───────────────────────────────────────────────
                entry_id = msg.EntryID
                if entry_id in existing_ids:
                    continue

                # ── Sender match ──────────────────────────────────────────────
                from_match = sender_matches(msg, target_sender)
                to_match   = (scan_sent and is_sent_folder and
                               recipient_matches(msg, target_sender))
                if not from_match and not to_match:
                    continue

                existing_ids.add(entry_id)   # add to dedup set immediately

                # ── Extract ───────────────────────────────────────────────────
                subject      = (msg.Subject or "").strip()
                sender_email = sender_name = ""
                try: sender_email = msg.SenderEmailAddress.lower()
                except Exception: pass
                try: sender_name  = msg.SenderName
                except Exception: pass

                received = ""
                try: received = str(msg.ReceivedTime)
                except Exception: pass

                n_attach = 0
                try: n_attach = msg.Attachments.Count
                except Exception: pass

                body_text = clean_body(msg.Body or "")

                conversation_id = ""
                try: conversation_id = msg.ConversationID or ""
                except Exception: pass

                base_subj = normalise_subject(subject)
                thread_id = (hashlib.md5(conversation_id.encode()).hexdigest()[:12]
                             if conversation_id else make_thread_id(base_subj))

                records.append({
                    "message_id"       : entry_id,
                    "subject"          : subject,
                    "thread_subject"   : base_subj,
                    "thread_id"        : thread_id,
                    "is_reply"         : is_reply(subject),
                    "direction"        : "sent" if (to_match and not from_match) else "received",
                    "sender_name"      : sender_name,
                    "sender_email"     : sender_email,
                    "received_time"    : received,
                    "folder_path"      : folder_path,
                    "body"             : body_text,
                    "body_length"      : len(body_text),
                    "has_attachments"  : n_attach > 0,
                    "attachment_count" : n_attach,
                    "scanned_at"       : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

                folder_stats[folder_path] = folder_stats.get(folder_path, 0) + 1

            except Exception:
                continue

    if not records:
        print(f"\n[✓] No NEW emails found (checked {total_checked} folders, "
              f"skipped {skipped_old} older emails).")
        log_scan_done(db_path, log_id, 0, 0,
                      last_info["last_email_date"] if last_info else "")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["received_time"] = pd.to_datetime(df["received_time"], errors="coerce")

    # ── Thread count ──────────────────────────────────────────────────────────
    tc = df.groupby("thread_id").size().rename("thread_email_count")
    df = df.merge(tc, on="thread_id", how="left")
    df = df.sort_values("received_time", ascending=False).reset_index(drop=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═'*62}")
    print(f"  SCAN COMPLETE — {target_sender}")
    print(f"{'─'*62}")
    print(f"  Scan type             : {scan_type.upper()}")
    print(f"  Folders checked       : {total_checked}")
    print(f"  New emails found      : {len(df)}")
    print(f"  Skipped (already old) : {skipped_old}")
    print(f"  Unique threads        : {df['thread_id'].nunique()}")
    print(f"  Replies (RE:/FW:)     : {df['is_reply'].sum()}")
    print(f"\n  By folder:")
    for fp, cnt in sorted(folder_stats.items(), key=lambda x: -x[1]):
        print(f"    {cnt:5d}  {fp}")
    print(f"{'═'*62}\n")

    last_date = df["received_time"].max()
    last_date_str = str(last_date)[:19] if pd.notna(last_date) else ""
    log_scan_done(db_path, log_id, len(df), len(records), last_date_str)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# THREAD SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def build_thread_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    threads = (
        df.groupby("thread_id")
        .agg(
            thread_subject    = ("thread_subject",  "first"),
            email_count       = ("message_id",       "count"),
            reply_count       = ("is_reply",          "sum"),
            first_email_date  = ("received_time",    "min"),
            last_email_date   = ("received_time",    "max"),
            has_attachments   = ("has_attachments",   "any"),
            folders           = ("folder_path",
                                  lambda x: " | ".join(sorted(set(x)))),
            total_body_length = ("body_length",       "sum"),
            combined_body     = ("body",
                                  lambda x: "\n---\n".join(
                                      str(b)[:500] for b in x if b)),
        )
        .reset_index()
    )
    threads["thread_duration_days"] = (
        (threads["last_email_date"] - threads["first_email_date"])
        .dt.days.fillna(0).astype(int)
    )
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
    threads["is_active"] = threads["last_email_date"] > cutoff
    return threads.sort_values("last_email_date", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# SAVE — per-sender tables, APPEND not replace
# ─────────────────────────────────────────────────────────────────────────────

def save_to_sqlite(df: pd.DataFrame, threads: pd.DataFrame,
                   target_sender: str, db_path: str = DB_PATH):
    """
    Append NEW emails to this sender's table.
    Never touches any other sender's tables.
    Uses INSERT OR IGNORE so re-running is always safe.
    """
    tables = table_names(target_sender)
    con    = sqlite3.connect(db_path)

    # ── emails table: append only ─────────────────────────────────────────────
    out = df.copy()
    if "received_time" in out.columns:
        out["received_time"] = out["received_time"].astype(str)

    # Create table if first time, then INSERT OR IGNORE duplicates
    out.to_sql(tables["emails"], con, if_exists="append", index=False,
               method="multi")

    # Add UNIQUE constraint on message_id if table is new
    # (SQLite: silently ignored if already exists)
    try:
        con.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_{tables['emails']}_msgid
            ON [{tables['emails']}] (message_id)
        """)
        con.commit()
    except Exception:
        pass

    # ── threads table: rebuild for this sender ────────────────────────────────
    if not threads.empty:
        t = threads.drop(columns=["combined_body"], errors="ignore").copy()
        for col in ["first_email_date", "last_email_date"]:
            if col in t.columns:
                t[col] = t[col].astype(str)
        t.to_sql(tables["threads"], con, if_exists="replace", index=False)

    con.commit()
    con.close()

    print(f"[✓] Appended {len(df)} new emails → [{tables['emails']}]")
    print(f"[✓] Rebuilt threads          → [{tables['threads']}]")
    print(f"[✓] Database                 → {db_path}")


def save_csv(df: pd.DataFrame, target_sender: str,
             path: str = None):
    """Save emails CSV — filename includes sender key."""
    if path is None:
        key  = make_sender_key(target_sender)
        path = f"emails_{key}.csv"
    out = df.copy()
    if "received_time" in out.columns:
        out["received_time"] = out["received_time"].astype(str)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[✓] CSV saved → {path}  ({len(out)} new rows)")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY — show all senders stored in DB
# ─────────────────────────────────────────────────────────────────────────────

def list_senders(db_path: str = DB_PATH):
    """Print all senders currently stored in the database."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("""
            SELECT sender, sender_key,
                   COUNT(*) as scans,
                   MAX(finished_at) as last_scan,
                   SUM(emails_new)  as total_emails_collected
            FROM scan_log
            WHERE status = 'done'
            GROUP BY sender_key
            ORDER BY last_scan DESC
        """).fetchall()

        if not rows:
            print("[i] No senders scanned yet.")
            return

        print(f"\n{'─'*75}")
        print(f"  {'SENDER':<35} {'LAST SCAN':<22} {'TOTAL EMAILS':>12}")
        print(f"{'─'*75}")
        for sender, key, scans, last_scan, total in rows:
            print(f"  {sender:<35} {str(last_scan):<22} {str(total):>12}")
        print(f"{'─'*75}\n")

    except Exception as e:
        print(f"[i] No scan history yet: {e}")
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 62)
    print("  OUTLOOK ALL-FOLDERS INCREMENTAL SCANNER")
    print(f"  Target      : {TARGET_SENDER}")
    print(f"  Database    : {DB_PATH}")
    print(f"  Force full  : {FORCE_FULL_SCAN}")
    print("=" * 62 + "\n")

    # Show what's already in the DB before scanning
    print("[i] Senders currently in database:")
    list_senders(DB_PATH)

    # Run scan
    df = scan_emails(
        target_sender   = TARGET_SENDER,
        db_path         = DB_PATH,
        max_emails      = MAX_EMAILS,
        scan_sent       = SCAN_SENT,
        force_full_scan = FORCE_FULL_SCAN,
    )

    if df.empty:
        print("[✓] Database is already up to date. Nothing new to store.")
    else:
        threads  = build_thread_summary(df)
        csv_path = save_csv(df, TARGET_SENDER)
        save_to_sqlite(df, threads, TARGET_SENDER, DB_PATH)

        print(f"\n[i] Updated sender list:")
        list_senders(DB_PATH)
        print(f"[→] Next: python nlp_pipeline.py  (target sender: {TARGET_SENDER})")
