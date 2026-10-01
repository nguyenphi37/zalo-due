import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from due_core import (
    DueCore,
    DueError,
    image_path,
    is_reparse,
    iter_processes,
    link_junction,
    pid_alive,
    safe_rmtree,
    taskkill,
)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def test_processes() -> None:
    pids = [pid for pid, _parent, _name in iter_processes()]
    check("list processes", os.getpid() in pids, f"count {len(pids)}")
    image = image_path(os.getpid()) or ""
    check("read process path", image.lower().endswith("python.exe"), image)


def test_guard() -> None:
    try:
        safe_rmtree(Path("C:/no-such-due-guard"))
    except DueError:
        check("refuse delete outside Due", True)
        return
    check("refuse delete outside Due", False)


def test_junction_delete() -> None:
    base = Path(tempfile.mkdtemp(prefix="due-safe-"))
    link = base / "profile" / "Local" / "Programs" / "Zalo"
    real = base / "real"
    try:
        real.mkdir()
        (real / "secret.txt").write_text("keep", encoding="utf-8")
        link_junction(link, real, create_target=False)
        check("create junction", is_reparse(link), str(link))
        (base / "profile" / "Roaming").mkdir()
        (base / "profile" / "Roaming" / "note.txt").write_text("x", encoding="utf-8")
        safe_rmtree(base / "profile")
        secret = (real / "secret.txt").read_text(encoding="utf-8")
        check("junction delete keeps target", secret == "keep" and not (base / "profile").exists())
    finally:
        if is_reparse(link):
            os.rmdir(link)
        shutil.rmtree(base, ignore_errors=True)


def test_profiles(arch: str) -> None:
    core = DueCore()
    core.stage_binaries()
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    profiles = [core.profile_path(item, bucket="selftest") for item in ids]
    pids = []
    try:
        probe = core.bin / arch / "DueProbe.exe"
        check(f"{arch} probe exists", probe.is_file(), str(probe))
        for profile in profiles:
            if profile.exists():
                safe_rmtree(profile)
            pid = core.launch_program(profile, probe, ["--mutex", "--hold", "6000"], bucket="selftest")
            pids.append(pid)
        deadline = time.time() + 10
        texts = {}
        while time.time() < deadline and len(texts) < 2:
            for profile in profiles:
                file = profile / "probe.txt"
                if file.exists() and profile not in texts:
                    texts[profile] = file.read_text(encoding="utf-8")
            time.sleep(0.1)
        check("both probes wrote results", len(texts) == 2, str(list(texts)))
        for profile, text in texts.items():
            roaming = str(profile / "Roaming")
            local = str(profile / "Local")
            lines = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
            check(
                f"roaming {profile.name[:8]}",
                os.path.normcase(lines.get("SH_ROAMING", "")) == os.path.normcase(roaming),
                lines.get("SH_ROAMING", ""),
            )
            check(
                f"local {profile.name[:8]}",
                os.path.normcase(lines.get("SH_LOCAL", "")) == os.path.normcase(local),
                lines.get("SH_LOCAL", ""),
            )
            check(
                f"csidl {profile.name[:8]}",
                os.path.normcase(lines.get("CSIDL_APPDATA", "")) == os.path.normcase(roaming),
                lines.get("CSIDL_APPDATA", ""),
            )
            check(f"mutex {profile.name[:8]}", lines.get("MUTEX") == "OK", lines.get("MUTEX", ""))
            check(f"alive {profile.name[:8]}", pid_alive(pids[profiles.index(profile)]))
    finally:
        for pid in pids:
            if pid_alive(pid):
                taskkill(pid)
        for profile in profiles:
            if profile.exists():
                safe_rmtree(profile)


if __name__ == "__main__":
    test_processes()
    test_guard()
    test_junction_delete()
    test_profiles("x64")
    test_profiles("x86")
    print("ALL_PASS")
