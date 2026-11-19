#!/usr/bin/env python3
import os
import sys
import re
import json
import shlex
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

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

def fetch_gpu_summary():
    info = {
        "vram_total_mib": 12288,
        "vram_used_mib": 0,
        "vram_free_mib": 12288,
        "gpu_util_pct": 0
    }
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=1.0
        ).decode().strip()
        parts = [int(p.strip()) for p in out.split(",") if p.strip().isdigit()]
        if len(parts) >= 4:
            info["vram_total_mib"] = parts[0]
            info["vram_used_mib"] = parts[1]
            info["vram_free_mib"] = parts[2]
            info["gpu_util_pct"] = parts[3]
    except Exception:
        pass
    return info

def fetch_gpu_apps():
    apps = {}
    try:
        app_out = subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=1.0
        ).decode().strip()
        for line in app_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[0].isdigit():
                pid = int(parts[0])
                mem = int(parts[1]) if parts[1].isdigit() else 0
                apps[pid] = mem
    except Exception:
        pass
    return apps

def fetch_listening_ports():
    ports = {}
    try:
        out = subprocess.check_output(
            ["ss", "-tlpn"],
            stderr=subprocess.DEVNULL,
            timeout=1.0
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

def fetch_processes():
    procs = {}
    try:
        ps_out = subprocess.check_output(
            ["ps", "-A", "-o", "pid,ppid,%cpu,%mem,user,comm,args", "--no-headers"],
            stderr=subprocess.DEVNULL,
            timeout=1.0
        ).decode()
        for line in ps_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 6)
            if len(parts) < 7:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
                cpu = float(parts[2])
                mem = float(parts[3])
                user = parts[4]
                comm = parts[5]
                args = parts[6]
                procs[pid] = {
                    "pid": pid,
                    "ppid": ppid,
                    "cpu": cpu,
                    "mem": mem,
                    "user": user,
                    "comm": comm,
                    "args": args
                }
            except ValueError:
                continue
    except Exception:
        pass
    return procs

def fetch_ollama_status():
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/ps")
        with urllib.request.urlopen(req, timeout=0.08) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def fetch_llama_router_status():
    try:
        req = urllib.request.Request("http://127.0.0.1:11435/health")
        with urllib.request.urlopen(req, timeout=0.08) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def extract_model_name(args_str, comm="", port=None, router_status=None):
    if "llama-router" in args_str or "llama-router" in comm:
        if router_status and router_status.get("backend_active") and router_status.get("current_model"):
            return f"{router_status.get('current_model')} (Loaded)"
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
    FORBIDDEN_UNITS = (
        "wayland", "hyprland", "desktop", "session", "quickshell",
        "user@", "app.slice", "app-", "systemd", "dbus", "xdg",
        "portal", "fcitx", "gnome", "pipewire", "wireplumber",
        "pulseaudio", "polkit", "graphical"
    )
    ALLOWED_AI_SERVICE_PREFIXES = (
        "llama", "ollama", "strata", "voicestudio", "voxtype",
        "vllm", "koboldcpp", "tgi", "text-generation", "lmstudio",
        "localai", "tabbyapi", "aphrodite"
    )
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
        user_pattern = r'(?:^|/)user@\d+\.service/(?:.*/)?([^/\s]+\.service)'
        for line in content.splitlines():
            m = re.search(user_pattern, line)
            if m:
                unit = m.group(1).lower()
                # Strictly reject any desktop session, compositor, or system infrastructure
                if any(f in unit for f in FORBIDDEN_UNITS):
                    continue
                # Strictly require unit to start with a recognized AI service prefix
                if any(unit.startswith(p) for p in ALLOWED_AI_SERVICE_PREFIXES):
                    return m.group(1)
    except Exception:
        pass
    return None

def get_process_cmd(pid, fallback=""):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
        if raw:
            parts = [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]
            if parts:
                return shlex.join(parts)
    except Exception:
        pass
    return fallback

def calculate_fit_recommendation(free_mib):
    if free_mib >= 16000:
        return "⚡ Fits up to ~32B (Q4) / ~14B (Q8)"
    elif free_mib >= 9000:
        return "⚡ Fits up to ~14B (Q4) / ~8B (Q8)"
    elif free_mib >= 5500:
        return "⚡ Fits up to ~8B (Q4) / ~3B (Q8)"
    elif free_mib >= 2800:
        return "⚡ Fits up to ~3B (Q4) / ~1.5B (Q8)"
    elif free_mib >= 1200:
        return "⚡ Fits up to ~1.5B / Embeddings"
    else:
        return "⚠️ Low VRAM Headroom • Free memory"

