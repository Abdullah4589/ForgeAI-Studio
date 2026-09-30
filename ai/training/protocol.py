"""Line-based messages from the training worker process to the app.

Each event is one stdout line: a marker followed by JSON. The marker separates events from
anything a library might print to stdout on its own.
"""

import json
import sys
from typing import Any

MARKER = "@@forge-training "

# Worker exit codes.
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CANCELLED = 3


def emit(event_type: str, **payload: Any) -> None:
    sys.stdout.write(MARKER + json.dumps({"type": event_type, **payload}) + "\n")
    sys.stdout.flush()


def parse(line: str) -> dict[str, Any] | None:
    """Return the event on this line, or None for ordinary output."""
    if not line.startswith(MARKER):
        return None
    try:
        event = json.loads(line[len(MARKER) :])
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) and "type" in event else None
