# Perseus Agent

A lightweight AI agent for **Termux (Android)**. All reasoning goes through a
provider API (OpenAI-compatible) — no local model, GGUF, ONNX, or CPU inference.

Created by **Mayugoro** (github.com/mayugoro).

> **Not a Hermes fork.** Perseus is a standalone project that borrows the same
> *UX concept* as Hermes (slash commands, status bar, sessions, skills), but the
> code is independent and focused on **Android only**. Perseus can read/inspect
> files and drive the shell/terminal; on a **rooted** device it runs with
> superuser (root) privileges, which is what unlocks its full, unrestricted
> capability on Android.

This repo ships **configuration-free**: base URL, model, and API key are set by
you on first setup. No provider is hardcoded.

## Install

```bash
pkg install -y git
git clone https://github.com/mayugoro/Perseus-Agent.git
cd Perseus-Agent
./install.sh
```

`install.sh` will:

1. install `python`, `git`, `expat`, and the Python dependency (`prompt_toolkit`)
   from `requirements.txt`
2. run the wizard: **Base URL** + **API key**; the model list is fetched from
   `{base_url}/models` and you pick from it
3. create the `perseus` launcher in `$PREFIX/bin`

Then:

```bash
perseus
```

## Manual setup

```bash
python3 perseus.py --init      # first-time provider wizard
python3 perseus.py model       # change provider / model / API key
python3 perseus.py             # REPL
python3 perseus.py -p "hello"  # one-shot command
```

If already installed:

```bash
perseus model
```

Config is stored at `~/.perseus/config.json` (0600). The API key can be stored
there, or left empty and provided via environment:

```bash
export PERSEUS_API_KEY='...'
```

## UI

- Perseus responses and turn separators are cyan/blue (same as the logo).
- The `[think]` block stays gray/dim.
- Tool calls are shown as blue `</tool>`.
- `❯` prompt with a status bar: model, context usage, response duration, session
  duration, and hints `/ commands · @ files · ! shell`.
- The context limit is auto-detected from `context_length` in `GET /models`
  (e.g. a 1M-token model shows `1000k`), not a hardcoded number.
- The status bar does not force a per-second refresh (which would yank the
  scroll view back to the bottom); numbers update on new input/turn.
- `/usage` shows estimated tokens, context, duration, reasoning, and steps.
- `!command` runs a shell command directly; `@file` attaches a workspace file
  to the message.
- `/copy` copies the last reply to the clipboard. Python handles the agent;
  the small `ui/` Node/TypeScript helper is used only for capabilities Python
  lacks on Termux (clipboard, notification, terminal highlight).

## REPL commands

Type `/` — the command list appears automatically (`prompt_toolkit` completion,
TTY required). Tab/arrows to choose, Enter to run.

```
/help                      help
/tools                     list tools
/new                       reset conversation
/mode ask|auto|read|full   permission mode
/model [id]                show provider + pick model + reasoning
/queue [task|run|rm N|clear]  task queue
/yolo                      toggle dangerous-tool confirmation
/reasoning [level]         default|low|medium|high
/think                     show/hide reasoning block
/learn                     auto-learn on/off
/curator                   auto-skill after complex tasks
/agents [on|off|max N]     parallel subagents
/steps [N]                 tool step limit (0/default = unlimited)
/sessions                  list saved sessions
/resume <N|id|title>       resume a session
/title [text]              set session title
/session                   active session info
/memory                    show profile + working memory
/forget <id>               delete a memory entry
/exit
```

`max_steps` defaults to **0 = unlimited**. Identical tool calls are skipped
after 3 repeats to avoid loops. Set a manual bound with `/steps 40` (0–500).
When the limit is hit, Perseus is asked to summarize progress instead of
returning an empty message.

`/model` with no argument shows the provider, current model, and the model list
from `/models`; pick a number or type an id. After choosing, the wizard asks for
a reasoning level (`default/low/medium/high`) sent as `reasoning_effort` — only
for models that support it. Or set it directly: `/reasoning high`.

`/queue <task>` adds a task, `/queue` lists, `/queue run` runs them in order,
`/queue rm N` and `/queue clear` manage. The queue persists in
`~/.perseus/queue.json`.

## Sessions

Sessions are stored in **SQLite + FTS5**: `~/.perseus/state.db`
(tables `sessions`, `messages`, `messages_fts`).

- `/sessions` — table: number | title | last used | first message
- `/sessions <word>` — search conversation content via FTS5
- `/resume N` / `/resume <id>` / `/resume <title>` — load session context and
  show the last 6 messages
- `/title <text>` — set the session title (shown in `/sessions` and `/exit`)
- `/session` — active session ID
- On `/exit`, Perseus prints a session summary + resume command

