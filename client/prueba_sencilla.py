import sys
import os
import time
import subprocess

def main():
    print("Hello, World!")
    script_path = os.path.abspath("prueba_sencilla.py") # convierte el main.py en una ruta absoluta
    interprete = os.path.expanduser("~/Desktop/Soflex/audio-test-env/bin/python")
    python_env = os.path.expanduser("~/Desktop/Soflex/audio-test-env/bin/activate")
    cmd = f"{interprete} {script_path}"
    subprocess.Popen(["gnome-terminal", "--", "bash", "-c", cmd])
    time.sleep(2)


if __name__ == "__main__":
    main()