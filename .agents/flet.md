# Κανόνες & Οδηγίες Flet (Flet API Standards)

*Αυτό το αρχείο περιέχει συγκεντρωμένους όλους τους κανόνες, τις καταργήσεις (deprecations) και τις ορθές πρακτικές για το Flet Framework στο παρόν project.*

## 1. ⚠️ ΣΗΜΑΝΤΙΚΕΣ ΚΑΤΑΡΓΗΣΕΙΣ & ΑΛΛΑΓΕΣ (Flet v0.80+ / v2.0+)

*   **ft.ElevatedButton**: Είναι deprecated. Χρησιμοποιούμε αποκλειστικά το **`ft.Button`** για απλή elevated συμπεριφορά. *Σημείωση: Στο `ft.Button` χρησιμοποιούμε την παράμετρο `content` αντί για `text` (π.χ. `ft.Button(content="Κείμενο", ...)`).*
*   **ft.app()**: Είναι deprecated. Χρησιμοποιούμε το **`ft.run(main)`** (όπου η συνάρτηση `main` περνιέται ως positional argument και όχι ως `target=main`).
*   **ft.border.all / symmetric / only**: Έχουν καταργηθεί ως module-level helpers. Χρησιμοποιούμε τις αντίστοιχες μεθόδους κλάσης της `ft.Border` (π.χ. **`ft.Border.all(width, color)`**, **`ft.Border.symmetric(...)`**).
*   **ft.alignment.center**: Χρησιμοποιούμε την κλάση **`ft.Alignment(0, 0)`** για κεντράρισμα.
*   **ft.UserControl**: Έχει καταργηθεί. Για custom components κληρονομούμε απευθείας από κάποιο Flet Control όπως το **`ft.Container`**.

## 2. ⚡ ΑΣΥΓΧΡΟΝΕΣ ΛΕΙΤΟΥΡΓΙΕΣ (Async / Coroutines)

*   Πολλές ενσωματωμένες μέθοδοι (όπως το `page.window.center()`, `audio.play()`, κ.λπ.) είναι πλέον **coroutine functions**.
*   Όταν καλούνται μέσα από σύγχρονη συνάρτηση `main(page: ft.Page)`, πρέπει να εκτελούνται μέσω της μεθόδου:
    ```python
    page.run_task(page.window.center)
    ```
*   Σε ασύγχρονα contexts, καλούνται με `await`:
    ```python
    await page.window.center_async()
    ```

## 3. 🔊 AUDIO STRATEGY (flet-audio)

*   Τα Audio controls **δεν ανήκουν** στο κεντρικό πακέτο `flet`. Εισάγονται από το **`flet_audio`**:
    ```python
    from flet_audio import Audio
    ```
*   Τα plugins δηλώνονται στο `pyproject.toml` κάτω από το `[tool.flet.plugins]`:
    ```toml
    [tool.flet.plugins]
    flet_audio = "Audio"
    ```
*   **Event Names**: Τα events είναι σε ενικό αριθμό: `on_position_change` (ΟΧΙ `on_position_changed`) και `on_state_change`.
*   **Event Properties**: Στους handlers, τα δεδομένα βρίσκονται στα attributes: `e.position` (ms), `e.state` (enum/string), `e.duration` (ms).
*   Οι μέθοδοι `.play()`, `.pause()`, `.resume()`, `.seek()` είναι ασύγχρονες (coroutine functions).

## 4. 🧩 ΠΡΩΤΟΚΟΛΛΟ MOUNTING (Services vs Overlay)

*   **Service-Only Plugins**: Plugins που λειτουργούν ως background services (όπως το `Audio` and το `PermissionHandler`) **ΔΕΝ ΠΡΕΠΕΙ** να προστίθενται στο `page.overlay` (προκαλεί σφάλμα "Unknown control").
*   **Σωστή Τοποθέτηση**: Προστίθενται αποκλειστικά στο `page.services`:
    ```python
    page.services.append(audio_player)
    ```
*   **Απαγόρευση Καθαρισμού**: Απαγορεύεται η χρήση του `page.services.clear()` διότι αποσυνδέει τα plugins από το Flutter runtime.
*   **Όνομα Control (`_c`)**: Διατηρούμε το default PascalCase που παρέχει η βιβλιοθήκη.

## 5. 🖼️ NATIVE SPLASH SCREEN (PyInstaller Splash)

