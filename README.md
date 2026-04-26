# BladeCNet
Local terminal network dashboard.
## Install
**Linux / macOS:**
```sh
curl -fsSL https://raw.githubusercontent.com/FadingBlade/BladeCNet/main/install.sh | sh
```
**Windows PowerShell:**
```powershell
irm https://raw.githubusercontent.com/FadingBlade/BladeCNet/main/install.ps1 | iex
```
The installer detects your OS and installs Python and psutil if needed and adds the `cnet` command to your PATH.

---

## Commands
```
cnet                   full network overview
cnet ip                local + public IP, ISP, location
cnet devices           scan LAN for connected devices
cnet bandwidth         live bandwidth usage per interface
cnet interfaces        all network interfaces + status
cnet ports             active listening ports + services
cnet watch             live refresh every 2s (Ctrl-C to stop)
cnet watch <n>         live refresh every n seconds
cnet update            update to latest version
cnet uninstall         remove BladeCNet
cnet help              show all commands
cnet                   show all commands
```

---

## Requirements
- Python 3.7+ (installer handles this)
- psutil (installer handles this)
- Same network as devices you want to scan

---

## Notes
`cnet devices` pings the full /24 subnet and reads the ARP cache — no root needed on most systems, but running as admin/sudo gives better MAC address results.

`cnet ports` may require admin/sudo on Windows and macOS to see all connections.

Public IP info is fetched from [ip-api.com](http://ip-api.com) — free, no API key needed.

---

## Uninstall
**Linux / macOS:** `rm ~/.local/bin/cnet ~/.local/bin/BladeCNet.py`

**Windows:** Delete `%USERPROFILE%\.BladeCNet` and remove it from PATH in System Settings.

(Or just run `cnet uninstall`)
