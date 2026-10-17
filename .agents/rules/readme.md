---
description: "README.md Standards & Rules (Strict Prohibitions: NO compilation/execution commands, NO project tree structure, NO creator links, NO version tags/numbers/comments in README)"
trigger: always
---

# 📜 Κανόνες Δομής & Περιεχομένου README.md (README Standards)

*Αυτός ο κανόνας ορίζει αυστηρά τι επιτρέπεται και τι απαγορεύεται στη σύνταξη και ενημέρωση του `README.md` και των `Release Notes` σε όλα τα projects.*

---

## ⛔ ΑΥΣΤΗΡΕΣ ΑΠΑΓΟΡΕΥΣΕΙΣ (STRICTLY FORBIDDEN)

1. **ΔΕΝ ΒΑΖΟΥΜΕ ΠΟΤΕ ΠΛΗΡΟΦΟΡΙΕΣ ΜΕΤΑΓΛΩΤΤΙΣΗΣ Η ΕΚΤΕΛΕΣΗΣ ΚΩΔΙΚΑ**:
   - ΑΠΑΓΟΡΕΥΕΤΑΙ η αναγραφή εντολών εκτέλεσης, σύνταξης εντολών terminal (`uv run ...`, `python main.py`, `npm start`, `flutter run`, κ.λπ.) ή οδηγιών μεταγλώττισης (PyInstaller build commands, compiler parameters).

2. **ΔΕΝ ΒΑΖΟΥΜΕ ΠΟΤΕ ΤΗ ΔΟΜΗ ΤΟΥ PROJECT (NO DIRECTORY TREE)**:
   - ΑΠΑΓΟΡΕΥΕΤΑΙ η συμπερίληψη της δομής φακέλων/αρχείων (project tree structure / ASCII trees `├── src/`) στο README.md.

3. **ΔΕΝ ΒΑΖΟΥΜΕ ΠΟΤΕ LINKS ΔΗΜΙΟΥΡΓΟΥ (NO CREATOR LINKS)**:
   - ΑΠΑΓΟΡΕΥΕΤΑΙ η συμπερίληψη αναφορών, συνδέσμων ή ενοτήτων δημιουργού (Creator links, personal website URLs, portfolio links) στο README.md ή στα Release Notes.

4. **ΔΕΝ ΒΑΖΟΥΜΕ ΠΟΤΕ ΕΚΔΟΣΕΙΣ / ΕΙΚΟΝΙΔΙΑ ΕΚΔΟΣΕΩΝ / ΣΧΟΛΙΑ ΕΚΔΟΣΕΩΝ ΣΤΟ README.MD**:
   - ΑΠΑΓΟΡΕΥΕΤΑΙ αυστηρά η αναγραφή αριθμών εκδόσεων, version tags (π.χ. `(v0.2.2)`, `(v1.0.0)`), σχολίων εκδόσεων ή κανόνων versioning μέσα στους τίτλους ή στα bullet points του `README.md`. Το `README.md` περιγράφει αποκλειστικά τις δυνατότητες της εφαρμογής στα Ελληνικά.

5. **Διαγραφή Υπαρχόντων Features (Deleting History)**:
   - ΑΠΑΓΟΡΕΥΕΤΑΙ η αφαίρεση ή διαγραφή πραγματικών λειτουργιών της εφαρμογής κατά τη διάρκεια ενημερώσεων.

6. **Dummy / Placeholder Content**:
   - ΑΠΑΓΟΡΕΥΟΝΤΑΙ τα placeholder links, κενές ενότητες, ή ψεύτικες πληροφορίες.

---

## ✅ ΤΙ ΕΠΙΤΡΕΠΕΤΑΙ & ΑΠΑΙΤΕΙΤΑΙ (ALLOWED / REQUIRED)

1. **Ελληνικό README.md & Ελληνικά Release Notes**:
   - Το `README.md` και τα Release Notes στο GitHub **ΠΡΕΠΕΙ** να συντάσσονται **ΠΑΝΤΑ στα Ελληνικά**.

2. **Σύντομη & Καθαρή Δομή Ενοτήτων**:
   - `# [Project Name] [Emoji]`
   - `> [Σύντομη Περιγραφή / Tagline]`
   - `## 🌟 Χαρακτηριστικά` (χωρίς αριθμό έκδοσης στον τίτλο ή στα bullets)
   - `## 🛠️ Αντιμετώπιση Προβλημάτων & Οδηγίες` (όπου απαιτείται)
