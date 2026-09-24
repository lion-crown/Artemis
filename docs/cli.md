# CLI Reference

`artemis` is a single Click app installed as `artemis` on `pip install artemis`.
It is registered in `src/artemis/cli/main.py`; commands are loaded
lazily from `src/artemis/cli/registry.py`.

```
$ artemis --help
Usage: artemis [OPTIONS] COMMAND [ARGS]...

  Artemis command-line interface.

Options:
  -v, --version           Show the installed artemis version.
  --user TEXT             Default --user for subcommands (admin acting on behalf
                          of a user). [env: ARTEMIS_USER]
  --agent TEXT            Default --agent for subcommands. [env: ARTEMIS_AGENT]
  --json                  Emit machine-readable JSON for list-style commands.
  -h, --help              Show this message and exit.

Commands:
  acp        Run Artemis agent as ACP server (stdio).
  admin      Admin commands.
  agent      Agent lifecycle commands.
  backup     Export and restore Artemis backups.
  chat       [deprecated] Alias for `artemis chats`.
  chats      Chat REPL and session management.
  channel    Channel management commands.
  clean      Remove CLI state or wipe all of ~/.artemis.
  completion Shell completion utilities.
  config     CLI state (base URL, defaults).
  cron       Cron job management commands.
  init       Bootstrap an Artemis server install.
  models     Model catalog and active-model settings.
  plugin     Install and manage plugins.
  provider   Provider management (admin write).
  run        Run artemis-server in the foreground.
  service    System service lifecycle (start/stop/restart/status).
  skills     Per-agent skill enable/disable.
  update     Check for and install a newer Artemis release.
  user       User management commands.
  version    Show the installed artemis version.
```

> **Tip.** Regenerate the per-subcommand listings below with
> `make docs-cli` (each `artemis <cmd> --help` is captured to stdout).

## Global options

| Option | Env | Effect |
|--------|-----|--------|
| `--user NAME` | `ARTEMIS_USER` | Default `--user` for subcommands (admin acting on behalf of a user) |
| `--agent ID` | `ARTEMIS_AGENT` | Default `--agent` for subcommands |
| `--json` | — | Emit machine-readable JSON for list-style commands |
| `-v, --version` | — | Print version and exit |

## Transport layers

Artemis commands pick one of three transports:

| Layer | When | Login? | Examples |
|-------|------|--------|----------|
| **Offline** (local DB only) | Need to read/write `~/.artemis` without a running server | No | `init`, `backup`, `plugin`, `agent list`, `chats list/get/create/update/delete`, `cron list`, `user *`, `admin overview/audit`, `models presets/list/active` |
| **Attach** (HTTP / WS) | Need a live `artemis run` process (IM, streams, model pulls) | Yes (`artemis user login`) | `chats send/repl`, `channel test/probe`, `models ollama-*`, `skills enable/disable`, `provider test` |
| **Embedded** (in-process) | CLI boots `ArtemisServer` for a single command | No | `artemis acp`, `artemis chats repl`, `artemis chats send` (defaults to embedded), `artemis agent create/from-expert/start/stop/reload` |

The dashboards and HTTP callers manage their own JWTs and do **not**
share `~/.artemis/cli_state.json`.

## `artemis init`

Bootstrap a fresh install (DB migrations, JWT secret, first admin).
Idempotent on the DB; pass `--force` to wipe `~/.artemis` first.

```
Usage: artemis init [OPTIONS]

  Bootstrap an Artemis server (~/.artemis dir, DB migrations, JWT secret, first admin).

Options:
  --admin-username TEXT       [env: ARTEMIS_ADMIN_USERNAME]
  --admin-password TEXT       [env: ARTEMIS_ADMIN_PASSWORD]
  --admin-display-name TEXT   [env: ARTEMIS_ADMIN_DISPLAY_NAME]
  --force                     Wipe existing ~/.artemis contents before bootstrapping.
  --yes                       Skip all interactive prompts.
  -h, --help                  Show this message and exit.
```

## `artemis run`

Start the FastAPI app in the foreground (delegates to
`artemis.launch.run_foreground_blocking`).

```
Usage: artemis run [OPTIONS]

  Start the Artemis server (foreground; uvicorn).

Options:
  --host TEXT                 Override ARTEMIS_BIND_HOST.
  --port INTEGER              Override ARTEMIS_PORT.
  --reload / --no-reload      Enable uvicorn auto-reload (dev only).
  --ssl / --no-ssl            Enable HTTPS with a self-signed cert (or a real one).
  --certfile PATH             TLS certificate (PEM).
  --keyfile PATH              TLS private key (PEM).
  --log-level [debug|info|warning|error]
  -h, --help                  Show this message and exit.
```

## `artemis service`

Install and manage the Artemis system service. The backend is detected
automatically (systemd on Linux, launchd on macOS); the scope
(`user` vs `system`) can be forced via `--scope` or
`ARTEMIS_SERVICE_SCOPE`.

