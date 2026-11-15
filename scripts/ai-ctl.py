#!/usr/bin/env python3
import os
import sys
import re
import time
import signal
import subprocess
import json

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

def save_custom_presets(presets):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CUSTOM_PRESETS_FILE, "w") as f:
        json.dump({"presets": presets}, f, indent=2)

def add_preset(preset_id, name, pattern, cmd):
    presets = load_custom_presets()
    for p in presets:
        if p["id"] == preset_id:
            p["name"] = name
            p["pattern"] = pattern
            p["cmd"] = cmd
            save_custom_presets(presets)
            print(f"[AI Sentinel] Updated preset: {name}")
            return True
    presets.append({
        "id": preset_id,
        "name": name,
        "pattern": pattern,
        "cmd": cmd
    })
    save_custom_presets(presets)
    print(f"[AI Sentinel] Added preset: {name}")
    return True

def remove_preset(preset_id):
    presets = load_custom_presets()
    presets = [p for p in presets if p["id"] != preset_id]
    save_custom_presets(presets)
    print(f"[AI Sentinel] Removed preset: {preset_id}")
    return True

def get_systemd_unit(pid):
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
            units = [u for u in re.findall(r'([^/\s]+\.service)', content) if not u.startswith("user@")]
            if units:
                return units[-1]
    except Exception:
        pass
    return None

def stop_pid(pid):
    unit = get_systemd_unit(pid)
    if unit:
        print(f"[AI Sentinel] Stopping systemd unit: {unit} for PID {pid}...")
        subprocess.run(["systemctl", "--user", "stop", unit], stderr=subprocess.DEVNULL)
        time.sleep(0.5)

    try:
        # Also kill process group if it spawned child engines (like llama-router -> llama-server)
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except Exception:
            os.kill(pid, signal.SIGTERM)

        for _ in range(15):
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
            except OSError:
                print(f"[AI Sentinel] Successfully terminated PID {pid}")
                return True

        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            os.kill(pid, signal.SIGKILL)

        print(f"[AI Sentinel] Force killed PID {pid}")
        return True
    except ProcessLookupError:
        return True
    except Exception as e:
        print(f"[AI Sentinel] Error killing PID {pid}: {e}")
        return False

def stop_all():
    print("[AI Sentinel] Stopping all AI servers...")
    services = ["llama-server.service", "ollama.service", "strata.service"]
    for s in services:
        subprocess.run(["systemctl", "--user", "stop", s], stderr=subprocess.DEVNULL)

    process_names = [
        "llama-server",
        "llama-router.py",
        "llama.cpp",
        "ollama",
        "strata",
        "strata-engine",
        "vllm",
        "koboldcpp"
    ]
    for p in process_names:
        subprocess.run(["pkill", "-15", "-f", p], stderr=subprocess.DEVNULL)

    time.sleep(0.8)

    for p in process_names:
        subprocess.run(["pkill", "-9", "-f", p], stderr=subprocess.DEVNULL)

    print("[AI Sentinel] All AI servers stopped and VRAM released.")
    return True

def start_engine(engine_name):
    print(f"[AI Sentinel] Starting engine: {engine_name}...")
    home = os.path.expanduser("~")
    
    # Check custom presets first
    custom_presets = load_custom_presets()
    for cp in custom_presets:
        if cp["id"] == engine_name:
            cmd = cp["cmd"]
            subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True

    if engine_name in ("llama-server", "llama-router", "llama.cpp", "llama"):
        # First check if systemd unit exists
        res = subprocess.run(["systemctl", "--user", "start", "llama-server.service"], stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            print("[AI Sentinel] Started llama-server.service via systemd")
            return True
        router_script = os.path.join(home, ".local/bin/llama-router.py")
        if os.path.exists(router_script):
            subprocess.Popen(["python3", router_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
        else:
            print(f"[AI Sentinel] Error: {router_script} not found")
            return False
    elif engine_name == "ollama":
        cmd = ["ollama", "serve"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    elif engine_name == "strata":
        subprocess.Popen(["bash", "-c", "strata launch"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    else:
        print(f"[AI Sentinel] Unknown engine: {engine_name}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: ai-ctl.py [stop <pid> | stop-all | start <engine> | add-preset <id> <name> <pattern> <cmd> | remove-preset <id>]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "stop" and len(sys.argv) >= 3:
        pid = int(sys.argv[2])
        stop_pid(pid)
    elif cmd in ("stop-all", "free-all", "kill-all"):
        stop_all()
    elif cmd == "start" and len(sys.argv) >= 3:
        engine = sys.argv[2]
        start_engine(engine)
    elif cmd == "add-preset" and len(sys.argv) >= 6:
        preset_id = sys.argv[2]
        name = sys.argv[3]
        pattern = sys.argv[4]
        launch_cmd = sys.argv[5]
        add_preset(preset_id, name, pattern, launch_cmd)
    elif cmd == "remove-preset" and len(sys.argv) >= 3:
        preset_id = sys.argv[2]
        remove_preset(preset_id)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
