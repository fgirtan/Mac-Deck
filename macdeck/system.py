"""Interacțiunea cu macOS: volum, luminozitate, comenzi. Pe alte sisteme rulează simulat."""
import ctypes
import os
import platform
import subprocess
import threading

IS_MAC = platform.system() == "Darwin"
SIM = (not IS_MAC) or os.environ.get("MACDECK_SIM") == "1"

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")

_sim = {"volume": 50, "muted": False, "brightness": 70}
_lock = threading.Lock()


def log_sim(*parts):
    print("  [simulat] " + " ".join(str(p) for p in parts))


def run(cmd, timeout=10, check=True):
    """Rulează o comandă. În modul simulat doar o afișează."""
    if SIM:
        log_sim(*cmd)
        return ""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or "comanda a eșuat: %s" % cmd[0])
    return r.stdout.strip()


def osa(*lines, timeout=10):
    args = ["osascript"]
    for line in lines:
        args += ["-e", line]
    return run(args, timeout=timeout)


def osa_file(name, *argv, timeout=15):
    return run(["osascript", os.path.join(SCRIPTS, name)] + [str(a) for a in argv], timeout=timeout)


# ------------------------------------------------------------------ volum

def get_volume():
    if SIM:
        return {"volume": _sim["volume"], "muted": _sim["muted"]}
    out = osa("set s to get volume settings",
              'return (output volume of s as text) & "," & (output muted of s as text)')
    vol, muted = out.split(",")
    if vol == "missing value":
        return {"volume": None, "muted": False}
    return {"volume": int(vol), "muted": muted == "true"}


def set_volume(v):
    v = max(0, min(100, int(round(float(v)))))
    with _lock:
        if SIM:
            _sim.update(volume=v, muted=False)
            return
        osa("set volume output volume %d without output muted" % v)


def toggle_mute():
    with _lock:
        if SIM:
            _sim["muted"] = not _sim["muted"]
            return
        osa("set volume output muted not (output muted of (get volume settings))")


# ------------------------------------------------------------------ luminozitate
# Ecranul intern al MacBook-ului, prin framework-ul privat DisplayServices
# (funcționează pe Apple Silicon și pe Intel recente).

_ds = None
_display_id = None


def _display_services():
    global _ds, _display_id
    if _ds is None:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGMainDisplayID.restype = ctypes.c_uint32
        ds = ctypes.CDLL("/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices")
        ds.DisplayServicesGetBrightness.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
        ds.DisplayServicesGetBrightness.restype = ctypes.c_int
        ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
        ds.DisplayServicesSetBrightness.restype = ctypes.c_int
        _ds, _display_id = ds, cg.CGMainDisplayID()
    return _ds, _display_id


def get_brightness():
    if SIM:
        return _sim["brightness"]
    try:
        ds, did = _display_services()
        f = ctypes.c_float()
        if ds.DisplayServicesGetBrightness(did, ctypes.byref(f)) != 0:
            return None  # ex. capac închis, doar monitor extern
        return int(round(f.value * 100))
    except OSError:
        return None


def set_brightness(v):
    v = max(0, min(100, int(round(float(v)))))
    if SIM:
        _sim["brightness"] = v
        return
    ds, did = _display_services()
    if ds.DisplayServicesSetBrightness(did, ctypes.c_float(max(v, 1) / 100.0)) != 0:
        raise RuntimeError("luminozitatea nu poate fi schimbată pe ecranul curent")


# ------------------------------------------------------------------ rețea

def hostname_local():
    if IS_MAC:
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"],
                                  capture_output=True, text=True).stdout.strip()
            if name:
                return name + ".local"
        except OSError:
            pass
    return platform.node().split(".")[0] + ".local"


def local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"
