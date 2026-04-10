"""
=============================================================
  Torrent Downloader  |  aria2c + Python
  Supports : .torrent files + magnet links
  Requires : aria2c binary  (see SETUP below)

  SETUP (one time):
  1. Download aria2c from: https://github.com/aria2/aria2/releases
     Get: aria2-1.x.x-win-64bit-build1.zip
  2. Extract aria2c.exe to: E:\tools\aria2\aria2c.exe
  3. pip install aria2p torf
  4. Run this script
=============================================================
"""

import subprocess
import sys
import os
import time
import threading
import torf
from pathlib import Path


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
ARIA2C_PATH  = r"E:\tools\aria2\aria2c.exe"   # ← path to aria2c.exe
DOWNLOAD_DIR = r"E:\DOWNLOADS\TORRENTS"
ARIA2C_PORT  = 6800                            # RPC port
ARIA2C_TOKEN = "mytoken123"                    # any secret token

# Extra trackers injected into every torrent
EXTRA_TRACKERS = ",".join([
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
    "udp://tracker.cyberia.is:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.moeking.me:6969/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://opentracker.io:6969/announce",
    "udp://tracker.theoks.net:6969/announce",
    "https://tracker.tamersunion.org:443/announce",
])


# ─────────────────────────────────────────────
#  ARIA2C PROCESS MANAGER
# ─────────────────────────────────────────────

