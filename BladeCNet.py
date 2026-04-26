#!/usr/bin/env python3
"""
BladeCNet — terminal network dashboard. IP info, devices, bandwidth at a glance.

  cnet                  full network overview (default)
  cnet ip               local + public IP info
  cnet devices          scan LAN for connected devices
  cnet bandwidth        live bandwidth usage per interface
  cnet interfaces       show all network interfaces
  cnet ports            show active listening ports
  cnet watch            live refresh every 2s (Ctrl-C to stop)
  cnet watch <n>        live refresh every n seconds
  cnet update           update to latest version
  cnet uninstall        remove BladeCNet
  cnet help             show all commands
"""

import sys, os, shutil, time, socket, struct, subprocess
import urllib.request, urllib.error, json
from pathlib import Path

VERSION = "1.0.0"
RAW     = "https://raw.githubusercontent.com/FadingBlade/BladeCNet/main/BladeCNet.py"

# ── Colors ────────────────────────────────────────────────────────────────────

class C:
    RST  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
    BRED = "\033[91m"; BGRN = "\033[92m"; BYEL = "\033[93m"
    BBLU = "\033[94m"; BMAG = "\033[95m"; BCYN = "\033[96m"; BWHT = "\033[97m"

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        for attr in [a for a in vars(C) if not a.startswith("_")]:
            setattr(C, attr, "")

# ── Helpers ───────────────────────────────────────────────────────────────────

def cols() -> int:
    return shutil.get_terminal_size((80, 24)).columns

def ruler(char="─"):
    return C.DIM + char * min(cols(), 72) + C.RST

def die(msg: str):
    print(f"\n  {C.BRED}✖ {msg}{C.RST}\n"); sys.exit(1)

def warn(msg: str):
    print(f"  {C.BYEL}⚠ {msg}{C.RST}")

def human(n: float, suffix="B") -> str:
    for unit in ("", "K", "M", "G", "T"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}{suffix}"
        n /= 1024
    return f"{n:.1f} P{suffix}"

def bar(pct: float, width: int = 28) -> str:
    pct   = max(0.0, min(100.0, pct))
    fill  = int(width * pct / 100)
    empty = width - fill
    color = C.BRED if pct >= 85 else C.BYEL if pct >= 60 else C.BGRN
    return f"{color}{'█' * fill}{C.DIM}{'░' * empty}{C.RST}"

def run_cmd(cmd: list, timeout=5) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def _find_self():
    return os.path.abspath(__file__), os.path.dirname(os.path.abspath(__file__))

def require_psutil():
    try:
        import psutil; return psutil
    except ImportError:
        print(f"\n  {C.BYEL}psutil not found — installing...{C.RST}\n")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "psutil",
             "--quiet", "--break-system-packages"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import psutil; return psutil

# ── IP Info ───────────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unavailable"

def get_public_ip_info() -> dict:
    """Query ip-api.com — free, no key needed."""
    try:
        with urllib.request.urlopen("http://ip-api.com/json/?fields=query,isp,org,city,regionName,country,timezone,lat,lon", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}

def get_hostname() -> str:
    try:    return socket.gethostname()
    except: return "unknown"

def get_gateway() -> str:
    if sys.platform == "win32":
        out = run_cmd(["ipconfig"])
        for line in out.splitlines():
            if "Default Gateway" in line and ":" in line:
                gw = line.split(":")[-1].strip()
                if gw and gw != "": return gw
        return "unknown"
    else:
        out = run_cmd(["ip", "route", "show", "default"])
        if out:
            parts = out.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
        out = run_cmd(["route", "-n"])
        for line in out.splitlines():
            if line.startswith("0.0.0.0"):
                parts = line.split()
                if len(parts) >= 2: return parts[1]
        return "unknown"

# ── Interfaces ────────────────────────────────────────────────────────────────

