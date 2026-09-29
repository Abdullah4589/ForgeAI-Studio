"""Minimal, read-only parser for the safetensors header.

We only need tensor names and shapes to identify architectures, so we parse the JSON header
directly: no tensor data is read, nothing is deserialized beyond JSON, and neither torch nor numpy
is required.
"""

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from ai.errors import InvalidSafetensorsError

# Real headers are a few MB at most; a bigger value means a corrupt or hostile file.
MAX_HEADER_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class TensorInfo:
    dtype: str
    shape: tuple[int, ...]


def read_header(path: Path) -> dict[str, TensorInfo]:
    try:
        file_size = path.stat().st_size
        with path.open("rb") as handle:
            prefix = handle.read(8)
            if len(prefix) != 8:
                raise InvalidSafetensorsError("File is too small to be a safetensors file.")
            (header_len,) = struct.unpack("<Q", prefix)
            if header_len <= 0 or header_len > MAX_HEADER_BYTES or header_len + 8 > file_size:
                raise InvalidSafetensorsError("File has an invalid safetensors header.")
            raw = handle.read(header_len)
    except OSError as exc:
        raise InvalidSafetensorsError("Could not read the safetensors file.") from exc

    try:
        header = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidSafetensorsError("File has a corrupt safetensors header.") from exc
    if not isinstance(header, dict):
        raise InvalidSafetensorsError("File has a corrupt safetensors header.")

    tensors: dict[str, TensorInfo] = {}
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("shape"), list):
            raise InvalidSafetensorsError("File has a corrupt safetensors header.")
        tensors[name] = TensorInfo(dtype=str(entry.get("dtype")), shape=tuple(entry["shape"]))
    if not tensors:
        raise InvalidSafetensorsError("File contains no tensors.")
    return tensors
