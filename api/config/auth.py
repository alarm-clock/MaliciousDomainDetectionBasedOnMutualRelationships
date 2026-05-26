import hashlib
from fastapi import Request, HTTPException
from api.config.config import Config


def make_sha256(text: str) -> str:
    """
    Convert the input text to a SHA-256 hexadecimal hash.
    """
    encoded: bytes = text.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def authenticate(request: Request) -> bool:
    """
    Validate the request authentication using the header defined in config.

    Returns:
    - True, if authentication succeeds

    Raises:
    - HTTPException with a specific status code if authentication fails
    """

    # 500 Internal Server Error
    try:
        cfg = Config.get_instance("config.json")
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Configuration file was not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration: {str(e)}"
        )

    header_name = cfg.server_conf.auth_header_name
    expected_hash = cfg.server_conf.pvd_hash

    if not header_name:
        raise HTTPException(
            status_code=500,
            detail="Auth header name is not configured"
        )

    if not expected_hash:
        raise HTTPException(
            status_code=500,
            detail="Auth hash is not configured"
        )
    incoming_value = request.headers.get(header_name)

    # 401 Unauthorized

    # The entire header is missing
    if incoming_value is None:
        raise HTTPException(
            status_code=401,
            detail=f"Missing authentication header: {header_name}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # The header exists, but is empty or whitespace only
    if not incoming_value.strip():
        raise HTTPException(
            status_code=401,
            detail=f"Empty authentication header: {header_name}",
            headers={"WWW-Authenticate": "Bearer"}
        )


    # 403 Forbidden
    computed_hash = make_sha256(incoming_value)

    if computed_hash != expected_hash:
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication credentials"
        )


    # 200 OK implicitly
    return True