```
Usage: artemis service [OPTIONS] COMMAND [ARGS]...

  Manage the Artemis system service (systemd on Linux, launchd on macOS).

Commands:
  start     Install (if missing) and start the service.
  stop      Stop the service.
  restart   Restart the service.
  status    Print whether the service is installed / running / healthy.
```

`status` probes the HTTP health endpoint and prints journal/log hints
on failure.

On Linux, `start` and `restart` install a systemd drop-in
(`artemis.service/10-nofile.conf`) with `LimitNOFILE=65535` (user
units are capped to the process hard rlimit so systemd cannot fail to
spawn). The main unit file is not rewritten unless it is missing or
you pass `--force-install`. `restart` always runs `systemctl restart`
even if writing the drop-in fails, so an upgrade that only restarts
still comes back. To undo: delete the drop-in, then
`systemctl daemon-reload && systemctl restart artemis`.

## `artemis user`

Local-DB user management. `login` requires a running server; the
rest are offline.

```
Usage: artemis user [OPTIONS] COMMAND [ARGS]...

  User management commands (local DB; no server login required).

Commands:
  create    Create a new user.
  list      List all users.
  passwd    Reset a user's password (admin).
  role      Set a user's role.
  disable   Disable a user.
  delete    Delete a user.
  login     Login against a running server; stores JWT for optional remote HTTP attach.
```

## `artemis agent`

Lifecycle and templates. Most commands boot an embedded
`ArtemisServer` to operate on the local DB without a remote round-trip.

```
Usage: artemis agent [OPTIONS] COMMAND [ARGS]...

  Agent lifecycle commands.

Commands:
  create        Create a new agent.
  from-expert   Create an agent from a bundled expert template.
  list          List agents.
  use           Pin this agent as the default for subsequent commands.
  start         Start the agent runtime.
  stop          Stop the agent runtime.
  reload        Reload the agent runtime.
  delete        Delete the agent row (and runtime).
  experts       List bundled expert templates.
```

`create` and `from-expert` accept `--user` (admin only) to create
agents on behalf of another user. `use` writes the agent id into
`~/.artemis/cli_state.json` so subsequent commands default to it.

## `artemis chats`

Thread CRUD + interactive REPL. The REPL and `send` use an embedded
server (no separate `artemis run` needed); `list` / `get` / `create` /
`update` / `delete` work fully offline against `~/.artemis/artemis.db`.

```
Usage: artemis chats [OPTIONS] COMMAND [ARGS]...

  Thread list/history and interactive chat (CLI channel / local DB).

Commands:
  list        List conversation threads for an agent.
  get         Show message history for a thread.
  create      Start a new thread (/new equivalent).
  update      Rename or pin a thread.
  delete      Delete a thread.
  send        Send one message and stream the response.
  repl        Interactive chat REPL (embedded server + CLI gateway channel).
```

`artemis chat` is a deprecated alias that prints a stderr warning and
forwards to `chats`.

## `artemis channel`

Local DB channel CRUD plus platform-specific bot creators. The
`wecom` / `weixin` / `feishu-setup` subcommands drive the QR-code
bot-creator flows; `config` is the offline config editor.

```
Usage: artemis channel [OPTIONS] COMMAND [ARGS]...

  Channel management commands.

Commands:
  list          List channels for an agent.
  get           Show one channel row.
  create        Create a channel.
  patch         Update a channel.
  delete        Delete a channel.
  test          Test a channel (instantiate → start → stop).
  config        Edit channel config offline.
  feishu-setup  Drive the Feishu bot-creator flow.
  bind          Bind-group helper for WeCom / Weixin (QR login, etc.).
```

## `artemis cron`

Local DB cron management. `run-now` requires a running `artemis run`
because the actual fire is dispatched through the live
`CronManager`.

```
Usage: artemis cron [OPTIONS] COMMAND [ARGS]...

  Cron job management commands.

Commands:
  list        List cron jobs for an agent.
  create      Create a cron job.
  delete      Delete a cron job.
  run-now     Trigger a cron job immediately.
```

`create --trigger` accepts cron expressions (`"0 9 * * *"`) and the
`interval:N` / `date:ISO8601` aliases. `--task-type text` pushes the
prompt verbatim; `--task-type agent` (default) runs the LLM and
pushes the reply. `--prompt` is required, must be non-empty and ≤
2000 characters.

## `artemis provider`

Local DB provider CRUD. `test` requires a running server.

```
Usage: artemis provider [OPTIONS] COMMAND [ARGS]...

  Provider management commands (local DB).

Commands:
  list      List providers.
  create    Create a provider.
  delete    Delete a provider.
  test      Ping the provider (requires running server).
```

## `artemis models`

Provider presets and active model management.

```
Usage: artemis models [OPTIONS] COMMAND [ARGS]...

  Model catalog and active-model settings.

Commands:
  presets       List built-in provider templates from harness-agent.
  list          List all resolved models across enabled providers.
  active        Show or set the global default model (admin).
  config        Interactively create a provider from presets and set the active model.
  ollama-list   List local Ollama models (requires a running server).
  ollama-pull   Pull a model via Ollama (requires a running server).
  ollama-rm     Remove a local Ollama model (requires a running server).
```

