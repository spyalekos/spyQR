---
description: "AI Reminders & Development Rules for SpyQR project (Flet, uv, built-in extensions, versioning, audio, QR scanner)"
trigger: always
---

# Οδηγίες & Κανόνες Ανάπτυξης AI (AI Reminders) - SpyQR

*Αυτό το αρχείο διαβάζεται και λαμβάνεται υπόψη από τον AI agent κατά την εκκίνηση του τρέχοντος project για την αποφυγή επαναλαμβανόμενων διευκρινίσεων.*

**Alias χρήστη:** Όταν ο χρήστης αναφέρει `οδηγίες` ή `οδηγιες`, εννοεί αυτό το αρχείο (`instructions.md`), εκτός αν δώσει πιο συγκεκριμένο path.

## ⛔ ΑΠΟΛΥΤΟΙ ΚΑΝΟΝΕΣ ΠΕΡΙΟΡΙΣΜΟΥ (CRITICAL)

1. **ΑΠΑΓΟΡΕΥΣΗ BUILD (DEFAULT):** Ο AI agent **ΔΕΝ ΕΠΙΤΡΕΠΕΤΑΙ** να τρέχει βαριές εντολές packaging στο παρασκήνιο χωρίς ρητή έγκριση του χρήστη, για αποφυγή παγώματος του συστήματος.
2. **ΜΗ ΧΡΗΣΗ ΠΟΡΩΝ:** Αποφεύγουμε εντολές που καταναλώνουν υπερβολική μνήμη ή CPU στο background.

## Βασικοί Κανόνες (Σημαντικοί)

1. **Package / Dependency Management:** 
   - Χρησιμοποιούμε **ΠΑΝΤΟΤΕ** `uv`. 
   - Δεν τρέχουμε «γυμνές» pip εντολές. Αξιοποιούμε `uv pip install ...`, `uv add ...` ή `uv run ...`.
   - Εικονικό περιβάλλον δημιουργείται πάντα με `uv venv --seed`.
   - **CRITICAL:** Εργαλεία που αφορούν αποκλειστικά Desktop development (π.χ. `pyinstaller`, `watchdog`) πρέπει να μπαίνουν στο `[dependency-groups] dev` και ΠΟΤΕ στα βασικά runtime dependencies.
   - **Flet Dependency:** Στα βασικά dependencies χρησιμοποιούμε `flet`, `flet-desktop` (για εκτέλεση desktop).

