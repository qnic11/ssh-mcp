# ssh-mcp

A small Windows STDIO MCP server that runs commands on Linux hosts through OpenSSH and returns `stdout`, `stderr`, and `exit_code`. It has no web server or remote agent.

## Install on a new Windows PC

You need Python 3.10+, Git, an SSH private key authorized on the Linux host, and the Windows OpenSSH Client. In an Administrator PowerShell:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

Then install the project in a virtual environment:

```powershell
git clone https://github.com/qnic11/ssh-mcp.git "$env:USERPROFILE\code\ssh-mcp"
Set-Location "$env:USERPROFILE\code\ssh-mcp"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

Keep the private key outside the repository, for example: `C:\Users\you\.ssh\ssh_mcp_ed25519`.

## Add it in ChatGPT Desktop / Codex

Open **Settings → MCP servers → Add server** and choose **STDIO**.

| Field | Value |
|---|---|
| Name | `ssh` |
| Command to launch | `C:\Users\you\code\ssh-mcp\.venv\Scripts\python.exe` |
| Arguments | Add `-m`, then `ssh_mcp.server` as two arguments |
| Working directory | `C:\Users\you\code\ssh-mcp` |

Add these entries in the form's **Environment variables** section:

| Key | Required | Example value |
|---|---|---|
| `SSH_MCP_USER` | Yes | `automation` |
| `SSH_MCP_IDENTITY_FILE` | Yes | `C:\Users\you\.ssh\ssh_mcp_ed25519` |
| `SSH_MCP_DEFAULT_TIMEOUT` | No | `30` |
| `SSH_MCP_ALLOWED_HOSTS` | No | `server-a.example.com,server-b.example.com` |
| `SSH_MCP_KNOWN_HOSTS_FILE` | No | `C:\Users\you\.ssh\ssh_mcp_known_hosts` |

Do not use **Environment variable passthrough** for these entries. Restart ChatGPT Desktop/Codex after saving. [Official MCP setup documentation](https://learn.chatgpt.com/docs/extend/mcp).

## Optional host controls

- With `SSH_MCP_ALLOWED_HOSTS`, only listed hosts are allowed. Without it, any valid host name or IP address is allowed.
- With `SSH_MCP_KNOWN_HOSTS_FILE`, host keys are checked strictly against that file. Without it, OpenSSH accepts and records a first-seen host key automatically; a changed key still fails.

## Security

- Use a dedicated non-root Linux account with minimal permissions.
- Restrict hosts and provide a verified `known_hosts` file when possible.
- Commands and their output can expose secrets; keep MCP tool approval enabled.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
