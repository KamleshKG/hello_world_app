"""
outlook_scanner.py
------------------
Scans Outlook (via win32com / COM automation) for emails from a specific sender.
NO IMAP required — uses the locally installed Outlook desktop app.
Writes results to emails.csv and loads into SQLite via spaCy NLP enrichment.

Requirements:
    pip install pywin32 pandas spacy
    python -m spacy download en_core_web_sm
"""

import win32com.client
import pandas as pd
import re
import os
import sqlite3
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
TARGET_SENDER   = "sender@example.com"   # ← Change this
CSV_OUTPUT      = "emails.csv"
DB_PATH         = "emails.db"
OUTLOOK_FOLDER  = "Inbox"               # or "Sent Items", etc.
MAX_EMAILS      = 500                    # safety cap
# ─────────────────────────────────────────────────────────────────────────────


def connect_outlook():
    """Connect to running Outlook instance via COM."""
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        return namespace
    except Exception as e:
        raise RuntimeError(f"Could not connect to Outlook: {e}\n"
                           "Make sure Outlook is installed and running.")


def get_folder(namespace, folder_name: str):
    """Get Outlook folder by name (searches all stores)."""
    for store in namespace.Stores:
        try:
            root = store.GetRootFolder()
            for folder in root.Folders:
                if folder.Name.lower() == folder_name.lower():
                    return folder
        except Exception:
            continue
    # Fallback: default inbox
    return namespace.GetDefaultFolder(6)  # 6 = olFolderInbox


def clean_body(raw: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scan_emails(target_sender: str = TARGET_SENDER,
                folder_name: str = OUTLOOK_FOLDER,
                max_emails: int = MAX_EMAILS) -> pd.DataFrame:
    """
    Iterate through Outlook folder and collect emails from target_sender.
    Returns a DataFrame.
    """
    print(f"[+] Connecting to Outlook…")
    ns = connect_outlook()
    folder = get_folder(ns, folder_name)
    messages = folder.Items
    messages.Sort("[ReceivedTime]", True)   # newest first

    records = []
    count   = 0

    print(f"[+] Scanning '{folder.Name}' for sender: {target_sender}")

    for msg in messages:
        if count >= max_emails:
            break
        try:
            # Works for MailItem (Class == 43)
            if msg.Class != 43:
                continue

            sender_email = ""
            try:
                sender_email = msg.SenderEmailAddress.lower()
            except Exception:
                pass

            sender_name = ""
            try:
                sender_name = msg.SenderName
            except Exception:
                pass

            # Filter by sender
            if target_sender.lower() not in sender_email and \
               target_sender.lower() not in sender_name.lower():
                continue

            received = ""
            try:
                received = str(msg.ReceivedTime)
            except Exception:
                pass

            body_text = clean_body(msg.Body or "")

            records.append({
                "message_id"    : msg.EntryID,
                "subject"       : msg.Subject or "",
                "sender_name"   : sender_name,
                "sender_email"  : sender_email,
                "received_time" : received,
                "body"          : body_text,
                "body_length"   : len(body_text),
                "has_attachments": msg.Attachments.Count > 0,
            })
            count += 1
            print(f"   [{count}] {msg.Subject[:60]}")

        except Exception as e:
            print(f"   [!] Skipped message: {e}")
            continue

    df = pd.DataFrame(records)
    print(f"\n[✓] Found {len(df)} emails from '{target_sender}'")
    return df


def save_csv(df: pd.DataFrame, path: str = CSV_OUTPUT):
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[✓] Saved CSV → {path}")


def save_sqlite_raw(df: pd.DataFrame, db_path: str = DB_PATH):
    """Save raw email data into SQLite (emails table)."""
    con = sqlite3.connect(db_path)
    df.to_sql("emails", con, if_exists="replace", index=False)
    con.commit()
    con.close()
    print(f"[✓] Saved raw emails → SQLite: {db_path}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = scan_emails()
    if df.empty:
        print("[!] No emails found. Check TARGET_SENDER in config.")
    else:
        save_csv(df)
        save_sqlite_raw(df)
        print("\n[→] Next step: run  nlp_pipeline.py  to enrich with spaCy NLP")
