"""Training worker process: `python -m ai.training.worker <config.json> <cancel-flag-path>`.

Runs one training job in its own process so a crash or out-of-memory error can't take down the
API, and all memory is returned to the system when it exits. Progress goes to stdout as protocol
events; cancellation is requested by the parent creating the cancel-flag file.
"""

import logging
import sys
import traceback
from pathlib import Path

from ai.errors import AIError, OutOfMemoryError
from ai.training import protocol
from ai.training.config import TrainingConfig
from ai.training.errors import TrainingCancelled


def main(argv: list[str]) -> int:
    config_path, cancel_path = Path(argv[1]), Path(argv[2])
    config = TrainingConfig.read(config_path)

    def should_cancel() -> bool:
        return cancel_path.exists()

    if config.backend == "mock":
        from ai.training.mock_trainer import train
    else:
        from ai.training.diffusers_trainer import train

    try:
        lora_path = train(config, protocol.emit, should_cancel)
    except TrainingCancelled as cancelled:
        protocol.emit("cancelled", last_checkpoint=cancelled.last_checkpoint)
        return protocol.EXIT_CANCELLED
    except AIError as exc:
        protocol.emit("error", code=exc.code, message=exc.message)
        return protocol.EXIT_FAILED
    except MemoryError:
        oom = OutOfMemoryError(
            "Training ran out of memory. Try a lower resolution, batch size 1, or a smaller rank."
        )
        protocol.emit("error", code=oom.code, message=oom.message)
        return protocol.EXIT_FAILED
    except Exception as exc:
        traceback.print_exc()  # stderr goes to the job's training log
        if "out of memory" in str(exc).lower():
            protocol.emit(
                "error",
                code=OutOfMemoryError.code,
                message="Training ran out of memory. Try a lower resolution or batch size 1.",
            )
        else:
            protocol.emit(
                "error",
                code="training_failed",
                message="Training failed unexpectedly. The training log has the details.",
            )
        return protocol.EXIT_FAILED
    protocol.emit("done", lora_path=str(lora_path))
    return protocol.EXIT_OK


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    sys.exit(main(sys.argv))
