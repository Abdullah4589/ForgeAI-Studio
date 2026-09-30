"""SD 1.x LoRA training with Diffusers + PEFT. Runs inside the training worker process.

Memory strategy (measured peak ~1.8 GB on CPU with a tiny SD 1.x model at 512 px): images and
captions are encoded once up front, then the VAE and text encoder are freed so only the UNet with
its LoRA adapters stays in memory; gradient checkpointing trades compute for activation memory.
"""

import importlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil
from PIL import Image, ImageOps

from ai.device import release_memory
from ai.errors import DependencyMissingError, ModelLoadError
from ai.lora.apply import apply_lora, remove_loras
from ai.pipelines.factory import PipelineRequest, build_pipeline
from ai.training.config import TrainingConfig
from ai.training.errors import TrainingCancelled

Emit = Callable[..., None]

# Attention projections: the standard, compact choice for SD LoRAs.
TARGET_MODULES = ["to_k", "to_q", "to_v", "to_out.0"]
SAMPLE_GUIDANCE = 7.5


def train(config: TrainingConfig, emit: Emit, should_cancel: Callable[[], bool]) -> Path:
    libs = _import_libraries()
    torch = libs["torch"]
    torch.manual_seed(config.seed)
    output = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    emit("status", message="Loading model")
    pipe = _load_pipeline(libs, config)
    tokenizer, text_encoder, vae, unet = pipe.tokenizer, pipe.text_encoder, pipe.vae, pipe.unet
    noise_scheduler = libs["diffusers"].DDPMScheduler.from_config(pipe.scheduler.config)
    del pipe
    for module in (text_encoder, vae, unet):
        module.requires_grad_(False)
    text_encoder.to(config.device)
    vae.to(config.device)

    emit("status", message=f"Preparing {len(config.items)} images")
    latents, embeddings = _encode_dataset(libs, config, tokenizer, text_encoder, vae, should_cancel)
    del text_encoder, vae
    release_memory()

    unet.to(config.device)
    unet.enable_gradient_checkpointing()
    unet.add_adapter(
        libs["peft"].LoraConfig(
            r=config.rank,
            lora_alpha=config.alpha,
            init_lora_weights="gaussian",
            target_modules=TARGET_MODULES,
        )
    )
    params = [p for p in unet.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=config.learning_rate)
    unet.train()

    generator = torch.Generator().manual_seed(config.seed)
    count = latents.shape[0]
    order: list[int] = []
    started = time.perf_counter()
    last_checkpoint: str | None = None
    for step in range(1, config.steps + 1):
        if should_cancel():
            raise TrainingCancelled(last_checkpoint)
        batch: list[int] = []
        while len(batch) < config.batch_size:
            if not order:  # reshuffle each epoch, reproducibly from the seed
                order = torch.randperm(count, generator=generator).tolist()
            batch.append(order.pop())
        loss = _train_step(
            torch,
            unet,
            noise_scheduler,
            optimizer,
            generator,
            latents,
            embeddings,
            batch,
            config.device,
        )
        emit(
            "progress",
            step=step,
            total=config.steps,
            loss=round(loss, 5),
            elapsed=round(time.perf_counter() - started, 3),
            memory_bytes=_memory_bytes(torch, config.device),
        )
        if config.save_every and step % config.save_every == 0 and step < config.steps:
            path = output / "checkpoints" / f"{config.name}-step-{step:06d}.safetensors"
            _save_lora(libs, unet, path)
            last_checkpoint = str(path)
            emit("checkpoint", step=step, path=str(path))

    final = output / f"{config.name}.safetensors"
    _save_lora(libs, unet, final)
    emit(
        "saved",
        path=str(final),
        avg_step_seconds=round((time.perf_counter() - started) / config.steps, 3),
    )
    del unet, optimizer, params
    release_memory()

    if config.sample_count:
        emit("status", message="Generating samples")
        _generate_samples(torch, config, final, emit, should_cancel)
    return final


def _import_libraries() -> dict[str, Any]:
    try:
        return {
            name: importlib.import_module(name)
            for name in ("torch", "diffusers", "peft", "numpy", "diffusers.utils", "peft.utils")
        }
    except ImportError as exc:
        raise DependencyMissingError(
            'AI dependencies are not installed. Install them with: pip install -e ".[ai]"'
        ) from exc


