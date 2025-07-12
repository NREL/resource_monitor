"""Tests the resource monitor CLI commands"""

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import psutil


def test_resource_monitor_sync(tmp_path):
    """Test the monitor in sync mode."""
    my_pid = os.getpid()
    subprocess.run(
        [
            "rmon",
            "collect",
            "--cpu",
            "--disk",
            "--memory",
            "--network",
            "-i1",
            "-d5",
            "-o",
            str(tmp_path),
            "--plots",
            str(my_pid),
        ],
        check=True,
    )
    _check_files(tmp_path)


def test_resource_monitor_sync_daemon(tmp_path):
    """Test the monitor in sync mode as a daemon."""
    my_pid = os.getpid()
    subprocess.run(
        [
            "rmon",
            "collect",
            "--cpu",
            "--disk",
            "--memory",
            "--network",
            "-i1",
            "-o",
            str(tmp_path),
            "--plots",
            str(my_pid),
            "--daemon",
        ],
        check=True,
    )
    pid: int | None = None
    for _ in range(100):
        pid = _find_rmon_collect_pid()
        if pid is not None:
            break
        time.sleep(0.1)

    assert pid is not None
    time.sleep(2)
    os.kill(pid, signal.SIGTERM)

    for _ in range(100):
        pid = _find_rmon_collect_pid()
        if pid is None:
            break
        time.sleep(0.1)
    assert pid is None

    _check_files(tmp_path)


def test_resource_monitor_process(tmp_path):
    """Test the monitor-process command."""
    cmd = [
        "rmon",
        "monitor-process",
        "-i1",
        "-o",
        str(tmp_path),
        "--plots",
        "python",
        "-c",
        "import time;time.sleep(3)",
    ]
    subprocess.run(cmd, check=True)
    hostname = socket.gethostname()
    assert (tmp_path / f"{hostname}.sqlite").exists()
    assert (tmp_path / f"{hostname}_results.json").exists()
    assert (tmp_path / "html" / f"{hostname}_process.html").exists()


def test_resource_monitor_async(tmp_path):
    """Test the monitor in async mode."""
    my_pid = os.getpid()
    cmd = [
        "rmon",
        "collect",
        "--cpu",
        "--disk",
        "--memory",
        "--network",
        "-i1",
        "-o",
        str(tmp_path),
        "--plots",
        "-I",
        str(my_pid),
    ]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True) as pipe:
        time.sleep(2)
        assert pipe.stdin is not None
        pipe.stdin.write("p\n")
        # Disable process ponitoring.
        pipe.stdin.write("\n")

        # Change resource types.
        pipe.stdin.write("r\n")
        pipe.stdin.write("cpu memory\n")

        # Re-enable process monitoring.
        pipe.stdin.write("p\n")
        pipe.stdin.write(f"{my_pid}\n")
        pipe.communicate(input="s\n")
        assert pipe.returncode == 0
        _check_files(tmp_path)


def _check_files(path: Path) -> None:
    hostname = socket.gethostname()
    assert (path / f"{hostname}.sqlite").exists()
    assert (path / f"{hostname}_results.json").exists()
    for filename in (
        f"{hostname}_cpu.html",
        f"{hostname}_disk.html",
        f"{hostname}_memory.html",
        f"{hostname}_network.html",
        f"{hostname}_process.html",
    ):
        assert (path / "html" / filename).exists()


def _find_rmon_collect_pid() -> int | None:
    for proc in psutil.process_iter(["cmdline"]):
        cmdline = " ".join(proc.info.get("cmdline", []) or [])
        if "rmon" in cmdline and "collect" in cmdline:
            return proc.pid
    return None
