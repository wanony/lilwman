# lilwman

A Discord bot for your server's shared wiki. Store notes, search them, tag them, and ask questions answered from the wiki using a local LLM.

## Commands

| Command | Description |
|---------|-------------|
| `/store content tags` | Store a wiki entry (tags optional, comma-separated) |
| `/search query` | Full-text search the wiki (paginated, 5 per page) |
| `/tag name` | List entries with a tag |
| `/delete id` | Delete an entry (own entries, or any if server admin) |
| `/ask question` | Ask a question — answered from matching wiki entries via local LLM |

---

## What you need

### 1. Discord bot token

1. Go to https://discord.com/developers/applications
2. Click **New Application**, give it a name
3. Go to **Bot** → click **Add Bot**
4. Under **Token** → **Reset Token** → copy it (this is your `DISCORD_TOKEN`)
5. Scroll down, enable **Message Content Intent** (not strictly required but good practice)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`
   - Copy the generated URL, open it, and invite the bot to your server

### 2. Your server (guild) ID

1. In Discord, open **Settings → Advanced → enable Developer Mode**
2. Right-click your server name → **Copy Server ID** (this is your `DISCORD_GUILD_ID`)

### 3. Ollama (local LLM)

Install from https://ollama.com then pull the model:

```bash
ollama pull qwen2.5:1.5b
```

The bot works best with small, fast models. `qwen2.5:1.5b` runs on most machines. Swap it in `.env` if you want something bigger.

---

## Running locally

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
# Clone and install deps
git clone https://github.com/wanony/lilwman.git
cd lilwman
uv sync --extra dev

# Copy env and fill in your values
cp .env.example .env
# Edit .env — set DISCORD_TOKEN, DISCORD_GUILD_ID, and DB_PATH (any writable path)

# Start Ollama (if not already running)
ollama serve &

# Run the bot
uv run python -m lilwman
```

The bot registers slash commands to your specific server on startup — they appear instantly (no 1-hour global propagation delay).

### Using process-compose (runs Ollama + bot together)

```bash
make dev
```

Requires `process-compose` installed (`brew install F1bonacc1/process-compose/process-compose` on Mac).

---

## Nix devShell

```bash
nix develop
```

Drops you into a shell with Python 3.11, uv, ollama, and process-compose available.

---

## Running tests

```bash
make test
# or
uv run pytest --cov=lilwman --cov-report=term-missing
```

No real Discord connection or Ollama needed — tests use in-memory SQLite and mocked LLM.

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | required | Bot token from Discord Developer Portal |
| `DISCORD_GUILD_ID` | required | Your server's ID (right-click server → Copy ID) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Model to use for `/ask` |
| `DB_PATH` | `data/lilwman.db` | SQLite database file path |

---

## Deploying to a server (`make deploy`)

The Makefile has a `deploy` target that rsyncs to a host called `gigi` and restarts a systemd service. Edit the `Makefile` to match your server hostname and path:

```makefile
deploy:
    rsync -av --exclude='.venv' --exclude='.env' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='.git' . yourhost:/opt/lilwman/
    ssh yourhost "cd /opt/lilwman && uv sync && sudo systemctl restart lilwman"
```

You'll need a `.env` file already on the server (don't commit it).
