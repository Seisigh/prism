# PRISM — Windows setup

Run these in PowerShell, in order. Quote the path everywhere; `Pengjie Wang` has a space in it and unquoted paths will fail in confusing ways.

## 1. Get into the folder

```powershell
cd "C:\Users\Pengjie Wang\Downloads\PRISM"
```

## 2. Unpack the starter files

Put `prism-starter.zip` in that folder first, then:

```powershell
Expand-Archive -Path .\prism-starter.zip -DestinationPath . -Force
Remove-Item .\prism-starter.zip
dir
```

You should see `BUILD_BRIEF.md`, `KICKOFF_PROMPT.md`, `COPY.md`, `NOTICE`, `.gitignore`, `docker-compose.yml`, `.env.example`, and `assets\`.

If `.gitignore` doesn't show, it's hidden. Check with `dir -Force`.

## 3. Reference screenshots

```powershell
mkdir docs\reference
```

Put the three retailer screenshots in `docs\reference\`. They are structural reference only and `.gitignore` already keeps them out of every commit.

## 4. Git and GitHub

```powershell
git init
git branch -M main
gh auth status
```

If `gh auth status` reports you are not logged in:

```powershell
gh auth login
```

Choose GitHub.com, HTTPS, then authenticate in the browser.

If `gh` is not recognized at all:

```powershell
winget install --id GitHub.cli
```

Close and reopen PowerShell afterward so PATH refreshes.

## 5. Postgres and Redis

Redis has no supported native Windows build, so run both services in Docker. Install Docker Desktop, start it, then:

```powershell
docker compose up -d
docker compose ps
```

Both containers should read `healthy`. Then:

```powershell
Copy-Item .env.example .env
```

The defaults in `.env.example` already match `docker-compose.yml`, so nothing needs editing.

To stop them later: `docker compose down`. To wipe the data and start clean: `docker compose down -v`.

## 6. Runtimes

```powershell
python --version
node --version
```

Need Python 3.11 or newer and Node 20 or newer.

```powershell
winget install --id Python.Python.3.12
winget install --id OpenJS.NodeJS.LTS
```

## 7. Claude Code

```powershell
claude --version
```

If it isn't installed:

```powershell
winget install --id Anthropic.ClaudeCode
```

Reopen PowerShell after installing.

## 8. Plugins and MCP servers

Start Claude Code in the project folder:

```powershell
claude
```

Then, inside the session:

```
/plugin install frontend-design
/mcp add playwright
/mcp add context7
```

## 9. Go

Paste the contents of `KICKOFF_PROMPT.md` as your first message.

---

## Permission modes

"Godmode" is the `bypassPermissions` mode:

```powershell
claude --dangerously-skip-permissions
```

Read the next paragraph before using it. Anthropic's documentation scopes that mode to "isolated containers and VMs only," and the built-in Bash sandbox that provides a second layer of protection does not exist on native Windows, only on macOS, Linux and WSL2. On a bare Windows machine, in a folder inside your user profile, it means any command runs with no confirmation and nothing behind it.

What you probably actually want is **auto mode**, which runs everything but routes actions through a classifier that reviews them instead of you:

```powershell
claude --permission-mode auto
```

On Pro, Max and Team plans this is already the starting mode, so plain `claude` most likely gives it to you. Check the status bar: `⏵⏵ auto mode on`.

Other modes, and how to move between them:

| Mode | Flag | What it does |
| --- | --- | --- |
| Manual | `--permission-mode default` | Asks before most edits, commands, and network calls |
| Accept edits | `--permission-mode acceptEdits` | Auto-approves file edits and common filesystem commands |
| Plan | `--permission-mode plan` | Reads only, no edits until you approve a plan |
| Auto | `--permission-mode auto` | Everything, with classifier review |
| Bypass | `--dangerously-skip-permissions` | Everything, no checks |

`Shift+Tab` cycles modes inside a running session, so you can start in auto and drop to manual for anything that makes you nervous.

To make auto the default for every session on this machine, put this in `~\.claude\settings.json`:

```json
{ "permissions": { "defaultMode": "auto" } }
```

Note that `auto` and `bypassPermissions` are both ignored if you set them in a project's `.claude/settings.json`; they only work from the flag or your user settings file.

---

## If things go wrong

**`claude` is not recognized** — PATH hasn't refreshed. Close and reopen PowerShell.

**Docker containers won't start** — Docker Desktop isn't running, or WSL2 isn't enabled. Open Docker Desktop and wait for the whale icon to settle.

**Port already in use** — something else holds 5432 or 6379. Find it with `netstat -ano | findstr "5432"`, or change the host side of the port mapping in `docker-compose.yml` and update `.env` to match.

**Playwright can't find a browser** — inside the project, `npx playwright install chromium`.

**Path errors mentioning `C:\Users\Pengjie`** — an unquoted path broke at the space. Quote it.