def section_interfaces(ps, verbose=False):
    addrs = ps.net_if_addrs()
    stats = ps.net_if_stats()

    print(f"\n  {C.BOLD}{C.BCYN}Interfaces{C.RST}")
    print(f"  {ruler()}")

    for name, addr_list in addrs.items():
        st    = stats.get(name)
        up    = st.isup if st else False
        speed = f"  {C.DIM}{st.speed} Mbps{C.RST}" if st and st.speed else ""
        status_col = C.BGRN if up else C.DIM
        status_lbl = "UP  " if up else "DOWN"

        ipv4 = next((a.address for a in addr_list if a.family == socket.AF_INET), None)
        ipv6 = next((a.address for a in addr_list
                     if hasattr(socket, "AF_INET6") and a.family == socket.AF_INET6
                     and not a.address.startswith("fe80")), None)
        import psutil as _psutil
        mac  = next((a.address for a in addr_list
                     if hasattr(_psutil, "AF_LINK") and a.family == _psutil.AF_LINK), None)

        print(f"  {status_col}{status_lbl}{C.RST}  {C.BWHT}{name:<16}{C.RST}{speed}")
        if ipv4: print(f"         {C.DIM}IPv4 {C.RST}{ipv4}")
        if ipv6: print(f"         {C.DIM}IPv6 {C.RST}{C.DIM}{ipv6}{C.RST}")
        if mac and verbose: print(f"         {C.DIM}MAC  {mac}{C.RST}")
    print()

# ── IP Section ────────────────────────────────────────────────────────────────

def section_ip(verbose=True):
    local   = get_local_ip()
    host    = get_hostname()
    gateway = get_gateway()

    print(f"\n  {C.BOLD}{C.BCYN}IP Info{C.RST}")
    print(f"  {ruler()}")
    print(f"  {'Hostname':<18} {C.BWHT}{host}{C.RST}")
    print(f"  {'Local IP':<18} {C.BGRN}{local}{C.RST}")
    print(f"  {'Gateway':<18} {C.BYEL}{gateway}{C.RST}")

    if verbose:
        print(f"  {C.DIM}Fetching public IP...{C.RST}", end="\r")
        info = get_public_ip_info()
        if info:
            pub   = info.get("query", "unavailable")
            isp   = info.get("isp", "")
            city  = info.get("city", "")
            region= info.get("regionName", "")
            country=info.get("country", "")
            tz    = info.get("timezone", "")
            loc   = ", ".join(filter(None, [city, region, country]))
            print(f"  {'Public IP':<18} {C.BCYN}{pub}{C.RST}          ")
            if isp:     print(f"  {'ISP':<18} {C.DIM}{isp}{C.RST}")
            if loc:     print(f"  {'Location':<18} {C.DIM}{loc}{C.RST}")
            if tz:      print(f"  {'Timezone':<18} {C.DIM}{tz}{C.RST}")
        else:
            print(f"  {'Public IP':<18} {C.DIM}unavailable (offline?){C.RST}          ")
    print()

# ── Device Scan ───────────────────────────────────────────────────────────────

def get_subnet(local_ip: str) -> str:
    parts = local_ip.rsplit(".", 1)
    return parts[0] + "." if len(parts) == 2 else "192.168.1."

