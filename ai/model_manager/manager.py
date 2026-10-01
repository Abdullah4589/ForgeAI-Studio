"""Owns the (at most one) loaded pipeline.

Only a single base model is kept in memory at a time: consumer GPUs rarely fit two, so loading a
different model always unloads the current one first.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ai.device import release_memory
from ai.pipelines.factory import PipelineRequest, build_pipeline

logger = logging.getLogger(__name__)

PipelineBuilder = Callable[[PipelineRequest], Any]


@dataclass(frozen=True)
class LoadedModel:
    request: PipelineRequest
    pipeline: Any
    loaded_at: float


class ModelManager:
    def __init__(self, builder: PipelineBuilder = build_pipeline) -> None:
        self._builder = builder
        self._loaded: LoadedModel | None = None
        # Re-entrant so `acquire()` callers can load while already holding the lock.
        self._lock = threading.RLock()

    @property
    def lock(self) -> threading.RLock:
        """Hold this while using a pipeline so it can't be unloaded mid-generation."""
        return self._lock

    def loaded_request(self) -> PipelineRequest | None:
        # Deliberately lock-free: a generation holds the lock for minutes, and callers (e.g. the
        # model list) only need a snapshot. Reading one attribute reference is atomic.
        loaded = self._loaded
        return loaded.request if loaded else None

    def load(self, request: PipelineRequest) -> Any:
        with self._lock:
            if self._loaded is not None and self._loaded.request == request:
                return self._loaded.pipeline
            self.unload()
            started = time.perf_counter()
            logger.info(
                "model_load_started",
                extra={"path": str(request.path), "device": request.device},
            )
            pipeline = self._builder(request)
            self._loaded = LoadedModel(request, pipeline, time.time())
            logger.info(
                "model_loaded",
                extra={
                    "path": str(request.path),
                    "device": request.device,
                    "seconds": round(time.perf_counter() - started, 2),
                },
            )
            return pipeline

    def unload(self) -> bool:
        with self._lock:
            if self._loaded is None:
                return False
            path = str(self._loaded.request.path)
            # Drop our only reference before collecting so the weights can actually be freed.
            self._loaded = None
            release_memory()
            logger.info("model_unloaded", extra={"path": path})
            return True