Resume from the shell:

```bash
perseus -c 20261118-204418-715     # full id
perseus -c "coffee chat"           # session title
# on resume, the last 6 messages are shown
perseus -c 20261118               # id prefix (latest match)
perseus -resume 20261118-204418-715
perseus -c <id> -p "continue the task"

perseus sessions list              # list sessions
perseus sessions search <word>     # search conversation content
perseus sessions <id|title>        # open a session (detail + last 6 messages)
perseus resume <id|title>          # jump straight into a session
```

Legacy JSONL files in `~/.perseus/sessions/` are migrated automatically once
the DB is first opened, then no longer written.

## Learning loop

- **User profile** and **working memory** are separated (`kind=profile` /
  `memory`); the profile is injected as its own block in the system prompt.
- **Consolidation**: near-duplicate facts (Jaccard >= 0.75) are merged on save.
- **Selective auto-learn**: only user facts/conventions; praise, small talk, and
  meta facts about Perseus (skill count, context, internals) are discarded.
- `/memory` shows profile + working memory; `/forget <id>` deletes an entry.
- **Automatic session search**: relevant old-session snippets are found via FTS
  and injected as "past session context".
- **Curator**: after a task using >= `curator_min_tools` (default 4) tools,
  Perseus asks the model to summarize the procedure into a markdown skill saved
  to `~/.perseus/skills/`. Toggle with `/curator`.
- **Live subagents**: each subagent gets a tag `[A1]`, `[A2]`, … so its tool
  progress is visible while running.

## YOLO

`/yolo` (or `/yolo on|off`) disables confirmation for dangerous tools —
equivalent to auto-approve in Hermes. The previous permission mode is restored
on `/yolo off`. `YOLO` status shows in the banner and status bar.

## Thinking & responding

- Responses stream (SSE): text appears token by token.
- While waiting, a spinner `⠋ thinking…` shows (TTY only).
- The `[think]` block appears only for real reasoning (length >=
  `min_think_chars` 200, or >= 2 lines); short directives like "respond briefly"
  are hidden. `/think` toggles the whole block.
- Perseus does not refuse requests or add moral/security disclaimers; it does
  what is asked if a tool exists, otherwise explains the technical reason.
- `auto_learn` (default on): after an answer, one lightweight call extracts up
  to 2 durable facts → stored in SQLite, injected into the next session.
- `skill_save` writes a procedure to `~/.perseus/skills/`; the skill list is
  indexed in the system prompt and loaded in full via `skill_view`.
- Context limit follows the model: read from `GET /models` at start and on every
  `/model`, so switching models updates the limit automatically.
- Token-based compression: when estimated tokens exceed `compress_at` (default
  70% of the model context), old messages are summarized and only the last 12
  kept. `context_messages` (36) is a belt-and-suspenders guard.

## Parallel subagents

The model can call `delegate_task` to run multiple subagents at once. Each
subagent has its own context, same model, and separate session — so it can
"think on its own" and results are merged.

Config in `~/.perseus/config.json`:

```json
"subagents": {"enabled": true, "max_parallel": 3, "permission": "auto"}
```

Or via REPL: `/agents`, `/agents on|off`, `/agents max N`,
`/agents permission auto|read`. Safe range 1–8; subagents cannot delegate
again (anti-recursion).

## Tools

- **File**: `read_file`, `write_file`, `patch_file`, `list_dir`, `search_files`
- **System**: `shell`, `python_exec`, `http_fetch`
- **Memory**: `memory_save`, `memory_search` (SQLite + FTS5)
- **Android**: `android_list_apps`, `android_app_info`, `android_install`,
  `android_uninstall`, `android_launch`, `android_logcat`
- **Skills**: `skill_list`, `skill_view`, `skill_save` (folder `skills/*.md`)

## Security

- Workspace jail: default `~/perseus-workspace`; paths outside are rejected
- `ask` mode: dangerous tools (write/delete/install/uninstall) require confirmation
- Automatic backup of overwritten files to `.perseus/backups/`
- Audit trail: sessions in `~/.perseus/state.db`

## Provider errors

If the upstream fails (network, timeout, 429, 5xx), Perseus retries **3× with a
15 s delay** (`retries`, `retry_delay` in config). 400/401/403/404 are not
retried (config/model errors). After all attempts fail, the error is shown but
the **session stays alive** — the prompt returns and you can continue.

## Limitations

- Requires connectivity; no offline mode
- `pm install` may be rejected by some PackageManagers → fall back to UI
  installer / SAI
- Without root, install/uninstall follows Android shell permissions
- Processes can be killed by Doze; use `termux-wake-lock` when needed

## License

MIT