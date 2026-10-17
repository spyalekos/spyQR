---
description: "QR Code scanner, generator, camera feeds, history storage, and built-in extensions rules for SpyQR"
trigger: always
---

# SpyQR Development & Architecture Rules

Αυτό το αρχείο περιέχει τους κανόνες, τις προδιαγραφές και τα πρότυπα αρχιτεκτονικής για την εφαρμογή **SpyQR**.

## 🎯 Σκοπός Έργου (Project Scope)
Το **SpyQR** είναι ένα προηγμένο, σύγχρονο QR Code Scanner & Utility γραμμένο σε Python με το framework **Flet**.
Αξιοποιεί τις επίσημες ενσωματωμένες επεκτάσεις του Flet (Built-in Extensions) για να προσφέρει πλήρη εμπειρία:
- **Ζωντανή Σάρωση (Live Scan)**: Real-time ανίχνευση και αποκωδικοποίηση QR codes μέσω κάμερας/webcam (OpenCV / QReader / Camera).
- **Σάρωση από Εικόνα & Clipboard**: Επιλογή αρχείου εικόνας από δίσκο ή επικόλληση εικόνας από το πρόχειρο.
- **Έξυπνη Ταξινόμηση Περιεχομένου**: Αυτόματη αναγνώριση τύπου QR (URL, Wi-Fi, Γεωγραφική Τοποθεσία `geo:`, vCard/Επαφή, E-mail, Τηλέφωνο, Κείμενο/JSON).
- **Προηγμένη Προβολή Δεδομένων**:
  - URLs: Άμεσο άνοιγμα και in-app web preview.
  - JSON / Structured Data: Προβολή και επεξεργασία μέσω `flet-code-editor`.
  - Geo coordinates: Εμφάνιση σημείου σε διαδραστικό χάρτη μέσω `flet-map`.
  - Στατιστικά: Γραφήματα σαρώσεων ανά κατηγορία μέσω `flet-charts`.
- **Ηχητική & Οπτική Ανατροφοδότηση**: Ηχητικό σήμα επιτυχούς σάρωσης μέσω `flet-audio` και δυναμικά animations μέσω `flet-lottie` / `flet-spinkit`.
- **Ασφαλής Ιστορικό**: Αποθήκευση ιστορικού σαρώσεων μέσω `flet-secure-storage` και προβολή με `flet-datatable2`.
- **Γεννήτρια QR (QR Generator)**: Δημιουργία προσαρμοσμένων QR codes με επιλογή χρωμάτων μέσω `flet-color-pickers`.

## 🧩 Χρήση Built-in Extensions (Flet Standard)
1. **Αυστηρή Τήρηση Συμβατότητας Desktop & Mobile**:
   - Ορισμένα Flutter plugins (όπως κάμερα υλικού ή flashlight σε Desktop Windows) ενδέχεται να απαιτούν πλατφόρμα κινητού (Android/iOS) ή native Flutter build.
   - Στο Desktop περιβάλλον (Windows), η εφαρμογή διατηρεί **πάντα ασφαλές fallback** (π.χ. OpenCV live feed για τη webcam, fallback alerts για flashlight, κ.ο.κ.) ώστε να μην εμφανίζεται ποτέ κόκκινο σφάλμα ("Red screen of death" / "Unknown control").
2. **Mounting Services vs Controls**:
   - Υπηρεσίες όπως `Audio`, `PermissionHandler`, `SecureStorage`, `Geolocator`, `Flashlight` προστίθενται **ΜΟΝΟ** στο `page.services`. ΠΟΤΕ στο `page.overlay` ή στο visual tree.
   - Οπτικά controls όπως `CodeEditor`, `ColorPicker`, `Lottie`, `Map`, `DataTable2`, `BarChart`/`PieChart` ενσωματώνονται κανονικά στο visual hierarchy.
3. **Διαχείριση Ήχου (Audio Feedback)**:
   - Χρησιμοποιείται το `flet-audio` για ήχους επιτυχούς ανάγνωσης (beep / scan success).
   - Κλήση ασύγχρονων μεθόδων αποκλειστικά μέσω `page.run_task(audio.play)` ή `await audio.play_async()`.

## 🛡️ Αποσφαλμάτωση & Έλεγχος Λειτουργίας (Debugging Invariants)
- **Έλεγχος UI Errors**: Στο Flet, ένα UI window μπορεί να ανοίξει κανονικά αλλά να περιέχει εσωτερικό κόκκινο Flutter error box εάν ένα control αποτύχει να γίνει render.
- Κατά την ανάπτυξη και τις δοκιμές με `uv run flet run`, ελέγχουμε πάντα τα console logs και τη συμπεριφορά του παραθύρου.
- Όλες οι ευαίσθητες ενέργειες (άνοιγμα κάμερας, parsing QR, φόρτωση αρχείων) περικλείονται σε δομημένα blocks `try-except` με φιλικά μηνύματα στο UI (SnackBars / Banners).
