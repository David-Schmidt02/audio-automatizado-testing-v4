import sys
import os
import time
import subprocess

url1 = "https://www.youtube.com/@olgaenvivo_/live"
url2 = "https://www.youtube.com/@luzutv/live"
url3 = "https://www.youtube.com/@todonoticias/live"
url4 = "https://www.youtube.com/@lanacion/live"
url5 = "https://www.youtube.com/@C5N/live"
url6 = "https://www.youtube.com/@A24com/live"
url7 = "https://www.youtube.com/@Telefe/live"
url8 = "https://www.youtube.com/@UrbanaPlayFM/live"

urls = [url1, url2, url3, url4, url5, url6, url7, url8]

def main():
    headless = "False"
    for url in urls:
        print(f"Processing {url}")
        # Construir los argumentos como string para bash
        #python_exec = sys.executable # se obtiene la ruta absoluta
        python_exec = os.path.expanduser("~/Desktop/Soflex/audio-test-env/bin/python")
        script_path = os.path.abspath("main.py") # convierte el main.py en una ruta absoluta
        #cmd = f"source ~/Desktop/Soflex/audio-test-env/bin/activate && {python_exec} {script_path} '{url}' '{headless}'"
        #subprocess.Popen([
        #    "gnome-terminal", "--", "bash", "-c", cmd
        #])
        subprocess.Popen([python_exec, script_path, url, headless])
        time.sleep(2)

if __name__ == "__main__":
    main()