"""QR code & 1D/2D Barcode scanner (ZXing-CPP + OpenCV), smart semantic classifier, online product/book resolver, and webcam stream manager."""

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import ImageGrab

try:
    import zxingcpp
    HAS_ZXING = True
except ImportError:
    HAS_ZXING = False


BARCODE_1D_FORMATS = {
    "EAN13",
    "EAN8",
    "UPCA",
    "UPCE",
    "Code128",
    "Code39",
    "Code93",
    "ITF",
    "Codabar",
    "DataBar",
    "DataBarExpanded",
    "DataBarLimited",
}


def detect_gs1_country(code: str) -> str:
    """Returns the GS1 country/region name based on the first 3 digits of an EAN-13/GTIN barcode."""
    if not code or len(code) < 3 or not code[:3].isdigit():
        return "Άγνωστη Χώρα"
    p = int(code[:3])
    if 0 <= p <= 19 or 30 <= p <= 39 or 60 <= p <= 139:
        return "ΗΠΑ / Καναδάς (GS1 US)"
    if 300 <= p <= 379:
        return "Γαλλία"
    if p == 380:
        return "Βουλγαρία"
    if p == 383:
        return "Σλοβενία"
    if p == 385:
        return "Κροατία"
    if 400 <= p <= 440:
        return "Γερμανία"
    if 450 <= p <= 459 or 490 <= p <= 499:
        return "Ιαπωνία"
    if 460 <= p <= 469:
        return "Ρωσία"
    if p == 471:
        return "Ταϊβάν"
    if 489 == p or (690 <= p <= 699):
        return "Κίνα"
    if 500 <= p <= 509:
        return "Ηνωμένο Βασίλειο (UK)"
    if p in (520, 521):
        return "Ελλάδα 🇬🇷 (GS1 Association Greece)"
    if p == 528:
        return "Λίβανος"
    if p == 529:
        return "Κύπρος 🇨🇾"
    if p == 531:
        return "Βόρεια Μακεδονία"
    if p == 535:
        return "Μάλτα"
    if p == 539:
        return "Ιρλανδία"
    if 540 <= p <= 549:
        return "Βέλγιο / Λουξεμβούργο"
    if p == 560:
        return "Πορτογαλία"
    if p == 569:
        return "Ισλανδία"
    if 570 <= p <= 579:
        return "Δανία"
    if p == 590:
        return "Πολωνία"
    if p == 594:
        return "Ρουμανία"
    if p == 599:
        return "Ουγγαρία"
    if 640 <= p <= 649:
        return "Φινλανδία"
    if 700 <= p <= 709:
        return "Νορβηγία"
    if p == 729:
        return "Ισραήλ"
    if 730 <= p <= 739:
        return "Σουηδία"
    if 754 <= p <= 755:
        return "Καναδάς"
    if 760 <= p <= 769:
        return "Ελβετία"
    if 800 <= p <= 839:
        return "Ιταλία"
    if 840 <= p <= 849:
        return "Ισπανία"
    if p == 858:
        return "Σλοβακία"
    if p == 859:
        return "Τσεχία"
    if p == 860:
        return "Σερβία"
    if 868 <= p <= 869:
        return "Τουρκία"
    if 870 <= p <= 879:
        return "Ολλανδία"
    if p == 880:
        return "Νότια Κορέα"
    if p == 890:
        return "Ινδία"
    if 900 <= p <= 919:
        return "Αυστρία"
    if 930 <= p <= 939:
        return "Αυστραλία"
    if 940 <= p <= 949:
        return "Νέα Ζηλανδία"
    if p == 977:
        return "Περιοδικό / Εφημερίδα (ISSN)"
    if p in (978, 979):
        return "Διεθνής Κωδικός Βιβλίου (ISBN / Bookland)"
    return f"Διεθνές Πρόθεμα GS1 ({code[:3]})"


