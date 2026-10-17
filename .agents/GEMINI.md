# SpyQR Project Guidelines, Cross-Project Standards & Learnings

## 0. Project Startup & Synchronization Protocol
- **Inspect Project Guidelines First**: Upon entering or starting work on any project, always examine the guidelines, rules, and documentation inside the `.agents/` folder (`.agents/GEMINI.md`, `.agents/instructions.md`, `.agents/flet.md`, and `.agents/rules/*.md`).
- **Cross-Project Knowledge Synchronization**: Any general development rules, Flet learnings, packaging optimizations, or documentation standards found in other projects under `c:\Users\alekos\pyAlekos\` must be incorporated and respected here.
- **Check Git / GitHub Synchronization**: Always verify the synchronization status of the project via `git fetch`, `git status -uno` / `gh repo sync` / `git pull`. If the local repository is behind the remote, pull/sync updates before making any code changes.

## 1. README.md & Release Notes Standards & Guidelines (STRICT)

### ❌ STRICTLY FORBIDDEN IN `README.md` & RELEASE NOTES:
- **NO English `README.md`**: `README.md` and GitHub Release Notes MUST ALWAYS be written in **Greek** (Ελληνικά).
- **NO Execution or Compilation Commands**: NEVER include code execution instructions (`uv run ...`, `python main.py`, `flet run`, etc.), syntax for running commands, or compilation details (PyInstaller parameters, build commands) in `README.md`.
- **NO Project Structure Trees**: NEVER include project folder/directory tree structures (`├── src/`, etc.) in `README.md`.
- **NO Creator Links in `README.md` or Release Notes**: NEVER include links or references to creator portfolio / personal websites in `README.md` or GitHub Release Notes (creator links belong inside the application UI only, if requested).
- **NO Version Tags/Numbers/Comments in `README.md`**: NEVER include version tags (e.g. `(v0.2.2)`), version numbers, or versioning rule comments in `README.md` titles or feature bullet points.
- **NO Deleting Historical Features**: NEVER delete existing application features when documenting new updates.
- **NO Placeholder Content**: NEVER leave broken links, dummy text, or unverified instructions.

### ✅ ALLOWED & REQUIRED IN `README.md`:
- **Greek Language**: Both `README.md` and GitHub Release Notes must be written in Greek.
- **Standard Clean Layout**:
  1. `# SpyQR 🔍📱` (Title & Emoji — NO version number)
  2. `> [Σύντομη Περιγραφή / Tagline]`
  3. `## 🌟 Χαρακτηριστικά` (Feature bullets without version tags)
  4. `## 🛠️ Αντιμετώπιση Προβλημάτων & Οδηγίες` (Troubleshooting & practical usage notes)

## 2. Versioning & Release Rules
- **Strict Increments (+0.0.1) with Decimal Rollover**: Every code modification MUST trigger a version bump strictly by `0.0.1` with rollover after `.9` (`0.1.9` -> `0.2.0`, `0.9.9` -> `1.0.0`). Never use `.10`.
- **Synchronized References**: Synchronize version numbers across `src/version.py`, `pyproject.toml`, `.agents/instructions.md`, and `.agents/rules/instructions.md` (NEVER put the version number in `README.md`).

## 3. Flet UI & Windows Desktop Architecture Rules
- **Desktop-Only Native Execution**: Run as a native desktop window via `ft.run(main)`. Never use `WEB_BROWSER` view unless explicitly requested.
- **No Flet Branding in Front-End UI**: Do not mention `Flet`, `flet-color-pickers`, `flet-map`, `flet.dev`, etc. in user-facing UI labels or descriptions.
- **Live UI Repaint on Windows Desktop**:
  - Never update Flet controls directly from a raw `threading.Thread`.
  - Use `page.run_task(async_worker)` + `await asyncio.to_thread(...)` + `await asyncio.sleep(0.015)`.
  - Keep an active `ft.ProgressRing` ticker visible during live streams/background tasks so Flutter's 60fps `scheduleFrame()` stays active.
  - Use the `1px` window width nudge (`force_window_repaint()`) when swapping major containers so Windows dispatches `WM_SIZE` / `WM_PAINT` immediately without requiring window focus switching.
  - Initialize dynamic `ft.Image` controls with valid 1x1 PNG `INITIAL_FRAME_BYTES` and `gapless_playback=True` to prevent the red `"valid src value must be specified"` error box.
- **Layout & Gray Screen Prevention**:
  - Avoid `expand=True` on inner `Column`/`Container` controls inside scrollable views (`ScrollMode.AUTO`). Use explicit widths/heights where needed.
  - Use `ft.Button(content=...)` (never `text=`), `ft.Dropdown(on_select=...)` (never `on_change=`), `ft.ExpansionTile(expanded=...)` (never `initially_expanded=`), and `color_picker.on_color_change` (normalizing 8-char `#AARRGGBB` Flutter hex strings to 6-char `#RRGGBB`).
  - Mount non-visual plugins (`Audio`, `PermissionHandler`, `SecureStorage`, `Geolocator`, `Flashlight`, `Clipboard`) exclusively in `page.services`, never in `page.overlay`.

## 4. Packaging & PyInstaller Standards (`SpyQR.spec`)
- **Explicit Approval for Builds**: Do not run `pyinstaller` unless the user explicitly asks to build the executable. When building, always use `uv run pyinstaller --clean --noconfirm SpyQR.spec`.
- **Binary Deduplication**: Filter root-level duplicate DLLs in `SpyQR.spec` that already exist inside `flet_desktop\app\flet\` and exclude `flet.testing`, `tkinter`, `unittest`, `pydoc`.
- **Native PyInstaller Splash Screen**: Use `Splash('assets/spyqr_splash.jpg', ...)` in `SpyQR.spec` (with a clean, text-free graphic) and close it via `pyi_splash.close()` in `src/main.py`.
- **Silent Subprocesses on Windows**: When invoking external CLI tools via `subprocess`, pass `creationflags=subprocess.CREATE_NO_WINDOW` on Windows to prevent console window flashes.