def find_aria2c() -> str:
    """Find aria2c.exe — check config path first, then PATH."""
    if os.path.isfile(ARIA2C_PATH):
        return ARIA2C_PATH
    # Try system PATH
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(path_dir, "aria2c.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


def start_aria2c(aria2c_exe: str) -> subprocess.Popen:
    """Start aria2c as a background RPC daemon."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    cmd = [
        aria2c_exe,
        f"--dir={DOWNLOAD_DIR}",
        "--enable-rpc=true",
        f"--rpc-listen-port={ARIA2C_PORT}",
        f"--rpc-secret={ARIA2C_TOKEN}",
        "--rpc-listen-all=false",
        "--bt-enable-lpd=true",          # Local Peer Discovery
        "--enable-dht=true",             # DHT
        "--enable-dht6=false",
        "--dht-listen-port=6881",
        "--bt-require-crypto=false",
        "--seed-time=0",                 # don't seed after finish
        "--max-connection-per-server=16",
        "--split=16",
        "--min-split-size=1M",
        f"--bt-tracker={EXTRA_TRACKERS}",
        "--bt-tracker-interval=30",
        "--follow-torrent=mem",
        "--quiet=true",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    time.sleep(2)  # give daemon time to start
    return proc


def connect_api():
    """Connect to running aria2c RPC daemon."""
    import aria2p
    api = aria2p.API(
        aria2p.Client(
            host="http://localhost",
            port=ARIA2C_PORT,
            secret=ARIA2C_TOKEN,
        )
    )
    # Test connection
    try:
        api.get_stats()
        return api
    except Exception as e:
        print(f"  [ERROR] Cannot connect to aria2c: {e}")
        return None


# ─────────────────────────────────────────────
#  DOWNLOAD
# ─────────────────────────────────────────────

def progress_bar(pct: float, width: int = 35) -> str:
    filled = int(width * pct / 100)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def human_size(b: int) -> str:
    for unit in ["B","KB","MB","GB"]:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"


def human_speed(bps: int) -> str:
    return human_size(bps) + "/s"


def download(api, source: str):
    """
    Add a torrent/magnet to aria2c and show live progress.
    source = magnet link string OR path to .torrent file
    """
    print()

    # Parse torrent info if .torrent file
    name = "Unknown"
    if not source.startswith("magnet:") and os.path.isfile(source):
        try:
            t    = torf.Torrent.read(source)
            name = t.name
            size = t.size
            print(f"  Name     : {name}")
            print(f"  Size     : {human_size(size)}")
            print(f"  Files    : {len(list(t.files))}")
            print(f"  Trackers : {sum(len(tier) for tier in t.trackers) if t.trackers else 0} (+ 12 extra injected)")
        except Exception:
            pass
    elif source.startswith("magnet:"):
        import urllib.parse
        # Extract and decode name from dn= param
        if "dn=" in source:
            dn   = source.split("dn=")[1].split("&")[0]
            name = urllib.parse.unquote_plus(dn)
        # Truncate long magnet URI to avoid console bleed
        display = source[:80] + "..." if len(source) > 80 else source
        print(f"  Name     : {name}")
        print(f"  Magnet   : {display}")

    print(f"  Save dir : {DOWNLOAD_DIR}")
    print("-" * 60)

    # Add to aria2c
    try:
        if source.startswith("magnet:"):
            dl = api.add_magnet(source)
        else:
            dl = api.add_torrent(source)
    except Exception as e:
        print(f"  [ERROR] Failed to add download: {e}")
        return

    print(f"  GID      : {dl.gid}")
    print(f"  Waiting for peers via DHT + {len(EXTRA_TRACKERS.split(','))} trackers...\n")

    # Progress loop
    stall_secs  = 0
    last_done   = 0

    try:
        while True:
            dl.update()

            status    = dl.status          # active/waiting/paused/error/complete
            pct       = dl.progress        # 0.0–100.0
            done      = dl.completed_length
            total     = dl.total_length
            dl_speed  = dl.download_speed
            ul_speed  = dl.upload_speed
            conns     = dl.connections
            seeders   = dl.num_seeders if hasattr(dl, 'num_seeders') else 0

            # ETA
            if dl_speed > 0 and total > 0:
                remaining = total - done
                eta_s     = remaining / dl_speed
                eta_str   = time.strftime("%H:%M:%S", time.gmtime(eta_s))
            else:
                eta_str   = "--:--:--"

            bar = progress_bar(pct)
            print(
                f"\r  {bar} {pct:5.1f}%"
                f"  {human_size(done)}/{human_size(total)}"
                f"  DL:{human_speed(dl_speed)}"
                f"  UL:{human_speed(ul_speed)}"
                f"  Peers:{conns}"
                f"  ETA:{eta_str}"
                f"  [{status}]     ",
                end="", flush=True
            )

            # Complete
            if status == "complete":
                print(f"\n\n  Download complete!")
                print(f"  Saved to : {DOWNLOAD_DIR}\\{name}")
                break

            # Error
            if status == "error":
                print(f"\n\n  [ERROR] {dl.error_message}")
                break

            # Stall detection — reannounce every 5 mins
            if done == last_done and dl_speed == 0:
                stall_secs += 1
                if stall_secs > 0 and stall_secs % 300 == 0:
                    print(f"\n  [INFO] Stalled {stall_secs//60}min — forcing reannounce...")
                    try:
                        api.client.call("aria2.changeOption", [dl.gid, {"bt-tracker": EXTRA_TRACKERS}])
                    except:
                        pass
            else:
                stall_secs = 0
                last_done  = done

            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n\n  Paused. Torrent stays in aria2c queue.")
        print(f"  GID: {dl.gid}  — resume with option [3]")


def list_downloads(api):
    """Show all active and waiting downloads."""
    active  = api.get_downloads()
    if not active:
        print("\n  No downloads in queue.")
        return
    print(f"\n  {'GID':<20}  {'Name':<40}  {'Progress':>8}  {'Speed':>10}  Status")
    print("  " + "-" * 95)
    for dl in active:
        dl.update()
        name = (dl.name or "Unknown")[:38]
        pct  = f"{dl.progress:.1f}%"
        spd  = human_speed(dl.download_speed)
        print(f"  {dl.gid:<20}  {name:<40}  {pct:>8}  {spd:>10}  {dl.status}")


# ─────────────────────────────────────────────
#  MENU
# ─────────────────────────────────────────────

def menu():
    # Find aria2c
    aria2c_exe = find_aria2c()
    if not aria2c_exe:
        print("\n  [ERROR] aria2c.exe not found!")
        print("  Download from: https://github.com/aria2/aria2/releases")
        print(f"  Extract aria2c.exe to: {ARIA2C_PATH}")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    print(f"\n  aria2c found : {aria2c_exe}")
    print(f"  Starting daemon...")
    proc = start_aria2c(aria2c_exe)
    api  = connect_api()

    if not api:
        proc.terminate()
        sys.exit(1)

    print(f"  aria2c ready  (PID {proc.pid})")

    try:
        while True:
            print()
            print("=" * 60)
            print("  Torrent Downloader  |  aria2c + Python")
            print("=" * 60)
            print(f"  Save dir : {DOWNLOAD_DIR}")
            print(f"  Trackers : {len(EXTRA_TRACKERS.split(','))} extra injected per torrent")
            print("-" * 60)
            print("  [1]  Download .torrent file")
            print("  [2]  Download magnet link")
            print("  [3]  List active downloads")
            print("  [0]  Exit")
            print("=" * 60)

            choice = input("  Choice: ").strip()

            if choice == "1":
                path = input("  Path to .torrent file: ").strip().strip('"')
                download(api, path)

            elif choice == "2":
                magnet = input("  Paste magnet link: ").strip()
                download(api, magnet)

            elif choice == "3":
                list_downloads(api)

            elif choice == "0":
                break

            else:
                print("  Invalid choice.")

            input("\n  Press Enter to continue...")

    finally:
        print("\n  Stopping aria2c daemon...")
        proc.terminate()
        print("  Done. Bye.")


if __name__ == "__main__":
    menu()
