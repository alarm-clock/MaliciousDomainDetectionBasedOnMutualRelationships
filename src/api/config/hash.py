"""
File: hash.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 28.03.2026
Brief: File that computes SHA-256 hash for a static secret string and prints the hexadecimal digest
"""

import hashlib

secret = "heslo"

# Encode the secret as UTF-8 and compute its SHA-256 hexadecimal digest.
print(hashlib.sha256(secret.encode("utf-8")).hexdigest())