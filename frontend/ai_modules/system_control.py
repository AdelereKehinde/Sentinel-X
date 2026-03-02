import datetime
import difflib
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path


APP_ALIASES = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "pen": "mspaint.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
}

FOLDER_ALIASES = {
    "desktop": str(Path.home() / "Desktop"),
    "documents": str(Path.home() / "Documents"),
    "downloads": str(Path.home() / "Downloads"),
    "pictures": str(Path.home() / "Pictures"),
    "music": str(Path.home() / "Music"),
    "videos": str(Path.home() / "Videos"),
}


def _normalize_app_name(app_name: str) -> str:
    app_name = app_name.strip().lower()
    if app_name in APP_ALIASES:
        return APP_ALIASES[app_name]

    candidate = difflib.get_close_matches(app_name, APP_ALIASES.keys(), n=1, cutoff=0.7)
    if candidate:
        return APP_ALIASES[candidate[0]]

    return app_name


def _open_path(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(path.strip('"')))
    if not os.path.exists(expanded):
        return f"I could not find this path: {expanded}"
    os.startfile(expanded)
    return f"Opening {expanded}"


def _open_app(app_name: str) -> str:
    target = _normalize_app_name(app_name)
    try:
        subprocess.Popen(target)
        return f"Opening {app_name}"
    except Exception:
        # Last fallback: try Windows shell start.
        try:
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=True)
            return f"Opening {app_name}"
        except Exception:
            return f"I could not open {app_name}"


def _open_mobile_app(package_name: str) -> str:
    adb_path = shutil.which("adb")
    if not adb_path:
        return "ADB is not installed. Install Android platform-tools to open mobile apps."
    if not package_name:
        return "Say: open mobile app com.package.name"

    try:
        subprocess.run([adb_path, "devices"], check=True, capture_output=True, text=True)
        subprocess.run(
            [adb_path, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
            check=True,
            capture_output=True,
            text=True,
        )
        return f"Opening mobile app {package_name}"
    except Exception:
        return "I could not open that mobile app. Check USB debugging and package name."


def _read_file(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(path.strip('"')))
    if not os.path.isfile(expanded):
        return "File not found."
    try:
        with open(expanded, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(400)
        return content if content else "File is empty."
    except Exception:
        return "I could not read that file."


def _list_folder(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(path.strip('"')))
    if not os.path.isdir(expanded):
        return "Folder not found."
    try:
        entries = sorted(os.listdir(expanded))[:12]
        if not entries:
            return "Folder is empty."
        return "Top items: " + ", ".join(entries)
    except Exception:
        return "I could not list that folder."


def execute_command(command: str):
    cmd = command.lower().strip()

    if "time" in cmd:
        return f"The time is {datetime.datetime.now().strftime('%H:%M')}."

    if "date" in cmd:
        return f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}."

    if "open youtube" in cmd:
        webbrowser.open("https://youtube.com")
        return "Opening YouTube."

    if "open google" in cmd:
        webbrowser.open("https://google.com")
        return "Opening Google."

    if cmd.startswith("search web "):
        query = command[11:].strip()
        if query:
            webbrowser.open(f"https://www.google.com/search?q={query}")
            return f"Searching the web for {query}."
        return "Tell me what to search."

    if cmd.startswith("open mobile app "):
        package_name = command[16:].strip()
        return _open_mobile_app(package_name)

    if cmd.startswith("open folder "):
        folder = command[12:].strip()
        folder = FOLDER_ALIASES.get(folder.lower(), folder)
        return _open_path(folder)

    if cmd.startswith("list folder "):
        folder = command[12:].strip()
        folder = FOLDER_ALIASES.get(folder.lower(), folder)
        return _list_folder(folder)

    if cmd.startswith("read file "):
        path = command[10:].strip()
        return _read_file(path)

    if cmd.startswith("open app "):
        return _open_app(command[9:].strip())

    if cmd.startswith("open "):
        target = command[5:].strip()
        if target.lower() in FOLDER_ALIASES:
            return _open_path(FOLDER_ALIASES[target.lower()])
        return _open_app(target)

    if "send email" in cmd:
        return "Sending email through brain server."

    return None
