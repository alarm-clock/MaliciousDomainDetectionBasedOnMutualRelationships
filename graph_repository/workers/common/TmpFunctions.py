TMP_REGISTRY = {}

def register(f_name: str, fun):
    TMP_REGISTRY[f_name] = fun