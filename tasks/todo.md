# 2026-03-25 Project Analysis, Refactor, and Modernization Plan

## Current Execution: Remove HOI4 GUI Feature Set
- [x] Identify remaining GUI preview/parsing hooks in app code, docs, packaging, and tests
- [x] Remove GUI preview module, app tab wiring, and sample GUI assets
- [x] Update README, packaging, and verification commands to reflect GUI removal
- [x] Verify no GUI preview feature references remain outside historical task notes

## Scope
- [x] Inspect repository structure, key entry points, and existing documentation
- [x] Identify concrete correctness risks, structural refactor targets, and modernization blockers
- [x] Define an execution order with verification gates for a follow-up implementation pass

## Current Snapshot
- [x] Repository is now centered around `main.py`, with the separate HOI4 GUI preview module removed from the root package
- [x] `main.py` concentrates most application responsibilities inside `GFXManager` starting at line 1359
- [x] HOI4 GUI preview/parsing code has been removed from the application shell and sample assets
- [x] There is no `pyproject.toml`, `requirements.txt`, `.gitignore`, or test suite in the repository root
- [x] Git currently tracks `__pycache__/*.pyc`, which indicates missing repo hygiene automation
- [x] Local verification is blocked by environment drift: `python` and `py` are not available on PATH in this workspace

## Key Findings
- [x] P1 correctness risk: DDS fallback writes PNG data under a `.dds` filename in [`main.py:113`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L113), [`main.py:128`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L128), [`main.py:133`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L133), and [`main.py:134`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L134)
- [x] P1 maintainability risk: `GFXManager` still mixes UI composition, persistence, drag-and-drop, file IO, reporting, and analysis in [`main.py:1359`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L1359)
- [x] P1 scope reduction: HOI4 GUI preview/parsing paths were removed entirely instead of being further modularized
- [x] P2 data safety risk: `save_gfx_to_file()` mutates `.gfx` files through raw string insertion based on the last `}` in [`main.py:2233`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L2233) and [`main.py:2258`](/C:/Users/Administrator/Documents/Code/HOI4GFXManager/main.py#L2258), which is fragile for nested or malformed content
- [x] P2 observability risk: broad `try/except Exception` and `print()` diagnostics remain in `main.py`, which makes failures hard to surface consistently in the GUI
- [x] P2 documentation drift: README and packaging had to be realigned again after fully removing HOI4 GUI preview support
- [x] P2 dependency drift: baseline environment guidance now lives in `pyproject.toml` and PowerShell scripts, but `.mcp.json` still assumes a bare `python` command in this workspace
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
  - Next add unit tests around GFX file rewrite behavior and analysis/report extraction
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
- [x] Phase 3: remove HOI4 GUI preview feature set
  - Keep Scripted GUI support removed and avoid reintroducing separate scripted parser paths
  - Remove the plain `.gui` preview module, app tab wiring, and GUI-specific sample assets
  - Align README, packaging, and tests around the reduced feature surface
- [ ] Phase 4: modernize app shell
  - Introduce a dedicated app package layout such as `src/hoi4_gfx_manager/`
  - Move startup code into a small `main.py` wrapper and keep package imports explicit
  - Centralize settings, project persistence, and path utilities

## Verification Gates For Follow-up Work
- [ ] Gate 1: repository bootstraps from a clean environment using one documented command
- [ ] Gate 2: DDS conversion tests prove output files are valid for both success and failure paths
- [ ] Gate 3: `.gfx` write operations preserve structure on representative sample files
- [ ] Gate 4: updated docs and package metadata no longer advertise or import removed HOI4 GUI preview features
- [ ] Gate 5: README, package metadata, and actual runtime commands match

## Recommended Execution Order
- [x] 1. Add packaging and environment bootstrap files so the project becomes runnable and testable again
- [x] 2. Fix the DDS fallback defect and add regression coverage
- [x] 3. Add `.gitignore`, stop tracking bytecode, and establish baseline compile/test commands
- [x] 4. Remove Scripted GUI functionality completely and keep plain `.gui` preview only
- [x] 5. Remove the remaining plain `.gui` preview module, wiring, and sample assets
- [ ] 6. Extract analysis worker logic behind a pure service boundary
- [ ] 7. Refresh README and release/versioning once code paths and supported features are settled

## Review / Result
- [x] Analysis completed from local repository evidence
- [x] Concrete risks identified with line anchors for follow-up implementation
- [x] Modernization plan written as an ordered checklist with verification gates
- [x] Stage 1 executed: added `pyproject.toml`, bootstrap/run/check PowerShell scripts, and aligned README installation guidance
- [x] Stage 2 executed: DDS conversion now fails closed, removes invalid output, and has regression tests under `tests/test_dds_conversion.py`
- [x] Stage 3 executed: added `.gitignore`, removed tracked `__pycache__` artifacts from git, and set `scripts/check.ps1` to run compile plus unittest discovery
- [x] Stage 4 executed: removed Scripted GUI parser/UI/rendering paths and updated docs to match plain `.gui` preview support
- [x] Stage 5 executed: removed the remaining plain `.gui` preview module, its app wiring, related sample assets, and matching package/doc/test references
- [x] Residual limitation: runtime verification is still blocked in this environment because no Python interpreter is available on PATH, so Gates 1, 2, 4, and 5 remain unproven locally
