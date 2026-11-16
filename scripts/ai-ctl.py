#!/usr/bin/env python3
import os
import sys
import re
import time
import signal
import shlex
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
    # Sanitize preset_id to safe alphanumeric characters, dashes, dots, and underscores
    preset_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '', preset_id.strip().lower())
    if not preset_id:
        print("[AI Sentinel] Invalid preset ID")
        return False

    name = name.strip()[:64]
    pattern = pattern.strip()[:64]
    if not name or not pattern:
        print("[AI Sentinel] Name and pattern cannot be empty")
        return False

    # Validate that cmd can be cleanly parsed into an argument vector
    try:
        argv = shlex.split(cmd)
        if not argv:
            print("[AI Sentinel] Invalid empty command")
            return False
        clean_cmd = shlex.join(argv)
    except ValueError as e:
        print(f"[AI Sentinel] Malformed command syntax: {e}")
        return False

    presets = load_custom_presets()
    for p in presets:
        if p["id"] == preset_id:
            p["name"] = name
            p["pattern"] = pattern
            p["cmd"] = clean_cmd
            save_custom_presets(presets)
            print(f"[AI Sentinel] Updated preset: {name}")
            return True
    presets.append({
        "id": preset_id,
        "name": name,
        "pattern": pattern,
        "cmd": clean_cmd
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
        uid = os.getuid()
        if os.stat(f"/proc/{pid}").st_uid != uid:
            return None
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
        user_pattern = rf'(?:^|/)user@{uid}\.service/(?:.*/)?([^/\s]+\.service)'
        for line in content.splitlines():
            m = re.search(user_pattern, line)
            if m:
                unit = m.group(1)
                if re.match(r'^[a-zA-Z0-9_\-\.\@]+\.service$', unit) and not unit.startswith("user@"):
                    return unit
    except Exception:
        pass
    return None

def stop_pid(pid):
    uid = os.getuid()
    try:
        stat_info = os.stat(f"/proc/{pid}")
        if stat_info.st_uid != uid:
            print(f"[AI Sentinel] Permission denied: PID {pid} is owned by UID {stat_info.st_uid}, not current UID {uid}")
            return False
    except (FileNotFoundError, ProcessLookupError):
        print(f"[AI Sentinel] Process PID {pid} already terminated")
        return True
    except Exception as e:
        print(f"[AI Sentinel] Error inspecting PID {pid}: {e}")
        return False

    unit = get_systemd_unit(pid)
    if unit:
        # Verify unit is actually an active user unit before stopping
        check = subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit])
        if check.returncode == 0:
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
    except PermissionError:
        print(f"[AI Sentinel] Permission denied killing PID {pid}")
        return False
    except Exception as e:
        print(f"[AI Sentinel] Error killing PID {pid}: {e}")
        return False

def stop_all():
    print("[AI Sentinel] Stopping all AI servers...")
    services = ["llama-server.service", "ollama.service", "strata.service", "voicestudio.service", "voxtype.service"]
    for s in services:
        subprocess.run(["systemctl", "--user", "stop", s], stderr=subprocess.DEVNULL)

    current_uid = str(os.getuid())
    process_names = [
        "llama-server",
        "llama-router.py",
        "llama.cpp",
        "dsh",
        "ollama",
        "strata",
        "strata-engine",
        "vllm",
        "koboldcpp",
        "voxtype"
    ]
    for p in process_names:
        subprocess.run(["pkill", "-u", current_uid, "-15", "-f", p], stderr=subprocess.DEVNULL)

    time.sleep(0.8)

    for p in process_names:
        subprocess.run(["pkill", "-u", current_uid, "-9", "-f", p], stderr=subprocess.DEVNULL)

    print("[AI Sentinel] All AI servers stopped and VRAM released.")
    return True

def run_command_safely(cmd_str):
    try:
        argv = [os.path.expanduser(a) for a in shlex.split(cmd_str)]
        if not argv:
            return False
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception as e:
        print(f"[AI Sentinel] Failed to launch '{cmd_str}': {e}")
        return False

def start_engine(engine_name):
    print(f"[AI Sentinel] Starting engine: {engine_name}...")
    
    # Check custom presets first
    custom_presets = load_custom_presets()
    for cp in custom_presets:
        if cp["id"] == engine_name:
            cmd = cp["cmd"]
            if run_command_safely(cmd):
                print(f"[AI Sentinel] Launched custom preset: {cp['name']}")
                return True
            return False

    builtin_commands = {
        "llama-server": "systemctl --user start llama-server.service",
        "llama-router": "systemctl --user start llama-server.service",
        "dsh": "dsh web",
        "ollama": "ollama serve",
        "strata": "strata launch",
        "voicestudio": "systemctl --user start voicestudio.service",
        "voxtype": "systemctl --user start voxtype.service",
        "vllm": "vllm serve",
        "koboldcpp": "koboldcpp"
    }

    if engine_name in builtin_commands:
        cmd = builtin_commands[engine_name]
        if run_command_safely(cmd):
            print(f"[AI Sentinel] Launched {engine_name} via: {cmd}")
            return True
        return False

    print(f"[AI Sentinel] Unknown engine: {engine_name}")
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: ai-ctl.py [stop <pid> | stop-all | start <engine> | add-preset <id> <name> <pattern> <cmd> | remove-preset <id>]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "stop" and len(sys.argv) >= 3:
        try:
            pid = int(sys.argv[2])
            stop_pid(pid)
        except ValueError:
            print(f"[AI Sentinel] Invalid PID: {sys.argv[2]}")
            sys.exit(1)
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
