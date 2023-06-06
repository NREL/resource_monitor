"""Tests the resource monitor CLI commands"""

import os
import socket
import subprocess
import time


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

    hostname = socket.gethostname()
    for filename in (
        f"{hostname}.sqlite",
        f"{hostname}_results.json",
        f"{hostname}_cpu.html",
        f"{hostname}_disk.html",
        f"{hostname}_memory.html",
        f"{hostname}_network.html",
        f"{hostname}_process.html",
    ):
        assert (tmp_path / filename).exists()


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

        hostname = socket.gethostname()
        for filename in (
            f"{hostname}.sqlite",
            f"{hostname}_results.json",
            f"{hostname}_cpu.html",
            f"{hostname}_disk.html",
            f"{hostname}_memory.html",
            f"{hostname}_network.html",
            f"{hostname}_process.html",
        ):
            assert (tmp_path / filename).exists()
