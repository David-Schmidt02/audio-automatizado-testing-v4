import sys
import os
import time
import subprocess
# ~/Desktop/Soflex/audio-test-env/bin/python 
# main.py "https://www.youtube.com/@olgaenvivo_/live" Chromium F
url1 = "https://www.youtube.com/@olgaenvivo_/live"
url2 = "https://www.youtube.com/@luzutv/live"
url3 = "https://www.youtube.com/@todonoticias/live"
url4 = "https://www.youtube.com/@lanacion/live"
url5 = "https://www.youtube.com/@C5N/live"
url6 = "https://www.youtube.com/@A24com/live"
url7 = "https://www.youtube.com/@Telefe/live"
url8 = "https://www.youtube.com/@UrbanaPlayFM/live"



urls = [url1, url2, url3, url4]

def main():
    formato = "ffmpeg" # o parec
    navigator = "Chromium"
    env_active = os.path.expanduser("~/Escritorio/Soflex/audio-test-env/bin/activate")
    python_env_interprete = os.path.expanduser("~/Escritorio/Soflex/audio-test-env/bin/python")
    script_path = os.path.abspath("main.py")
    #num_cores = 6  # Cambia este valor según los núcleos que quieras usar

    for i, url in enumerate(urls):
        print(f"Processing {url}")
        #core = i % num_cores  # Asigna núcleo de forma cíclica
        """cmd = f"taskset -c {core} {python_env_interprete} {script_path} '{url}' '{navigator}' '{formato}'; exec bash"
        """
        cmd = f"{python_env_interprete} {script_path} '{url}' '{navigator}' '{formato}'; exec bash"
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", cmd])
        time.sleep(20)

if __name__ == "__main__":
    main()