## `artemis skills`

Per-agent skill enable / disable. All subcommands need a running
server (the dashboard's Skill Hub and bundled `~/.artemis/skills/`
library are queried at boot).

```
Usage: artemis skills [OPTIONS] COMMAND [ARGS]...

  Manage agent skills (enable / disable / list).

Commands:
  list      List skills for an agent.
  enable    Enable a skill for the agent.
  disable   Disable a skill for the agent.
  config    Show / edit the per-agent skills config.
```

## `artemis admin`

Local DB admin operations. `rotate-jwt-secret` works without a
running server (it edits the SQLite secret row directly).

```
Usage: artemis admin [OPTIONS] COMMAND [ARGS]...

  Admin commands (local DB).

Commands:
  overview             Show admin overview (user count, agent state distribution).
  audit                Show audit log entries.
  providers            Global (admin) providers.
  rotate-jwt-secret    Rotate the JWT secret directly via the local DB.
```

## `artemis backup`

Export and restore Artemis backups. Works fully offline.

```
Usage: artemis backup [OPTIONS] COMMAND [ARGS]...

  Backup and restore database + local agent workspaces.

Commands:
  create     Create a backup archive (DB + workspaces + config).
  restore    Restore a backup archive into ~/.artemis.
  auto       Automatic backup status and one-shot run.
```

### `artemis backup auto`

Automatic backups are scheduled **inside** a running `artemis run` process
(via the same system-job mechanism as TLS renewal). Configure in
`config.json` under `backup`, with env overrides
`ARTEMIS_BACKUP_AUTO_ENABLED`, `ARTEMIS_BACKUP_SCHEDULE`,
`ARTEMIS_BACKUP_RETENTION_COUNT`, or via the dashboard Backup settings.

```
Usage: artemis backup auto [OPTIONS] COMMAND [ARGS]...

Commands:
  status  Print automatic backup settings from config.json.
  run     Create one automatic backup now and prune by retention.
```

Default schedule when enabled: `cron:0 4 * * *` (daily 04:00, server
timezone). Automatic archives are named `artemis-auto-backup-*.tar.gz`;
retention only deletes those files and never touches manual
`artemis-backup-*.tar.gz` archives.

## `artemis plugin`

Install and manage third-party plugins (drop into `~/.artemis/plugins/`).
The same plugin manager powers the dashboard's "Plugins" page.

Artemis also **seeds bundled plugins** into `~/.artemis/plugins/` during
`artemis init` and every `artemis run` start. They are listed in Admin →
Plugins but stay **globally disabled** until you turn them on. An id
already recorded in `config.json` → `bundled_plugins_seeded` is not
copied again after uninstall.

```
Usage: artemis plugin [OPTIONS] COMMAND [ARGS]...

  Install and manage plugins.

Commands:
  list       List installed plugins.
  install    Install a plugin (local path or git URL).
  uninstall  Remove an installed plugin.
  reload     Reload all installed plugins without restart.
```

## `artemis acp`

Expose an Artemis agent as a stdio JSON-RPC ACP server. Boots a
standalone Artemis server (reads `~/.artemis`); does **not** require
`artemis run` to be running.

```
Usage: artemis acp [OPTIONS]

  Run Artemis agent as ACP server (stdio).

Options:
  --agent TEXT   Agent to expose (default: ARTEMIS_AGENT or first agent).
  --debug        Log to stderr.
  -h, --help     Show this message and exit.
```

See [ACP integration](./acp.md) for the Zed setup example and the
runner object schema.

## `artemis clean`

Reset CLI state or wipe the whole `~/.artemis` tree. Destructive — read
the help carefully.

```
Usage: artemis clean [OPTIONS]

  Remove CLI state or wipe all of ~/.artemis.

Options:
  --state / --all       What to remove.
  --yes                 Skip the confirmation prompt.
  -h, --help            Show this message and exit.
```

## `artemis config`

Inspect / edit `~/.artemis/cli_state.json` (default base URL, user,
agent).

```
Usage: artemis config [OPTIONS] COMMAND [ARGS]...

  CLI state (base URL, defaults).

Commands:
  show       Print the current CLI state.
  set-user   Pin the default --user.
```

## `artemis completion` / `artemis version`

```text
$ artemis completion show bash   # dump a shell snippet
$ artemis completion install     # append to ~/.zshrc / ~/.bashrc
$ artemis version                # print the installed artemis version
```

## CLI state file

`~/.artemis/cli_state.json` stores:

```json
{
  "base_url": "http://127.0.0.1:8088",
  "token": null,
  "default_user": null,
  "default_agent": null
}
```

The path is exposed as `artemis.cli.support.state.default_state_path()`
and can be overridden via `ARTEMIS_HOME`. Delete the file to log out
the CLI without hitting the server. The dashboard and HTTP callers
do not share this file — they manage their own tokens.
