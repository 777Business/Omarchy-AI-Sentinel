# AI Sentinel 🧠

> The essential Local AI & VRAM manager for the Omarchy Linux shell.

[![Omarchy Plugin](https://img.shields.io/badge/Omarchy-Plugin-blue)](https://omarchy.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI Sentinel** lives directly in your Omarchy status bar. It automatically discovers any running local AI or LLM backend (**Ollama**, **llama.cpp / llama-server**, **Strata**, **vLLM**, etc.), monitors real-time GPU VRAM and compute load, and gives you one-click controls to stop, switch, or release GPU memory.

![AI Sentinel Preview](preview.png)

---

## Features

- 🔍 **Zero-Config Auto-Discovery**: Automatically detects active AI servers and extracts the active model name, PID, listening port, and per-PID VRAM.
- ⚡ **Universal GPU Process Detection**: Automatically catches *any* custom AI server, microservice, or PyTorch process utilizing GPU compute.
- 📌 **Custom Presets & One-Click Pinning**: Detected new or unlisted servers can be pinned to your permanent launch presets with one click.
- 🟢 **Glanceable Top Bar Pill**:
  - **Idle**: Clean neutral icon when no models are loaded (`🧠 AI`).
  - **Active**: Live badge with active server count & VRAM consumed (e.g. `🟢 AI (1) • 5.8 GB`).
  - **Warning**: Glows amber when total GPU VRAM exceeds 85%, alerting you before out-of-memory (OOM) crashes happen.
- 🛑 **One-Click Stop & Switch**:
  - Individual `STOP` buttons on each detected server card.
  - Properly disables associated `systemd` user units so rogue servers cannot auto-respawn behind your back.
- ⚡ **Panic "Free All VRAM" Button**: Instantly terminates all active AI backends and resets GPU memory to baseline.
- 🚀 **Quick Start Presets**: One-click launch buttons for your favorite local engines (**Ollama**, **Strata**, **Llama-Router**).
- 🎨 **Native Omarchy Theme**: Seamlessly adapts to your active Material 3 colors, dark/light modes, and font scale.

---

## Installation

Add directly via the Omarchy plugin manager:

```bash
omarchy plugin add https://github.com/777Business/Omarchy-AI-Sentinel.git --enable
```

Or clone manually into your plugins directory:

```bash
cd ~/.config/omarchy/plugins
git clone https://github.com/777Business/Omarchy-AI-Sentinel.git
omarchy plugin enable omarchy-ai-sentinel --section right
```

---

## Removal

To disable or completely remove the plugin:

```bash
# Disable without uninstalling:
omarchy plugin disable omarchy-ai-sentinel

# Completely uninstall:
omarchy plugin remove omarchy-ai-sentinel --yes
```

---

## Dependencies

- **Python 3** (Standard on Omarchy/Arch Linux)
- **NVIDIA GPU Driver** (`nvidia-smi` utility for VRAM tracking)

---

## Architecture

- **`manifest.json`**: Official Omarchy Plugin Schema v1 specification.
- **`BarWidget.qml`**: Bar pill and live poll trigger.
- **`Panel.qml`**: Flyout control center with GPU gauge, server list, and preset actions.
- **`scripts/ai-sampler.py`**: Lightweight, non-blocking process & `nvidia-smi` JSON sampler.
- **`scripts/ai-ctl.py`**: Process supervisor and clean memory releaser.

---

## License

MIT © 777Business