def lookup_product_online(barcode_str: str) -> Dict[str, Any]:
    """Queries OpenFoodFacts, OpenBeautyFacts, OpenProductsFacts, or OpenLibrary APIs for live product/book details."""
    code = (barcode_str or "").strip()
    info: Dict[str, Any] = {"found": False}
    if not code or not code.isdigit():
        return info

    headers = {"User-Agent": "SpyQR/0.1.5 (Desktop QR & Barcode Scanner Utility)"}

    # 1. If ISBN (978 / 979), query OpenLibrary Books API
    if len(code) == 13 and code.startswith(("978", "979")):
        try:
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{code}&format=json&jscmd=data"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                book_key = f"ISBN:{code}"
                if book_key in data:
                    b = data[book_key]
                    authors = ", ".join(a.get("name", "") for a in b.get("authors", []))
                    publishers = ", ".join(p.get("name", "") for p in b.get("publishers", []))
                    return {
                        "found": True,
                        "source": "OpenLibrary",
                        "name": b.get("title", "Βιβλίο"),
                        "brand": authors or publishers,
                        "category": "Βιβλίο / Έκδοση (ISBN)",
                        "quantity": f"Σελίδες: {b.get('number_of_pages', '-')}",
                        "publish_date": b.get("publish_date", ""),
                    }
        except Exception:
            pass

    # 2. Query OpenFoodFacts / OpenBeautyFacts / OpenProductsFacts
    endpoints = [
        ("OpenFoodFacts", f"https://world.openfoodfacts.org/api/v2/product/{code}.json"),
        ("OpenBeautyFacts", f"https://world.openbeautyfacts.org/api/v2/product/{code}.json"),
        ("OpenProductsFacts", f"https://world.openproductsfacts.org/api/v2/product/{code}.json"),
    ]
    for source_name, url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == 1 and "product" in data:
                    p = data["product"]
                    name = (
                        p.get("product_name_el")
                        or p.get("product_name")
                        or p.get("generic_name_el")
                        or p.get("generic_name")
                        or ""
                    ).strip()
                    brand = (p.get("brands") or "").strip()
                    categories = (p.get("categories") or "").strip()
                    quantity = (p.get("quantity") or "").strip()
                    nutriscore = (p.get("nutriscore_grade") or "").upper()
                    if name or brand:
                        return {
                            "found": True,
                            "source": source_name,
                            "name": name or f"Προϊόν ({brand})",
                            "brand": brand,
                            "category": categories[:80] if categories else "Εμπορικό Προϊόν",
                            "quantity": quantity,
                            "nutriscore": nutriscore,
                        }
        except Exception:
            continue

    return info


