import threading

channel_map = {}   # ssrc (str) -> channel_name (str)
channel_map_lock = threading.Lock()