2. **Built-in Extensions Protocol (https://flet.dev/docs/extend/built-in-extensions):**
   - Χρησιμοποιούμε όσο το δυνατόν περισσότερα built-in extensions:
     - `flet-audio`: Ηχητικό σήμα επιτυχούς σάρωσης QR (beep/chime) και ηχητικά εφέ.
     - `flet-permission-handler`: Έλεγχος δικαιωμάτων κάμερας και αποθήκευσης.
     - `flet-lottie`: Εντυπωσιακά animations σάρωσης (radar scanner beam, success badge, radar pulses).
     - `flet-spinkit`: Spinners / ενδείξεις φόρτωσης κατά την εκκίνηση κάμερας ή ανάλυση εικόνας.
     - `flet-code-editor`: Προβολή και επεξεργασία δεδομένων QR (JSON, XML, κώδικας, raw payload).
     - `flet-color-pickers`: Επιλογή χρωμάτων για τη γεννήτρια QR codes και εξατομίκευση του θέματος.
     - `flet-secure-storage`: Ασφαλής αποθήκευση ιστορικού σαρώσεων και ρυθμίσεων χρήστη.
     - `flet-charts`: Στατιστικά και γραφήματα (BarChart, PieChart) σαρώσεων ανά κατηγορία.
     - `flet-datatable2`: Πίνακας ιστορικού σαρώσεων με ταξινόμηση, αναζήτηση, αντιγραφή και εξαγωγή.
     - `flet-map`: Προβολή σημείου σε διαδραστικό χάρτη OpenStreetMap όταν το QR περιέχει γεωγραφικές συντεταγμένες (`geo:`).
     - `flet-webview`: Προεπισκόπηση συνδέσμων ιστού όταν το QR περιέχει URL.
     - `flet-geolocator`: Εύρεση τρέχουσας τοποθεσίας για δημιουργία γεωγραφικών QR codes.
     - `flet-flashlight`: Ενεργοποίηση φακού (όπου υποστηρίζεται).

3. **Πρότυπο Mounting (Services vs Overlay):**
   - **Service-Only Plugins**: Plugins που λειτουργούν ως background services (`Audio`, `PermissionHandler`, `SecureStorage`, `Geolocator`, `Flashlight`) **ΔΕΝ ΠΡΕΠΕΙ** να προστίθενται στο `page.overlay` ή στο visual tree (προκαλεί σφάλμα "Unknown control").
   - **Σωστή Τοποθέτηση**: Προστίθενται αποκλειστικά στο `page.services`:
     ```python
     page.services.append(service_instance)
     ```
   - **Απαγόρευση Καθαρισμού**: **ΑΠΑΓΟΡΕΥΕΤΑΙ** η χρήση του `page.services.clear()`.
   - **Visual Controls**: Τα visual controls (`Lottie`, `CodeEditor`, `ColorPicker`, `DataTable2`, `Map`, `BarChart`, `PieChart`, `SpinKit`) τοποθετούνται κανονικά μέσα στο visual layout (`page.add()`, `Column`, `Row`, `Container`).

4. **Framework Standards (Flet v0.80+ / v1.0+):**
   - Το project χρησιμοποιεί τη βιβλιοθήκη **Flet** (Material Design 3).
   - **Button**: Χρησιμοποιούμε αποκλειστικά `ft.Button` με παράμετρο `content` (ΟΧΙ `text` και ΟΧΙ `ft.ElevatedButton`).
   - **ft.run**: Χρησιμοποιούμε `ft.run(main)` (όχι το deprecated `ft.app(target=main)`).
   - **Border**: Χρησιμοποιούμε `ft.Border.all()`, `ft.Border.symmetric()`.
   - **Alignment**: Χρησιμοποιούμε `ft.Alignment(x, y)` (π.χ. `ft.Alignment(0, 0)` για κεντράρισμα).
   - **Custom Controls**: Κληρονομούμε από `ft.Container` (όχι από το καταργημένο `ft.UserControl`).
   - **Dropdown**: Χρησιμοποιούμε `on_select` αντί για `on_change`.
   - **Colors**: Αποφεύγουμε ανύπαρκτες αποχρώσεις άνω του 900 (π.χ. `BLUE_GREY_950`). Χρησιμοποιούμε ρητά hex codes (π.χ. `#0e131f`).
   - **Async Coroutines**: Μέθοδοι όπως `audio.play()`, `page.clipboard.set()` καλούνται είτε με `await` σε async context, είτε μέσω `page.run_task(coroutine)`.
   - **CRITICAL (Καταγραφή Σφαλμάτων):** Κάθε νέο σφάλμα, ιδιαιτερότητα του Flet API ή Gotcha που επιλύεται κατά την ανάπτυξη, **ΠΡΕΠΕΙ ΥΠΟΧΡΕΩΤΙΚΑ** να καταγράφεται στο αρχείο [`.agents/flet.md`](file:///c:/Users/alekos/pyAlekos/spyQR/.agents/flet.md) στην «Ενότητα 6: 🐛 ΕΠΙΛΥΜΕΝΑ ΣΦΑΛΜΑΤΑ & GOTCHAS» για μελλοντική αναφορά.

5. **Εκδόσεις (Versioning):**
   - **CRITICAL:** Όταν αλλάζουμε ακόμη και ένα byte στον κώδικα, δημιουργούμε νέα έκδοση (version bump) αυστηρά κατά `+0.0.1`.
   - Χρησιμοποιούμε **δεκαδικό σύστημα με rollover** (π.χ. 0.1.0 -> 0.1.1 ... 0.1.9 -> 0.2.0, και 0.9.9 -> 1.0.0, ΠΟΤΕ `.10`).
   - Ενημερώνονται **ΟΛΕΣ** οι αναφορές συγχρονισμένα: `pyproject.toml`, `src/version.py`, `.agents/instructions.md`, `.agents/rules/instructions.md`.
   - **ΑΠΑΓΟΡΕΥΣΗ ΣΤΟ `README.md`:** Στο `README.md` **ΔΕΝ** γράφουμε ποτέ αριθμό έκδοσης, εντολές εκτέλεσης/μεταγλώττισης, δομή φακέλων ή links δημιουργού (βλ. Κανόνα 9 & [`.agents/rules/readme.md`](file:///c:/Users/alekos/pyAlekos/spyQR/.agents/rules/readme.md)).

6. **Black Screen, Gray Screen & Red Error Prevention (CRITICAL):**
   - Η «μαύρη οθόνη», η «γκρι οθόνη» ή το «κόκκινο πλαίσιο Flutter error» αποφεύγεται με structured try-except blocks στην `main`.
   - **UI Early Rendering:** Καλούμε `page.add()` με βασικό layout αμέσως, και φορτώνουμε ασύγχρονα τις κάμερες ή τα βαριά components.
   - **Αποφυγή Γκρι Οθόνης (Scrollable Views):** Σε scrollable views (`ScrollMode.AUTO`), αποφεύγουμε το `expand=True` σε εσωτερικά `Column`/`Container` και χρησιμοποιούμε ρητά πλάτη/ύψη.
   - **Desktop Safe Fallbacks:** Σε Windows Desktop, εάν ένα hardware plugin δεν διαθέτει Flutter engine support, η εφαρμογή διατηρεί αυτόματο graceful fallback (π.χ. OpenCV live camera feed με Flet Image stream), διασφαλίζοντας 100% λειτουργικότητα χωρίς crash.
   - **Live UI Repaint (Windows Desktop):** Απαγορεύεται η ενημέρωση του UI από `threading.Thread`. Χρησιμοποιούμε πάντα `page.run_task(async_worker)` + `await asyncio.to_thread(...)` + ενεργό `ft.ProgressRing` ticker + `1px` window resize nudge (`force_window_repaint()`), και αρχικοποιούμε τα `ft.Image` με έγκυρα 1x1 PNG bytes.
   - **Cross-Project Knowledge Lookup (`~\pyAlekos`):** Κάθε γενικός κανόνας ή οδηγία που υπάρχει στα υπόλοιπα projects του φακέλου `c:\Users\alekos\pyAlekos` (όπως `readme.md`, `flet.md`, `GEMINI.md`, `instructions.md`) ενσωματώνεται και ισχύει αυτόματα και σε αυτό το project.
   - **Automated UI Verification Guard:** Όταν ο agent τρέχει αυτοματοποιημένο έλεγχο UI (π.χ. για screenshots), πρέπει ΠΑΝΤΑ να κλείνει το παράθυρο σε `finally: await page.window.close()` ώστε να μην κολλάει ποτέ η διεργασία στο παρασκήνιο.

7. **Naming Convention & Ανοχή σε Μικρά/Κεφαλαία:**
   - Το όνομα της εφαρμογής ξεκινά με κεφαλαίο: **`SpyQR`**.
   - Όταν ο χρήστης αναφέρει αρχείο, εντολή, φάκελο ή σύμβολο με διαφορετικά μικρά/κεφαλαία, ο AI agent ψάχνει πρώτα case-insensitive αντιστοιχίες μέσα στο project.

8. **PyInstaller & Native Splash Screen (Desktop Build):**
   - Όταν ζητηθεί build από τον χρήστη, εκτελούμε πάντα με `--clean`: `uv run pyinstaller --clean --noconfirm SpyQR.spec`.
   - Στο `SpyQR.spec` η παράμετρος `console` είναι πάντα `False`, εφαρμόζεται φίλτρο deduplication για τα binaries του `flet_desktop`, και το `Splash('assets/spyqr_splash.jpg')` χρησιμοποιεί καθαρή εικόνα **χωρίς καθόλου κείμενο**.

9. **Κανόνες Δομής & Περιεχομένου `README.md` & `Release Notes` (`.agents/rules/readme.md`):**
   - **ΠΑΝΤΑ ΣΤΑ ΕΛΛΗΝΙΚΑ:** Τόσο το `README.md` όσο και τα `Release Notes` στο GitHub γράφονται αποκλειστικά στα **Ελληνικά**.
   - **ΑΥΣΤΗΡΕΣ ΑΠΑΓΟΡΕΥΣΕΙΣ ΣΤΟ `README.md`:**
     1. **ΟΧΙ** εντολές εκτέλεσης ή μεταγλώττισης (`uv run ...`, `python ...`, `pyinstaller ...`).
     2. **ΟΧΙ** δομή φακέλων/αρχείων του project (`├── src/`).
     3. **ΟΧΙ** links ή ενότητα δημιουργού (Creator links / portfolio URLs) στο `README.md` ή στα Release Notes.
     4. **ΟΧΙ** αριθμοί εκδόσεων, version tags (π.χ. `(v0.2.2)`) ή σχόλια εκδόσεων στον τίτλο ή στα bullets του `README.md`.
     5. **ΟΧΙ** διαγραφή υπαρχόντων χαρακτηριστικών κατά τις ενημερώσεις.

10. **Συντομεύσεις & Αλληλεπίδραση (Interaction Shortcuts):**
    - **Η Συντόμευση `^` (Hands-off / Shutdown)**:
      - Το σύμβολο `^` ως αυτόνομο μήνυμα χρήστη σημαίνει **hands-off / κλείνουμε για σήμερα**.
      - Μόλις ο χρήστης γράψει `^`, ο AI agent **ΠΡΕΠΕΙ** να τερματίσει/κλείσει αμέσως οποιαδήποτε ενεργή background διεργασία (όπως `uv run flet run`) για να ελευθερωθούν πόροι συστήματος.
      - Ο AI agent ολοκληρώνει τη συνομιλία αποχαιρετώντας ευγενικά τον χρήστη, χωρίς να εκτελέσει νέες ενέργειες, εντολές ή να περιμένει περαιτέρω είσοδο.

---

## 📍 Τελευταία Γνωστή Κατάσταση (Last Known State)

### 🚀 ΤΡΕΧΟΥΣΑ ΕΚΔΟΣΗ: v0.2.2
- Πλήρης συγχρονισμός όλων των κανόνων από τα υπόλοιπα projects του `pyAlekos` ([`.agents/rules/readme.md`](file:///c:/Users/alekos/pyAlekos/spyQR/.agents/rules/readme.md), [`.agents/GEMINI.md`](file:///c:/Users/alekos/pyAlekos/spyQR/.agents/GEMINI.md), [`.agents/flet.md`](file:///c:/Users/alekos/pyAlekos/spyQR/.agents/flet.md)) και αναμόρφωση του [`README.md`](file:///c:/Users/alekos/pyAlekos/spyQR/README.md) στα Ελληνικά (χωρίς αριθμούς εκδόσεων, εντολές εκτέλεσης, δομή project ή links δημιουργού).
- Δημιουργία νέου καθαρού (χωρίς καθόλου κείμενο) Splash Screen (`assets/spyqr_splash.jpg`), μεταγλώττιση standalone εκτελέσιμου `dist/SpyQR.exe`, και δημοσίευση σε public GitHub repository (`spyalekos/SpyQR`) μαζί με το GitHub Release `v0.2.2`.
- Μεταφορά του **Διαδραστικού Χάρτη (`flet-map`)** από την καρτέλα «Αποτέλεσμα» στο κάτω μέρος της καρτέλας **«Δημιουργός»** ως **Click-on-Map Location QR Picker**: με κλικ οπουδήποτε πάνω στον χάρτη (ή επιλογή από τα κουμπιά γρήγορης μετάβασης πόλεων), μετακινείται η πινέζα και δημιουργείται αυτόματα QR Code τοποθεσίας GPS (`geo:lat,lon`).
- Προσθήκη ενεργού συνδέσμου και αναφοράς στον δημιουργό **[SpyAlekos](https://alekos.program.gr)** (καθώς και GitHub `https://github.com/spyalekos`) στην πάνω μπάρα της εφαρμογής (`AppBar`), στο υποσέλιδο της καρτέλας «Βοήθεια» και στο `README.md`.
- Προσθήκη κουμπιού **Άμεσης Ενέργειας (Αστραπή ⚡ / `ft.Icons.BOLT`)** δίπλα στο κουμπί «Προβολή & Επεξεργασία» στην καρτέλα «Σαρωτής»: αν το αποτέλεσμα είναι ιστοσελίδα (`URL`) την ανοίγει απευθείας στον default browser, αν είναι συντεταγμένες (`GEO`) τις ανοίγει απευθείας στο Google Maps μέσω του default browser, και αν είναι προϊόν (`PRODUCT`) ή οτιδήποτε άλλο μεταβαίνει στην καρτέλα «Προβολή & Επεξεργασία» (`Αποτέλεσμα`).
- Αναβάθμιση της καρτέλας **«Στατιστικά»**: μεγαλύτερα γραφήματα σε κάθετη διάταξη (πάνω το μεγάλο **Διάγραμμα Πίτας** με αναλυτικό Υπόμνημα & ποσοστά %, και από κάτω το **Ιστόγραμμα / BarChart** με άξονες X/Y, ετικέτες κατηγοριών και tooltips), καθώς και προσθήκη 3ης κάρτας «Δημοφιλέστερη Κατηγορία».
- Υλοποίηση πλήρους **Αντιστροφής Χρωμάτων (Color Invert Dark ↔ Light)** σε όλα τα controls της εφαρμογής κατά το πάτημα του εικονιδίου της λάμπας (`invert_control_tree`).
- Διόρθωση παραμέτρου `expanded=False` (αντί `initially_expanded=False`) στο `ft.ExpansionTile` για Flet v1.0+.
- Αφαίρεση όλων των αναφορών στο Flet (`flet-color-pickers`, `flet-code-editor`, `flet-map`, `flet-webview`, `flet-datatable2`, `flet-charts`, `Geolocator`, `flet.dev` κ.λπ.) από το front-end της εφαρμογής.
- Πλήρης επιδιόρθωση και αναβάθμιση του **Δημιουργού QR Codes & Barcodes**: διόρθωση του event `on_color_change` στο `ColorPicker`, κανονικοποίηση των 8-ψήφιων `#AARRGGBB` χρωμάτων του Flutter σε `#RRGGBB`, προσθήκη άμεσων διαδραστικών ρυθμιστικών **RGB (R, G, B Sliders 0-255)**, πεδίου HEX, έτοιμων χρωμάτων, επιλογής χρώματος φόντου, ρυθμιστικών μεγέθους/περιθωρίου (`box_size`, `border`), επιπέδου διόρθωσης σφαλμάτων (`ECC`) και παραθύρου αποθήκευσης PNG (`file_picker.save_file`).
- Αντικατάσταση της καρτέλας «Επεκτάσεις» με πλήρη καρτέλα **«Βοήθεια»** (Οδηγός Χρήσης & Έξυπνης Αναγνώρισης).
- Προσθήκη **Έξυπνης Αναγνώρισης Περιεχομένου (Smart Semantic Detection)**: όταν σκανάρει **Εμπορικό Προϊόν** (`EAN-13`, `EAN-8`, `UPC-A`, `GTIN-14`) καταλαβαίνει ότι είναι προϊόν, εντοπίζει τη χώρα GS1 (π.χ. `520` = Ελλάδα 🇬🇷), αναζητά αυτόματα online την ονομασία και τη μάρκα του (OpenFoodFacts / OpenBeautyFacts / OpenProductsFacts) και εμφανίζει άμεσα κουμπιά αναζήτησης σε **Skroutz** & **Google**. Επίσης ξεχωρίζει **Βιβλία (ISBN-13)** μέσω OpenLibrary, **Περιοδικά (ISSN)**, **Κωδικούς Αποθήκης/Courier**, **Gov.gr / ΑΑΔΕ**, **YouTube**, **E-Shops**, **Wi-Fi**, **Επαφές (vCard)**, **Ραντεβού Ημερολογίου (vEvent)**, **IBAN / SEPA**, **GPS**, **SMS**, **Email**, **Τηλέφωνα** και **JSON**.
- Προσθήκη πλήρους αναγνώρισης και δημιουργίας κανονικών **Barcodes (1D & 2D)** εκτός από QR Codes.
- Προσθήκη `SpyQR.spec`, `assets/spyqr_splash.jpg`, `assets/icon.ico`, υποστήριξης `pyi_splash.close()` και `sys._MEIPASS`, και δημιουργία standalone εκτελέσιμου `dist/SpyQR.exe` με `uv run pyinstaller SpyQR.spec`.
- Διόρθωση **Windows Desktop Repaint Freeze** κατά την εκκίνηση της κάμερας (μετατροπή του βρόχου κάμερας σε `async def camera_async_worker` μέσω `page.run_task` + `asyncio.to_thread`, προσθήκη ενεργού `ft.ProgressRing` ticker για συνεχή 60fps ανανέωση και `1px` window width nudge `force_window_repaint()` ώστε η εικόνα να εμφανίζεται ακαριαία χωρίς αλλαγή focus παραθύρου).
- Διόρθωση σφάλματος `"valid src value must be specified."` στο `ft.Image` κατά την εκκίνηση της κάμερας.
- Αρχικοποίηση νέου project **SpyQR**.
- Εικονικό περιβάλλον με `uv venv --seed`.
- Ενσωμάτωση του συνόλου των Flet built-in extensions (audio, permissions, lottie, spinkit, code-editor, color-pickers, secure-storage, charts, datatable2, map, webview, geolocator, camera, flashlight).
- Υποστήριξη real-time camera scanning (OpenCV detector), ανάλυσης εικόνων από αρχείο/clipboard, προβολής/επεξεργασίας δεδομένων με syntax highlighting, διαδραστικού χάρτη, και γεννήτριας QR codes με παλέτα χρωμάτων.
