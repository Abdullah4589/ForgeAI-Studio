"""Errors raised by the AI layer.

Each carries a stable machine-readable `code` and a `message` that is safe to show to end users.
Technical details belong in logs, never in `message`.
"""


class AIError(Exception):
    code = "ai_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DependencyMissingError(AIError):
    code = "ai_dependencies_missing"


class ModelLoadError(AIError):
    code = "model_load_failed"


class UnsupportedModelError(AIError):
    code = "unsupported_model"


class InvalidSafetensorsError(AIError):
    code = "invalid_safetensors"


class InvalidLoraError(AIError):
    code = "invalid_lora"


class IncompatibleLoraError(AIError):
    code = "incompatible_lora"


class OutOfMemoryError(AIError):
    code = "out_of_memory"

    DEFAULT_MESSAGE = (
        "Not enough memory to finish this generation. Try a smaller resolution, fewer images, "
        "enabling CPU offloading, or a lower-memory model."
    )

    def __init__(self, message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)


class GenerationFailedError(AIError):
    code = "generation_failed"


class GenerationCancelledError(AIError):
    code = "cancelled"

    def __init__(self, message: str = "Generation was cancelled.") -> None:
        super().__init__(message)
