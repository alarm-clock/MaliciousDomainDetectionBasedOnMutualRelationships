import psutil

GB = 1024**3
def enough_memory() -> bool:
    mem = psutil.virtual_memory()
    available = mem.available / GB

    return available > 4#GB