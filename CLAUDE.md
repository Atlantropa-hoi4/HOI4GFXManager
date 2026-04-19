# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Supported environment

- Python baseline is **3.13.x** (`requires-python = ">=3.13,<3.14"`). Python 3.14 is deliberately not yet validated — don't upgrade the pin without running the full check pipeline.
- Primary platform is Windows; all workflow scripts are PowerShell (`.ps1`). When running in WSL/Linux, replicate their steps manually — there are no Bash equivalents.

## Common commands

All commands assume Windows PowerShell from the repo root:

```powershell
# First-time setup (creates .venv, installs -e .[dev])
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -IncludeDev

# Launch the PyQt6 app
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1

# Baseline verification: compileall + unittest discover
powershell -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

Override the interpreter when `py -3.13` isn't available:

```powershell
.\scripts\bootstrap.ps1 -PythonExe C:\Path\To\python.exe -IncludeDev
```

Run a single test directly (after bootstrap):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_dds_conversion.ImageConverterDDSTests.test_save_as_dds_keeps_valid_dds_output
```

Entry points installed by `pip install -e .`:
- `hoi4-gfx-manager` → `hoi4_gfx_manager.app:main` (GUI)
- `hoi4-focus-shine` → `focusgfxshine:main` (CLI utility)

The legacy top-level `main.py` is a 5-line wrapper that re-exports `hoi4_gfx_manager.app.main`; it's kept only so `python main.py` still works.

## Architecture

Source lives under `src/hoi4_gfx_manager/` (src-layout). `focusgfxshine.py` is the only remaining top-level module.

### `hoi4_gfx_manager/` layout

```
src/hoi4_gfx_manager/
├── app.py                    # QApplication bootstrap + main()
├── services/                 # Qt-free business logic
│   ├── image_conversion.py   # ImageConverter: PNG/JPG/BMP/DDS (cv2.imwrite + DDS magic validation)
│   ├── gfx_repository.py     # scan_mod_folder / save_gfx_to_file / remove_gfx_from_file / update_gfx_texture_path
│   ├── analysis.py           # analyze_mod_folder() pure fn + AnalysisWorker QThread wrapper
│   └── focus_shine.py        # FocusGFXShineGenerator (shared with focusgfxshine.py CLI)
└── ui/                       # Qt-aware layer
    ├── main_window.py        # GFXManager(QMainWindow): assembly + service dispatch only
    ├── theme.py              # DARK_STYLESHEET, IMAGE_PLACEHOLDER_STYLE, IMAGE_EXTENSIONS
    ├── tree_widget.py        # GFXTreeWidget (custom drag-drop)
    └── dialogs/              # One file per workflow dialog
        ├── batch_convert.py, batch_import.py, drag_drop.py,
        ├── focus_shine.py, gfx_edit.py, project_manager.py
```

Rules of thumb:
- **New business logic** (file IO, parsing, conversion) goes in `services/`. No `PyQt6` imports there.
- **New UI workflows** get their own `ui/dialogs/*.py` file; `GFXManager` only wires them.
- `ImageConverter`, `AnalysisWorker`, `FocusGFXShineGenerator`, `GFXTreeWidget`, `GFXManager`, and all six dialog classes are the stable public API — preserve names on further refactor.

### DDS conversion contract

`services/image_conversion.py:ImageConverter._save_as_dds` **must validate the `DDS ` magic header** (`DDS_MAGIC = b"DDS "`) before accepting output. On encoder failure or wrong magic, delete the partial file and raise `RuntimeError`. Regression tests in `tests/test_dds_conversion.py` pin this contract.

### `focusgfxshine.py` is independent

Standalone CLI that injects missing `_shine` entries into a `goals_shine.gfx` file. It still lives at the repo root (not inside the package) and has no GUI dependencies. The GUI's `FocusShineDialog` uses `hoi4_gfx_manager.services.focus_shine.FocusGFXShineGenerator` — keep the two in sync if you change the generator logic.

### `hoi4/welcome_splash.gfx`

The only shipped sample asset. Tests and packaging expect it to stay.

## Testing pattern (important)

`tests/test_dds_conversion.py` uses a **stub-injection pattern**: before importing `hoi4_gfx_manager.services.image_conversion`, it populates `sys.modules` with fake `PyQt6`, `cv2`, `numpy`, and `PIL` modules (see `ensure_dependency_stubs()`). The test also inserts `src/` into `sys.path` so the package resolves without `pip install -e .`. This lets unit tests run without a real Qt/OpenCV install.

When adding tests that touch the package:
- Reuse `ensure_dependency_stubs()` — don't import the services at module top level in a new test file without it.
- If your test exercises new Qt widgets/functions, extend the `widget_names` / `core_names` / `gui_names` lists rather than importing the real classes.
- Patch through the module-bound names (e.g. `image_conversion.cv2`, `image_conversion.np`, `image_conversion.Image`), not the stub modules directly.

`check.ps1` runs `compileall` + `unittest discover -s tests -p "test_*.py"`. It does not run `ruff` or `pytest` despite both being in `[dev]` — add them explicitly if needed.

## Active refactor context

`tasks/todo.md` and `tasks/lessons.md` record the modernization history. Current state:

- Phase 1 (DDS failure handling) — **done**, protected by regression tests.
- Phase 2 (extract `services/image_conversion.py`, `services/gfx_repository.py`, `services/analysis.py`) — **done**.
- Phase 3 (split dialogs into `ui/dialogs/`, slim `GFXManager` to assembly) — **done**.
- A prior HOI4 GUI preview feature was fully removed. Do not reintroduce `.gui` parsing or preview paths — that decision was deliberate and repeated corrections are logged in `tasks/lessons.md`.
- `services/gfx_repository.save_gfx_to_file` rewrites `.gfx` files by locating the last `}` — still flagged as fragile for nested/malformed content. Prefer parser-based handling for any new write paths.

## Reference drift to watch

- `.mcp.json` shells out to bare `python`. This is known-broken on machines where only `py -3.13` is available and is tracked as tooling drift — don't "fix" it by changing other code to match.
- README advertises v2.1 but `pyproject.toml` version is authoritative.
