"""
File: auth.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 30.03.2026
Brief: File that contains helper methods for request authentication, including SHA-256 hashing
    and validation of authentication header against configured credentials
"""

import hashlib
from fastapi import Request, HTTPException
from api.config.config import Config


def make_sha256(text: str) -> str:
    """
    Method that converts input text into SHA-256 hexadecimal hash string
    :param text: `str` text that will be hashed
    :return: `str` hexadecimal SHA-256 hash of given input text
    """
    # Encode input string into UTF-8 byte representation before hashing.
    encoded: bytes = text.encode("utf-8")

    # Return hexadecimal representation of computed SHA-256 digest.
    return hashlib.sha256(encoded).hexdigest()


def authenticate(request: Request) -> bool:
    """
    Method that validates request authentication using header name and expected hash loaded from configuration
    :param request: `Request` incoming FastAPI request object
    :return: `bool` True if authentication succeeds
    :raises HTTPException: if configuration cannot be loaded, authentication header is missing or empty,
        or provided credentials are invalid
    """

    # Try to load application configuration containing authentication settings.
    try:
        cfg = Config.get_instance("config.json")

    # Configuration file is missing, therefore authentication cannot be performed.
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Configuration file was not found"
        )

    # Any other configuration-related failure is reported as internal server error.
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration: {str(e)}"
        )

    # Read authentication-related values from loaded server configuration.
    header_name = cfg.server_conf.auth_header_name
    expected_hash = cfg.server_conf.pvd_hash

    # Header name must be configured, otherwise server cannot know which header to inspect.
    if not header_name:
        raise HTTPException(
            status_code=500,
            detail="Auth header name is not configured"
        )

    # Expected hash must be configured, otherwise provided credentials cannot be verified.
    if not expected_hash:
        raise HTTPException(
            status_code=500,
            detail="Auth hash is not configured"
        )

    # Extract authentication header value from incoming request.
    incoming_value = request.headers.get(header_name)

    # Authentication header is completely missing from request.
    if incoming_value is None:
        raise HTTPException(
            status_code=401,
            detail=f"Missing authentication header: {header_name}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Authentication header exists, but it does not contain any usable value.
    if not incoming_value.strip():
        raise HTTPException(
            status_code=401,
            detail=f"Empty authentication header: {header_name}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Hash provided header value so it can be compared with configured hash.
    computed_hash = make_sha256(incoming_value)

    # Reject request if provided credentials do not match expected value.
    if computed_hash != expected_hash:
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication credentials"
        )

    # Authentication succeeded.
    return True