def scan_ai_processes(gpu_apps, listening_ports, all_procs, custom_presets, router_status, ollama_status):
    servers = []
    current_uid_name = os.environ.get("USER", "shadow")

    # Built-in engine signatures
    patterns = [
        ("llama-server", "Llama Server", "llama-server"),
        ("llama-router", "Llama Router", "llama-server"),
        ("llama.cpp", "Llama.cpp", "llama-server"),
        ("llama-cli", "Llama CLI", "llama-server"),
        ("dsh", "DeepSeek Harness", "dsh"),
        ("ollama", "Ollama", "ollama"),
        ("strata", "Strata Engine", "strata"),
        ("voicestudio", "VoiceStudio", "voicestudio"),
        ("voxtype", "Voxtype", "voxtype"),
        ("vllm", "vLLM Server", "vllm"),
        ("koboldcpp", "KoboldCPP", "koboldcpp"),
        ("text-generation-inference", "TGI Server", "tgi"),
        ("lmstudio", "LM Studio", "lmstudio"),
        ("localai", "LocalAI", "localai"),
        ("tabbyapi", "TabbyAPI", "tabbyapi"),
        ("aphrodite", "Aphrodite Engine", "aphrodite")
    ]

    for cp in custom_presets:
        patterns.append((cp["pattern"].lower(), cp["name"], cp["id"]))

    ignore_comm = {
        "hyprland", "xwayland", "quickshell", "nautilus", "chrome", "firefox",
        "electron", "filmcraft", "filmcraft-cli", "antigravity", "mpv", "vlc",
        "obs", "steam", "telegram", "discord", "spotify", "alacritty", "kitty",
        "ghostty", "foot", "chatgpt", "wireplumber", "pipewire"
    }

    candidates = {}
    ollama_accounted_pids = set()

    # Step 1: Ingest active Ollama models directly from API if present
    if ollama_status and isinstance(ollama_status.get("models"), list) and len(ollama_status["models"]) > 0:
        for idx, om in enumerate(ollama_status["models"]):
            model_tag = om.get("name") or om.get("model") or "Ollama Model"
            vram_bytes = om.get("size_vram", 0)
            vram_mib = round(vram_bytes / (1024 * 1024))
            details = om.get("details", {})
            quant = details.get("quantization_level", "")
            param_size = details.get("parameter_size", "")
            disp_model = model_tag
            if param_size:
                disp_model += f" ({param_size}" + (f", {quant})" if quant else ")")

            # Match PID from Ollama processes holding GPU compute memory
            matched_pid = None
            for p_id, p in all_procs.items():
                if p["user"] == "ollama" or "ollama" in p["comm"].lower() or "/ollama/" in p["args"]:
                    if p_id in gpu_apps:
                        matched_pid = p_id
                        ollama_accounted_pids.add(p_id)
                        if vram_mib == 0:
                            vram_mib = gpu_apps[p_id]
                        break

            target_id = f"ollama:{model_tag}"
            display_pid = matched_pid if matched_pid else 11434

            candidates[f"ollama_{idx}"] = {
                "pid": display_pid,
                "target_id": target_id,
                "ppid": 1,
                "name": "Ollama",
                "engine": "ollama",
                "model": disp_model,
                "port": 11434,
                "vram_mib": vram_mib,
                "cpu_pct": all_procs.get(matched_pid, {}).get("cpu", 0.0) if matched_pid else 0.0,
                "mem_pct": all_procs.get(matched_pid, {}).get("mem", 0.0) if matched_pid else 0.0,
                "service_unit": "ollama.service",
                "is_saved": True,
                "cmd": f"ollama run {model_tag}",
                "comm": "ollama",
                "is_ollama_api": True,
                "model_tag": model_tag
            }

    # Step 2: Ingest general OS processes
    for pid, p in all_procs.items():
        if pid in ollama_accounted_pids:
            continue

        comm = p["comm"]
        args = p["args"]
        args_lower = args.lower()

        if "ai-sampler.py" in args or "ai-ctl.py" in args or "grep" in comm or "--type=" in args:
            continue

        if any(w in args_lower for w in ["compile_worker", "subproc_pool", "--multiprocessing-fork", "resource_tracker"]):
            continue

        matched_engine = None
        friendly_name = None
        is_saved = False

        for pat, fname, eng in patterns:
            if pat in comm.lower() or pat in args_lower:
                if "python" in comm and "llama-router" not in args and "vllm" not in args and pat not in args_lower:
                    continue
                matched_engine = eng
                friendly_name = fname
                is_saved = True
                break

        # Universal fallback: any process holding GPU compute memory that isn't a desktop app
        if not matched_engine and pid in gpu_apps and comm.lower() not in ignore_comm:
            matched_engine = "detected-gpu"
            friendly_name = comm.capitalize()
            is_saved = False

        if matched_engine:
            vram_mib = gpu_apps.get(pid, 0)
            # If Ollama daemon is running idle with 0 VRAM and no active models, skip adding daemon process
            if matched_engine == "ollama" and vram_mib == 0:
                continue

            port = listening_ports.get(pid)
            model = extract_model_name(args, comm, port, router_status)
            service_unit = is_systemd_service(pid)
            cmd_full = get_process_cmd(pid, fallback=args)

            candidates[pid] = {
                "pid": pid,
                "target_id": str(pid),
                "ppid": p["ppid"],
                "name": friendly_name,
                "engine": matched_engine,
                "model": model,
                "port": port if port else "-",
                "vram_mib": vram_mib,
                "cpu_pct": p["cpu"],
                "mem_pct": p["mem"],
                "service_unit": service_unit,
                "is_saved": is_saved,
                "cmd": cmd_full,
                "comm": comm,
                "is_ollama_api": False
            }

    # Step 3: Hierarchy resolution — collapse worker/child processes
    def find_candidate_root(p_id):
        if not isinstance(p_id, int):
            return None
        curr = all_procs.get(p_id, {}).get("ppid")
        while curr and curr > 1:
            if curr in candidates:
                return curr
            curr = all_procs.get(curr, {}).get("ppid")
        return None

    roots = {}
    for key, cand in candidates.items():
        if isinstance(key, str) and key.startswith("ollama_"):
            roots[key] = cand
            continue

        parent_cand = find_candidate_root(cand["pid"])
        if parent_cand:
            parent = candidates[parent_cand]
            parent["vram_mib"] += cand["vram_mib"]
            parent["cpu_pct"] = round(parent["cpu_pct"] + cand["cpu_pct"], 1)
            parent["mem_pct"] = round(parent["mem_pct"] + cand["mem_pct"], 1)
            if parent["port"] == "-" and cand["port"] != "-":
                parent["port"] = cand["port"]
            if parent["model"] in ("Default Model", "Multi-Model (Dynamic)") and cand["model"] not in ("Default Model", "Multi-Model (Dynamic)"):
                parent["model"] = cand["model"]
            if not parent["service_unit"] and cand["service_unit"]:
                parent["service_unit"] = cand["service_unit"]
        else:
            roots[cand["pid"]] = cand

    # Step 4: Roll up non-candidate descendant workers holding GPU VRAM
    for p_id, p_info in all_procs.items():
        if p_id not in candidates and p_id in gpu_apps and p_id not in ollama_accounted_pids:
            curr = p_info.get("ppid")
            while curr and curr > 1:
                if curr in roots:
                    roots[curr]["vram_mib"] += gpu_apps[p_id]
                    roots[curr]["cpu_pct"] = round(roots[curr]["cpu_pct"] + p_info["cpu"], 1)
                    break
                curr = all_procs.get(curr, {}).get("ppid")

    # Step 5: Format display representation
    for key, s in roots.items():
        vram_mib = s["vram_mib"]
        s["vram_gb"] = f"{vram_mib / 1024:.1f} GB" if vram_mib >= 1024 else f"{vram_mib} MB"
        # Determine API endpoint URL for 1-click copying
        if s.get("port") and s["port"] != "-":
            s["endpoint_url"] = f"http://localhost:{s['port']}/v1"
        elif s["engine"] == "ollama":
            s["endpoint_url"] = "http://localhost:11434/v1"
        else:
            s["endpoint_url"] = ""
        servers.append(s)

    return servers

