#!/usr/bin/env python3
import os
import sys
import re
import time
import signal
import shlex
import subprocess
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

CONFIG_DIR = os.path.expanduser("~/.config/omarchy-ai-sentinel")
CUSTOM_PRESETS_FILE = os.path.join(CONFIG_DIR, "custom_presets.json")

# Core system, window manager, desktop compositor, and user session components
# that must NEVER be killed or signaled under any circumstances.
PROTECTED_COMMS = {
    "systemd", "init", "hyprland", "start-hyprland", "xwayland",
    "quickshell", "omarchy", "bash", "zsh", "sh", "fish",
    "pipewire", "wireplumber", "dbus", "dbus-broker", "dbus-daemon",
    "portal", "xdg-desktop-portal", "xdg-desktop-portal-hyprland",
    "xdg-desktop-portal-gtk", "fcitx5", "gnome-keyring-d", "polkit",
    "polkitd", "antigravity", "electron", "chrome", "firefox", "chromium",
    "alacritty", "kitty", "foot", "ghostty", "wezterm", "steam",
    "discord", "telegram", "spotify", "filmcraft", "obs", "mpv",
    "wayland-session", "uwsm", "owed"
}

FORBIDDEN_SERVICE_KEYWORDS = (
    "wayland", "hyprland", "desktop", "session", "quickshell",
    "user@", "app.slice", "app-", "systemd", "dbus", "xdg",
    "portal", "fcitx", "gnome", "pipewire", "wireplumber",
    "pulseaudio", "polkit", "graphical"
)

ALLOWED_AI_SERVICE_PREFIXES = (
    "llama-server", "llama-router", "ollama", "strata", "voicestudio",
    "voxtype", "vllm", "koboldcpp", "tgi", "text-generation", "lmstudio",
    "localai", "tabbyapi", "aphrodite"
)

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
    preset_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '', preset_id.strip().lower())
    if not preset_id:
        print("[AI Sentinel] Invalid preset ID")
        return False

    name = name.strip()[:64]
    pattern = pattern.strip()[:64]
    if not name or not pattern:
        print("[AI Sentinel] Name and pattern cannot be empty")
        return False

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

def unload_ollama_model(model_tag):
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model": model_tag, "keep_alive": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            print(f"[AI Sentinel] Successfully unloaded Ollama model: {model_tag}")
            return True
    except Exception as e:
        print(f"[AI Sentinel] Note: Ollama model {model_tag} unload request returned: {e}")
        return False

def unload_llama_router():
    try:
        req = urllib.request.Request("http://127.0.0.1:11435/unload", data=b"{}")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            print("[AI Sentinel] Successfully unloaded Llama Router model")
            return True
    except Exception:
        return False

def get_systemd_unit(pid):
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            content = f.read()
        user_pattern = r'(?:^|/)user@\d+\.service/(?:.*/)?([^/\s]+\.service)'
        for line in content.splitlines():
            m = re.search(user_pattern, line)
            if m:
                unit = m.group(1).lower()
                # Reject any system infrastructure, desktop session, compositor, or slice
                if any(k in unit for k in FORBIDDEN_SERVICE_KEYWORDS):
                    continue
                # Require unit to start with a recognized legitimate AI prefix
                if any(unit.startswith(p) for p in ALLOWED_AI_SERVICE_PREFIXES):
                    return m.group(1)
    except Exception:
        pass
    return None

def is_safe_to_kill(pid):
    """
    Strict safety verification to prevent killing desktop session,
    compositor, shell, or core system processes.
    """
    if not isinstance(pid, int) or pid <= 1:
        return False
    if pid in (os.getpid(), os.getppid()):
        return False

    current_uid = os.getuid()
    try:
        stat_info = os.stat(f"/proc/{pid}")
        if stat_info.st_uid != current_uid:
            return False

        with open(f"/proc/{pid}/comm", "r") as f:
            comm = f.read().strip().lower()
        if comm in PROTECTED_COMMS:
            return False

        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read().lower()

        # Reject any critical desktop programs
        for kw in [b"hyprland", b"quickshell", b"antigravity", b"electron", b"uwsm", b"systemd"]:
            if kw in raw:
                return False

        return True
    except Exception:
        return False

def get_direct_children(parent_pid):
    """Safely retrieves only immediate children of a specific process."""
    children = []
    try:
        out = subprocess.check_output(
            ["pgrep", "-P", str(parent_pid)],
            stderr=subprocess.DEVNULL
        ).decode()
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                c_pid = int(line)
                if is_safe_to_kill(c_pid):
                    children.append(c_pid)
    except Exception:
        pass
    return children