def parse_qr_content(raw: str, code_format: str = "QRCode") -> Dict[str, Any]:
    """Analyzes raw QR or Barcode string and determines exact semantic type, human description, and action parameters."""
    text = (raw or "").strip()
    fmt = (code_format or "QRCode").strip()
    is_1d_barcode = fmt in BARCODE_1D_FORMATS or (
        fmt.upper() not in ("QRCODE", "QR_CODE", "MICROQRCODE") and fmt != ""
    )

    result: Dict[str, Any] = {
        "raw": text,
        "format": fmt,
        "type": "TEXT",
        "title": "Απλό Κείμενο",
        "summary": "Ελεύθερο κείμενο ή σημείωση",
        "icon": "notes",
        "details": {"format": fmt, "Είδος Κώδικα": fmt, "Περιεχόμενο": text},
    }

    if not text:
        return result

    # -------------------------------------------------------------
    # 1. PRODUCT / BOOK / MAGAZINE / COMMERCIAL BARCODES
    # -------------------------------------------------------------
    digits_only = re.match(r"^\d{8,14}$", text) is not None
    if digits_only and len(text) in (8, 12, 13, 14):
        country = detect_gs1_country(text if len(text) != 12 else "0" + text)
        # Check if ISBN Book (978 / 979)
        if len(text) == 13 and text.startswith(("978", "979")):
            result["type"] = "BOOK"
            result["format"] = fmt if is_1d_barcode else "ISBN-13"
            result["title"] = "Βιβλίο (Κωδικός ISBN-13)"
            result["summary"] = f"Διεθνής Κωδικός Βιβλίου ISBN: {text}"
            result["icon"] = "menu_book"
            result["details"] = {
                "Κατηγορία": "Βιβλίο / Εκδόσεις (ISBN-13)",
                "Κωδικός ISBN": text,
                "Μορφή Barcode": result["format"],
                "Προέλευση": country,
                "lookup_url": f"https://www.google.com/search?q=ISBN+{text}",
                "skroutz_url": f"https://www.skroutz.gr/search?keyphrase={text}",
            }
            return result

        # Check if ISSN Magazine / Newspaper (977)
        if len(text) == 13 and text.startswith("977"):
            result["type"] = "MAGAZINE"
            result["format"] = fmt if is_1d_barcode else "ISSN-13"
            result["title"] = "Περιοδικό / Εφημερίδα (ISSN)"
            result["summary"] = f"Κωδικός Περιοδικής Έκδοσης ISSN: {text}"
            result["icon"] = "newspaper"
            result["details"] = {
                "Κατηγορία": "Περιοδικό / Τύπος (ISSN)",
                "Κωδικός ISSN": text,
                "Μορφή Barcode": result["format"],
                "lookup_url": f"https://www.google.com/search?q=ISSN+{text}",
            }
            return result

        # Commercial Retail Product (EAN-13, EAN-8, UPC-A, GTIN-14)
        effective_fmt = fmt if is_1d_barcode else (
            "EAN-13" if len(text) == 13 else ("EAN-8" if len(text) == 8 else ("UPC-A" if len(text) == 12 else "GTIN-14"))
        )
        result["type"] = "PRODUCT"
        result["format"] = effective_fmt
        result["title"] = f"Εμπορικό Προϊόν ({effective_fmt})"
        result["summary"] = f"Προϊόν Λιανικής • Κωδικός: {text} • {country}"
        result["icon"] = "shopping_bag"
        result["details"] = {
            "Κατηγορία": "Εμπορικό Προϊόν Λιανικής (GTIN / EAN)",
            "Κωδικός Προϊόντος": text,
            "Πρότυπο Barcode": effective_fmt,
            "Χώρα Καταχώρησης GS1": country,
            "Κατάσταση Αναζήτησης": "Αναζήτηση στοιχείων προϊόντος...",
            "lookup_url": f"https://www.google.com/search?q={text}",
            "skroutz_url": f"https://www.skroutz.gr/search?keyphrase={text}",
            "openfoodfacts_url": f"https://world.openfoodfacts.org/product/{text}",
        }
        return result

    # -------------------------------------------------------------
    # 2. INDUSTRIAL / LOGISTICS BARCODE (Code128, Code39, ITF, etc.)
    # -------------------------------------------------------------
    if is_1d_barcode:
        result["type"] = "BARCODE"
        result["format"] = fmt
        result["title"] = f"Γραμμωτός Κώδικας Αποθήκης / Σειριακός ({fmt})"
        result["summary"] = f"Κωδικός Logistics / Σειριακός Αριθμός ({fmt}): {text}"
        result["icon"] = "inventory_2"
        result["details"] = {
            "Κατηγορία": "Βιομηχανικός Κώδικας / Αποθήκη / Courier",
            "Περιεχόμενο Κωδικού": text,
            "Πρότυπο Barcode": fmt,
            "Μήκος Χαρακτήρων": str(len(text)),
            "lookup_url": f"https://www.google.com/search?q={urllib.parse.quote(text)}",
        }
        return result

    # -------------------------------------------------------------
    # 3. WI-FI NETWORK
    # -------------------------------------------------------------
    if text.upper().startswith("WIFI:"):
        result["type"] = "WIFI"
        result["title"] = "Ασύρματο Δίκτυο Wi-Fi"
        result["icon"] = "wifi"
        ssid_match = re.search(r"[;:]S:([^;]+)", text, re.IGNORECASE)
        pass_match = re.search(r"[;:]P:([^;]+)", text, re.IGNORECASE)
        type_match = re.search(r"[;:]T:([^;]+)", text, re.IGNORECASE)
        hidden_match = re.search(r"[;:]H:([^;]+)", text, re.IGNORECASE)
        ssid = ssid_match.group(1) if ssid_match else "Άγνωστο Δίκτυο"
        sec = type_match.group(1) if type_match else "WPA/WPA2"
        pwd = pass_match.group(1) if pass_match else "(Χωρίς Κωδικό)"
        result["summary"] = f"Δίκτυο Wi-Fi «{ssid}» (Ασφάλεια: {sec})"
        result["details"] = {
            "Κατηγορία": "Σύνδεση Ασύρματου Δικτύου Wi-Fi",
            "Όνομα Δικτύου (SSID)": ssid,
            "Κωδικός Πρόσβασης (Password)": pwd,
            "Τύπος Ασφαλείας": sec,
            "Κρυφό Δίκτυο": "Ναι" if (hidden_match and hidden_match.group(1).lower() == "true") else "Όχι",
        }
        return result

    # -------------------------------------------------------------
    # 4. CRYPTO / PAYMENT / IBAN
    # -------------------------------------------------------------
    if text.lower().startswith(("bitcoin:", "ethereum:", "solana:", "litecoin:")):
        coin = text.split(":")[0].capitalize()
        addr = text.split(":")[1].split("?")[0]
        result["type"] = "CRYPTO"
        result["title"] = f"Πορτοφόλι Κρυπτονομίσματος ({coin})"
        result["summary"] = f"Διεύθυνση Πληρωμής {coin}: {addr[:24]}..."
        result["icon"] = "currency_bitcoin"
        result["details"] = {
            "Κατηγορία": f"Πληρωμή Κρυπτονομίσματος ({coin})",
            "Νόμισμα": coin,
            "Διεύθυνση Πορτοφολιού": addr,
            "Πλήρες URI": text,
        }
        return result

    if text.startswith("BCD\n") or re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", text.replace(" ", "")):
        result["type"] = "PAYMENT"
        result["title"] = "Τραπεζική Πληρωμή / IBAN (EPC QR)"
        result["summary"] = f"Στοιχεία Τραπεζικού Λογαριασμού / Έμβασμα SEPA"
        result["icon"] = "account_balance"
        result["details"] = {
            "Κατηγορία": "Τραπεζική Συναλλαγή / IBAN",
            "Στοιχεία": text,
        }
        return result

    # -------------------------------------------------------------
    # 5. CALENDAR EVENT (VEVENT)
    # -------------------------------------------------------------
    if "BEGIN:VEVENT" in text.upper():
        sum_match = re.search(r"\nSUMMARY:(.*?)\r?\n", text, re.IGNORECASE)
        loc_match = re.search(r"\nLOCATION:(.*?)\r?\n", text, re.IGNORECASE)
        dt_match = re.search(r"\nDTSTART[^:]*:(.*?)\r?\n", text, re.IGNORECASE)
        ev_title = sum_match.group(1).strip() if sum_match else "Προγραμματισμένη Εκδήλωση"
        result["type"] = "EVENT"
        result["title"] = f"Εκδήλωση Ημερολογίου: {ev_title}"
        result["summary"] = f"Ραντεβού / Εκδήλωση: {ev_title}"
        result["icon"] = "event"
        result["details"] = {
            "Κατηγορία": "Εκδήλωση Ημερολογίου (iCalendar / vEvent)",
            "Τίτλος Εκδήλωσης": ev_title,
            "Τοποθεσία": loc_match.group(1).strip() if loc_match else "-",
            "Έναρξη": dt_match.group(1).strip() if dt_match else "-",
        }
        return result

    # -------------------------------------------------------------
    # 6. VCARD / MECARD (CONTACT)
    # -------------------------------------------------------------
    if "BEGIN:VCARD" in text.upper() or text.upper().startswith("MECARD:"):
        result["type"] = "VCARD"
        fn_match = re.search(r"\nFN:(.*?)\r?\n", text, re.IGNORECASE) or re.search(r"N:([^;]+)", text, re.IGNORECASE)
        tel_match = re.search(r"\nTEL[^:]*:(.*?)\r?\n", text, re.IGNORECASE) or re.search(r"TEL:([^;]+)", text, re.IGNORECASE)
        email_match = re.search(r"\nEMAIL[^:]*:(.*?)\r?\n", text, re.IGNORECASE) or re.search(r"EMAIL:([^;]+)", text, re.IGNORECASE)
        org_match = re.search(r"\nORG:(.*?)\r?\n", text, re.IGNORECASE) or re.search(r"ORG:([^;]+)", text, re.IGNORECASE)
        person_name = fn_match.group(1).strip() if fn_match else "Επαφή"
        phone_val = tel_match.group(1).strip() if tel_match else "-"
        email_val = email_match.group(1).strip() if email_match else "-"
        org_val = org_match.group(1).strip() if org_match else "-"
        result["title"] = f"Κάρτα Επαφής ({person_name})"
        result["summary"] = f"Επαφή: {person_name} • Τηλ: {phone_val}"
        result["icon"] = "contact_page"
        result["details"] = {
            "Κατηγορία": "Κάρτα Επαφής (vCard / MeCard)",
            "Ονοματεπώνυμο": person_name,
            "Τηλέφωνο": phone_val,
            "Email": email_val,
            "Εταιρεία / Οργανισμός": org_val,
        }
        return result

    # -------------------------------------------------------------
    # 7. GEO LOCATION / MAPS
    # -------------------------------------------------------------
    geo_match = re.match(r"^geo:([+-]?\d+(?:\.\d+)?),([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    maps_match = re.search(r"[?&]q=([+-]?\d+(?:\.\d+)?),([+-]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if geo_match or maps_match:
        m = geo_match or maps_match
        lat = float(m.group(1))
        lon = float(m.group(2))
        result["type"] = "GEO"
        result["title"] = "Γεωγραφική Τοποθεσία (Συντεταγμένες GPS)"
        result["summary"] = f"Στίγμα Χάρτη: Πλάτος {lat}, Μήκος {lon}"
        result["icon"] = "location_on"
        result["details"] = {
            "Κατηγορία": "Γεωγραφικό Στίγμα GPS",
            "Γεωγραφικό Πλάτος (Latitude)": str(lat),
            "Γεωγραφικό Μήκος (Longitude)": str(lon),
            "latitude": lat,
            "longitude": lon,
            "lookup_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
        }
        return result

    # -------------------------------------------------------------
    # 8. SMS MESSAGE
    # -------------------------------------------------------------
    if text.lower().startswith(("smsto:", "sms:")):
        parts = text.split(":", 2)
        recipient = parts[1] if len(parts) > 1 else ""
        msg_body = parts[2] if len(parts) > 2 else ""
        result["type"] = "SMS"
        result["title"] = f"Μήνυμα SMS προς {recipient}"
        result["summary"] = f"Αποστολή SMS στον αριθμό {recipient}"
        result["icon"] = "sms"
        result["details"] = {
            "Κατηγορία": "Μήνυμα SMS",
            "Παραλήπτης": recipient,
            "Κείμενο Μηνύματος": msg_body or "-",
        }
        return result

    # -------------------------------------------------------------
    # 9. EMAIL
    # -------------------------------------------------------------
    if text.lower().startswith(("mailto:", "matmsg:")) or re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", text):
        email_clean = text[7:] if text.lower().startswith("mailto:") else text
        email_addr = email_clean.split("?")[0]
        result["type"] = "EMAIL"
        result["title"] = f"Διεύθυνση Email ({email_addr})"
        result["summary"] = f"Ηλεκτρονικό Ταχυδρομείο: {email_addr}"
        result["icon"] = "email"
        result["details"] = {
            "Κατηγορία": "Ηλεκτρονικό Ταχυδρομείο (Email)",
            "Διεύθυνση Email": email_addr,
            "lookup_url": f"mailto:{email_addr}",
        }
        return result

    # -------------------------------------------------------------
    # 10. TELEPHONE
    # -------------------------------------------------------------
    if text.lower().startswith("tel:") or re.match(r"^\+?[\d\s\-()]{7,15}$", text):
        phone_clean = text[4:] if text.lower().startswith("tel:") else text
        result["type"] = "TEL"
        result["title"] = f"Τηλεφωνικός Αριθμός ({phone_clean.strip()})"
        result["summary"] = f"Κλήση Τηλεφώνου: {phone_clean.strip()}"
        result["icon"] = "phone"
        result["details"] = {
            "Κατηγορία": "Τηλεφωνικός Αριθμός",
            "Αριθμός": phone_clean.strip(),
        }
        return result

    # -------------------------------------------------------------
    # 11. URL / WEBSITE / SOCIAL / GOV.GR / YOUTUBE
    # -------------------------------------------------------------
    if re.match(r"^https?://", text, re.IGNORECASE) or text.lower().startswith("www."):
        url = text if text.lower().startswith("http") else f"https://{text}"
        parsed_u = urllib.parse.urlparse(url)
        domain = (parsed_u.netloc or "").lower()

        site_kind = "Ιστοσελίδα / Σύνδεσμος Ιστού"
        if "youtube.com" in domain or "youtu.be" in domain:
            site_kind = "Βίντεο YouTube"
        elif "gov.gr" in domain or "aade.gr" in domain or "myaade" in domain:
            site_kind = "Κρατικό Έγγραφο / Απόδειξη (gov.gr / ΑΑΔΕ)"
        elif "skroutz.gr" in domain or "bestprice.gr" in domain or "amazon." in domain:
            site_kind = "Ηλεκτρονικό Κατάστημα (E-Shop)"
        elif "github.com" in domain or "gitlab.com" in domain:
            site_kind = "Αποθετήριο Κώδικα (GitHub / GitLab)"
        elif any(s in domain for s in ("facebook.com", "instagram.com", "linkedin.com", "tiktok.com", "x.com", "twitter.com")):
            site_kind = "Κοινωνικό Δίκτυο (Social Media)"
        elif "maps.google" in domain or "goo.gl/maps" in url.lower():
            site_kind = "Χάρτης Google Maps"

        result["type"] = "URL"
        result["title"] = f"{site_kind} ({domain})"
        result["summary"] = f"{site_kind} στο domain {domain}"
        result["icon"] = "language"
        result["details"] = {
            "Κατηγορία": site_kind,
            "Τομέας (Domain)": domain,
            "Πλήρης Διεύθυνση URL": url,
            "url": url,
            "lookup_url": url,
        }
        return result

    # -------------------------------------------------------------
    # 12. JSON / STRUCTURED DATA
    # -------------------------------------------------------------
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            parsed = json.loads(text)
            keys_str = ", ".join(list(parsed.keys())[:6]) if isinstance(parsed, dict) else f"Λίστα {len(parsed)} στοιχείων"
            result["type"] = "JSON"
            result["title"] = "Δομημένα Δεδομένα JSON"
            result["summary"] = f"Αντικείμενο JSON ({keys_str})"
            result["icon"] = "data_object"
            result["details"] = {
                "Κατηγορία": "Δομημένα Δεδομένα JSON",
                "Πεδία / Κλειδιά": keys_str,
                "formatted": json.dumps(parsed, indent=2, ensure_ascii=False),
            }
            return result
        except Exception:
            pass

    return result


class CameraScanner:
    """Manages OpenCV webcam video stream and real-time QR + 1D/2D Barcode detection."""

    def __init__(
        self,
        on_frame: Callable[[bytes], None],
        on_scan: Callable[[str, Dict[str, Any]], None],
    ):
        self.on_frame = on_frame
        self.on_scan = on_scan
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._qr_detector = cv2.QRCodeDetector()
        self._barcode_detector = (
            cv2.barcode.BarcodeDetector() if hasattr(cv2, "barcode") else None
        )
        self._last_detected_text = ""
        self._last_scan_time = 0.0
        self.paused = False

    def is_running(self) -> bool:
        return self._running

    def _detect_any_code(
        self, frame: np.ndarray
    ) -> Tuple[Optional[str], str, Optional[np.ndarray]]:
        """Detects QR codes and all 1D/2D Barcodes using ZXing-CPP with OpenCV fallback."""
        if HAS_ZXING:
            try:
                results = zxingcpp.read_barcodes(frame)
                if results:
                    r = results[0]
                    text = (r.text or "").strip()
                    if text:
                        fmt_name = r.format.name if hasattr(r, "format") else "BARCODE"
                        pos = r.position
                        pts = np.array(
                            [
                                [pos.top_left.x, pos.top_left.y],
                                [pos.top_right.x, pos.top_right.y],
                                [pos.bottom_right.x, pos.bottom_right.y],
                                [pos.bottom_left.x, pos.bottom_left.y],
                            ],
                            dtype=np.int32,
                        )
                        return text, fmt_name, pts
            except Exception as e:
                print(f"[CameraScanner] ZXing detection error: {e}")

        try:
            val, pts, _ = self._qr_detector.detectAndDecode(frame)
            if val:
                return val.strip(), "QRCode", pts
        except Exception:
            pass

        if self._barcode_detector is not None:
            try:
                retval, decoded_info, decoded_type, points = (
                    self._barcode_detector.detectAndDecodeWithType(frame)
                )
                if retval and decoded_info:
                    for info, btype, bpts in zip(decoded_info, decoded_type, points):
                        if info:
                            return info.strip(), str(btype or "BARCODE"), bpts
            except Exception:
                pass

        return None, "", None

    def open_camera(self, camera_index: int = 0) -> bool:
        """Opens the webcam device without starting an OS thread (for async loop usage)."""
        if self._running and self._cap and self._cap.isOpened():
            return True

        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            print(f"[CameraScanner] Failed to open camera index {camera_index}")
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._cap = cap
        self._running = True
        self.paused = False
        return True

    def grab_frame(self) -> Tuple[Optional[bytes], Optional[Tuple[str, Dict[str, Any]]]]:
        """Reads and processes a single frame synchronously (designed for asyncio.to_thread)."""
        if not self._running or not self._cap or not self._cap.isOpened():
            return None, None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None, None

        scan_event: Optional[Tuple[str, Dict[str, Any]]] = None

        if not self.paused:
            val, fmt_name, pts = self._detect_any_code(frame)
            if val:
                if pts is not None:
                    pts_int = pts.astype(int)
                    cv2.polylines(frame, [pts_int], True, (0, 255, 128), 3)
                    try:
                        flat_pts = pts_int.reshape(-1, 2)
                        lx, ly = int(flat_pts[0][0]), max(22, int(flat_pts[0][1]) - 10)
                        cv2.putText(
                            frame,
                            f"{fmt_name}: {val[:24]}",
                            (lx, ly),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.55,
                            (0, 255, 128),
                            2,
                        )
                    except Exception:
                        pass

                now = time.time()
                if (val != self._last_detected_text) or (now - self._last_scan_time > 2.5):
                    self._last_detected_text = val
                    self._last_scan_time = now
                    parsed = parse_qr_content(val, fmt_name)
                    scan_event = (val, parsed)

        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        box_w, box_h = 180, 140
        cv2.rectangle(
            frame,
            (cx - box_w, cy - box_h),
            (cx + box_w, cy + box_h),
            (0, 200, 255),
            1,
        )
        cv2.line(frame, (cx - box_w + 15, cy), (cx + box_w - 15, cy), (0, 120, 255), 1)

        bracket_len = 22
        color = (0, 255, 128) if (time.time() - self._last_scan_time < 0.8) else (0, 200, 255)
        cv2.line(frame, (cx - box_w, cy - box_h), (cx - box_w + bracket_len, cy - box_h), color, 3)
        cv2.line(frame, (cx - box_w, cy - box_h), (cx - box_w, cy - box_h + bracket_len), color, 3)
        cv2.line(frame, (cx + box_w, cy - box_h), (cx + box_w - bracket_len, cy - box_h), color, 3)
        cv2.line(frame, (cx + box_w, cy - box_h), (cx + box_w, cy - box_h + bracket_len), color, 3)
        cv2.line(frame, (cx - box_w, cy + box_h), (cx - box_w + bracket_len, cy + box_h), color, 3)
        cv2.line(frame, (cx - box_w, cy + box_h), (cx - box_w, cy + box_h - bracket_len), color, 3)
        cv2.line(frame, (cx + box_w, cy + box_h), (cx + box_w - bracket_len, cy + box_h), color, 3)
        cv2.line(frame, (cx + box_w, cy + box_h), (cx + box_w, cy + box_h - bracket_len), color, 3)

        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return buffer.tobytes(), scan_event

    def start(self, camera_index: int = 0) -> bool:
        """Starts the webcam scanning loop in a background daemon thread."""
        if not self.open_camera(camera_index):
            return False
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stops the webcam stream and releases camera resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _worker_loop(self) -> None:
        """Internal capture loop running on worker thread."""
        while self._running and self._cap and self._cap.isOpened():
            frame_bytes, scan_event = self.grab_frame()
            if frame_bytes is None:
                time.sleep(0.05)
                continue
            if scan_event:
                try:
                    self.on_scan(scan_event[0], scan_event[1])
                except Exception as e:
                    print(f"[CameraScanner] Error in on_scan callback: {e}")
            try:
                self.on_frame(frame_bytes)
            except Exception:
                pass
            time.sleep(0.03)

    def scan_image_file(self, file_path: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Scans a static image file from disk for QR codes or Barcodes."""
        try:
            img_array = np.fromfile(file_path, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img is None:
                return None
            val, fmt_name, _ = self._detect_any_code(img)
            if val:
                parsed = parse_qr_content(val, fmt_name)
                return val, parsed
        except Exception as e:
            print(f"[CameraScanner] Image file scan error: {e}")
        return None

    def scan_clipboard(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Scans an image currently stored in system clipboard for QR codes or Barcodes."""
        try:
            clip_img = ImageGrab.grabclipboard()
            if clip_img is not None:
                cv_img = cv2.cvtColor(np.array(clip_img.convert("RGB")), cv2.COLOR_RGB2BGR)
                val, fmt_name, _ = self._detect_any_code(cv_img)
                if val:
                    parsed = parse_qr_content(val, fmt_name)
                    return val, parsed
        except Exception as e:
            print(f"[CameraScanner] Clipboard scan error: {e}")
        return None
