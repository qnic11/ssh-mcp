from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ssh_mcp.server import Settings, execute, load_settings


SETTINGS = Settings(
    ssh_path="C:/Windows/System32/OpenSSH/ssh.exe",
    user="automation",
    allowed_hosts=frozenset({"server.example.com"}),
    identity_file=Path("C:/keys/automation"),
    known_hosts_file=Path("C:/keys/known_hosts"),
    default_timeout_seconds=30,
)


class ExecuteTests(unittest.TestCase):
    def test_loads_without_optional_host_settings(self) -> None:
        with tempfile.NamedTemporaryFile() as identity_file:
            environment = {
                "SSH_MCP_USER": "automation",
                "SSH_MCP_IDENTITY_FILE": identity_file.name,
                "SSH_MCP_SSH_PATH": sys.executable,
            }
            with patch.dict(os.environ, environment, clear=True):
                settings = load_settings()

        self.assertIsNone(settings.allowed_hosts)
        self.assertIsNone(settings.known_hosts_file)

    def test_returns_ssh_output_and_strict_options(self) -> None:
        completed = subprocess.CompletedProcess(["ssh"], 7, "output", "error")
        with patch("ssh_mcp.server.subprocess.run", return_value=completed) as run:
            result = execute(SETTINGS, "server.example.com", "id", 12)

        self.assertEqual({"stdout": "output", "stderr": "error", "exit_code": 7}, result)
        arguments = run.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=yes", arguments)
        self.assertIn("PasswordAuthentication=no", arguments)
        self.assertIn(f"UserKnownHostsFile={SETTINGS.known_hosts_file}", arguments)
        self.assertEqual("automation@server.example.com", arguments[-2])
        self.assertEqual("id", arguments[-1])
        self.assertEqual(12, run.call_args.kwargs["timeout"])

    def test_rejects_a_host_outside_the_allowlist(self) -> None:
        with patch("ssh_mcp.server.subprocess.run") as run:
            result = execute(SETTINGS, "other.example.com", "id")

        self.assertEqual(126, result["exit_code"])
        self.assertIn("not allowed", result["stderr"])
        run.assert_not_called()

    def test_allows_any_valid_host_without_an_allowlist_or_known_hosts_file(self) -> None:
        unrestricted = Settings(
            ssh_path=SETTINGS.ssh_path,
            user=SETTINGS.user,
            allowed_hosts=None,
            identity_file=SETTINGS.identity_file,
            known_hosts_file=None,
            default_timeout_seconds=SETTINGS.default_timeout_seconds,
        )
        completed = subprocess.CompletedProcess(["ssh"], 0, "ok", "")
        with patch("ssh_mcp.server.subprocess.run", return_value=completed) as run:
            result = execute(unrestricted, "new-host.example.com", "hostname")

        self.assertEqual({"stdout": "ok", "stderr": "", "exit_code": 0}, result)
        arguments = run.call_args.args[0]
        self.assertIn("StrictHostKeyChecking=accept-new", arguments)
        self.assertFalse(any(argument.startswith("UserKnownHostsFile=") for argument in arguments))

    def test_returns_partial_output_after_timeout(self) -> None:
        timeout = subprocess.TimeoutExpired(["ssh"], 3, output=b"partial", stderr=b"warning")
        with patch("ssh_mcp.server.subprocess.run", side_effect=timeout):
            result = execute(SETTINGS, "server.example.com", "sleep 5", 3)

        self.assertEqual("partial", result["stdout"])
        self.assertEqual(124, result["exit_code"])
        self.assertIn("warning", result["stderr"])
        self.assertIn("timed out after 3 seconds", result["stderr"])


if __name__ == "__main__":
    unittest.main()
