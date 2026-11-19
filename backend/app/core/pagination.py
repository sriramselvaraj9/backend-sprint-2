import base64
import binascii
import uuid

from app.exceptions.domain import InvalidCursorError


def encode_cursor(record_id: uuid.UUID | str) -> str:
    """
    Encode a record UUID (or string ID) into an opaque URL-safe base64 string cursor.
    """
    return base64.urlsafe_b64encode(str(record_id).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str) -> uuid.UUID:
    """
    Decode an opaque base64 cursor into a record UUID.
    Raises InvalidCursorError (HTTP 400) if malformed.
    """
    if not cursor_str or not isinstance(cursor_str, str):
        raise InvalidCursorError(message="Cursor cannot be empty")
    try:
        try:
            raw = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
            return uuid.UUID(raw)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return uuid.UUID(cursor_str)
    except (ValueError, TypeError) as e:
        raise InvalidCursorError(message=f"Invalid pagination cursor: '{cursor_str}'") from e
