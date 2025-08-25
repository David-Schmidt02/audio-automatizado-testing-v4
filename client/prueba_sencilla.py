import sys
import os
import time
import subprocess

def main():
    print("Hello, World!")
    script_path = os.path.abspath("prueba_sencilla.py") # convierte el main.py en una ruta absoluta
    for a in range(2):
        cmd = f"{sys.executable} {script_path}"
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", cmd])
        time.sleep(2)


if __name__ == "__main__":
    main()