*   Για να αποφευχθεί η καθυστέρηση φόρτωσης (loading delay) των βιβλιοθηκών της Python/Flet, **ΔΕΝ** υλοποιούμε splash screen μέσω του κώδικα Flet.
*   **Πρότυπο Υλοποίησης**: Χρησιμοποιούμε την εγγενή λειτουργία **`Splash`** του PyInstaller.
*   **Στο spec αρχείο (`SpyQR.spec`)**:
    *   Εισάγουμε την κλάση: `from PyInstaller.building.api import Splash`
    *   Ορίζουμε το αντικείμενο `splash`:
        ```python
        splash = Splash(
            'assets/spyqr_splash.jpg',
            binaries=a.binaries,
            datas=a.datas,
            text_pos=None,
            text_size=12,
            minify_script=True,
            always_on_top=True,
        )
        ```
    *   Προσθέτουμε τα `splash` και `splash.binaries` στο αντικείμενο `EXE(...)`:
        ```python
        exe = EXE(
            pyz,
            a.scripts,
            splash,
            splash.binaries,
            a.binaries,
            a.datas,
            ...
        )
        ```
*   **Στον Python κώδικα (`main.py`)**:
    *   Κλείνουμε το splash screen μόλις το UI φορτωθεί πλήρως (μετά το `page.update()` στο τέλος της `main`), χρησιμοποιώντας:
        ```python
        try:
            import pyi_splash
            pyi_splash.close()
        except ImportError:
            pass
        ```

## 6. 🐛 ΕΠΙΛΥΜΕΝΑ ΣΦΑΛΜΑΤΑ & GOTCHAS (RESOLVED ISSUES)

*   **TypeError: Button.__init__() got an unexpected keyword argument 'text'**:
    *   **Πρόβλημα:** Στο Flet v0.80+, η κλάση `ft.Button` (καθώς και οι υποκλάσεις της όπως η `ft.FilledButton`, `ft.ElevatedButton` κ.λπ.) δεν δέχεται την παράμετρο `text`.
    *   **Λύση:** Χρησιμοποιούμε την παράμετρο `content` (π.χ. `ft.Button(content="Κείμενο", ...)`).
*   **AttributeError: 'super' object has no attribute '__getattr__' (BLUE_GREY_950)**:
    *   **Πρόβλημα:** Οι παλέτες χρωμάτων του Flet (Material Design) όπως η `ft.Colors.BLUE_GREY` φτάνουν μέχρι το shade `900`. Η χρήση μη υπαρκτών αποχρώσεων όπως `BLUE_GREY_950` προκαλεί `AttributeError`.
    *   **Λύση:** Για πολύ σκούρες αποχρώσεις (π.χ. shade 950), χρησιμοποιούμε ρητά hex color string (π.χ. `bgcolor="#0e131f"`).
*   **TypeError: Dropdown.__init__() got an unexpected keyword argument 'on_change'**:
    *   **Πρόβλημα:** Στο Flet v0.80+, η κλάση `ft.Dropdown` δεν δέχεται την παράμετρο `on_change` στον κατασκευαστή της.
    *   **Λύση:** Χρησιμοποιούμε την παράμετρο `on_select` (π.χ. `ft.Dropdown(on_select=handler, ...)`).
*   **ModuleNotFoundError: No module named 'flet.desktop' / 'flet_desktop' (Flet v1.0+ PyInstaller Build)**:
    *   **Πρόβλημα:** Στο Flet v1.0+, το desktop runtime διαχωρίστηκε στο ξεχωριστό πακέτο `flet-desktop` (`flet_desktop`). Κατά τη δημιουργία εκτελέσιμου μέσω PyInstaller, το default analysis δεν εντοπίζει τα submodules και datas του `flet_desktop` και του `flet`, προκαλώντας σφάλμα εύρεσης του desktop client κατά την εκτέλεση του `.exe`.
    *   **Λύση:** Στο αρχείο `.spec` (π.χ. `spypress.spec`), εισάγουμε τη συνάρτηση `collect_all` από το `PyInstaller.utils.hooks` και συλλέγουμε ρητά τα binaries, datas και hiddenimports των πακέτων `flet` και `flet_desktop`:
        ```python
        from PyInstaller.utils.hooks import collect_all

        for pkg in ['flet', 'flet_desktop']:
            pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
            datas += pkg_datas
            binaries += pkg_binaries
            hiddenimports += pkg_hiddenimports
        ```
*   **TypeError: Image.__init__() got an unexpected keyword argument 'src_base64'**:
    *   **Πρόβλημα:** Στο Flet v1.0+, η παράμετρος `src_base64` της `ft.Image` καταργήθηκε.
    *   **Λύση:** Χρησιμοποιούμε απευθείας την παράμετρο `src`, η οποία δέχεται είτε raw `bytes` (π.χ. `src=frame_bytes`), είτε data URI string (π.χ. `src=f"data:image/png;base64,{b64}"`).
*   **AttributeError: module 'flet.controls.padding' has no attribute 'symmetric'**:
    *   **Πρόβλημα:** Στο Flet v1.0+, τα module-level helpers `ft.padding.symmetric`, `ft.padding.all` καταργήθηκαν.
    *   **Λύση:** Χρησιμοποιούμε τις μεθόδους κλάσης της `ft.Padding` (κεφαλαίο P): `ft.Padding.symmetric(horizontal=10, vertical=4)`, `ft.Padding.all(10)`.
