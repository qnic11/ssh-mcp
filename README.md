# ssh-mcp

A minimal MCP server for Windows that exposes one tool, `run_ssh_command`. It runs a command on an allowlisted Linux host through the built-in OpenSSH client and returns `stdout`, `stderr`, and `exit_code`.

The server uses MCP over STDIO only. It starts no web server and requires no remote agent.

## Requirements

- Windows 10/11 with the **OpenSSH Client** optional feature installed (`ssh.exe` must be on `PATH`).
- Python 3.10 or newer.
- An SSH private key authorized for a least-privilege account on each target server.
- A verified `known_hosts` file containing the target hosts' host keys.

## Install

```powershell
git clone https://github.com/qnic11/ssh-mcp.git
Set-Location ssh-mcp
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

## Configure

Create a dedicated key and configure its public key on the target Linux account. Obtain each server's host-key fingerprint through a trusted out-of-band channel, verify it, and save the corresponding public host-key entry in a dedicated `known_hosts` file. Do **not** accept an unknown host key interactively and do not use `StrictHostKeyChecking=no`.

Set the required variables in the environment that launches ChatGPT Desktop or Codex:

```powershell
$env:SSH_MCP_USER = "automation"
$env:SSH_MCP_ALLOWED_HOSTS = "server-a.example.com,server-b.example.com"
$env:SSH_MCP_IDENTITY_FILE = "C:\Users\you\.ssh\ssh_mcp_ed25519"
$env:SSH_MCP_KNOWN_HOSTS_FILE = "C:\Users\you\.ssh\ssh_mcp_known_hosts"
$env:SSH_MCP_DEFAULT_TIMEOUT = "30"  # optional; 1 to 3600 seconds
```

`SSH_MCP_SSH_PATH` is optional when `ssh.exe` is on `PATH`; set it to an absolute path otherwise. The server deliberately ignores normal SSH configuration files, disables password and keyboard-interactive authentication, and requires a host in `SSH_MCP_ALLOWED_HOSTS`.

## ChatGPT Desktop / Codex configuration

In ChatGPT Desktop or the Codex IDE extension, go to **Settings → MCP servers → Add server**, choose **STDIO**, and use:

- Command: `C:\path\to\ssh-mcp\.venv\Scripts\python.exe`
- Arguments: `-m ssh_mcp.server`
- Working directory: `C:\path\to\ssh-mcp`

Restart after saving. The [official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp) confirms that ChatGPT Desktop, Codex CLI, and the IDE extension share this local configuration and support STDIO commands with environment variables.

Equivalent `~/.codex/config.toml` configuration:

```toml
[mcp_servers.ssh]
command = "C:\\path\\to\\ssh-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "ssh_mcp.server"]
cwd = "C:\\path\\to\\ssh-mcp"
env_vars = [
  "SSH_MCP_USER",
  "SSH_MCP_ALLOWED_HOSTS",
  "SSH_MCP_IDENTITY_FILE",
  "SSH_MCP_KNOWN_HOSTS_FILE",
  "SSH_MCP_DEFAULT_TIMEOUT",
]
default_tools_approval_mode = "prompt"
tool_timeout_sec = 3605
```

The client timeout is intentionally slightly higher than the server's maximum command timeout so the server can return its timeout result.

## Tool

`run_ssh_command(host, command, timeout_seconds=None)` accepts only a configured host. `timeout_seconds` defaults to `SSH_MCP_DEFAULT_TIMEOUT` and is limited to 1–3600 seconds.

Example result:

```json
{
  "stdout": "Linux server-a 6.8.0\n",
  "stderr": "",
  "exit_code": 0
}
```

Exit code `124` means the local timeout expired; `126` means invalid tool input; `255` means the SSH client could not be started.

## Security notes

- Treat this as privileged command-execution access. Use a dedicated Linux account with the smallest practical permissions; do not use `root`.
- Keep the private key outside the repository, protected by Windows ACLs and, where workable for noninteractive use, a secure credential/agent workflow.
- Keep the host allowlist narrow. A model can run only the commands you approve, but commands still execute with the configured account's permissions.
- Verify and review host-key changes before updating the dedicated `known_hosts` file. Host-key mismatch failures are intentional.
- Secrets printed by remote commands become MCP tool output. Avoid commands that expose credentials and keep tool approval enabled.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
