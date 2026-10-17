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

## 5. Current Project State & Session Handoff
- **Current Version**: `0.2.5` (synchronized in `src/version.py`, `pyproject.toml`, `.agents/instructions.md`, `.agents/rules/instructions.md`).
- **Next Version on Code Change**: `0.2.6`.
- **GitHub Repository**: Public repository [`spyalekos/spyQR`](https://github.com/spyalekos/spyQR) (`origin/master` fully synced).
- **Published GitHub Release**: [`v0.2.2`](https://github.com/spyalekos/spyQR/releases/tag/v0.2.2) with standalone executable `dist/SpyQR.exe` uploaded and Greek Release Notes.
- **Splash Screen & Icon**: Clean text-free 3D holographic QR/Barcode graphic at `assets/spyqr_splash.jpg` (`600x340`) and app icon at `assets/icon.ico` / `assets/icon.png`.
- **Low-Memory Android APK Build (`build_apk.sh`)**:
  - Stages the Flutter/Android project in `/tmp/spyqr_android_stage` (outside the IDE workspace so `dart language-server --protocol lsp` never spawns and saves 1.3 GB RAM).
  - Overrides Flet 1.0.4's default `-Xmx8G` via `[tool.flet.android.gradle_properties]` with `-Xmx768m -Xms128m -XX:MaxMetaspaceSize=256m -XX:ReservedCodeCacheSize=64m -XX:+UseSerialGC`.
  - Runs 4 decoupled sequential phases (`prepare_flet_stage` -> `patch_android_scanner` -> standalone `flutter assemble` -> `./gradlew assembleRelease -x compileFlutterBuildRelease -x lintVitalRelease`) so Dart `gen_snapshot` and Gradle JVM never run simultaneously in RAM.
- **Application Architecture (Dual Windows Desktop & Android Native Support)**:
  - **Tab 1 ("Σαρωτής")**: Live OpenCV DirectShow camera stream (`camera_async_worker` + `ProgressRing` ticker + `force_window_repaint`) on Windows Desktop and Native ZXing 1D/2D camera & image scanner (`spyqr://scan/start` & `spyqr://scan/file` via `MainActivity.kt` + `.spyqr_scan_result.json` IPC) on Android, image file picker, clipboard image/text scanner, audio beep feedback, and Quick Action Bolt button (`ft.Icons.BOLT`) next to "Προβολή & Επεξεργασία".
  - **Tab 2 ("Αποτέλεσμα")**: Smart Semantic Detection badge & structured details (Retail products with GS1 country & live OpenFoodFacts lookup + Skroutz/Google buttons, Books via OpenLibrary, Magazines, Gov.gr/AADE, Wi-Fi, vCard, vEvent, SEPA/IBAN, Crypto, GPS, SMS, Email, Tel, JSON) + syntax-highlighted `CodeEditor`.
  - **Tab 3 ("Δημιουργός")**: QR & 1D Barcode generator (`QR`, `CODE128`, `EAN13`, `EAN8`, `UPCA`, `CODE39`), interactive RGB sliders (`0-255`), HEX input, preset color swatches, HSV `ColorPicker` (`on_color_change` with 8-char `#AARRGGBB` normalization), box size/border sliders, ECC selector, PNG export (`src_bytes` SAF support on Android + disk write on Desktop), and **Click-on-Map Geo QR Picker** (`flet_map.Map` with `on_tap` & Greek city presets) at the bottom.
  - **Tab 4 ("Ιστορικό")**: Encrypted persistent scan history (`SecureStorage` + local fallback), `DataTable2` with search filter, 1-click reload/copy/delete, and UTF-8 CSV export (`src_bytes` SAF support on Android + disk write on Desktop).
  - **Tab 5 ("Στατιστικά")**: Vertical analytics layout with large `PieChart` (percentages & legend) on top, `BarChart` histogram below, and 3 summary cards.
  - **Tab 6 ("Βοήθεια")**: Comprehensive Greek user guide and creator references (**SpyAlekos** — `https://alekos.program.gr` & `https://github.com/spyalekos`).
  - **AppBar**: Creator link, audio toggle, and full recursive Dark ↔ Light UI color inversion (`invert_control_tree`) via the lightbulb button.