*   **RuntimeError: Control must be added to the page first (κατά τον έλεγχο `if control.page:`)**:
    *   **Πρόβλημα:** Στο Flet v1.0+, η ανάγνωση της ιδιότητας `control.page` σε control που δεν έχει προστεθεί ακόμα στη σελίδα προκαλεί `RuntimeError` αντί να επιστρέψει `None`.
    *   **Λύση:** Χρησιμοποιούμε βοηθητική συνάρτηση `safe_update(control)` με `try: control.update() except Exception: pass`.
*   **TypeError: Tab.__init__() got an unexpected keyword argument 'text' (Αλλαγή αρχιτεκτονικής Tabs στο Flet v1.0+)**:
    *   **Πρόβλημα:** Στο Flet v1.0+, το `ft.Tabs` άλλαξε σε controller wrapper και το `ft.Tab` δέχεται `label` αντί για `text` και δεν δέχεται `content`.
    *   **Λύση:** Χρησιμοποιούμε `ft.Tabs(length=N, content=ft.Column([ft.TabBar(tabs=[ft.Tab(label="...", icon=...)]), ft.TabBarView(controls=[...], expand=True)], expand=True))`.
*   **AttributeError: 'Page' object has no attribute 'open' / 'launch_url' / 'clipboard' (Flet v1.0+)**:
    *   **Πρόβλημα:** Στο Flet v1.0+, οι μέθοδοι `page.open()`, `page.launch_url()` και η ιδιότητα `page.clipboard` μετακινήθηκαν ή άλλαξαν.
    *   **Λύση:**
        *   Για SnackBars/Dialogs: `page.show_dialog(ft.SnackBar(...))`
        *   Για Clipboard: Δημιουργούμε `clipboard_service = ft.Clipboard()`, το προσθέτουμε στο `page.services.append(clipboard_service)` και καλούμε `page.run_task(clipboard_service.set, text)`.
        *   Για FilePicker: Η `await file_picker.pick_files(...)` είναι πλέον coroutine και επιστρέφει απευθείας τη λίστα αρχείων.
        *   Για άνοιγμα URL σε Desktop: `webbrowser.open(url)`.
*   **Built-in Extensions API Gotchas (`flet-code-editor`, `flet-charts`, `flet-map`, `flet-camera`, `flet-webview`)**:
    *   **`flet_code_editor.CodeEditor`**: Δέχεται `code_theme=fce.CodeTheme.VS2015` (ΟΧΙ `theme=`).
    *   **`flet_charts.BarChart` & `BarChartGroup`**: Το `BarChart` δέχεται `groups=` (ΟΧΙ `bar_groups=`) και το `BarChartGroup` δέχεται `rods=` (ΟΧΙ `bar_rods=`).
    *   **`flet_map.Map` & `Marker`**: Το `Map` δέχεται `initial_center=fm.MapLatitudeLongitude(lat, lon)` (ΟΧΙ `configuration=`) και το `Marker` δέχεται `coordinates=fm.MapLatitudeLongitude(lat, lon)` (ΟΧΙ `point=`). Για αποφυγή σφάλματος "Access blocked" στα πλακίδια χάρτη, χρησιμοποιούμε tile server όπως ο ArcGIS `World_Street_Map` με έγκυρο `user_agent_package_name`.
    *   **`flet_camera.Camera` & `flet_webview.WebView` σε Windows Desktop**: Το `flet-camera` εγείρει `FletUnsupportedPlatformException` σε Windows και το `flet-webview` εμφανίζει κόκκινο πλαίσιο `"Webview is not yet supported on this Platform."`. Σε Windows Desktop χρησιμοποιούμε OpenCV (`cv2.VideoCapture(0, cv2.CAP_DSHOW)`) για την κάμερα και ελέγχουμε το `page.platform` πριν την προσθήκη `WebView`.
*   **Κόκκινο Πλαίσιο Σφάλματος Flutter: `valid src value must be specified.` σε `ft.Image`**:
    *   **Πρόβλημα:** Όταν ένα `ft.Image` αρχικοποιείται με κενό `src` (π.χ. `src=b""` ή `src=""`) και προστεθεί στο visual tree (π.χ. κατά το πάτημα «Έναρξη Κάμερας» πριν ακόμα έρθει το πρώτο frame από το OpenCV thread), το Flutter Image widget εμφανίζει κόκκινο πλαίσιο σφάλματος `"valid src value must be specified."`.
    *   **Λύση:**
        1. Αρχικοποιούμε πάντα το `ft.Image` με έγκυρα bytes μιας 1x1 PNG εικόνας (`INITIAL_FRAME_BYTES`) και `gapless_playback=True`.
        2. Διατηρούμε το `camera_placeholder` ορατό κατά την εκκίνηση της κάμερας και αντικαθιστούμε το `camera_stack_container.content = camera_view` **μόνο** μέσα στο `on_frame_received(frame_bytes)` αφού ληφθεί το πρώτο μη-κενό frame.
