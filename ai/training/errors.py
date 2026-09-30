from ai.errors import AIError


class TrainingFailedError(AIError):
    code = "training_failed"


class TrainingCancelled(Exception):
    """Raised inside the worker when the user asks to stop."""

    def __init__(self, last_checkpoint: str | None) -> None:
        super().__init__("Training was cancelled.")
        self.last_checkpoint = last_checkpoint
