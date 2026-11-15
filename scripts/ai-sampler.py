#!/usr/bin/env python3
import os
import sys
import re
import json
import subprocess
import urllib.request
import urllib.error

CONFIG_DIR = os.path.expanduser("~/.config/omarchy-ai-sentinel")
CUSTOM_PRESETS_FILE = os.path.join(CONFIG_DIR, "custom_presets.json")

def load_custom_presets():
    if not os.path.exists(CUSTOM_PRESETS_FILE):
        return []
    try:
        with open(CUSTOM_PRESETS_FILE, "r") as f:
            data = json.load(f)
            return data.get("presets", [])
    except Exception:
        return []

def get_gpu_info():
    info = {
        "vram_total_mib": 12288,
        "vram_used_mib": 0,
        "vram_free_mib": 12288,
        "gpu_util_pct": 0,
        "apps": {}
    }
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode().strip()
        parts = [int(p.strip()) for p in out.split(",") if p.strip().isdigit()]
        if len(parts) >= 4:
            info["vram_total_mib"] = parts[0]
            info["vram_used_mib"] = parts[1]
            info["vram_free_mib"] = parts[2]
            info["gpu_util_pct"] = parts[3]
    except Exception:
        pass

    try:
        app_out = subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode().strip()
        for line in app_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[0].isdigit():
                pid = int(parts[0])
                mem = int(parts[1]) if parts[1].isdigit() else 0
                info["apps"][pid] = mem
    except Exception:
        pass

    return info

