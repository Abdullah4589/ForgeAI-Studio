"""Real image generation with Hugging Face Diffusers."""

import importlib
import logging
from typing import Any, Literal

from ai.device import release_memory
from ai.errors import (
    AIError,
    GenerationCancelledError,
    GenerationFailedError,
    OutOfMemoryError,
)
from ai.generation.types import (
    CancelToken,
    GenerationOutput,
    GenerationParams,
    ModelRef,
    ProgressCallback,
)
from ai.lora.apply import apply_lora, remove_loras
from ai.model_manager.manager import ModelManager
from ai.pipelines.factory import PipelineRequest

logger = logging.getLogger(__name__)


class DiffusersBackend:
    def __init__(
        self,
        model_manager: ModelManager,
        device: Literal["cuda", "cpu"],
        enable_cpu_offload: bool,
    ) -> None:
        self._manager = model_manager
        self._device = device
        self._cpu_offload = enable_cpu_offload

    def generate(
        self, params: GenerationParams, on_progress: ProgressCallback, cancel: CancelToken
    ) -> GenerationOutput:
        # Holding the lock prevents an API "unload" from freeing the pipeline mid-run.
        with self._manager.lock:
            pipe = self._manager.load(self._pipeline_request(params.model))
            try:
                return self._run(pipe, params, on_progress, cancel)
            finally:
                if params.lora is not None and not remove_loras(pipe):
                    self._manager.unload()
                release_memory()

    def preload(self, model: ModelRef) -> None:
        self._manager.load(self._pipeline_request(model))

    def release(self) -> None:
        self._manager.unload()

    @property
    def _offload_enabled(self) -> bool:
        return self._cpu_offload and self._device == "cuda"

    def _pipeline_request(self, model: ModelRef) -> PipelineRequest:
        return PipelineRequest(
            path=model.path,
            source_type=model.source_type,
            architecture=model.architecture,
            device=self._device,
            enable_cpu_offload=self._offload_enabled,
        )

    def _run(
        self,
        pipe: Any,
        params: GenerationParams,
        on_progress: ProgressCallback,
        cancel: CancelToken,
    ) -> GenerationOutput:
        torch = importlib.import_module("torch")
        if params.lora is not None:
            apply_lora(pipe, params.lora.path, params.lora.strength)

        seeds = [params.image_seed(i) for i in range(params.num_images)]
        # CPU generators give identical noise on every device, keeping seeds portable.
        generators = [torch.Generator(device="cpu").manual_seed(seed) for seed in seeds]

        def on_step_end(
            pipeline: Any, step: int, _timestep: Any, callback_kwargs: dict[str, Any]
        ) -> dict[str, Any]:
            if cancel.is_set():
                pipeline._interrupt = True  # Diffusers' supported way to stop the denoising loop.
            on_progress(step + 1, params.steps)
            return callback_kwargs

        try:
            result = pipe(
                prompt=params.prompt,
                negative_prompt=params.negative_prompt or None,
                width=params.width,
                height=params.height,
                num_inference_steps=params.steps,
                guidance_scale=params.guidance_scale,
                num_images_per_prompt=params.num_images,
                generator=generators,
                callback_on_step_end=on_step_end,
            )
        except AIError:
            raise
        except (torch.cuda.OutOfMemoryError, MemoryError) as exc:
            logger.warning("generation_out_of_memory", extra={"device": self._device})
            raise OutOfMemoryError() from exc
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower():
                raise OutOfMemoryError() from exc
            logger.exception("generation_runtime_error")
            raise GenerationFailedError(
                "Image generation failed. Check the server logs for details."
            ) from exc

        if cancel.is_set():
            raise GenerationCancelledError()

        return GenerationOutput(
            images=list(result.images),
            seeds=seeds,
            device=self._device,
            model_config={
                "backend": "diffusers",
                "pipeline": type(pipe).__name__,
                "scheduler": type(pipe.scheduler).__name__,
                "dtype": str(pipe.unet.dtype).removeprefix("torch."),
                "cpu_offload": self._offload_enabled,
            },
        )