def main():
    custom_presets = load_custom_presets()

    # High-performance parallel data gathering (<30ms)
    with ThreadPoolExecutor(max_workers=6) as pool:
        f_gpu = pool.submit(fetch_gpu_summary)
        f_apps = pool.submit(fetch_gpu_apps)
        f_ports = pool.submit(fetch_listening_ports)
        f_procs = pool.submit(fetch_processes)
        f_router = pool.submit(fetch_llama_router_status)
        f_ollama = pool.submit(fetch_ollama_status)

        gpu_info = f_gpu.result()
        gpu_apps = f_apps.result()
        listening_ports = f_ports.result()
        all_procs = f_procs.result()
        router_status = f_router.result()
        ollama_status = f_ollama.result()

    servers = scan_ai_processes(
        gpu_apps, listening_ports, all_procs, custom_presets, router_status, ollama_status
    )

    total_ai_vram_mib = sum(s["vram_mib"] for s in servers)
    total_ai_gb = f"{total_ai_vram_mib / 1024:.1f} GB" if total_ai_vram_mib >= 1024 else f"{total_ai_vram_mib} MB"

    total_gpu_used = gpu_info["vram_used_mib"]
    total_gpu_cap = gpu_info["vram_total_mib"]
    gpu_free_mib = gpu_info["vram_free_mib"]

    # 3-tier VRAM partition: AI vs System (compositor, browser) vs Free
    system_vram_mib = max(0, total_gpu_used - total_ai_vram_mib)
    used_pct = round((total_gpu_used / total_gpu_cap) * 100) if total_gpu_cap > 0 else 0
    ai_pct = round((total_ai_vram_mib / total_gpu_cap) * 100) if total_gpu_cap > 0 else 0
    system_pct = round((system_vram_mib / total_gpu_cap) * 100) if total_gpu_cap > 0 else 0
    free_pct = max(0, 100 - ai_pct - system_pct)

    is_warning = used_pct >= 85
    fit_recommendation = calculate_fit_recommendation(gpu_free_mib)

    if len(servers) > 0:
        badge_text = f"AI ({len(servers)}) • {total_ai_gb}"
        badge_status = "warning" if is_warning else "active"
    else:
        badge_text = "AI"
        badge_status = "idle"

    # Built-in presets with live active-detection
    builtins = [
        {"id": "llama-server", "name": "Llama Server", "engine": "llama-server", "cmd": "systemctl --user start llama-server.service"},
        {"id": "dsh", "name": "DeepSeek", "engine": "dsh", "cmd": "dsh web"},
        {"id": "ollama", "name": "Ollama", "engine": "ollama", "cmd": "ollama serve"},
        {"id": "strata", "name": "Strata", "engine": "strata", "cmd": "strata launch"},
        {"id": "voicestudio", "name": "VoiceStudio", "engine": "voicestudio", "cmd": "systemctl --user start voicestudio.service"},
        {"id": "vllm", "name": "vLLM", "engine": "vllm", "cmd": "vllm serve"}
    ]

    active_engines = {s["engine"] for s in servers}
    active_comms = {s["comm"].lower() for s in servers}

    presets = []
    for b in builtins:
        b_dict = dict(b)
        b_dict["is_custom"] = False
        b_dict["is_active"] = (b["engine"] in active_engines) or (b["id"] in active_engines)
        presets.append(b_dict)

    for cp in custom_presets:
        cp_dict = dict(cp)
        cp_dict["is_custom"] = True
        pat = cp.get("pattern", "").lower()
        cp_dict["is_active"] = any(pat in s["comm"].lower() or pat in s["cmd"].lower() for s in servers)
        presets.append(cp_dict)

    data = {
        "status": badge_status,
        "badge_text": badge_text,
        "server_count": len(servers),
        "total_ai_vram_mib": total_ai_vram_mib,
        "total_ai_vram_gb": total_ai_gb,
        "system_vram_mib": system_vram_mib,
        "system_vram_gb": f"{system_vram_mib / 1024:.1f} GB" if system_vram_mib >= 1024 else f"{system_vram_mib} MB",
        "gpu_total_mib": total_gpu_cap,
        "gpu_used_mib": total_gpu_used,
        "gpu_free_mib": gpu_free_mib,
        "gpu_used_gb": f"{total_gpu_used / 1024:.1f} GB",
        "gpu_free_gb": f"{gpu_free_mib / 1024:.1f} GB",
        "gpu_total_gb": f"{total_gpu_cap / 1024:.1f} GB",
        "gpu_used_pct": used_pct,
        "ai_vram_pct": ai_pct,
        "system_vram_pct": system_pct,
        "free_vram_pct": free_pct,
        "gpu_compute_pct": gpu_info["gpu_util_pct"],
        "is_warning": is_warning,
        "fit_recommendation": fit_recommendation,
        "presets": presets,
        "servers": servers
    }

    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