def stop_target(target):
    # Case 1: Ollama model tag
    if str(target).startswith("ollama:"):
        model_tag = str(target).split("ollama:", 1)[1]
        return unload_ollama_model(model_tag)

    try:
        pid = int(target)
    except ValueError:
        print(f"[AI Sentinel] Invalid target: {target}")
        return False

    current_uid = os.getuid()
    try:
        stat_info = os.stat(f"/proc/{pid}")
        # Check if process is an Ollama runner running as dedicated ollama user
        if stat_info.st_uid != current_uid:
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", "replace")
                if "ollama" in cmdline:
                    unload_all_ollama_models()
                    return True
            except Exception:
                pass
            print(f"[AI Sentinel] Permission denied: PID {pid} is owned by UID {stat_info.st_uid}")
            return False
    except (FileNotFoundError, ProcessLookupError):
        print(f"[AI Sentinel] Process PID {pid} already terminated")
        return True
    except Exception as e:
        print(f"[AI Sentinel] Error inspecting PID {pid}: {e}")
        return False

    # Safety check: Never kill protected desktop processes
    if not is_safe_to_kill(pid):
        print(f"[AI Sentinel] Safety abort: PID {pid} is a protected system/desktop process!")
        return False

    # Case 2: Systemd managed AI unit (e.g. voicestudio.service, llama-server.service)
    unit = get_systemd_unit(pid)
    if unit:
        check = subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit])
        if check.returncode == 0:
            print(f"[AI Sentinel] Stopping systemd unit cleanly: {unit} for PID {pid}...")
            subprocess.run(["systemctl", "--user", "stop", unit], stderr=subprocess.DEVNULL)
            # Wait for systemd to gracefully terminate the service cgroup
            for _ in range(8):
                time.sleep(0.1)
                chk = subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit])
                if chk.returncode != 0:
                    print(f"[AI Sentinel] Systemd unit {unit} stopped successfully.")
                    return True
            # Systemd handles cleanup; never fall through to dangerous killpg
            return True

    # Case 3: Check if PID is llama-router, trigger /unload first
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", "replace")
        if "llama-router" in cmdline:
            unload_llama_router()
    except Exception:
        pass

    # Case 4: Standalone user AI process
    # NEVER use os.killpg() — target only this exact PID and verified direct children
    children = get_direct_children(pid)

    try:
        os.kill(pid, signal.SIGTERM)
        for c in children:
            try:
                os.kill(c, signal.SIGTERM)
            except OSError:
                pass

        # Polling check loop for clean exit
        for _ in range(8):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except OSError:
                print(f"[AI Sentinel] Gracefully terminated PID {pid}")
                return True

        # Force kill only as last resort, strictly targeting this PID and direct children
        if is_safe_to_kill(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        for c in children:
            if is_safe_to_kill(c):
                try:
                    os.kill(c, signal.SIGKILL)
                except OSError:
                    pass

        print(f"[AI Sentinel] Force terminated PID {pid}")
        return True
    except ProcessLookupError:
        return True
    except PermissionError:
        print(f"[AI Sentinel] Permission denied terminating PID {pid}")
        return False
    except Exception as e:
        print(f"[AI Sentinel] Error terminating PID {pid}: {e}")
        return False

def unload_all_ollama_models():
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/ps")
        with urllib.request.urlopen(req, timeout=0.3) as resp:
            data = json.loads(resp.read().decode())
            for m in data.get("models", []):
                tag = m.get("name") or m.get("model")
                if tag:
                    unload_ollama_model(tag)
    except Exception:
        pass

def stop_all():
    print("[AI Sentinel] Liberating VRAM & Stopping all AI servers safely...")

    # 1. Unload all Ollama models and router models cleanly via API
    unload_all_ollama_models()
    unload_llama_router()

    # 2. Stop legitimate user AI systemd services
    allowed_services = ["llama-server.service", "voicestudio.service", "strata.service", "voxtype.service"]
    for s in allowed_services:
        check = subprocess.run(["systemctl", "--user", "is-active", "--quiet", s])
        if check.returncode == 0:
            print(f"[AI Sentinel] Stopping systemd service: {s}")
            subprocess.run(["systemctl", "--user", "stop", s], stderr=subprocess.DEVNULL)

    # 3. Target ONLY verified standalone AI binary names (exact name match, never loose substring)
    current_uid = os.getuid()
    target_binaries = ["llama-server", "llama-cli", "strata-engine", "vllm", "koboldcpp"]
    
    candidates = []
    for tb in target_binaries:
        try:
            out = subprocess.check_output(
                ["pgrep", "-u", str(current_uid), "-x", tb],
                stderr=subprocess.DEVNULL
            ).decode()
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    p = int(line)
                    if is_safe_to_kill(p):
                        candidates.append(p)
        except Exception:
            pass

    for p in candidates:
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass

    if candidates:
        time.sleep(0.3)
        for p in candidates:
            try:
                os.kill(p, 0)
                if is_safe_to_kill(p):
                    os.kill(p, signal.SIGKILL)
            except OSError:
                pass

    print("[AI Sentinel] All AI servers stopped and VRAM liberated safely.")
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

def copy_to_clipboard(text):
    try:
        p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return True
    except Exception as e:
        print(f"[AI Sentinel] wl-copy error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: ai-ctl.py [stop <target> | stop-all | start <engine> | add-preset <id> <name> <pattern> <cmd> | remove-preset <id> | copy <text>]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "stop" and len(sys.argv) >= 3:
        stop_target(sys.argv[2])
    elif cmd in ("stop-all", "free-all", "kill-all", "release-all"):
        stop_all()
    elif cmd == "start" and len(sys.argv) >= 3:
        start_engine(sys.argv[2])
    elif cmd == "add-preset" and len(sys.argv) >= 6:
        preset_id = sys.argv[2]
        name = sys.argv[3]
        pattern = sys.argv[4]
        launch_cmd = sys.argv[5]
        add_preset(preset_id, name, pattern, launch_cmd)
    elif cmd == "remove-preset" and len(sys.argv) >= 3:
        preset_id = sys.argv[2]
        remove_preset(preset_id)
    elif cmd == "copy" and len(sys.argv) >= 3:
        copy_to_clipboard(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