def get_listening_ports():
    ports = {}
    try:
        out = subprocess.check_output(
            ["ss", "-tlpn"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode()
        for line in out.splitlines():
            m_port = re.search(r':(\d+)\s+', line)
            if not m_port:
                continue
            port = int(m_port.group(1))
            for m_pid in re.finditer(r'pid=(\d+)', line):
                pid = int(m_pid.group(1))
                ports[pid] = port
    except Exception:
        pass
    return ports

def extract_model_name(args_str, comm="", port=None):
    if "llama-router" in args_str:
        target_port = port if (port and port != "-") else 11435
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{target_port}/health")
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("backend_active") and data.get("current_model"):
                    return f"{data.get('current_model')} (Loaded)"
                return "Multi-Model (On-Demand)"
        except Exception:
            return "Multi-Model (Dynamic)"

    m = re.search(r'(?:-m|--model)\s+([^\s]+)', args_str)
    if m:
        path = m.group(1)
        base = os.path.basename(path)
        return re.sub(r'\.(?:gguf|bin|safetensors)$', '', base, flags=re.I)

    m = re.search(r'--alias\s+([^\s]+)', args_str)
    if m:
        return m.group(1)

    m = re.search(r'(?:--pack|--native)\s+([^\s]+)', args_str)
    if m:
        return os.path.basename(m.group(1))

    return "Default Model"

def is_systemd_service(pid):
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
            units = [u for u in re.findall(r'([^/\s]+\.service)', content) if not u.startswith("user@")]
            if units:
                return units[-1]
    except Exception:
        pass
    return None

def scan_ai_processes(gpu_info, listening_ports, custom_presets):
    servers = []
    
    # Built-in engines
    patterns = [
        ("llama-server", "Llama Server", "llama-server"),
        ("llama-router", "Llama Router", "llama-server"),
        ("llama.cpp", "Llama.cpp", "llama-server"),
        ("llama-cli", "Llama CLI", "llama-server"),
        ("ollama", "Ollama", "ollama"),
        ("strata", "Strata Engine", "strata"),
        ("vllm", "vLLM Server", "vllm"),
        ("koboldcpp", "KoboldCPP", "koboldcpp"),
        ("text-generation-inference", "TGI Server", "tgi"),
        ("lmstudio", "LM Studio", "lmstudio"),
        ("localai", "LocalAI", "localai"),
        ("tabbyapi", "TabbyAPI", "tabbyapi"),
        ("aphrodite", "Aphrodite Engine", "aphrodite")
    ]

    # Add custom saved presets
    for cp in custom_presets:
        patterns.append((cp["pattern"].lower(), cp["name"], cp["id"]))

    try:
        ps_out = subprocess.check_output(
            ["ps", "-eo", "pid,ppid,%cpu,%mem,comm,args", "--no-headers"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode()
    except Exception:
        return servers

    seen_pids = set()

    # Known non-AI applications to ignore even if they use GPU memory/compute
    ignore_comm = {
        "hyprland", "xwayland", "quickshell", "nautilus", "chrome", "firefox",
        "electron", "filmcraft", "filmcraft-cli", "antigravity", "mpv", "vlc",
        "obs", "steam", "telegram", "discord", "spotify", "alacritty", "kitty",
        "ghostty", "foot", "chatgpt"
    }

    for line in ps_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            cpu = float(parts[2])
            mem = float(parts[3])
            comm = parts[4]
            args = parts[5]
        except ValueError:
            continue

        if "ai-sampler.py" in args or "ai-ctl.py" in args or "grep" in comm or "--type=" in args:
            continue

        matched_engine = None
        friendly_name = None
        is_saved = False

        for pat, fname, eng in patterns:
            if pat in comm.lower() or pat in args.lower():
                if "python" in comm and "llama-router" not in args and "vllm" not in args and pat not in args.lower():
                    continue
                matched_engine = eng
                friendly_name = fname
                is_saved = True
                break

        # Catch-all: Any process holding GPU Compute memory that isn't a desktop app
        if not matched_engine and pid in gpu_info["apps"] and comm.lower() not in ignore_comm:
            matched_engine = "detected-gpu"
            friendly_name = comm.capitalize()
            is_saved = False

        if matched_engine and pid not in seen_pids:
            seen_pids.add(pid)
            
            port = listening_ports.get(pid)
            if not port:
                m_port = re.search(r'(?:-p|--port)\s+(\d+)', args)
                if m_port:
                    port = int(m_port.group(1))

            vram_mib = gpu_info["apps"].get(pid, 0)

            model = extract_model_name(args, comm, port)
            service_unit = is_systemd_service(pid)

            servers.append({
                "pid": pid,
                "ppid": ppid,
                "name": friendly_name,
                "engine": matched_engine,
                "model": model,
                "port": port if port else "-",
                "vram_mib": vram_mib,
                "vram_gb": f"{vram_mib / 1024:.1f} GB" if vram_mib >= 1024 else f"{vram_mib} MB",
                "cpu_pct": cpu,
                "mem_pct": mem,
                "service_unit": service_unit,
                "is_saved": is_saved,
                "cmd": args[:120],
                "comm": comm
            })

    return servers

def main():
    custom_presets = load_custom_presets()
    gpu = get_gpu_info()
    ports = get_listening_ports()
    servers = scan_ai_processes(gpu, ports, custom_presets)

    total_ai_vram = sum(s["vram_mib"] for s in servers)
    total_ai_gb = f"{total_ai_vram / 1024:.1f} GB" if total_ai_vram >= 1024 else f"{total_ai_vram} MB"

    total_gpu_used = gpu["vram_used_mib"]
    total_gpu_cap = gpu["vram_total_mib"]
    used_pct = round((total_gpu_used / total_gpu_cap) * 100) if total_gpu_cap > 0 else 0
    is_warning = used_pct >= 85

    if len(servers) > 0:
        badge_text = f"AI ({len(servers)}) • {total_ai_gb}"
        badge_status = "warning" if is_warning else "active"
    else:
        badge_text = "AI"
        badge_status = "idle"

    # Presets list for UI
    presets = [
        {"id": "llama-server", "name": "Llama Server", "cmd": "systemctl --user start llama-server.service"},
        {"id": "ollama", "name": "Ollama", "cmd": "ollama serve"},
        {"id": "strata", "name": "Strata", "cmd": "strata launch"}
    ]
    for cp in custom_presets:
        presets.append(cp)

    data = {
        "status": badge_status,
        "badge_text": badge_text,
        "server_count": len(servers),
        "total_ai_vram_mib": total_ai_vram,
        "total_ai_vram_gb": total_ai_gb,
        "gpu_total_mib": total_gpu_cap,
        "gpu_used_mib": total_gpu_used,
        "gpu_free_mib": gpu["vram_free_mib"],
        "gpu_used_gb": f"{total_gpu_used / 1024:.1f} GB",
        "gpu_total_gb": f"{total_gpu_cap / 1024:.1f} GB",
        "gpu_used_pct": used_pct,
        "gpu_compute_pct": gpu["gpu_util_pct"],
        "is_warning": is_warning,
        "presets": presets,
        "servers": servers
    }

    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
