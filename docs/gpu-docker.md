# Running ForgeAI Studio with an NVIDIA GPU in Docker

The default `docker compose up` stack runs the API on **CPU**. To use an NVIDIA GPU:

1. Install a recent NVIDIA driver and the
   [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
   On Windows use Docker Desktop with the WSL 2 backend; GPU support comes through WSL.
2. Check the toolkit works:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```
3. Start the stack with the GPU override:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
   ```
   The override rebuilds the API image with CUDA 12.4 PyTorch wheels, reserves one GPU and sets
   `DEVICE=cuda`.
4. Open the **System** page: it should list your GPU, CUDA version and VRAM.

## Choosing a different CUDA version

Pick the wheel index matching your driver (see <https://pytorch.org/get-started/locally/>) and set
`TORCH_INDEX_URL` in `docker-compose.gpu.yml`, e.g. `https://download.pytorch.org/whl/cu126`.

## Low-VRAM GPUs

Set `ENABLE_CPU_OFFLOAD=true` on the `api` service. Idle submodules then stay in system RAM and
move to the GPU only while in use: slower, but SDXL fits in far less VRAM.

## Status

The GPU override is provided as documentation and has not been exercised on real NVIDIA hardware
by the project's automated checks (CI has no GPU). The CPU image is built in CI.
