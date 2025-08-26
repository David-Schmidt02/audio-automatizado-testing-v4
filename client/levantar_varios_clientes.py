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


urls = [url1, url2, url3, url4, url5]

"""def main():
    headless = "False"
    navigator = "Chromium"  # o "Chromium"
    # Construir los argumentos como string para bash
    env_active = os.path.expanduser("~/Soflex/audio-test-env/bin/activate")
    python_env_interprete = os.path.expanduser("~/Soflex/audio-test-env/bin/python")
    script_path = os.path.abspath("main.py") # convierte el main.py en una ruta absoluta
    for url in urls:
        print(f"Processing {url}")
        cmd = f"{python_env_interprete} {script_path} '{url}' '{navigator}' '{headless}'; exec bash"
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", cmd])
        time.sleep(10)"""

def main():
    headless = "False"
    navigator = "Chromium"
    env_active = os.path.expanduser("~/Soflex/audio-test-env/bin/activate")
    python_env_interprete = os.path.expanduser("~/Soflex/audio-test-env/bin/python")
    script_path = os.path.abspath("main.py")
    num_cores = 6  # Cambia este valor según los núcleos que quieras usar

    for i, url in enumerate(urls):
        print(f"Processing {url}")
        core = i % num_cores  # Asigna núcleo de forma cíclica
        cmd = f"taskset -c {core} {python_env_interprete} {script_path} '{url}' '{navigator}' '{headless}'; exec bash"
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", cmd])
        time.sleep(10)

if __name__ == "__main__":
    main()
