import hashlib

secret = "heslo"
print(hashlib.sha256(secret.encode("utf-8")).hexdigest())