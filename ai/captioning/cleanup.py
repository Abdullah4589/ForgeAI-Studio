"""Turns raw captioner output into training-style captions."""

import re

# Florence-2 (and most caption models) open with a description of the frame rather than the
# content. Training captions read better starting with the subject: "a painting of ...".
_FRAMING_PREFIXES = re.compile(
    r"^(?:the|this) (?:image|picture|photo|photograph|artwork) "
    r"(?:shows|is|depicts|features|contains|appears to be)\s+",
    re.IGNORECASE,
)
_SPACES = re.compile(r"\s+")
_ARTICLES = {"a", "an", "the"}


def clean_caption(raw: str) -> str:
    text = _SPACES.sub(" ", raw).strip()
    text = _FRAMING_PREFIXES.sub("", text)
    first, _, rest = text.partition(" ")
    # Lower-case only a leading article ("A painting" -> "a painting"); proper nouns and
    # acronyms ("Paris", "NASA") keep their capitals.
    if first.lower() in _ARTICLES:
        text = f"{first.lower()} {rest}" if rest else first.lower()
    return text
