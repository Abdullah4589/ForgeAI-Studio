# Running ForgeAI Studio on a cloud GPU

No NVIDIA GPU at home? Run the **API on a rented GPU** and keep the **web UI on your own
machine**. Generation then takes seconds instead of minutes, and full-size, realistic models fit.

```
your machine                                cloud GPU machine
browser -> web UI (localhost:3000) -> SSH tunnel (localhost:8000) -> API + models + GPU
```

The API is never exposed on a public URL: it has no authentication, so it listens on `localhost`
of the cloud machine and you reach it through an SSH tunnel.

This guide uses [Lightning AI](https://lightning.ai) Studios, which have a free monthly GPU
allowance and support SSH. Any Linux machine with an NVIDIA GPU and SSH works the same way.

> **Not Google Colab's free tier:** it disallows using a notebook as a web UI or through a
> tunnel, and has restricted Stable Diffusion web UIs specifically.

## 1. Create the GPU machine (once)

1. Sign up at <https://lightning.ai> and create a new **Studio**.
2. Switch the Studio's machine from CPU to a **GPU** (a T4 with 16 GB is enough for everything
   below).
3. Open the Studio's terminal and run:
   ```bash
   git clone https://github.com/Abdullah4589/ForgeAI-Studio.git forge-ai-studio
   cd forge-ai-studio
   bash scripts/cloud_setup.sh
   ```
   The script installs the app with GPU PyTorch, downloads a realistic SD 1.x model
   ([Realistic Vision V5.1](https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE), about
   4.3 GB) and starts the API. It is ready when you see `app_started`. Leave the terminal open.

## 2. Connect from your machine

1. In the Studio, open its **SSH** instructions and run the one-time key setup command it shows
   on your own machine. That command contains a personal token: don't share it or commit it.
2. Make sure nothing else uses port 8000 locally (stop a locally running API first), then open
   the tunnel and leave it running:
   ```bash
   ssh -L 8000:localhost:8000 s_<your-studio-id>@ssh.lightning.ai
   ```
3. Start the web UI as usual and open <http://localhost:3000>:
   ```bash
   cd apps/web
   npm run dev
   ```
4. Check the **System** page: it should show the cloud GPU, its VRAM and the CUDA version.

## 3. Generate

Pick the model on the Generate page. Good starting settings for Realistic Vision:

| Setting | Value |
| --- | --- |
| Size | 512×768 (portrait) or 768×512 (landscape) |
| Steps | 25 |
| Guidance scale | 5 |
| Negative prompt | `blurry, low quality, deformed, cartoon, painting, extra fingers` |

Example prompt: `photo of a man in a grey suit standing in front of stone columns, natural light,
85mm, sharp focus`.

### A sharper, larger model (SDXL)

For 1024×1024 images, add a realistic SDXL model (about 14 GB to download). Stop the API with
`Ctrl+C`, then:

```bash
bash scripts/cloud_setup.sh SG161222/RealVisXL_V4.0
```

Use 1024×1024, about 25 steps and a guidance scale of 5. SDXL is several times slower than SD 1.x.

## 4. When you are done

- **Stop the Studio** (or switch it back to CPU) so it stops using your GPU allowance.
- Next time: start the Studio on a GPU, run `bash scripts/cloud_setup.sh` again (it skips what is
  already installed), then repeat step 2.

## Good to know

- **Your data lives in the Studio**, under `storage/`: models, generated images, datasets, LoRAs
  and the history database. Use the Download button in the UI to copy images to your machine.
- **These models ship without the NSFW safety checker**, so nothing is filtered.
- **Model licences:** check each model's page before using its images commercially.
- **Out of memory:** start the API with `ENABLE_CPU_OFFLOAD=true bash scripts/cloud_setup.sh`.
- **`PORT=9000 bash scripts/cloud_setup.sh`** uses another port; change the tunnel to match
  (`-L 8000:localhost:9000` keeps the local side on 8000, which is what the web UI expects).

## Your own NVIDIA machine

On Linux, `bash scripts/cloud_setup.sh` works unchanged; skip the tunnel and open the web UI on
the same machine. On Windows, follow the README's installation steps with a CUDA build of
PyTorch. For Docker, see [gpu-docker.md](gpu-docker.md).

## Status

Written from the provider's documentation and not yet run end to end on real GPU hardware by the
project (CI has no GPU). The app's CUDA code paths are unit-tested with fakes only.
