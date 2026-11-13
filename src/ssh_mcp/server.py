"""A minimal STDIO MCP server that executes commands through Windows OpenSSH."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 3600
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
USER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class ConfigurationError(ValueError):
    """Raised when the server's required security configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    ssh_path: str
    user: str
    allowed_hosts: frozenset[str] | None
    identity_file: Path
    known_hosts_file: Path | None
    default_timeout_seconds: int


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} must be set")
    return value


def _existing_file(name: str) -> Path:
    path = Path(_required_env(name)).expanduser()
    if not path.is_file():
        raise ConfigurationError(f"{name} must name an existing file: {path}")
    return path.resolve()


def _parse_timeout(value: str, variable_name: str) -> int:
    try:
        timeout = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{variable_name} must be an integer") from error
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ConfigurationError(
            f"{variable_name} must be between 1 and {MAX_TIMEOUT_SECONDS} seconds"
        )
    return timeout


def load_settings() -> Settings:
    """Read and validate the explicit, least-privilege server configuration."""
    user = _required_env("SSH_MCP_USER")
    if not USER_PATTERN.fullmatch(user):
        raise ConfigurationError("SSH_MCP_USER contains unsupported characters")

    allowed_hosts_value = os.environ.get("SSH_MCP_ALLOWED_HOSTS", "").strip()
    allowed_hosts = None
    if allowed_hosts_value:
        allowed_hosts = frozenset(host.strip() for host in allowed_hosts_value.split(",") if host.strip())
        if not allowed_hosts or any(not NAME_PATTERN.fullmatch(host) for host in allowed_hosts):
            raise ConfigurationError("SSH_MCP_ALLOWED_HOSTS must be a comma-separated list of host names or IPs")

    configured_ssh = os.environ.get("SSH_MCP_SSH_PATH", "ssh.exe")
    ssh_path = shutil.which(configured_ssh) or configured_ssh
    if not Path(ssh_path).is_file() and shutil.which(ssh_path) is None:
        raise ConfigurationError(f"SSH client was not found: {configured_ssh}")

    return Settings(
        ssh_path=ssh_path,
        user=user,
        allowed_hosts=allowed_hosts,
        identity_file=_existing_file("SSH_MCP_IDENTITY_FILE"),
        known_hosts_file=(
            _existing_file("SSH_MCP_KNOWN_HOSTS_FILE")
            if os.environ.get("SSH_MCP_KNOWN_HOSTS_FILE", "").strip()
            else None
        ),
        default_timeout_seconds=_parse_timeout(
            os.environ.get("SSH_MCP_DEFAULT_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)),
            "SSH_MCP_DEFAULT_TIMEOUT",
        ),
    )


def _validated_timeout(timeout_seconds: int | None, default: int) -> int:
    timeout = default if timeout_seconds is None else timeout_seconds
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise ValueError("timeout_seconds must be an integer")
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    return timeout


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _ssh_arguments(settings: Settings, host: str, command: str, timeout: int) -> list[str]:
    host_verification = (
        [
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={settings.known_hosts_file}",
            "-o",
            "GlobalKnownHostsFile=NUL",
        ]
        if settings.known_hosts_file is not None
        else ["-o", "StrictHostKeyChecking=accept-new"]
    )
    arguments = [
        settings.ssh_path,
        "-F",
        "none",
        "-T",
        "-i",
        str(settings.identity_file),
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        *host_verification,
        "-o",
        f"ConnectTimeout={timeout}",
        f"{settings.user}@{host}",
        command,
    ]
    return arguments


def execute(settings: Settings, host: str, command: str, timeout_seconds: int | None = None) -> dict[str, Any]:
    """Run one command without a local shell and return its remote process result."""
    if settings.allowed_hosts is not None and host not in settings.allowed_hosts:
        return {"stdout": "", "stderr": f"Host is not allowed: {host}", "exit_code": 126}
    if not NAME_PATTERN.fullmatch(host):
        return {"stdout": "", "stderr": "Host contains unsupported characters", "exit_code": 126}
    if not command or not command.strip():
        return {"stdout": "", "stderr": "command must not be empty", "exit_code": 126}

    try:
        timeout = _validated_timeout(timeout_seconds, settings.default_timeout_seconds)
    except ValueError as error:
        return {"stdout": "", "stderr": str(error), "exit_code": 126}

    arguments = _ssh_arguments(settings, host, command, timeout)
    try:
        result = subprocess.run(
            arguments,
            # SSH must not consume the MCP server's JSON-RPC input stream.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stderr = _as_text(error.stderr)
        if stderr and not stderr.endswith("\n"):
            stderr += "\n"
        return {
            "stdout": _as_text(error.stdout),
            "stderr": f"{stderr}Command timed out after {timeout} seconds.",
            "exit_code": 124,
        }
    except OSError as error:
        return {"stdout": "", "stderr": f"Could not start ssh: {error}", "exit_code": 255}

    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


mcp = FastMCP("ssh-mcp")
_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


@mcp.tool()
def run_ssh_command(host: str, command: str, timeout_seconds: int | None = None) -> dict[str, Any]:
    """Run a shell command on one configured SSH host and return stdout, stderr, and exit_code."""
    try:
        return execute(_get_settings(), host, command, timeout_seconds)
    except ConfigurationError as error:
        return {"stdout": "", "stderr": f"SSH MCP configuration error: {error}", "exit_code": 78}


def main() -> None:
    """Start the MCP STDIO transport after failing fast on bad configuration."""
    _get_settings()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
