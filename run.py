import os
import sys
import subprocess
import time

LOCK_FILE = "bot.lock"

if os.path.exists(LOCK_FILE):
    print("Bot already running.")
    sys.exit()

with open(LOCK_FILE, "w") as f:
    f.write(str(time.time()))

try:
    # start bot
    bot_process = subprocess.Popen(["python", "bot.py"])

    # start streamlit
    streamlit_process = subprocess.Popen([
        "streamlit", "run", "app.py"
    ])

    bot_process.wait()
    streamlit_process.wait()

finally:
    os.remove(LOCK_FILE)