def _load_pipeline(libs: dict[str, Any], config: TrainingConfig) -> Any:
    pipeline_cls = libs["diffusers"].StableDiffusionPipeline
    # Training never needs the safety checker; skipping it saves ~1.2 GB of memory.
    kwargs = {
        "dtype": libs["torch"].float32,
        "safety_checker": None,
        "requires_safety_checker": False,
    }
    try:
        if config.source_type == "diffusers":
            return pipeline_cls.from_pretrained(config.model_path, use_safetensors=True, **kwargs)
        return pipeline_cls.from_single_file(config.model_path, **kwargs)
    except (OSError, ValueError) as exc:
        raise ModelLoadError("The base model could not be loaded for training.") from exc


def _encode_dataset(
    libs: dict[str, Any],
    config: TrainingConfig,
    tokenizer: Any,
    text_encoder: Any,
    vae: Any,
    should_cancel: Callable[[], bool],
) -> tuple[Any, Any]:
    torch, numpy = libs["torch"], libs["numpy"]
    latents, embeddings = [], []
    with torch.no_grad():
        for item in config.items:
            if should_cancel():
                raise TrainingCancelled(None)
            with Image.open(item.image_path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
            image = ImageOps.fit(
                image, (config.resolution, config.resolution), Image.Resampling.LANCZOS
            )
            pixels = torch.from_numpy(numpy.asarray(image, dtype=numpy.float32))
            pixels = (pixels.permute(2, 0, 1) / 127.5 - 1.0).unsqueeze(0).to(config.device)
            latent = vae.encode(pixels).latent_dist.sample() * vae.config.scaling_factor
            ids = tokenizer(
                [item.caption],
                padding="max_length",
                truncation=True,
                max_length=tokenizer.model_max_length,
                return_tensors="pt",
            ).input_ids.to(config.device)
            latents.append(latent)
            embeddings.append(text_encoder(ids)[0])
    return torch.cat(latents), torch.cat(embeddings)


def _train_step(
    torch: Any,
    unet: Any,
    noise_scheduler: Any,
    optimizer: Any,
    generator: Any,
    latents: Any,
    embeddings: Any,
    batch: list[int],
    device: str,
) -> float:
    latent = latents[batch]
    noise = torch.randn(latent.shape, generator=generator).to(device)
    timesteps = torch.randint(
        0, noise_scheduler.config.num_train_timesteps, (len(batch),), generator=generator
    ).to(device)
    noisy = noise_scheduler.add_noise(latent, noise, timesteps)
    if noise_scheduler.config.prediction_type == "v_prediction":
        target = noise_scheduler.get_velocity(latent, noise, timesteps)
    else:
        target = noise
    prediction = unet(noisy, timesteps, embeddings[batch]).sample
    loss = torch.nn.functional.mse_loss(prediction.float(), target.float())
    loss.backward()
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    return float(loss.item())


def _save_lora(libs: dict[str, Any], unet: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = libs["diffusers.utils"].convert_state_dict_to_diffusers(
        libs["peft.utils"].get_peft_model_state_dict(unet)
    )
    libs["diffusers"].StableDiffusionPipeline.save_lora_weights(
        save_directory=str(path.parent),
        unet_lora_layers=state,
        weight_name=path.name,
        safe_serialization=True,
        # Stores rank/alpha so the LoRA loads at the scale it was trained with.
        unet_lora_adapter_metadata=unet.peft_config["default"].to_dict(),
    )


def _generate_samples(
    torch: Any,
    config: TrainingConfig,
    lora_path: Path,
    emit: Emit,
    should_cancel: Callable[[], bool],
) -> None:
    pipe = build_pipeline(
        PipelineRequest(
            path=Path(config.model_path),
            source_type=config.source_type,
            architecture=config.architecture,
            device=config.device,
            enable_cpu_offload=False,
        )
    )
    apply_lora(pipe, lora_path, 1.0)
    prompts = config.sample_prompts or ["a picture"]
    try:
        for index in range(config.sample_count):
            if should_cancel():
                break  # the LoRA is already saved; stop sampling only
            result = pipe(
                prompt=prompts[index % len(prompts)],
                width=config.resolution,
                height=config.resolution,
                num_inference_steps=config.sample_steps,
                guidance_scale=SAMPLE_GUIDANCE,
                generator=torch.Generator(device="cpu").manual_seed(config.seed + index),
            )
            flags = getattr(result, "nsfw_content_detected", None) or [False]
            path = Path(config.output_dir) / "samples" / f"sample-{index + 1}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            result.images[0].save(path)
            emit("sample", index=index, path=str(path), safety_blocked=bool(flags[0]))
    finally:
        remove_loras(pipe)
        del pipe
        release_memory()


def _memory_bytes(torch: Any, device: str) -> int:
    if device == "cuda":
        return int(torch.cuda.memory_allocated())
    return int(psutil.Process().memory_info().rss)
