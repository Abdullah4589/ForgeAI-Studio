"""Filesystem helpers that keep untrusted names inside their storage directories."""

import re
import unicodedata
from pathlib import Path

from forge_api.errors import UnprocessableError

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
MAX_FILENAME_LENGTH = 128


def safe_filename(original: str, *, required_suffix: str) -> str:
    """Reduce an uploaded filename to a safe basename with the expected extension.

    Directory components are discarded (both separators, since clients may be on Windows),
    characters are restricted to [A-Za-z0-9._-], and leading dots are removed so the result can
    never be a hidden file, '.' or '..'.
    """
    basename = re.split(r"[\\/]", original)[-1]
    normalized = unicodedata.normalize("NFKD", basename).encode("ascii", "ignore").decode()
    if not normalized.lower().endswith(required_suffix):
        raise UnprocessableError(f"Only {required_suffix} files are allowed.")
    stem = normalized[: -len(required_suffix)]
    stem = _UNSAFE_CHARS.sub("_", stem).strip("._-")[: MAX_FILENAME_LENGTH - len(required_suffix)]
    if not stem:
        raise UnprocessableError("The file name is not valid.")
    return f"{stem}{required_suffix}"


def resolve_within(base: Path, relative: str) -> Path:
    """Resolve `relative` under `base`, rejecting anything that escapes it."""
    base_resolved = base.resolve()
    candidate = (base_resolved / relative).resolve()
    if not candidate.is_relative_to(base_resolved):
        raise UnprocessableError("Invalid path.")
    return candidate
