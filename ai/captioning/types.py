from typing import Protocol

from PIL.Image import Image


class Captioner(Protocol):
    """Turns an image into a suggested training caption.

    Implementations load their model lazily on first use and must free it in `release()`, so a
    captioner and an image-generation model are never both held in memory.
    """

    # Recorded next to each AI caption so users know which model wrote it.
    name: str

    def caption(self, image: Image) -> str: ...

    def release(self) -> None: ...
