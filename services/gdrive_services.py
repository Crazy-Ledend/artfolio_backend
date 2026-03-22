import re
from typing import Optional


# Patterns that appear in GDrive shareable links
_PATTERNS = [
    r"/file/d/([a-zA-Z0-9_-]+)",   # .../file/d/FILE_ID/view
    r"id=([a-zA-Z0-9_-]+)",         # ...?id=FILE_ID
    r"/d/([a-zA-Z0-9_-]+)",         # short /d/FILE_ID
]


def extract_file_id(url: str) -> Optional[str]:
    """
    Extract the GDrive file ID from any shareable / direct URL format.

    Supported formats:
      https://drive.google.com/file/d/FILE_ID/view?usp=sharing
      https://drive.google.com/open?id=FILE_ID
      https://drive.google.com/uc?export=view&id=FILE_ID
      https://drive.google.com/thumbnail?id=FILE_ID
    """
    if not url:
        return None
    for pattern in _PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def thumbnail_url(file_id: str, width: int = 800) -> str:
    """
    Fast thumbnail — works for public / anyone-with-link files.
    sz param controls max dimension.
    """
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{width}"


def view_url(file_id: str) -> str:
    """
    Full-resolution direct view URL.
    """
    return f"https://drive.google.com/uc?export=view&id={file_id}"


def shareable_url(file_id: str) -> str:
    """
    Human-readable GDrive link — useful for admin UI.
    """
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"