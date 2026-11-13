# ssh-mcp

A small Windows STDIO MCP server that runs commands on Linux hosts through OpenSSH and returns `stdout`, `stderr`, and `exit_code`. It has no web server or remote agent.

## Set up a working environment

The following end-to-end procedure creates a dedicated, non-interactive SSH key, authorizes it on the target Linux account, installs the MCP server, and adds it to ChatGPT Desktop / Codex.

### 1. Install prerequisites

You need Python 3.10+, Git, and the Windows OpenSSH Client. In an Administrator PowerShell:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

Install the project in a virtual environment:

```powershell
winget install --id Git.Git -e
New-Item -ItemType Directory -Force "$env:USERPROFILE\code"
git clone https://github.com/qnic11/ssh-mcp.git "$env:USERPROFILE\code\ssh-mcp"
Set-Location "$env:USERPROFILE\code\ssh-mcp"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

If `git clone` fails after installation open a new terminal session.

### 2. Create a dedicated automation key

Keep the private key outside the repository. The MCP server runs OpenSSH in batch mode, so use a dedicated key **without a passphrase**; when `ssh-keygen` prompts for one, press Enter twice.

```powershell
$key = 'C:\Users\ticqu\Documents\keys\freepbx17-lab_quarea_ed25519'

ssh-keygen -t ed25519 -f $key -C 'quarea-ssh automation'
```

Restrict access to the private key so that Windows OpenSSH will accept it:

```powershell
icacls $key /inheritance:r
icacls $key /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(R)"
```

Show the public key:

```powershell
Get-Content "$key.pub"
```

Log into the target Linux machine as the account that MCP will use, then append that one-line public key to `~/.ssh/authorized_keys`. Do not replace existing entries.

```bash
install -d -m 700 ~/.ssh
printf '%s\n' 'paste-the-public-key-here' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 3. Add the MCP server in ChatGPT Desktop / Codex

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
| `SSH_MCP_IDENTITY_FILE` | Yes | `C:\Users\ticqu\Documents\keys\freepbx17-lab_quarea_ed25519` |
| `SSH_MCP_DEFAULT_TIMEOUT` | No | `30` |
| `SSH_MCP_ALLOWED_HOSTS` | No | `server-a.example.com,server-b.example.com` |
| `SSH_MCP_KNOWN_HOSTS_FILE` | No | `C:\Users\you\.ssh\ssh_mcp_known_hosts` |

Do not use **Environment variable passthrough** for these entries. Restart ChatGPT Desktop/Codex after saving. [Official MCP setup documentation](https://learn.chatgpt.com/docs/extend/mcp).

### 4. Verify the installation

Ask the MCP client to run a harmless command such as `uname -r` against the target host. A successful response includes `stdout` and `exit_code: 0`.

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
