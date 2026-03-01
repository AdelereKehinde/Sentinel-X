import os
import webbrowser
import datetime
import subprocess

def execute_command(command):
    command = command.lower()

    # TIME
    if "time" in command:
        return f"The time is {datetime.datetime.now().strftime('%H:%M')}"

    # OPEN WEBSITE
    if "open youtube" in command:
        webbrowser.open("https://youtube.com")
        return "Opening YouTube"

    if "open google" in command:
        webbrowser.open("https://google.com")
        return "Opening Google"

    # OPEN ANY APP (WINDOWS SEARCH STYLE)
    if command.startswith("open "):
        app_name = command.replace("open ", "").strip()
        try:
            subprocess.Popen(app_name)
            return f"Opening {app_name}"
        except:
            return f"I could not find {app_name}"

    # READ FILE (CURRENT DIRECTORY ONLY)
    if "read file" in command:
        try:
            filename = command.split("read file")[-1].strip()
            with open(filename, "r") as f:
                content = f.read(300)
            return content
        except:
            return "File not found."

    # EMAIL → handled by backend
    if "send email" in command:
        return "Sending email through brain server."

    return None