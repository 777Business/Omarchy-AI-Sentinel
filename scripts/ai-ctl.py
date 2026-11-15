#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess
import json

def get_systemd_unit(pid):
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
            if "systemd" in content and ".service" in content:
                for part in content.split("/"):
                    if part.endswith(".service"):
                        return part.strip()
    except Exception:
        pass
    return None

def stop_pid(pid):
    unit = get_systemd_unit(pid)
    if unit:
        print(f"[AI Sentinel] Stopping systemd unit: {unit} for PID {pid}...")
        subprocess.run(["systemctl", "--user", "stop", unit], stderr=subprocess.DEVNULL)
        time.sleep(1)

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(15):
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
            except OSError:
                print(f"[AI Sentinel] Successfully terminated PID {pid}")
                return True
        # Force kill if still alive
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
    # 1. Stop any known systemd AI services
    services = ["llama-server.service", "ollama.service", "strata.service"]
    for s in services:
        subprocess.run(["systemctl", "--user", "stop", s], stderr=subprocess.DEVNULL)

    # 2. Kill by process names
    process_names = [
        "llama-server",
        "llama-router.py",
        "ollama",
        "strata",
        "strata-engine",
        "vllm"
    ]
    for p in process_names:
        subprocess.run(["pkill", "-15", "-f", p], stderr=subprocess.DEVNULL)

    time.sleep(1)

    for p in process_names:
        subprocess.run(["pkill", "-9", "-f", p], stderr=subprocess.DEVNULL)

    print("[AI Sentinel] All AI servers stopped and VRAM released.")
    return True

def start_engine(engine_name):
    print(f"[AI Sentinel] Starting engine: {engine_name}...")
    home = os.path.expanduser("~")
    if engine_name == "ollama":
        cmd = ["ollama", "serve"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    elif engine_name == "llama-router":
        router_script = os.path.join(home, ".local/bin/llama-router.py")
        if os.path.exists(router_script):
            subprocess.Popen(["python3", router_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
        else:
            print(f"[AI Sentinel] Error: {router_script} not found")
            return False
    elif engine_name == "strata":
        # Launch strata via bash
        subprocess.Popen(["bash", "-c", "strata launch"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    else:
        print(f"[AI Sentinel] Unknown engine: {engine_name}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: ai-ctl.py [stop <pid> | stop-all | start <engine>]")
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
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
