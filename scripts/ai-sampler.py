#!/usr/bin/env python3
import os
import sys
import re
import json
import subprocess
import glob

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
        # Look for pid=XXXX and port
        for line in out.splitlines():
            m_port = re.search(r':(\d+)\s+', line)
            m_pid = re.search(r'pid=(\d+)', line)
            if m_port and m_pid:
                port = int(m_port.group(1))
                pid = int(m_pid.group(1))
                ports[pid] = port
    except Exception:
        pass
    return ports

def extract_model_name(args_str):
    # Check -m or --model
    m = re.search(r'(?:-m|--model)\s+([^\s]+)', args_str)
    if m:
        path = m.group(1)
        base = os.path.basename(path)
        # remove extensions like .gguf, .bin
        return re.sub(r'\.(?:gguf|bin|safetensors)$', '', base, flags=re.I)

    # Check --alias
    m = re.search(r'--alias\s+([^\s]+)', args_str)
    if m:
        return m.group(1)

    # Check --pack or --native
    m = re.search(r'(?:--pack|--native)\s+([^\s]+)', args_str)
    if m:
        return os.path.basename(m.group(1))

    return "Default Model"

def is_systemd_service(pid):
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
            if "systemd" in content and ".service" in content:
                m = re.search(r'/([^/]+\.service)', content)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None

def scan_ai_processes(gpu_info, listening_ports):
    servers = []
    
    # Signatures for known AI engines
    patterns = [
        ("llama-server", "Llama Server", "llama-server"),
        ("llama-router", "Llama Router", "llama-server"),
        ("ollama", "Ollama", "ollama"),
        ("strata", "Strata Engine", "strata"),
        ("vllm", "vLLM Server", "vllm"),
        ("text-generation-inference", "TGI Server", "tgi"),
        ("lmstudio", "LM Studio", "lmstudio")
    ]

    try:
        ps_out = subprocess.check_output(
            ["ps", "-eo", "pid,ppid,%cpu,%mem,comm,args", "--no-headers"],
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode()
    except Exception:
        return servers

    seen_pids = set()

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

        # Skip our own sampler / ctl scripts or greps
        if "ai-sampler.py" in args or "ai-ctl.py" in args or "grep" in comm:
            continue

        matched_engine = None
        friendly_name = None
        for pat, fname, eng in patterns:
            if pat in comm.lower() or pat in args.lower():
                # Avoid picking up python scripts that just import or mention ollama unless it's a server
                if "python" in comm and "llama-router" not in args and "vllm" not in args:
                    continue
                matched_engine = eng
                friendly_name = fname
                break

        if not matched_engine:
            # Check if this process is holding compute memory according to nvidia-smi
            if pid in gpu_info["apps"] and ("python" in comm or "server" in comm):
                matched_engine = "custom-ai"
                friendly_name = comm.capitalize()

        if matched_engine and pid not in seen_pids:
            seen_pids.add(pid)
            
            # Port detection
            port = listening_ports.get(pid)
            if not port:
                # check command line flags -p / --port
                m_port = re.search(r'(?:-p|--port)\s+(\d+)', args)
                if m_port:
                    port = int(m_port.group(1))

            vram_mib = gpu_info["apps"].get(pid, 0)
            if vram_mib == 0 and "vram_used_mib" in gpu_info and len(seen_pids) == 1:
                # If only one AI process and nvidia-smi didn't break down by PID
                vram_mib = max(0, gpu_info["vram_used_mib"] - 600)

            model = extract_model_name(args)
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
                "cmd": args[:120]
            })

    return servers

def main():
    gpu = get_gpu_info()
    ports = get_listening_ports()
    servers = scan_ai_processes(gpu, ports)

    total_ai_vram = sum(s["vram_mib"] for s in servers)
    total_ai_gb = f"{total_ai_vram / 1024:.1f} GB" if total_ai_vram >= 1024 else f"{total_ai_vram} MB"

    total_gpu_used = gpu["vram_used_mib"]
    total_gpu_cap = gpu["vram_total_mib"]
    used_pct = round((total_gpu_used / total_gpu_cap) * 100) if total_gpu_cap > 0 else 0
    is_warning = used_pct >= 85

    # Badge label for navigation bar
    if len(servers) > 0:
        badge_text = f"AI ({len(servers)}) • {total_ai_gb}"
        badge_status = "warning" if is_warning else "active"
    else:
        badge_text = "AI"
        badge_status = "idle"

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
        "servers": servers
    }

    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