*   **Δυναμικό Redraw & Repaint Freeze σε Windows Desktop (Απαίτηση αλλαγής focus παραθύρου για εμφάνιση εικόνας/κάμερας)**:
    *   **Πρόβλημα:** Στα Windows desktop, οι κλήσεις `page.update()` ή `control.update()` από non-async OS threads (`threading.Thread`) εκτελούνται εκτός του κύριου asyncio event loop του Flet. Όταν το παράθυρο δεν δέχεται εξωτερικό OS event, το Flutter engine δεν λαμβάνει frame ticker event και δεν επανασχεδιάζει την εικόνα της κάμερας μέχρι ο χρήστης να αλλάξει ενεργή εφαρμογή (focus/blur) και να επιστρέψει.
    *   **Οριστική Λύση (Τριπλό Πρότυπο από `SpyQBank`, `spyclearbg`, `spywalk`):**
        1. **Async Event Loop (`page.run_task` + `asyncio.to_thread`)**: Ο βρόχος ανάγνωσης της κάμερας εκτελείται ως `async def camera_async_worker()` μέσω `page.run_task(camera_async_worker)`, καλώντας το `await asyncio.to_thread(scanner_engine.grab_frame)` και `await asyncio.sleep(0.015)` ώστε τα updates να στέλνονται απευθείας από το κύριο asyncio loop του Flet.
        2. **Active `ft.ProgressRing` Ticker**: Διατηρούμε ένα ορατό `ft.ProgressRing(visible=True)` όσο η κάμερα είναι ενεργή, το οποίο αναγκάζει το Flutter engine να εκτελεί συνεχή 60fps `scheduleFrame()` ticker.
        3. **1px Window Width Nudge (`force_window_repaint`)**: Κατά την εναλλαγή του container (`camera_placeholder` <-> `camera_view`), αυξομειώνουμε προγραμματιστικά το `page.window.width` κατά `+1px` και επαναφέρουμε:
           ```python
           w = page.window.width
           if w:
               page.window.width = w + 1
               page.update()
               page.window.width = w
               page.update()
           ```
           ώστε το λειτουργικό σύστημα να στείλει ακαριαίο μήνυμα redraw στο Flutter χωρίς να χρειάζεται αλλαγή παραθύρου.
*   **`flet_color_pickers.ColorPicker`: Μη λειτουργία `on_change` και 8-ψήφιο ARGB hex (`#AARRGGBB`)**:
    *   **Πρόβλημα:**
        1. Στο `flet-color-pickers` (`v1.0.4`), το event αλλαγής χρώματος ονομάζεται **`on_color_change`** (ΟΧΙ `on_change`). Αν οριστεί `color_picker.on_change = ...`, ο handler δεν καλείται ποτέ.
        2. Επιπλέον, το Flutter `ColorPicker` επιστρέφει στο `e.data` 8-ψήφιο δεκαεξαδικό χρώμα μορφής **`#AARRGGBB`** (Alpha-Red-Green-Blue, π.χ. `#ffff0000` για κόκκινο), ενώ η βιβλιοθήκη `PIL.ImageColor` (που χρησιμοποιούν τα `qrcode` και `python-barcode`) ερμηνεύει τα 8-ψήφια hex ως `#RRGGBBAA` (Red-Green-Blue-Alpha), αλλοιώνοντας εντελώς τα κανάλια RGB!
    *   **Λύση:**
        1. Χρησιμοποιούμε `color_picker.on_color_change = handler` και `enable_alpha=False`.
        2. Κανονικοποιούμε πάντα το χρώμα αφαιρώντας τα 2 πρώτα ψηφία Alpha όταν το μήκος είναι 8 (`if len(c) == 8: c = c[2:]` -> `#RRGGBB`) και επιστρέφουμε raw `PNG bytes` στο `ft.Image.src`.
        3. Παρέχουμε παράλληλα άμεσα `ft.Slider` για τα κανάλια **R, G, B (0-255)**, πεδίο HEX και έτοιμα swatches χρωμάτων σε αμφίδρομο συγχρονισμό.
*   **`TypeError: ExpansionTile.__init__() got an unexpected keyword argument 'initially_expanded'`**:
    *   **Πρόβλημα:** Στο Flet v1.0+, η παράμετρος `initially_expanded` του `ft.ExpansionTile` καταργήθηκε.
    *   **Λύση:** Χρησιμοποιούμε την παράμετρο **`expanded=False`** (ή `expanded=True`).