def ping_host(ip: str) -> bool:
    flag = "-n" if sys.platform == "win32" else "-c"
    try:
        r = subprocess.run(
            ["ping", flag, "1", "-W", "1", ip] if sys.platform != "win32"
            else ["ping", flag, "1", "-w", "500", ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        return r.returncode == 0
    except Exception:
        return False

def resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""

def get_mac_for_ip(ip: str) -> str:
    """Read ARP cache — no root needed."""
    if sys.platform == "win32":
        out = run_cmd(["arp", "-a", ip])
        for line in out.splitlines():
            if ip in line:
                parts = line.split()
                for p in parts:
                    if "-" in p and len(p) == 17: return p.upper()
                    if ":" in p and len(p) == 17: return p.upper()
    else:
        # Try /proc/net/arp first (Linux)
        try:
            with open("/proc/net/arp") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if parts and parts[0] == ip and parts[2] != "0x0":
                        return parts[3].upper()
        except Exception:
            pass
        out = run_cmd(["arp", "-n", ip])
        for line in out.splitlines():
            if ip in line:
                for part in line.split():
                    if ":" in part and len(part) == 17:
                        return part.upper()
    return ""

def section_devices():
    local = get_local_ip()
    if local == "unavailable":
        warn("Cannot determine local IP — are you connected?")
        print()
        return

    subnet = get_subnet(local)
    print(f"\n  {C.BOLD}{C.BCYN}Connected Devices{C.RST}  {C.DIM}scanning {subnet}0/24 ...{C.RST}")
    print(f"  {ruler()}")

    import threading
    found = []
    lock  = threading.Lock()

    def probe(i):
        ip = f"{subnet}{i}"
        if ip == local:
            with lock:
                found.append((ip, get_hostname(), get_mac_for_ip(ip), True))
            return
        if ping_host(ip):
            host = resolve_hostname(ip)
            mac  = get_mac_for_ip(ip)
            with lock:
                found.append((ip, host, mac, False))

    threads = [threading.Thread(target=probe, args=(i,), daemon=True)
               for i in range(1, 255)]
    for t in threads: t.start()

    # Show spinner while scanning
    spinner = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    idx = 0
    for t in threads:
        t.join(timeout=3)
        print(f"\r  {C.DIM}{spinner[idx % len(spinner)]} scanning...{C.RST}", end="", flush=True)
        idx += 1

    print(f"\r{' ' * 30}\r", end="")

    found.sort(key=lambda x: [int(p) for p in x[0].split(".")])

    if not found:
        print(f"  {C.DIM}No devices found.{C.RST}\n")
        return

    print(f"  {C.DIM}{'IP':<18} {'Hostname':<28} {'MAC'}{C.RST}")
    print(f"  {ruler('·')}")
    for ip, host, mac, is_self in found:
        self_tag = f" {C.BGRN}← you{C.RST}" if is_self else ""
        h = host if host else C.DIM + "unknown" + C.RST
        m = mac  if mac  else C.DIM + "—" + C.RST
        print(f"  {C.BCYN}{ip:<18}{C.RST} {h:<28} {C.DIM}{m}{C.RST}{self_tag}")

    print(f"\n  {C.DIM}{len(found)} device{'s' if len(found)!=1 else ''} found{C.RST}\n")

# ── Bandwidth ─────────────────────────────────────────────────────────────────

def section_bandwidth(ps, interval=1.0):
    net1 = ps.net_io_counters(pernic=True)
    time.sleep(interval)
    net2 = ps.net_io_counters(pernic=True)

    print(f"\n  {C.BOLD}{C.BCYN}Bandwidth{C.RST}  {C.DIM}(per interface, {interval}s sample){C.RST}")
    print(f"  {ruler()}")
    print(f"  {C.DIM}{'Interface':<16} {'↑ Send':>12}  {'↓ Recv':>12}  {'Total ↑':>12}  {'Total ↓':>12}{C.RST}")
    print(f"  {ruler('·')}")

    active = False
    for nic in net2:
        if nic not in net1: continue
        s1, s2 = net1[nic], net2[nic]
        sent_rate = (s2.bytes_sent - s1.bytes_sent) / interval
        recv_rate = (s2.bytes_recv - s1.bytes_recv) / interval
        if s2.bytes_sent == 0 and s2.bytes_recv == 0: continue
        active = True
        sc = C.BGRN if sent_rate > 0 else C.DIM
        rc = C.BCYN  if recv_rate > 0 else C.DIM
        print(f"  {C.BWHT}{nic:<16}{C.RST} "
              f"{sc}{human(sent_rate, 'B/s'):>12}{C.RST}  "
              f"{rc}{human(recv_rate, 'B/s'):>12}{C.RST}  "
              f"{C.DIM}{human(s2.bytes_sent):>12}  {human(s2.bytes_recv):>12}{C.RST}")

    if not active:
        print(f"  {C.DIM}No active interfaces.{C.RST}")
    print()

# ── Ports ─────────────────────────────────────────────────────────────────────

COMMON_PORTS = {
    20: "FTP-data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 6379: "Redis", 8080: "HTTP-alt", 8443: "HTTPS-alt",
    27017: "MongoDB",
}

def section_ports(ps):
    print(f"\n  {C.BOLD}{C.BCYN}Listening Ports{C.RST}")
    print(f"  {ruler()}")

    try:
        conns = ps.net_connections(kind="inet")
    except (AttributeError, psutil.AccessDenied):
        try:
            conns = ps.net_connections()
        except Exception:
            warn("Cannot read connections — try running as admin/root.")
            print(); return

    listening = sorted(
        {c for c in conns if c.status == "LISTEN"},
        key=lambda c: c.laddr.port if c.laddr else 0
    )

    if not listening:
        print(f"  {C.DIM}No listening ports found.{C.RST}\n"); return

    print(f"  {C.DIM}{'Port':<8} {'Proto':<8} {'Address':<22} {'Service'}{C.RST}")
    print(f"  {ruler('·')}")
    for c in listening:
        port  = c.laddr.port if c.laddr else 0
        addr  = c.laddr.ip   if c.laddr else "*"
        proto = "TCP" if c.type == socket.SOCK_STREAM else "UDP"
        svc   = COMMON_PORTS.get(port, "")
        pc    = C.BYEL if svc else C.BWHT
        print(f"  {pc}{port:<8}{C.RST} {C.DIM}{proto:<8}{addr:<22}{C.RST} {C.BMAG}{svc}{C.RST}")
    print()

# ── Overview ──────────────────────────────────────────────────────────────────

def cmd_default(args):
    ps = require_psutil()
    print()
    print(f"  {C.BOLD}{C.BCYN}BladeCNet{C.RST} {C.DIM}v{VERSION}{C.RST}")
    print(f"  {ruler('═')}")
    section_ip(verbose=True)
    section_bandwidth(ps, interval=0.5)
    print(f"  {C.DIM}run  cnet devices  to scan LAN  |  cnet watch  for live view{C.RST}\n")

def cmd_ip(args):
    section_ip(verbose=True)

def cmd_devices(args):
    section_devices()

def cmd_bandwidth(args):
    ps = require_psutil()
    section_bandwidth(ps, interval=1.0)

def cmd_interfaces(args):
    ps = require_psutil()
    section_interfaces(ps, verbose=True)

def cmd_ports(args):
    ps = require_psutil()
    section_ports(ps)

def cmd_watch(args):
    ps       = require_psutil()
    interval = 2
    if args:
        try: interval = float(args[0])
        except ValueError: pass

    try:
        while True:
            os.system("cls" if sys.platform == "win32" else "clear")
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S")
            print()
            print(f"  {C.BOLD}{C.BCYN}BladeCNet{C.RST} {C.DIM}v{VERSION}  —  {now}  —  every {interval}s  (Ctrl-C to stop){C.RST}")
            print(f"  {ruler('═')}")
            section_ip(verbose=False)
            section_bandwidth(ps, interval=interval * 0.8)
            section_interfaces(ps, verbose=False)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print(f"\n  {C.DIM}Stopped.{C.RST}\n")

def cmd_update(args):
    script, _ = _find_self()
    print(f"\n  {C.DIM}Checking for updates...{C.RST}", flush=True)
    try:
        with urllib.request.urlopen(RAW, timeout=8) as r:
            new_src = r.read()
        new_ver = VERSION
        for line in new_src.decode().splitlines():
            if line.strip().startswith("VERSION"):
                try: new_ver = line.split('"')[1]
                except IndexError: pass
                break
        if new_ver == VERSION:
            print(f"  {C.BGRN}✔ Already up to date{C.RST}  (v{VERSION})\n"); return
        with open(script, "wb") as f:
            f.write(new_src)
        print(f"  {C.BGRN}✔ Updated{C.RST}  v{VERSION} → v{new_ver}\n")
    except Exception as e:
        print(f"  {C.BRED}✖ Update failed:{C.RST} {e}\n")

def cmd_uninstall(args):
    script, folder = _find_self()
    print(f"\n  {C.BYEL}This will remove BladeCNet from your machine.{C.RST}")
    try:
        ans = input("  Are you sure? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {C.DIM}Cancelled.{C.RST}\n"); return
    if ans != "y":
        print(f"  {C.DIM}Cancelled.{C.RST}\n"); return
    removed = []
    try: os.remove(script); removed.append(script)
    except Exception as e: print(f"  {C.DIM}Could not remove {script}: {e}{C.RST}")
    for wrapper in [os.path.join(folder, "cnet"), os.path.join(folder, "cnet.cmd")]:
        if os.path.exists(wrapper):
            try: os.remove(wrapper); removed.append(wrapper)
            except Exception as e: print(f"  {C.DIM}Could not remove {wrapper}: {e}{C.RST}")
    if removed:
        print(f"\n  {C.BGRN}✔ Removed:{C.RST}")
        for f in removed: print(f"    {C.DIM}{f}{C.RST}")
    print(f"\n  {C.DIM}BladeCNet uninstalled. Goodbye.{C.RST}\n")

def cmd_help(args):
    print(f"""
  {C.BOLD}{C.BCYN}BladeCNet{C.RST} {C.DIM}v{VERSION}{C.RST}  — terminal network dashboard

  {C.BOLD}Commands:{C.RST}
    {C.BCYN}cnet{C.RST}                 full network overview
    {C.BCYN}cnet ip{C.RST}              local + public IP info
    {C.BCYN}cnet devices{C.RST}         scan LAN for connected devices
    {C.BCYN}cnet bandwidth{C.RST}       bandwidth usage per interface
    {C.BCYN}cnet interfaces{C.RST}      all network interfaces + status
    {C.BCYN}cnet ports{C.RST}           active listening ports
    {C.BCYN}cnet watch{C.RST}           live refresh every 2s
    {C.BCYN}cnet watch <n>{C.RST}       live refresh every n seconds
    {C.BCYN}cnet update{C.RST}          update to latest version
    {C.BCYN}cnet uninstall{C.RST}       remove BladeCNet
    {C.BCYN}cnet help{C.RST}            show this help

  {C.BOLD}APIs used:{C.RST}
    {C.DIM}socket          hostname, local IP resolution
    psutil          interfaces, bandwidth, connections
    ip-api.com      public IP + ISP + geolocation (free)
    /proc/net/arp   ARP cache for MAC addresses (Linux)
    arp -a          ARP cache for MAC addresses (Windows/macOS)
    ping            LAN device discovery{C.RST}
""")

# ── Main ──────────────────────────────────────────────────────────────────────

DISPATCH = {
    "ip":         cmd_ip,
    "devices":    cmd_devices,
    "bandwidth":  cmd_bandwidth,
    "interfaces": cmd_interfaces,
    "ports":      cmd_ports,
    "watch":      cmd_watch,
    "update":     cmd_update,
    "uninstall":  cmd_uninstall,
    "help":       cmd_help,
}

def main():
    args = sys.argv[1:]
    if not args:
        cmd_default([]); return
    cmd  = args[0].lower()
    rest = args[1:]
    if cmd in DISPATCH:
        DISPATCH[cmd](rest)
    else:
        die(f"Unknown command: '{cmd}' — try cnet help")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.DIM}Bye.{C.RST}")
