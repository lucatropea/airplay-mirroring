from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_ID = "leapbtw.uxplay"
EXE_NAMES = ("uxplay-windows.exe", "UxPlay-Windows.exe", "uxplay.exe")
PROGRAM_DIRS = ("uxplay-windows", "UxPlay-Windows", "Programs/uxplay-windows")


def ensure_uxplay() -> Path:
    found = locate_executable()
    if found is not None:
        return found
    print("Installing AirPlay receiver (uxplay-windows, ~90 MB)...")
    print("Windows may ask for administrator approval (Bonjour service).")
    if install_via_winget() != 0:
        raise SystemExit(
            "Installation failed. Try in PowerShell:\n"
            f"  winget install --id {PACKAGE_ID} -e"
        )
    found = locate_executable()
    if found is None:
        raise SystemExit(
            "Installation finished but the executable was not found. "
            "Launch uxplay-windows from the Start menu and try again."
        )
    return found


def launch_uxplay(exe: Path) -> int:
    print("AirPlay receiver running.")
    print("On iPad: Control Center → Screen Mirroring → select this PC.")
    print("Quit uxplay-windows (window or tray icon) to stop.")
    try:
        completed = subprocess.run([str(exe)], cwd=str(exe.parent))
        return int(completed.returncode or 0)
    except OSError as exc:
        raise SystemExit(f"Could not start {exe.name}: {exc}") from exc


def locate_executable() -> Path | None:
    for name in EXE_NAMES:
        on_path = shutil.which(name)
        if on_path:
            return Path(on_path).resolve()

    for root in install_roots():
        if not root.is_dir():
            continue
        for name in EXE_NAMES:
            direct = root / name
            if direct.is_file():
                return direct.resolve()
            try:
                for match in root.rglob(name):
                    if match.is_file() and "uninstall" not in match.name.lower():
                        return match.resolve()
            except OSError:
                continue
    return None


def install_roots() -> list[Path]:
    env = os.environ
    bases = [env.get("ProgramFiles"), env.get("ProgramFiles(x86)"), env.get("LocalAppData")]
    roots: list[Path] = []
    for value in bases:
        if not value:
            continue
        base = Path(value)
        for folder in PROGRAM_DIRS:
            roots.append(base / folder.replace("/", os.sep))
    return roots


def install_via_winget() -> int:
    winget = shutil.which("winget")
    if winget is None:
        print("winget is not available.", file=sys.stderr)
        return 1
    return subprocess.call(
        [
            winget,
            "install",
            "--id",
            PACKAGE_ID,
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )
