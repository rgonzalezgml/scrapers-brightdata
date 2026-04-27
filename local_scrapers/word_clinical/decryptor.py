import io
from pathlib import Path

import msoffcrypto


def decrypt_docx(filepath: str | Path, password: str) -> io.BytesIO:
    """Decrypt a password-protected .docx and return a BytesIO ready for python-docx."""
    with open(filepath, "rb") as f:
        office = msoffcrypto.OfficeFile(f)
        office.load_key(password=password)
        buf = io.BytesIO()
        office.decrypt(buf)
    buf.seek(0)
    return buf
