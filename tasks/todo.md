# 2026-03-25 Project Analysis, Refactor, and Modernization Plan

## Scope
- [x] Inspect repository structure, key entry points, and existing documentation
- [x] Identify concrete correctness risks, structural refactor targets, and modernization blockers
- [x] Define an execution order with verification gates for a follow-up implementation pass

## Current Snapshot
- [x] Repository is centered around two large modules: `main.py` (2830 lines) and `gui_previewer.py` (2377 lines)
- [x] `main.py` concentrates most application responsibilities inside `GFXManager` starting at line 1357
- [x] `gui_previewer.py` combines parsing, scripted GUI support, rendering, and widget composition in one file
- [x] There is no `pyproject.toml`, `requirements.txt`, `.gitignore`, or test suite in the repository root
- [x] Git currently tracks `__pycache__/*.pyc`, which indicates missing repo hygiene automation
- [x] Local verification is blocked by environment drift: `python` and `py` are not available on PATH in this workspace

## Key Findings
- [x] P1 correctness risk: DDS fallback writes PNG data under a `.dds` filename in [`main.py:114`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L114), [`main.py:130`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L130), [`main.py:137`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L137), and [`main.py:141`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L141)
- [x] P1 maintainability risk: `GFXManager` spans 1487 lines and mixes UI composition, persistence, drag-and-drop, file IO, reporting, and analysis in [`main.py:1357`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L1357)
- [x] P1 maintainability risk: parser and renderer logic are tightly coupled across [`gui_previewer.py:116`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/gui_previewer.py#L116), [`gui_previewer.py:617`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/gui_previewer.py#L617), and [`gui_previewer.py:1351`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/gui_previewer.py#L1351)
- [x] P2 data safety risk: `save_gfx_to_file()` mutates `.gfx` files through raw string insertion based on the last `}` in [`main.py:2239`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L2239) and [`main.py:2264`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L2264), which is fragile for nested or malformed content
- [x] P2 observability risk: broad `try/except Exception` and `print()` diagnostics are used throughout both main modules, which makes failures hard to surface consistently in the GUI
- [x] P2 documentation drift: README still describes the GUI previewer as incomplete and lists removing scripted GUI support as TODO while the current code invests heavily in that area in [`README.md:26`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/README.md#L26) and [`README.md:199`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/README.md#L199)
- [x] P2 dependency drift: README install guidance still uses ad-hoc `pip install ... pywavelets` with no lockfile or environment bootstrap, and `pywavelets` is not referenced in the repository in [`README.md:125`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/README.md#L125)
- [x] P3 tooling drift: `.mcp.json` shells out to `python`, but this machine currently has no `python` command available, so auxiliary tooling is out of sync with the environment

## Modernization Targets
- [x] Introduce a reproducible environment definition
  - Added `pyproject.toml` with project metadata, dependency groups, and executable entry points
  - Pinned runtime dependencies for PyQt6, Pillow, numpy, and opencv-python
  - Replaced ambiguous README install snippets with one supported bootstrap flow
- [x] Choose and document a supported Python baseline
  - Standardized the current support target on Python 3.13.x
  - Documented that Python 3.14 validation is deferred to a later phase
- [x] Add repository hygiene defaults
  - Added `.gitignore` for `__pycache__/`, virtual environments, editor state, and generated reports
  - Removed tracked bytecode artifacts from git index while leaving local files untouched
- [ ] Add automated verification
  - Expanded `scripts/check.ps1` into a baseline compile-plus-test command
  - Added focused parser-free DDS regression tests that avoid full GUI boot
  - Added DDS regression coverage for encoder failure, invalid header output, valid DDS header retention, and `convert_image()` error propagation
  - Next add unit tests around GFX file rewrite behavior and GUI parser extraction
  - Add CI for lint, static compile, and tests on Windows

## Refactor Plan
- [ ] Phase 1: stabilize correctness before reshaping architecture
  - Replaced fake DDS fallback behavior with explicit failure plus DDS header validation and failed-output cleanup
  - Guard file rewrite operations with parser-style block handling and backup-safe writes
  - Replace silent prints with structured logging plus GUI-facing error reporting
- [ ] Phase 2: extract non-UI services from `main.py`
  - Create `services/image_conversion.py`
  - Create `services/gfx_repository.py` for parse/save/remove operations
  - Create `services/analysis.py` for GFX usage scanning and report generation
  - Keep Qt dialogs thin and move business logic behind testable APIs
- [ ] Phase 3: split GUI previewer by responsibility
  - Separate scripted GUI parsing, GUI layout parsing, rendering, and preview widgets into distinct modules
  - Define shared dataclasses and typed contracts for parsed GUI elements
  - Decide whether scripted GUI support stays as a supported feature or is removed; align README and code accordingly
- [ ] Phase 4: modernize app shell
  - Introduce a dedicated app package layout such as `src/hoi4_gfx_manager/`
  - Move startup code into a small `main.py` wrapper and keep package imports explicit
  - Centralize settings, project persistence, and path utilities

## Verification Gates For Follow-up Work
- [ ] Gate 1: repository bootstraps from a clean environment using one documented command
- [ ] Gate 2: DDS conversion tests prove output files are valid for both success and failure paths
- [ ] Gate 3: `.gfx` write operations preserve structure on representative sample files
- [ ] Gate 4: parser tests cover both `hoi4/*.gui` fixtures and scripted GUI edge cases
- [ ] Gate 5: README, package metadata, and actual runtime commands match

## Recommended Execution Order
- [x] 1. Add packaging and environment bootstrap files so the project becomes runnable and testable again
- [x] 2. Fix the DDS fallback defect and add regression coverage
- [x] 3. Add `.gitignore`, stop tracking bytecode, and establish baseline compile/test commands
- [ ] 4. Extract `ImageConverter` and GFX file persistence into services
- [ ] 5. Extract analysis worker logic behind a pure service boundary
- [ ] 6. Split `gui_previewer.py` into parser, model, renderer, and widget modules
- [ ] 7. Refresh README and release/versioning once code paths and supported features are settled

## Review / Result
- [x] Analysis completed from local repository evidence
- [x] Concrete risks identified with line anchors for follow-up implementation
- [x] Modernization plan written as an ordered checklist with verification gates
- [x] Stage 1 executed: added `pyproject.toml`, bootstrap/run/check PowerShell scripts, and aligned README installation guidance
- [x] Stage 2 executed: DDS conversion now fails closed, removes invalid output, and has regression tests under `tests/test_dds_conversion.py`
- [x] Stage 3 executed: added `.gitignore`, removed tracked `__pycache__` artifacts from git, and set `scripts/check.ps1` to run compile plus unittest discovery
- [x] Residual limitation: runtime verification is still blocked in this environment because no Python interpreter is available on PATH, so Gates 1 and 2 remain unproven locally
