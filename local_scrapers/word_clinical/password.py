from pathlib import Path


def derive_password(filepath: str | Path) -> str:
    """Last 4 chars of the first word in the filename, reversed."""
    stem = Path(filepath).name
    first_word = stem.split(" ")[0]
    return first_word[-4:][::-1]
