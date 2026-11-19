# AI Sentinel 🧠

> **The Intelligent Local AI Supervisor & VRAM Sentinel for Omarchy Linux.**  
> Monitor, orchestrate, and liberate GPU memory across local LLM engines with a single click directly from your desktop bar.

[![Omarchy Plugin](https://img.shields.io/badge/Omarchy-Plugin%20v1-7c3aed?style=flat-square&logo=archlinux)](https://omarchy.org)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20%2F%20Wayland-blue?style=flat-square&logo=linux)](https://github.com/777Business/Omarchy-AI-Sentinel)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=flat-square)](LICENSE)
[![NVIDIA CUDA](https://img.shields.io/badge/GPU-NVIDIA%20CUDA%20%26%20ROCm-76b900?style=flat-square&logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)

---

<p align="center">
  <img src="preview.png" alt="Omarchy AI Sentinel Interface Preview" width="450" />
</p>

---

## The Problem

When running modern local AI backends (**llama-server**, **llama-router**, **Ollama**, **vLLM**, or autonomous agent harnesses like **DeepSeek Harness / dsh**), local LLMs often occupy 6 GB to 16+ GB of GPU VRAM silently in the background. 

Leaving an unmanaged model loaded consumes power, throttles system graphics, and causes immediate **CUDA Out-Of-Memory (OOM)** crashes when launching video editors, games, 3D suites, or secondary model tests. 

**AI Sentinel** solves this permanently by integrating directly into your Omarchy status bar:
- **Know at a glance** exactly which models are loaded and how much VRAM they consume.
- **Inspect** model names, PIDs, listening ports, CPU %, and systemd service units.
- **Liberate VRAM instantly** with granular per-server stops or a single **Panic VRAM Release** button.

---

## ✨ Key Features

### 🔍 Zero-Config Auto-Discovery & Model Introspection
AI Sentinel runs a sub-30ms non-blocking asynchronous concurrent sampler that continuously inspects active compute processes, networking sockets, local AI APIs, and GPU hardware metrics.
- **Model Name & Spec Extraction**: Automatically queries Ollama's local API (`/api/ps`) and llama-router (`/health`) or command-line weights flags (`-m`, `--model`) to show the friendly model name, parameter size, and quantization level (e.g. `qwen2.5:3b (3.1B, Q4_K_M)`, `DeepSeek-V4-Pro-Qwen3.5-9B`).
- **Zero-Root Ollama Integration**: Tracks active models running under dedicated system users (`ollama`) and issues clean `keep_alive: 0` API unload commands to instantly liberate VRAM without requiring sudo.
- **Dynamic Router Support**: Native integration with dynamic LLM proxies and routers (`llama-router`), distinguishing between loaded standby states and active inference sessions.
- **Universal GPU Fallback**: Catches *any* custom PyTorch, JAX, or CUDA process consuming GPU compute memory while filtering out desktop utilities (browsers, video editors, shell).

### 📊 Real-Time VRAM & Compute Telemetry
- **3-Tier VRAM Breakdown**: Distinguishes between VRAM consumed specifically by AI models, VRAM held by desktop/system processes (compositor, browser), and remaining free headroom.
- **Model Fit Advisor**: Dynamically calculates and displays what parameter sizes comfortably fit into remaining VRAM (e.g. `⚡ Fits up to ~14B (Q4) / ~8B (Q8)`).
- **Sub-30ms Concurrent Threading**: Parallelizes `nvidia-smi`, `ss`, `ps`, and HTTP health probes into a 6-worker pool for near-instant telemetry.
- **Proactive 85% Warning**: The bar pill dynamically transitions to warning mode when VRAM pressure exceeds safe operating thresholds, preventing unexpected OOM kernel kills.

### 🛑 One-Click Lifecycle Management & Systemd Integration
- **Granular Server Stop & Model Unload**: Terminate individual runaway backends or unload specific Ollama/router models directly from their dedicated card with instant `Stopping...` visual feedback.
- **Systemd Unit Awareness**: Detects if an AI server is supervised by `systemd` (e.g. `llama-server.service`, `ollama.service`). Stopping a service unit cleanly issues `systemctl --user stop`, preventing systemd from auto-respawning it behind your back.
- **Graceful SIGINT Termination**: Sends clean shutdown signals before falling back to forceful kills, eliminating model unload core dumps.

### 🚨 Instant Panic "Release All VRAM"
Need to quickly launch a demanding game, render a video timeline in FilmCraft / DaVinci Resolve, or spin up a new agent cluster? Tap **Release All VRAM & Stop AI Servers** to instantly terminate all AI processes, flush Ollama and router models, and liberate GPU memory to pristine desktop baseline.

### 📌 Expanded Quick Start Grid, Active Indicators & Preset Creator
- Pre-configured responsive launcher grid for **Llama Server**, **DeepSeek**, **Ollama**, **Strata**, **VoiceStudio**, and **vLLM**.
- **Live Active Preset Badges**: Presets dynamically display green `● ACTIVE` indicators when their engines are running.
- **In-Panel Preset Creator**: Use the inline `+ Add Preset` builder to save custom launcher commands directly from the UI.
- **1-Click API Copy**: Copy OpenAI-compatible endpoint URLs (`http://localhost:<port>/v1`) directly to your clipboard.

### 🎨 Native Omarchy & Quickshell Integration
Built with pure Qt Quick / QML following the official Omarchy Quattro design language:
- Harmonizes with active desktop palette, corner radii, and spacing scales.
- Exposes full **ShellIpc** remote targets (`open`, `close`, `toggle`, `refresh`).

---

## 🛠️ Supported AI Backends

| Engine / Framework | Detection Method | Model Introspection | Service Management |
| :--- | :--- | :--- | :--- |
| **llama-server / llama.cpp** | Binary & Process Name | Path / Name Parsing | Process Group / Systemd |
| **llama-router** | Port 11435 & Health API | Dynamic On-Demand / Loaded | `systemctl --user` |
| **Ollama** | CLI / Service (`ollama serve`) | Active Loaded Model API | `systemctl` / Process |
| **vLLM** | Python module / CLI `--model` | Hugging Face ID / Path | Process Group |
| **Strata Engine** | Native process invocation | Weight filename | Process Group |
| **KoboldCPP** | Executable pattern | Weight filename | Process Group |
| **Text Generation Inference (TGI)** | Process arguments | Model repository ID | Container / Process |
| **LM Studio / LocalAI / TabbyAPI** | Binary signature | Active session | Process Group |
| **Generic PyTorch / CUDA Compute** | GPU memory heuristic | Process commandline | PID Termination |

---

## 📥 Installation

### Method 1: Using the Omarchy Plugin CLI (Recommended)
Add and enable the plugin directly in your Omarchy environment:

```bash
omarchy plugin add https://github.com/777Business/Omarchy-AI-Sentinel.git --enable --section right
```

### Method 2: Manual Git Clone
Clone directly into your Omarchy plugins directory:

```bash
cd ~/.config/omarchy/plugins
git clone https://github.com/777Business/Omarchy-AI-Sentinel.git
omarchy plugin enable omarchy-ai-sentinel --section right
omarchy restart shell
```

---

## 🎮 Desktop Keybinding & IPC Control

AI Sentinel exposes native `ShellIpc` bindings. You can bind a keyboard shortcut in Hyprland to toggle the panel on demand:

Add to your `~/.config/hypr/hyprland.conf`:
```ini
# Toggle AI Sentinel overlay
bind = $mainMod, A, exec, quickshell ipc -p ~/.local/share/omarchy-quattro/shell/shell.qml call omarchy-ai-sentinel toggle
```

Available IPC endpoints:
```bash
# Toggle the flyout panel
quickshell ipc -p ~/.local/share/omarchy-quattro/shell/shell.qml call omarchy-ai-sentinel toggle

# Open panel
quickshell ipc -p ~/.local/share/omarchy-quattro/shell/shell.qml call omarchy-ai-sentinel open

# Close panel
quickshell ipc -p ~/.local/share/omarchy-quattro/shell/shell.qml call omarchy-ai-sentinel close

# Force refresh hardware and process telemetry
quickshell ipc -p ~/.local/share/omarchy-quattro/shell/shell.qml call omarchy-ai-sentinel refresh
```

---

## ⚙️ Architecture & Dataflow

```mermaid
flowchart TD
    subgraph GPU["NVIDIA GPU Hardware"]
        NV["nvidia-smi"]
    end

    subgraph OS["Linux OS & Systemd"]
        PROC["/proc filesystem"]
        SS["ss (Listening Ports)"]
        SYS["systemd user units"]
    end

    subgraph Sentinel["Omarchy AI Sentinel"]
        SAMPLER["scripts/ai-sampler.py"]
        CTL["scripts/ai-ctl.py"]
        BAR["BarWidget.qml (Top Pill)"]
        PANEL["Panel.qml (Control Card)"]
    end

    subgraph AI["Active AI Backends"]
        LLAMA["llama-server"]
        ROUTER["llama-router.py"]
        OLLAMA["ollama"]
        VLLM["vLLM / PyTorch"]
    end

    NV -->|VRAM & Compute %| SAMPLER
    PROC -->|PID, PPID, CPU, RSS| SAMPLER
    SS -->|Open Ports: 11434, 11435, ...| SAMPLER
    ROUTER -.->|HTTP /health Query| SAMPLER

    SAMPLER -->|JSON Payload| BAR
    BAR -->|Data Binding| PANEL

    PANEL -->|Stop / Start / Panic Release| CTL
    CTL -->|systemctl --user stop| SYS
    CTL -->|SIGINT / SIGKILL| AI
```

---

## 📁 Repository Structure

```
Omarchy-AI-Sentinel/
├── BarWidget.qml       # Omarchy bar widget, status dot, and background sampler process
├── Panel.qml           # Floating flyout control panel with VRAM gauge and server list
├── manifest.json       # Omarchy Plugin Schema v1 manifest
├── preview.png         # High-resolution screenshot preview
├── scripts/
│   ├── ai-sampler.py   # Asynchronous telemetry & process inspector
│   └── ai-ctl.py       # Action dispatcher for starting/stopping servers & presets
└── README.md           # Documentation
```

---

## 🔧 Configuration & Custom Presets

User custom presets are persisted in standard JSON format at:
```
~/.config/omarchy-ai-sentinel/custom_presets.json
```

Example configuration:
```json
[
  {
    "id": "deepseek-local",
    "name": "DeepSeek 9B",
    "pattern": "llama-server",
    "cmd": "~/.local/bin/llama-server.sh"
  }
]
```

---

## 🗑️ Removal & Disabling

```bash
# Temporarily disable without removing
omarchy plugin disable omarchy-ai-sentinel

# Permanently remove
omarchy plugin remove omarchy-ai-sentinel --yes
```

---

## 🤝 Contributing

Contributions, bug reports, and pull requests are welcome! If you use an AI engine not currently recognized by default, feel free to submit an issue or open a PR extending `scripts/ai-sampler.py`.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.  
Crafted with ❤️ for the **Omarchy Linux** ecosystem.
