"""Datele pentru pagina Activity Monitor: CPU, memorie, rețea, disc, baterie, GPU, top procese.
Colectorul pornește la prima cerere și se oprește singur după 15 s fără cereri."""
import collections
import math
import os
import random
import re
import signal
import subprocess
import threading
import time

from .system import SIM

HISTORY = 60
SUDOERS_HINT = ('Pentru GPU și temperatură rulează o dată în Terminal:\n'
                'echo "$USER ALL=(root) NOPASSWD: /usr/bin/powermetrics" | sudo tee /etc/sudoers.d/macdeck')


def _sh(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.hist = {k: collections.deque(maxlen=HISTORY) for k in ("cpu", "mem", "net_in", "net_out", "disk", "gpu")}
        self.now = {}
        self.top = {"cpu": [], "mem": []}
        self.last_request = 0
        self.thread = None
        self.iostat = None
        self.pm = None
        self.pm_state = {}
        self._net_prev = None
        self._tick = 0

    # ---------------------------------------------------------------- API
    def snapshot(self):
        self.last_request = time.time()
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        with self.lock:
            return {"now": dict(self.now), "hist": {k: list(v) for k, v in self.hist.items()},
                    "top": dict(self.top)}

    def kill(self, pid):
        pid = int(pid)
        if SIM:
            return "Proces %d închis (simulat)" % pid
        user = _sh(["ps", "-o", "user=", "-p", str(pid)]).strip()
        if not user:
            raise RuntimeError("procesul nu mai există")
        if pid < 200 or user != os.environ.get("USER", user) or user == "root":
            raise RuntimeError("procesele de sistem nu pot fi închise din deck")
        os.kill(pid, signal.SIGTERM)
        return "Proces închis"

    # ---------------------------------------------------------------- colectare
    def _loop(self):
        if not SIM:
            self._start_streams()
        try:
            while time.time() - self.last_request < 15:
                t0 = time.time()
                try:
                    self._sample()
                except Exception as e:
                    print("  ! monitor: %s" % e)
                time.sleep(max(0.2, 1.0 - (time.time() - t0)))
        finally:
            for p in (self.iostat, self.pm):
                if p:
                    p.terminate()
            self.iostat = self.pm = None

    def _start_streams(self):
        self.iostat = subprocess.Popen(["iostat", "-w", "1", "-K"], stdout=subprocess.PIPE, text=True, bufsize=1)
        threading.Thread(target=self._read_iostat, args=(self.iostat,), daemon=True).start()
        # GPU + presiune termică: doar dacă există regula sudoers (fără parolă)
        if subprocess.run(["sudo", "-n", "/usr/bin/powermetrics", "-h"], capture_output=True).returncode == 0:
            self.pm = subprocess.Popen(["sudo", "-n", "/usr/bin/powermetrics", "--samplers", "gpu_power,thermal",
                                        "-i", "2000"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, bufsize=1)
            threading.Thread(target=self._read_pm, args=(self.pm,), daemon=True).start()
        else:
            self.pm_state = {"gpu_hint": SUDOERS_HINT}

    def _read_iostat(self, p):
        header = None
        for line in p.stdout:
            parts = line.split()
            if not parts:
                continue
            if "us" in parts and "sy" in parts:
                header = parts
                continue
            if header is None or not re.match(r"^[\d.]+$", parts[0]):
                continue
            try:
                vals = [float(x) for x in parts]
            except ValueError:
                continue
            # coloanele: [KB/t tps MB/s] x discuri, apoi us sy id, apoi 1m 5m 15m
            us_i = header.index("us")
            n_disk_cols = len(vals) - (len(header) - us_i)
            mbs = sum(vals[i] for i in range(2, n_disk_cols, 3))
            off = n_disk_cols
            cpu = vals[off] + vals[off + 1]
            with self.lock:
                self.now["cpu"] = round(cpu, 1)
                self.now["cpu_user"] = vals[off]
                self.now["cpu_sys"] = vals[off + 1]
                self.now["disk"] = round(mbs, 2)

    def _read_pm(self, p):
        for line in p.stdout:
            m = re.search(r"GPU (?:HW )?active residency:\s+([\d.]+)%", line)
            if m:
                self.pm_state["gpu"] = float(m.group(1))
            m = re.search(r"Current pressure level:\s+(\w+)", line)
            if m:
                self.pm_state["thermal"] = m.group(1)

    def _sample(self):
        self._tick += 1
        if SIM:
            return self._sample_sim()
        now = {}
        # memorie
        vm = _sh(["vm_stat"])
        page = int((re.search(r"page size of (\d+)", vm) or [0, 16384])[1])
        pages = {k: int(v) for k, v in re.findall(r'^"?(.+?)"?:\s+(\d+)\.', vm, re.M)}
        total = int(_sh(["sysctl", "-n", "hw.memsize"]).strip() or 0)
        used = (pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
                + pages.get("Pages occupied by compressor", 0)) * page
        if total:
            now["mem_total_gb"] = round(total / 2 ** 30, 1)
            now["mem_used_gb"] = round(used / 2 ** 30, 1)
            now["mem"] = round(100.0 * used / total, 1)
        lvl = _sh(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]).strip()
        now["pressure"] = {"1": "normal", "2": "atenție", "4": "critic"}.get(lvl, "normal")
        sw = re.search(r"used = ([\d.]+)M", _sh(["sysctl", "-n", "vm.swapusage"]))
        now["swap_gb"] = round(float(sw.group(1)) / 1024, 2) if sw else 0
        # rețea
        ib = ob = 0
        for line in _sh(["netstat", "-ibn"]).splitlines()[1:]:
            c = line.split()
            # doar interfețele fizice (Wi-Fi / Ethernet), rândul <Link#> (cu adresa MAC)
            if len(c) >= 11 and c[2].startswith("<Link#") and c[0].startswith("en"):
                try:
                    ib += int(c[6]); ob += int(c[9])
                except ValueError:
                    pass
        t = time.time()
        if self._net_prev:
            dt = max(0.1, t - self._net_prev[2])
            now["net_in"] = max(0, (ib - self._net_prev[0]) / dt / 1024)
            now["net_out"] = max(0, (ob - self._net_prev[1]) / dt / 1024)
        self._net_prev = (ib, ob, t)
        # baterie (o dată la 10 s)
        if self._tick % 10 == 1:
            b = _sh(["pmset", "-g", "batt"])
            m = re.search(r"(\d+)%;\s*([^;]+);\s*([^\s]+)?", b)
            if m:
                self.now["battery"] = int(m.group(1))
                self.now["battery_state"] = m.group(2).strip()
                self.now["battery_left"] = (m.group(3) or "").strip() if m.group(3) and ":" in m.group(3) else ""
                self.now["on_ac"] = "AC Power" in b
        # top procese (o dată la 3 s)
        if self._tick % 3 == 1:
            self.top = {"cpu": self._ps("-r"), "mem": self._ps("-m")}
        with self.lock:
            self.now.update(now)
            self.now.update({k: v for k, v in self.pm_state.items()})
            self._push_hist()

    def _ps(self, order):
        rows = []
        out = _sh(["ps", "-Aceo", "pid=,pcpu=,rss=,user=,comm=", order])
        me = os.environ.get("USER", "")
        for line in out.splitlines()[:6]:
            c = line.split(None, 4)
            if len(c) == 5:
                rows.append({"pid": int(c[0]), "cpu": float(c[1]), "mem_mb": round(int(c[2]) / 1024),
                             "name": c[4], "mine": c[3] == me})
        return rows[:5]

    def _push_hist(self):
        for k in self.hist:
            v = self.now.get(k)
            if v is not None:
                self.hist[k].append(round(v, 2))

    def _sample_sim(self):
        t = self._tick
        with self.lock:
            self.now.update({
                "cpu": round(25 + 20 * math.sin(t / 5) + random.random() * 10, 1), "cpu_user": 20, "cpu_sys": 8,
                "mem": 62 + random.random() * 3, "mem_used_gb": 10.1, "mem_total_gb": 16, "pressure": "normal",
                "swap_gb": 0.3, "net_in": abs(400 * math.sin(t / 3)), "net_out": abs(60 * math.cos(t / 4)),
                "disk": abs(12 * math.sin(t / 7)), "battery": 84, "battery_state": "discharging",
                "battery_left": "5:12", "on_ac": False, "gpu": 12 + random.random() * 6, "thermal": "Nominal",
            })
            self.top = {"cpu": [{"pid": 501, "cpu": 38.2, "mem_mb": 820, "name": "Google Chrome Helper", "mine": True},
                                {"pid": 612, "cpu": 21.0, "mem_mb": 1400, "name": "Screaming Frog SEO Spider", "mine": True},
                                {"pid": 88, "cpu": 6.1, "mem_mb": 90, "name": "WindowServer", "mine": False},
                                {"pid": 733, "cpu": 4.0, "mem_mb": 510, "name": "Slack", "mine": True},
                                {"pid": 810, "cpu": 2.2, "mem_mb": 300, "name": "Claude", "mine": True}],
                        "mem": [{"pid": 612, "cpu": 21.0, "mem_mb": 1400, "name": "Screaming Frog SEO Spider", "mine": True},
                                {"pid": 501, "cpu": 38.2, "mem_mb": 820, "name": "Google Chrome Helper", "mine": True}]}
            self._push_hist()


MONITOR = Monitor()
