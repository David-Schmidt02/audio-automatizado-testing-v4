import os
import sys
import time

def restart_script():
    print("Restarting script...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

import subprocess
import sys

def relanzar_script():
    args = [sys.executable] + sys.argv
    print(f"Lanzando nuevo proceso: {' '.join(args)}")
    subprocess.Popen(args)

# Example usage:
if __name__ == "__main__":
    # Your script's main logic here
    print("Script is running.")
    # ...
    time.sleep(5)  # Simulate some processing time
    # When you want to restart:
    relanzar_script()