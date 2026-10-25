# AGENTS.md

Guidance for coding agents working in this repository. Human-facing
documentation lives in `README.md`; this file covers how the code is put
together and what must not break.

## What this is

An `on_change_hook` for
[kde-material-you-colors](https://github.com/LuisBocanegra/kde-material-you-colors)
(KMYC). KMYC writes a Material 3 palette to `/tmp/kde-material-you-colors-$USER.json`;
`hook/apply.py` reads it, builds a `Palette`, and asks every target module to
render theme files for one app.

Nothing here is a library or a daemon. It is a single-shot CLI invoked on
palette change (and manually), plus a set of pure-ish render functions.

## Non-negotiables

- **Standard library only.** No pip dependencies, no vendored Python packages.
  `hook/localstorage.py` exists so the project does not need `plyvel`.
- **No network.** The hook reads KMYC's local JSON and writes local files. Do not
  add downloads, telemetry, or version checks.
- **Write only under `$HOME`** (via `Path.home()` / `XDG_*` / `tempfile.gettempdir()`).
  Never write `/etc`, `/usr`, or anything requiring root; never call `sudo`.
- **Every write goes through `ctx.write()` or `managed.atomic_write()`.** Direct
  `Path.write_text()` skips atomicity and leaves `state.json` without a hash, so
  the next run rewrites the file forever.
- **Back up before the first edit** of a user-owned file: `managed.backup_once()`
  (single files) or `hook/targets/hayase.py::_backup` (directories). Never delete
  or rewrite a file that carries the `kde-material-you-colors hook` marker into a
  backup.
- **`--dry-run` must stay side-effect free**: no writes, no backups, no
  subprocesses that mutate state, no reloads. Log instead.
- **One target failing must not abort the run** — raise inside the target, let
  `apply.py` catch and log it.
- **Vendored theme templates stay byte-identical** to upstream
  (`hook/templates/discord-*.css`). They are rendered at runtime through
  `{{ … }}` expressions; do not hand-edit them, and update
  `THIRD-PARTY-NOTICES.md` if the set changes.

## Layout

```
hook/apply.py        CLI, flock, state, target loop, reload pass
hook/context.py      Context: palette, raw JSON, changed/files maps, ctx.write()
hook/mycolors.py     OKLab/OKLCH, WCAG contrast, Palette (+ ANSI slots), load_palette
hook/template.py     {{ colors.<role>.<mode>.<fmt> }} / {{ mode }} renderer
hook/managed.py      atomic_write, write_if_changed, backup_once, set_key_line,
                     set_arg_line, file_hash, log(), rotate_log
hook/localstorage.py Chromium LevelDB reader/writer (Hayase)
hook/targets/        one module per surface; registry in targets/__init__.py
hook/templates/      theme templates consumed by targets (Discord, Pear, Hayase)
hook/archive/        retired targets — not imported, not registered
```

Runtime artifacts (git-ignored, never commit): `hook/state.json`, `hook/.lock`,
`hook/backups/`, `__pycache__/`, and `config.conf`.

## Execution model

`apply.py` main, in order:

1. `argparse`; `--list` prints `targets.ORDER` names and exits.
2. `flock` on `hook/.lock` (non-blocking). A second instance prints to stderr and
   exits `0` — concurrent runs are a no-op, not an error.
3. Read the KMYC JSON (`--json` → `KMYC_JSON` → `/tmp/kde-material-you-colors-$USER.json`),
   retrying 3× with 0.3 s sleeps; build `Palette` via `load_palette()`.
4. Short circuit: unless `--force`/`--dry-run`, skip everything when
   `state.json`'s palette digest matches **and** every recorded file still hashes
   the same (`up_to_date()`).
5. Per target: `available(ctx)` gate (usually "config dir exists") → `apply(ctx)`.
   Exceptions are logged with traceback and counted, never re-raised.
6. Second pass calls the optional `reload(ctx)` hook (SIGUSR2, `bat cache --build`,
   pywalfox poke, log-only for fish/firefox).
7. Save `state.json` (`palette` digest, `files` path→sha256 prefix, `variant`)
   **only when no `--only` was given** and not in dry-run.

Exit codes: `0` ok, `1` failure (bad/missing JSON, or any target raised; dry-run
also returns `1` on failure), `2` unknown `--only` name.

Targets receive `Context` and must be idempotent: same palette in, same bytes
out.

## Adding or changing a target

1. Create `hook/targets/<name>.py` with:
   - module docstring: which app file(s) are written, the config key involved,
     and any app-side switch the user must enable;
   - `NAME = "<kebab-case>"`;
   - `available(ctx) -> bool` — cheap existence check, no side effects;
   - `apply(ctx) -> None` — render, `ctx.write(...)`, then `managed.set_key_line` /
     `set_arg_line` for config keys, followed by `ctx.track(path)`;
   - optional `reload(ctx) -> None` — only when the app supports live reload,
     guard it with `ctx.any_changed()` / specific `ctx.changed[...]` keys.
2. Register the module in `hook/targets/__init__.py`: import it and add it to
   `ORDER` (files first, expensive work such as `bat cache --build` last).
3. Templates go in `hook/templates/`; render them with `template.render(...)` and
   prepend the managed marker header like `hook/targets/discord.py` does.
4. Verify (see below) and document the target in the README table.

Do not introduce a base class, plugin discovery, or a config file for targets —
the registry list is the extension point.

## Code conventions

- `from __future__ import annotations` at the top of every module; Python ≥ 3.9.
- 4-space indent, `black`-compatible formatting, double quotes, trailing commas
  in multi-line literals.
- Comments explain *why* (app loader quirks, ordering, specificity), never what.
  Docstrings state the observable contract and app-side requirements.
- Logging via `managed.log()`; `debug` for skipped targets, `info` for writes and
  reloads, `warning` for degraded outcomes, `error` for target failure (handled in
  `apply.py`).
- Subprocesses: full argument list, `capture_output=True`, `check=False`,
  `timeout=` set, failures downgraded to `warning`. Never shell out with `shell=True`.
- File contents are compared before writing (`write_if_changed`) — do not add a
  code path that rewrites unconditionally, or `state.json` becomes meaningless
  and editors reload pointlessly.

## Template rules

`hook/template.py` implements only Noctalia's expression subset:
`{{ colors.<role>.<default|dark|light>.<format> }}` and `{{ mode }}`. Roles are
snake_case (`on_surface_variant` → `onSurfaceVariant`). Formats: `hex`,
`hex_stripped`, `rgb`, `rgb_csv`, `rgba`, `hsl`, `hsla`, `red`, `green`, `blue`,
`alpha`, `hue`, `saturation`, `lightness`. Unknown expressions are emitted as
`{{UNKNOWN:…}}` and logged — never silently substituted. Extending the grammar
means extending `KNOWN_FORMATS`/`render` **and** the docstring.

Palette invariants: ANSI slots follow the Noctalia `fixed_palette.cpp` mapping;
foregrounds pass `ensure_contrast(..., 4.5)` against `background`; bright slots
reuse normal hues except 0 and 7. Changing the mapping changes every terminal
theme — treat it as a breaking change.

## Verification

There is no test suite; verify against a real palette instead:

```bash
python3 hook/apply.py --list
python3 hook/apply.py --dry-run --verbose        # must exit 0, no writes
python3 hook/apply.py --only <name> --force -v   # exercise one target
python3 hook/apply.py --only <name> --force      # second run: no diffs, exit 0
```

Then inspect the generated file(s) named in the target docstring and the log at
`~/.local/share/kde-material-you-colors/hook.log`. For rendered templates, grep
the output for `{{UNKNOWN:` — any hit is a bug in the role/format name.

Before finishing a change: `git status --short` must show only intended files,
and no `state.json`/`backups/`/`config.conf` may be staged.

## Public-repo hygiene

- License is MIT (`LICENSE`); vendored theme provenance is in
  `THIRD-PARTY-NOTICES.md`. Do not add CSS copied from a repository without a
  license — `discord-material.css` is the known gray area and must keep its
  explicit note.
- Never commit secrets, absolute `/home/<user>` paths, hostnames, or generated
  theme output. Paths are always derived at runtime.
- Commit messages: imperative subject, one logical change, body explains the
  app behaviour that motivated it.
