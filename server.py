#!/usr/bin/env python3
"""VEYRIS v2 local companion. Zero third-party dependencies, no broker access."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import heapq
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import brain
import updater
import release_updater

VERSION = "2.4.1"
HOST, PORT = "127.0.0.1", 8767
ROOT = Path(__file__).resolve().parent
HOME = Path.home()
TOKEN = secrets.token_urlsafe(32)
USER_FOLDERS = {k: HOME / k for k in ("Downloads", "Documents", "Desktop")}
NEWS_BAT = HOME / "Downloads" / "VEYRIS_Futures_News_Dashboard" / "VEYRIS_Futures_News" / "start_dashboard.bat"
TRADING_HTML = HOME / "Documents" / "Rainmeter" / "Skins" / "VeyrisHUD" / "@Resources" / "Dashboard" / "index.html"
ALLOWED_ACTIONS = {
    "tradingview": ("TradingView", "https://www.tradingview.com/chart/"),
    "tradovate": ("Tradovate", "https://trader.tradovate.com/"),
    "chatgpt": ("ChatGPT", "https://chatgpt.com/"),
    "news": ("Futures News", "http://127.0.0.1:8765/"),
    "dashboard": ("Existing VEYRIS Dashboard", str(TRADING_HTML)),
    "downloads": ("Downloads", str(HOME / "Downloads")),
    "documents": ("Documents", str(HOME / "Documents")),
    "taskmanager": ("Task Manager", "taskmgr.exe"),
}
LAST_STATUS = {"time": 0.0, "value": None}
STATUS_LOCK = threading.Lock()


def memory_stats():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError("Memory measurement unavailable")
    return {"total": m.ullTotalPhys, "used": m.ullTotalPhys - m.ullAvailPhys,
            "percent": m.dwMemoryLoad}


def cpu_percent():
    def snapshot():
        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        ok = ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        if not ok:
            return None
        cv = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
        return cv(idle), cv(kernel), cv(user)
    one = snapshot()
    time.sleep(0.18)
    two = snapshot()
    if not one or not two:
        return None
    idle, kernel, user = [b - a for a, b in zip(one, two)]
    total = kernel + user
    return round(max(0.0, min(100.0, 100.0 * (1 - idle / total))), 1) if total else None


def status():
    with STATUS_LOCK:
        if LAST_STATUS["value"] and time.monotonic() - LAST_STATUS["time"] < 5:
            return LAST_STATUS["value"]
        disk = shutil.disk_usage(str(HOME.anchor))
        ram = memory_stats()
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        result = {"host": os.environ.get("COMPUTERNAME", "Windows PC"), "version": VERSION,
                  "cpu_percent": cpu_percent(), "cpu_threads": os.cpu_count(),
                  "ram": ram, "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
                  "uptime_hours": round(ctypes.windll.kernel32.GetTickCount64() / 3600000, 1),
                  "timestamp": int(time.time()), "drive": HOME.anchor}
        LAST_STATUS["time"], LAST_STATUS["value"] = time.monotonic(), result
        return result


def defender():
    ps = (
        "$s=Get-MpComputerStatus -ErrorAction Stop;"
        "[PSCustomObject]@{enabled=$s.AntivirusEnabled;realtime=$s.RealTimeProtectionEnabled;"
        "behavior=$s.BehaviorMonitorEnabled;tamper=$s.IsTamperProtected;"
        "signatures=[string]$s.AntivirusSignatureLastUpdated;"
        "quick=[string]$s.QuickScanEndTime;full=[string]$s.FullScanEndTime;"
        "threats=@(Get-MpThreat -ErrorAction SilentlyContinue | "
        "Select-Object -First 10 ThreatName,IsActive)} | ConvertTo-Json -Depth 4 -Compress"
    )
    try:
        p = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, timeout=18, creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode:
            return {"available": False, "error": "Windows Defender status unavailable"}
        raw = json.loads(p.stdout)
        return {"available": True, **raw}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"available": False, "error": "Defender status lookup timed out or is unavailable"}


def walk_files(folder: Path, cap=65000):
    visited = 0
    stack = [folder]
    while stack and visited < cap:
        base = stack.pop()
        try:
            with os.scandir(base) as items:
                for ent in items:
                    if visited >= cap:
                        break
                    visited += 1
                    try:
                        if ent.is_symlink():
                            continue
                        if ent.is_dir(follow_symlinks=False):
                            stack.append(Path(ent.path))
                        elif ent.is_file(follow_symlinks=False):
                            yield ent
                    except (OSError, ValueError):
                        continue
        except (OSError, PermissionError):
            continue


def biggest(folder_name="Downloads"):
    if folder_name not in USER_FOLDERS:
        return {"error": "Choose Downloads, Documents, or Desktop"}
    root = USER_FOLDERS[folder_name]
    top = []
    checked = 0
    for ent in walk_files(root):
        checked += 1
        try:
            item = (ent.stat(follow_symlinks=False).st_size, ent.path)
            if len(top) < 15:
                heapq.heappush(top, item)
            elif item > top[0]:
                heapq.heapreplace(top, item)
        except OSError:
            pass
    return {"scope": folder_name, "checked_files": checked,
            "items": [{"path": path, "name": Path(path).name, "bytes": size}
                      for size, path in sorted(top, reverse=True)]}


def find_files(query):
    query = query.lower().strip().strip('"').strip("'")
    if not 2 <= len(query) <= 90 or any(x in query for x in ("\\", "/", ":", "*", "?")):
        return {"error": "Search for a filename using 2–90 letters, numbers, or spaces"}
    matches, checked = [], 0
    for label, root in USER_FOLDERS.items():
        for ent in walk_files(root, 20000):
            checked += 1
            if query in ent.name.lower():
                try:
                    size = ent.stat(follow_symlinks=False).st_size
                    matches.append({"name": ent.name, "path": ent.path, "scope": label, "bytes": size})
                except OSError:
                    pass
            if len(matches) >= 25:
                break
    return {"query": query, "checked_files": checked, "items": matches[:25]}


def launch(which):
    if which not in ALLOWED_ACTIONS and which != "start_news":
        return {"ok": False, "message": "This action is not approved."}
    if which == "start_news":
        if not NEWS_BAT.is_file():
            return {"ok": False, "message": "Futures news startup file was not found."}
        subprocess.Popen(["cmd.exe", "/c", str(NEWS_BAT)], cwd=str(NEWS_BAT.parent),
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        return {"ok": True, "message": "News server startup requested. Open the News dashboard after it starts."}
    label, target = ALLOWED_ACTIONS[which]
    if target.startswith("https://") or target.startswith("http://"):
        webbrowser.open(target)
    elif target == "taskmgr.exe":
        subprocess.Popen(["taskmgr.exe"])
    else:
        location = Path(target)
        if not location.exists():
            return {"ok": False, "message": label + " could not be found."}
        os.startfile(str(location))
    return {"ok": True, "message": "Opened " + label + "."}


def interpret(message):
    q = message.strip()
    low = q.lower()
    if not low or len(q) > 500:
        return {"kind": "text", "message": "Enter a short command (500 characters or fewer)."}
    if any(word in low for word in ("help", "what can", "commands", "examples")):
        return {"kind": "text", "message": "Try: 'system status', 'check Defender', 'largest downloads', 'find screenshot', 'open tradingview', 'open news', or 'open downloads'. For deeper AI work, open ChatGPT with Remote Desktop Commander connected."}
    if any(word in low for word in ("defender", "malware", "security", "antivirus", "virus")):
        return {"kind": "security", "data": defender(), "message": "Microsoft Defender status (read-only). This is not a malware scan."}
    if any(word in low for word in ("largest", "biggest", "large files", "space hog")):
        scope = next((s for s in USER_FOLDERS if s.lower() in low), "Downloads")
        return {"kind": "files", "data": biggest(scope), "message": "Largest files in " + scope}
    m = re.match(r"^(?:find|search(?: for)?|locate)\s+(?:file\s+)?(.+)$", q, re.IGNORECASE)
    if m:
        return {"kind": "files", "data": find_files(m.group(1)), "message": "Filename search results"}
    for action, aliases in (
        ("start_news", ("start news", "launch news server")),
        ("tradingview", ("tradingview", "trading view")),
        ("tradovate", ("tradovate",)),
        ("dashboard", ("veyris dashboard", "trading dashboard")),
        ("news", ("news dashboard", "open news", "futures news")),
        ("downloads", ("open downloads", "downloads folder")),
        ("documents", ("open documents", "documents folder")),
        ("taskmanager", ("task manager", "taskmanager")),
        ("chatgpt", ("open chatgpt", "launch chatgpt")),
    ):
        if low.startswith(("open ", "launch ", "start ", "show ")) and any(a in low for a in aliases):
            return {"kind": "confirm", "action": action,
                    "message": "I can open this for you. Press Confirm to proceed."}
    if any(x in low for x in ("cpu", "ram", "memory", "status", "storage", "disk", "system", "uptime")):
        return {"kind": "status", "data": status(), "message": "Live system telemetry"}
    return {"kind": "text", "message": "I can run local PC checks and approved launch commands. For open-ended AI reasoning, use the ChatGPT button with your Remote Desktop Commander connection. Try 'help' for examples."}


class Handler(BaseHTTPRequestHandler):
    server_version = "VEYRIS/2"
    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/status"):
            print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

    def send_json(self, obj, http_status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(http_status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/index.html"):
            html = (ROOT / "index.html").read_text(encoding="utf-8").replace("__SESSION_TOKEN__", TOKEN)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        elif path in ("/style.css", "/app.js"):
            content = (ROOT / path.lstrip("/")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css" if path.endswith(".css") else "text/javascript")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
        elif path == "/api/status":
            self.send_json(status())
        elif path == "/api/security":
            self.send_json(defender())
        elif path == "/api/brain-status":
            self.send_json(brain.availability())
        elif path == "/api/update-status":
            self.send_json(updater.status())
        elif path == "/api/release-status":
            self.send_json(release_updater.status())
        elif path == "/api/biggest":
            args = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            self.send_json(biggest(args.get("scope", ["Downloads"])[0]))
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path not in ("/api/command", "/api/action", "/api/ai", "/api/update-check", "/api/update-sync", "/api/release-check"):
            return self.send_json({"error": "Not found"}, 404)
        if self.headers.get("X-VEYRIS-Token") != TOKEN:
            return self.send_json({"error": "Authorization failed"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 100000:
                return self.send_json({"error": "Invalid request length"}, 400)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                return self.send_json({"error": "Invalid request"}, 400)
            if self.path == "/api/command":
                result = interpret(str(data.get("text", "")))
            elif self.path == "/api/release-check":
                # Signed GitHub release checks only; no unsigned code execution.
                result = release_updater.check_latest()
            elif self.path == "/api/update-check":
                result = updater.maintain(sync_models=False)
            elif self.path == "/api/update-sync":
                if updater.status()["maintenance_running"]:
                    result = {"ok": False, "message": "An upgrade check is already running"}
                else:
                    threading.Thread(target=updater.maintain, kwargs={"sync_models": True, "force": True}, daemon=True).start()
                    result = {"ok": True, "message": "Model refresh started; check Update Center for results"}
            elif self.path == "/api/ai":
                question = str(data.get("text", ""))
                context = None
                lower = question.lower()
                # Read-only context only; the AI can never invoke PC write/launch actions.
                if any(term in lower for term in ("system status", "cpu usage", "ram usage", "memory usage", "disk space", "free space", "computer stats")):
                    context = {"system": status()}
                elif any(term in lower for term in ("defender status", "antivirus status", "security status", "real-time protection")):
                    context = {"defender": defender()}
                result = brain.reply(question, data.get("history"), context)
            else:
                result = launch(str(data.get("action", "")))
            self.send_json(result)
        except (json.JSONDecodeError, ValueError, TypeError):
            self.send_json({"error": "Invalid request"}, 400)
        except Exception as exc:
            print("Request error:", type(exc).__name__, str(exc), flush=True)
            self.send_json({"error": "Task failed; see the local console"}, 500)


def main():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        print("Cannot start VEYRIS: port %s is unavailable (%s)" % (PORT, exc))
        raise SystemExit(1)
    server.daemon_threads = True
    print("VEYRIS v%s online at http://%s:%d" % (VERSION, HOST, PORT), flush=True)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open("http://%s:%d/" % (HOST, PORT))).start()
    try:
        server.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
