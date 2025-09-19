# telegram-mark-read-archived

**This is not a bot.** The script runs as your personal Telegram account and requires you to authorize it whenever a new session is created.

The tool automatically clears unread counters for every archived dialog in Telegram, including forum topics, so nothing gets stuck with an unread badge.

## Why you might want this

- If you cannot stand unread message badges and want to keep the archive spotless.
- If you live by an inbox-zero policy and never want archived conversations to pile up.
- If you move entertainment or low-priority channels to the archive but still get distracted by unread flags.

## Features

- Periodically scans all archived chats and marks each dialog as read.
- Resets unread counters for every conversation it finds.
- For forum-style groups, fetches up to `TOPIC_LIMIT` topics and marks them as read to clear topic counters.
- Works with accounts protected by two-factor authentication; the script will prompt for the password when necessary.
- Streams logs to stdout with a configurable log level.

## Requirements

- Python 3.9 or newer for local execution.
- Docker installed if you prefer the container workflow.
- Telegram API credentials (`api_id`, `api_hash`) and the phone number of the account that should run the script.

## Repository layout

- `archive_read_service.py` — main script.
- `config-example.yaml` — sample configuration to copy as a starting point.
- `requirements.txt` — Python dependencies.
- `Dockerfile` — container recipe for the service.
- `docker-compose.yml` — Compose definition for running the container with persisted state.
- `build.sh` — helper script that builds the Docker image.
- `run.sh` — helper script that starts the Compose stack and attaches to the container.
- `Makefile` — helper target for building the Docker image.

## Local setup

1. Clone the repository and move into the project directory:
   ```bash
   git clone https://github.com/<user>/telegram-mark-read-archived.git
   cd telegram-mark-read-archived
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create the configuration file next to the script and edit it:
   ```bash
   cp config-example.yaml config.yaml
   nano config.yaml
   ```

### Configuring `config.yaml`

The configuration file contains two sections.

`telegram`:
- `api_id` / `api_hash` — values from [https://my.telegram.org/apps](https://my.telegram.org/apps).
- `phone` — the phone number linked to the Telegram account (international format).
- `session` — Telethon session name without an extension; the file is created automatically. You may point it to a subdirectory such as `sessions/telegram_read`.

`service`:
- `check_interval` — number of seconds between archive scans (default: 600).
- `log_level` — logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

> ⚠️ Place `config.yaml` in the same directory as `archive_read_service.py`. The script loads it from the relative path `./config.yaml`.

## Running the script locally

```bash
python archive_read_service.py
```

During the first run Telethon sends a login code to your Telegram account. Enter the code (and a 2FA password if requested) to authorize the session. Future runs reuse the saved session file.

The script loops indefinitely: after every `check_interval` seconds it lists archived dialogs, clears unread counters, and processes forum topics. Press `Ctrl+C` to stop it.

### Logging

Logs are printed to stdout. Control the verbosity through `service.log_level`. With `DEBUG` you can see details about individual forum topics and errors.

### Topic limit for forums

The script reads up to `TOPIC_LIMIT` topics from each forum (default 100). Override it by setting an environment variable before launching the script, for example:

```bash
TOPIC_LIMIT=250 python archive_read_service.py
```

## Docker workflow

Containerising the script keeps dependencies isolated and simplifies deployment. The Docker image does **not** include `config.yaml`; mount it at runtime so secrets stay on the host.

### Prepare configuration

1. Copy and customise `config.yaml` as described above. To persist sessions outside the container, set `session: "sessions/telegram_read"` (or similar) in the config.
2. Create the session directory on the host:
   ```bash
   mkdir -p sessions
   ```

### Build the image

```bash
./build.sh
```

The script wraps `docker build` and tags the image as `telegram-auto-read`. Override the tag by exporting `IMAGE_NAME=my-tag` before running the script.

You can achieve the same result with `make docker-build` if you prefer the Makefile target.

### Launch with Docker Compose

The repository provides a Compose file and a helper script that prepare the container, print the startup logs, and attach to the running service so you can enter the Telegram login code on the first run.

```bash
./run.sh
```

The script recreates the `archive_read_service` container defined in `docker-compose.yml`, shows the recent logs, and then attaches to the interactive session. When you want to detach without stopping the service, press `Ctrl+p` followed by `Ctrl+q`. Stop the container with `docker compose down` when you are done.

Compose mounts `config.yaml` into `/app/config.yaml` (read-only) and binds the `sessions` directory so Telethon can persist its login data. Ensure the `session` path configured in `config.yaml` matches the mounted directory (for example, `sessions/telegram_read`).

Both `build.sh` and `run.sh` respect the `IMAGE_NAME` environment variable, allowing you to reuse a custom tag across build and runtime. To adjust the number of forum topics processed per dialog, export `TOPIC_LIMIT=250` (or similar) before invoking `run.sh`; the value is passed into the container via Compose.

## Troubleshooting

- **`FileNotFoundError: config.yaml`** — check that the configuration file exists next to the script or is correctly mounted into the container.
- **Authorization errors** — verify `api_id`, `api_hash`, and the phone number. When two-factor authentication is enabled, provide the password when prompted.
- **Forum topics remain unread** — increase `TOPIC_LIMIT` via the environment variable if a forum has more than 100 active topics.

## License

This project is released under the [MIT License](LICENSE).
