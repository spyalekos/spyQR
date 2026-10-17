import asyncio
import base64
import json
import os
import sys
import threading
import time
import webbrowser
from typing import Any, Dict, List, Optional
import flet as ft

# 14 Flet Built-in Extensions:
import flet_audio as fa
import flet_camera as fcam
import flet_charts as fc
import flet_code_editor as fce
import flet_color_pickers as fcp
import flet_datatable2 as fdt
import flet_flashlight as ff
import flet_geolocator as fg
import flet_lottie as flot
import flet_map as fm
import flet_permission_handler as fph
import flet_secure_storage as fss
import flet_spinkit as fsk
import flet_webview as fwv

from generator import generate_qr_image, save_qr_to_file
from history import HistoryManager
from scanner import CameraScanner, lookup_product_online, parse_qr_content
from version import APP_DESCRIPTION, APP_NAME, __version__


def get_assets_path() -> str:
    """Returns absolute path to the assets directory (supports PyInstaller bundle)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    return assets_dir


def main(page: ft.Page):
    """Main application lifecycle and UI setup."""
    page.title = f"{APP_NAME} v{__version__} - QR Code Scanner & Utility"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 1100
    page.window.height = 800
    page.window.min_width = 850
    page.window.min_height = 650

    try:
        page.run_task(page.window.center)
    except Exception:
        pass

    assets_dir = get_assets_path()
    beep_wav_path = os.path.join(assets_dir, "beep.wav")

    # ---------------------------------------------------------
    # 1. MOUNTING SERVICES (Definitive Standard: page.services)
    # ---------------------------------------------------------
    audio_player = fa.Audio(
        src=beep_wav_path if os.path.exists(beep_wav_path) else "assets/beep.wav",
        autoplay=False,
    )
    permission_handler = fph.PermissionHandler()
    secure_storage = fss.SecureStorage()
    flashlight_service = ff.Flashlight()
    geolocator_service = fg.Geolocator()
    clipboard_service = ft.Clipboard()

    page.services.append(audio_player)
    page.services.append(permission_handler)
    page.services.append(secure_storage)
    page.services.append(flashlight_service)
    page.services.append(geolocator_service)
    page.services.append(clipboard_service)

    # ---------------------------------------------------------
    # 2. STATE & MANAGERS
    # ---------------------------------------------------------
    history_mgr = HistoryManager(page, secure_storage)
    sound_enabled = True
    flashlight_on = False
    current_result: Dict[str, Any] = {
        "raw": "5201054001050",
        "type": "PRODUCT",
        "format": "EAN-13",
        "title": "Εμπορικό Προϊόν (EAN-13)",
        "summary": "Κωδικός Προϊόντος: 5201054001050 • Προέλευση: Ελλάδα 🇬🇷 (GS1 Association Greece)",
        "icon": "shopping_bag",
        "details": {
            "Κατηγορία": "Εμπορικό Προϊόν Λιανικής",
            "Πρότυπο Barcode": "EAN-13",
            "Κωδικός GTIN / EAN": "5201054001050",
            "Χώρα / Προέλευση (GS1)": "Ελλάδα 🇬🇷 (GS1 Association Greece)",
        },
    }

    def play_beep():
        if sound_enabled and audio_player:
            try:
                page.run_task(audio_player.play)
            except Exception as e:
                print(f"[Audio] Play error: {e}")

    # ---------------------------------------------------------
    # 3. CAMERA & SCANNER ENGINE
    # ---------------------------------------------------------
    # Valid 1x1 dark PNG so ft.Image.src is never empty (prevents Flutter "valid src value must be specified." error)
    INITIAL_FRAME_BYTES = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x60\x60"
        b"\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    camera_view = ft.Image(
        src=INITIAL_FRAME_BYTES,
        fit=ft.BoxFit.CONTAIN,
        width=640,
        height=480,
        border_radius=12,
        gapless_playback=True,
    )
    placeholder_status_text = ft.Text(
        "Η κάμερα είναι ανενεργή",
        size=16,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.GREY_400,
    )
    placeholder_sub_text = ft.Text(
        "Πατήστε «Έναρξη Κάμερας» για ζωντανή σάρωση QR & Barcodes (EAN, UPC, Code128)",
        size=13,
        color=ft.Colors.GREY_500,
    )
    camera_placeholder = ft.Container(
        content=ft.Column(
            [
                fsk.Ring(color=ft.Colors.BLUE_400, size=50),
                ft.Container(height=10),
                placeholder_status_text,
                placeholder_sub_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment(0, 0),
        width=640,
        height=480,
        bgcolor="#141a29",
        border_radius=12,
        border=ft.Border.all(1, "#232f47"),
    )
    camera_stack_container = ft.Container(
        content=camera_placeholder,
        width=640,
        height=480,
        border_radius=12,
        alignment=ft.Alignment(0, 0),
    )

    last_scan_banner = ft.Text(
        "Αναμονή για σάρωση QR ή Barcode...",
        size=14,
        color=ft.Colors.LIGHT_BLUE_300,
        weight=ft.FontWeight.W_500,
        selectable=True,
    )

    def safe_update(control):
        try:
            control.update()
        except Exception:
            pass

    # Active ticker indicator (ProgressRing Ticker Pattern for Windows Desktop 60fps repaint)
    camera_live_ring = ft.ProgressRing(
        width=16,
        height=16,
        stroke_width=2,
        color=ft.Colors.GREEN_400,
        visible=False,
    )
    camera_live_badge = ft.Row(
        [
            camera_live_ring,
            ft.Text("Ζωντανή Ροή Κάμερας (Ενεργή)", size=12, color=ft.Colors.GREEN_400, weight=ft.FontWeight.W_600),
        ],
        spacing=8,
        visible=False,
    )

    def force_window_repaint():
        """Forces immediate OS window repaint on Windows Desktop (1px resize nudge pattern)."""
        try:
            page.update()
            if not getattr(page, "web", False):
                w = page.window.width
                if w:
                    page.window.width = w + 1
                    page.update()
                    page.window.width = w
                    page.update()
        except Exception:
            pass

    def on_frame_received(frame_bytes: bytes):
        if not frame_bytes:
            return
        first_mount = camera_stack_container.content is not camera_view
        camera_view.src = frame_bytes
        if first_mount:
            camera_stack_container.content = camera_view
            camera_live_ring.visible = True
            camera_live_badge.visible = True
            force_window_repaint()
        else:
            safe_update(camera_view)

    async def enrich_product_async(raw_code: str, parsed_dict: Dict[str, Any]):
        """Asynchronously queries online databases (OpenFoodFacts / OpenLibrary) for scanned product/book barcode."""
        info = await asyncio.to_thread(lookup_product_online, raw_code)
        details = parsed_dict.setdefault("details", {})
        if info.get("found"):
            prod_name = info.get("name", "")
            brand = info.get("brand", "")
            cat = info.get("category", "")
            qty = info.get("quantity", "")
            full_label = f"{prod_name} ({brand})" if brand and brand not in prod_name else prod_name
            parsed_dict["title"] = f"Προϊόν: {full_label}" if parsed_dict.get("type") == "PRODUCT" else f"Βιβλίο: {full_label}"
            parsed_dict["summary"] = f"Εντοπίστηκε: {full_label} • {cat} {qty}".strip()
            details["Ονομασία Προϊόντος"] = prod_name
            if brand:
                details["Μάρκα / Εκδότης"] = brand
            if cat:
                details["Κατηγορία Είδους"] = cat
            if qty:
                details["Ποσότητα / Μέγεθος"] = qty
            details["Κατάσταση Αναζήτησης"] = f"Βρέθηκε στη βάση {info.get('source', 'Online')}"
            last_scan_banner.value = f"✅ {parsed_dict['title']} [{raw_code}]"
            safe_update(last_scan_banner)
        else:
            details["Κατάσταση Αναζήτησης"] = "Έτοιμο για αναζήτηση σε Skroutz / Google (δεν βρέθηκε στην ανοιχτή βάση)"
        if current_result is parsed_dict:
            update_result_tab(parsed_dict)

    def on_scan_detected(raw_text: str, parsed: Dict[str, Any]):
        nonlocal current_result
        current_result = parsed
        play_beep()
        q_type = parsed.get("type", "TEXT")
        title_str = parsed.get("title", q_type)
        summary_str = parsed.get("summary", raw_text[:60])
        history_mgr.add_entry(raw_text, q_type, parsed.get("details"))
        
        last_scan_banner.value = f"✅ {title_str}: {summary_str}"
        safe_update(last_scan_banner)

        update_result_tab(parsed)
        refresh_history_tab()
        refresh_analytics_tab()

        if q_type in ("PRODUCT", "BOOK"):
            try:
                page.run_task(enrich_product_async, raw_text, parsed)
            except Exception:
                pass

        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(f"Αναγνωρίστηκε: {title_str} — {summary_str}"),
                bgcolor=ft.Colors.GREEN_800,
                duration=2800,
            )
        )

    scanner_engine = CameraScanner(
        on_frame=on_frame_received,
        on_scan=on_scan_detected,
    )

    # ---------------------------------------------------------
    # 4. FILE PICKER FOR IMAGE UPLOAD & CLIPBOARD
    # ---------------------------------------------------------
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def pick_file_click(e):
        files = await file_picker.pick_files(
            dialog_title="Επιλογή εικόνας με QR Code ή Barcode",
            file_type=ft.FilePickerFileType.IMAGE,
        )
        if files and len(files) > 0:
            file_path = files[0].path
            res = scanner_engine.scan_image_file(file_path)
            if res:
                raw_text, parsed = res
                on_scan_detected(raw_text, parsed)
                tabs.selected_index = 1
                page.update()
            else:
                page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text("Δεν εντοπίστηκε έγκυρο QR code ή Barcode στην επιλεγμένη εικόνα."),
                        bgcolor=ft.Colors.RED_800,
                    )
                )

    def scan_clipboard_click(e):
        res = scanner_engine.scan_clipboard()
        if res:
            raw_text, parsed = res
            on_scan_detected(raw_text, parsed)
            tabs.selected_index = 1
            page.update()
        else:
            page.show_dialog(
                ft.SnackBar(
                    content=ft.Text("Δεν βρέθηκε εικόνα με QR code ή Barcode στο πρόχειρο (Clipboard)."),
                    bgcolor=ft.Colors.ORANGE_800,
                )
            )

    # ---------------------------------------------------------
    # 5. UI CONTROLS & EVENT HANDLERS (Scanner Tab)
    # ---------------------------------------------------------
    start_cam_btn = ft.Button(
        content=ft.Row(
            [ft.Icon(ft.Icons.VIDEOCAM, color=ft.Colors.WHITE), ft.Text("Έναρξη Κάμερας")],
            tight=True,
        ),
        bgcolor=ft.Colors.BLUE_600,
        color=ft.Colors.WHITE,
    )
    stop_cam_btn = ft.Button(
        content=ft.Row(
            [ft.Icon(ft.Icons.VIDEOCAM_OFF, color=ft.Colors.WHITE), ft.Text("Διακοπή")],
            tight=True,
        ),
        bgcolor=ft.Colors.RED_700,
        color=ft.Colors.WHITE,
        disabled=True,
    )
    sound_btn = ft.IconButton(
        icon=ft.Icons.VOLUME_UP,
        tooltip="Ήχος σάρωσης (On/Off)",
        icon_color=ft.Colors.GREEN_400,
    )
    flash_btn = ft.IconButton(
        icon=ft.Icons.FLASH_OFF,
        tooltip="Φακός (Flashlight)",
        icon_color=ft.Colors.GREY_400,
    )

    def toggle_sound(e):
        nonlocal sound_enabled
        sound_enabled = not sound_enabled
        sound_btn.icon = ft.Icons.VOLUME_UP if sound_enabled else ft.Icons.VOLUME_OFF
        sound_btn.icon_color = ft.Colors.GREEN_400 if sound_enabled else ft.Colors.GREY_400
        sound_btn.update()

    def toggle_flashlight(e):
        nonlocal flashlight_on
        flashlight_on = not flashlight_on
        flash_btn.icon = ft.Icons.FLASH_ON if flashlight_on else ft.Icons.FLASH_OFF
        flash_btn.icon_color = ft.Colors.AMBER_400 if flashlight_on else ft.Colors.GREY_400
        flash_btn.update()
        try:
            if flashlight_on:
                page.run_task(flashlight_service.turn_on)
            else:
                page.run_task(flashlight_service.turn_off)
        except Exception:
            pass

    sound_btn.on_click = toggle_sound
    flash_btn.on_click = toggle_flashlight

    async def camera_async_worker():
        """Async camera loop on Flet's main asyncio event loop for guaranteed live UI repaint."""
        placeholder_status_text.value = "Εκκίνηση κάμερας..."
        placeholder_sub_text.value = "Παρακαλώ περιμένετε για σύνδεση με την κάμερα"
        camera_stack_container.content = camera_placeholder
        page.update()
        await asyncio.sleep(0.01)

        success = await asyncio.to_thread(scanner_engine.open_camera, 0)
        if not success:
            placeholder_status_text.value = "Η κάμερα είναι ανενεργή"
            placeholder_sub_text.value = "Πατήστε «Έναρξη Κάμερας» για ζωντανή σάρωση QR"
            camera_stack_container.content = camera_placeholder
            camera_live_ring.visible = False
            camera_live_badge.visible = False
            start_cam_btn.disabled = False
            stop_cam_btn.disabled = True
            force_window_repaint()
            page.show_dialog(
                ft.SnackBar(
                    content=ft.Text("Αποτυχία ανοίγματος κάμερας! Βεβαιωθείτε ότι υπάρχει συνδεδεμένη webcam."),
                    bgcolor=ft.Colors.RED_800,
                )
            )
            return

        start_cam_btn.disabled = True
        stop_cam_btn.disabled = False
        camera_live_ring.visible = True
        camera_live_badge.visible = True
        page.update()
        await asyncio.sleep(0.01)

        while scanner_engine.is_running():
            frame_bytes, scan_event = await asyncio.to_thread(scanner_engine.grab_frame)
            if not scanner_engine.is_running():
                break
            if frame_bytes:
                on_frame_received(frame_bytes)
            if scan_event:
                on_scan_detected(scan_event[0], scan_event[1])
            await asyncio.sleep(0.015)

    def start_camera_click(e):
        if scanner_engine.is_running():
            return
        start_cam_btn.disabled = True
        page.update()
        page.run_task(camera_async_worker)

    def stop_camera_click(e):
        scanner_engine.stop()
        camera_live_ring.visible = False
        camera_live_badge.visible = False
        placeholder_status_text.value = "Η κάμερα είναι ανενεργή"
        placeholder_sub_text.value = "Πατήστε «Έναρξη Κάμερας» για ζωντανή σάρωση QR & Barcodes (EAN, UPC, Code128)"
        camera_stack_container.content = camera_placeholder
        start_cam_btn.disabled = False
        stop_cam_btn.disabled = True
        force_window_repaint()

    start_cam_btn.on_click = start_camera_click
    stop_cam_btn.on_click = stop_camera_click

    def execute_quick_action_click(e):
        """Lightning bolt quick action: URL -> Browser, GEO -> Google Maps, Product/Other -> Result Tab."""
        q_type = current_result.get("type", "TEXT")
        raw_val = (current_result.get("raw") or "").strip()
        details = current_result.get("details", {})

        if q_type == "URL":
            target_url = details.get("url") or raw_val
            if target_url and not target_url.lower().startswith("http"):
                target_url = f"https://{target_url}"
            if target_url:
                try:
                    webbrowser.open(target_url)
                except Exception as ex:
                    print(f"[QuickAction URL] Error: {ex}")
        elif q_type == "GEO":
            lat = details.get("latitude")
            lon = details.get("longitude")
            maps_url = details.get("lookup_url")
            if not maps_url and lat is not None and lon is not None:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            elif not maps_url:
                clean_geo = raw_val[4:].split("?")[0] if raw_val.lower().startswith("geo:") else raw_val
                maps_url = f"https://www.google.com/maps/search/?api=1&query={clean_geo}"
            try:
                webbrowser.open(maps_url)
            except Exception as ex:
                print(f"[QuickAction GEO] Error: {ex}")
        else:
            tabs.selected_index = 1
            page.update()

    scanner_tab_view = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.QR_CODE_SCANNER, color=ft.Colors.BLUE_400, size=28),
                        ft.Text("Ζωντανός Σαρωτής QR & Barcodes (1D / 2D)", size=22, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Text(
                    "Αυτόματη αναγνώριση QR Codes, EAN-13, EAN-8, UPC-A/E, Code128, Code39, ITF, DataMatrix & PDF417 από κάμερα, αρχείο ή πρόχειρο.",
                    size=13,
                    color=ft.Colors.GREY_400,
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                ft.Row(
                    [
                        camera_stack_container,
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Επιλογές Σάρωσης", size=16, weight=ft.FontWeight.W_600),
                                    ft.Row([start_cam_btn, stop_cam_btn], spacing=10),
                                    camera_live_badge,
                                    ft.Divider(height=15, color="#232f47"),
                                    ft.Button(
                                        content=ft.Row([ft.Icon(ft.Icons.UPLOAD_FILE), ft.Text("Φόρτωση Εικόνας...")], tight=True),
                                        on_click=pick_file_click,
                                        bgcolor="#1e293b",
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Button(
                                        content=ft.Row([ft.Icon(ft.Icons.CONTENT_PASTE), ft.Text("Από Πρόχειρο (Clipboard)")], tight=True),
                                        on_click=scan_clipboard_click,
                                        bgcolor="#1e293b",
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Divider(height=15, color="#232f47"),
                                    ft.Row(
                                        [
                                            ft.Text("Εφέ & Ρυθμίσεις:", size=13, color=ft.Colors.GREY_400),
                                            sound_btn,
                                            flash_btn,
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Text("Τελευταίο Αποτέλεσμα:", size=12, color=ft.Colors.GREY_400),
                                                last_scan_banner,
                                                ft.Row(
                                                    [
                                                        ft.Button(
                                                            content=ft.Text("Προβολή & Επεξεργασία"),
                                                            on_click=lambda _: setattr(tabs, "selected_index", 1) or page.update(),
                                                            bgcolor=ft.Colors.BLUE_700,
                                                            color=ft.Colors.WHITE,
                                                        ),
                                                        ft.IconButton(
                                                            icon=ft.Icons.BOLT,
                                                            icon_color=ft.Colors.AMBER_400,
                                                            bgcolor="#1e293b",
                                                            tooltip="Άμεση Ενέργεια (URL ➔ Browser, GPS ➔ Google Maps, Προϊόν/Λοιπά ➔ Προβολή & Επεξεργασία)",
                                                            on_click=lambda e: execute_quick_action_click(e),
                                                        ),
                                                    ],
                                                    spacing=8,
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                ),
                                            ],
                                            spacing=6,
                                        ),
                                        padding=12,
                                        border_radius=8,
                                        bgcolor="#0f172a",
                                        border=ft.Border.all(1, "#334155"),
                                    ),
                                ],
                                spacing=12,
                            ),
                            padding=15,
                            width=380,
                            bgcolor="#111827",
                            border_radius=12,
                            border=ft.Border.all(1, "#1f2937"),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=20,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        ),
        padding=20,
    )

    # ---------------------------------------------------------
    # 6. TAB 2: RESULT & VIEWER (CodeEditor, Map, WebView)
    # ---------------------------------------------------------
    result_type_badge = ft.Container(
        content=ft.Text("PRODUCT (EAN-13)", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.BLUE_700,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=6,
    )
    result_title_text = ft.Text("Εμπορικό Προϊόν (EAN-13)", size=20, weight=ft.FontWeight.BOLD)
    result_raw_text = ft.Text(
        "5201054001050",
        size=14,
        selectable=True,
        color=ft.Colors.LIGHT_BLUE_200,
    )

    # Code Editor component
    code_editor_control = fce.CodeEditor(
        value="Κατηγορία: Εμπορικό Προϊόν Λιανικής\nΠρότυπο Barcode: EAN-13\nΚωδικός GTIN / EAN: 5201054001050\nΧώρα / Προέλευση (GS1): Ελλάδα 🇬🇷 (GS1 Association Greece)",
        language=fce.CodeLanguage.YAML,
        code_theme=fce.CodeTheme.VS2015,
        height=150,
    )

    # In-app WebView preview - supported on Android, iOS, macOS, Web
    supports_webview = bool(
        page.web
        or page.platform in [ft.PagePlatform.ANDROID, ft.PagePlatform.IOS, ft.PagePlatform.MACOS]
    )
    if supports_webview:
        webview_control = fwv.WebView(
            url="https://www.skroutz.gr",
            height=240,
        )
        webview_inner: ft.Control = webview_control
    else:
        webview_control = None
        webview_inner = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.WEB, color=ft.Colors.BLUE_400, size=22),
                    ft.Text(
                        "Οι σύνδεσμοι ιστοσελίδων ανοίγουν απευθείας στον προεπιλεγμένο φυλλομετρητή (Browser).",
                        size=13,
                        color=ft.Colors.GREY_300,
                    ),
                ],
                spacing=10,
            ),
            padding=12,
            bgcolor="#111827",
            border_radius=8,
        )

    webview_container = ft.Container(
        content=webview_inner,
        border_radius=10,
        border=ft.Border.all(1, "#334155"),
        visible=False,
    )

    def copy_result_click(e):
        val = result_raw_text.value or ""
        try:
            page.run_task(clipboard_service.set, val)
        except Exception:
            pass
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text("Αντιγράφηκε στο πρόχειρο!"),
                bgcolor=ft.Colors.GREEN_700,
                duration=1500,
            )
        )

    def open_browser_click(e):
        url = result_raw_text.value or ""
        details = current_result.get("details", {})
        lookup_url = details.get("lookup_url", "")
        if url.startswith("http"):
            try:
                webbrowser.open(url)
            except Exception as ex:
                print(f"[LaunchUrl] Error: {ex}")
        elif lookup_url:
            try:
                webbrowser.open(lookup_url)
            except Exception as ex:
                print(f"[LaunchUrl] Error: {ex}")
        else:
            try:
                webbrowser.open(f"https://www.google.com/search?q={url}")
            except Exception as ex:
                print(f"[LaunchUrl] Error: {ex}")

    result_summary_text = ft.Text(
        "Κωδικός Προϊόντος: 5201054001050 • Προέλευση: Ελλάδα 🇬🇷 (GS1 Association Greece)",
        size=13,
        color=ft.Colors.GREEN_300,
        weight=ft.FontWeight.W_500,
    )
    smart_details_column = ft.Column(
        [
            ft.Row([ft.Text("• Κατηγορία:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300), ft.Text("Εμπορικό Προϊόν Λιανικής", size=13, color=ft.Colors.WHITE)]),
            ft.Row([ft.Text("• Πρότυπο Barcode:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300), ft.Text("EAN-13", size=13, color=ft.Colors.WHITE)]),
            ft.Row([ft.Text("• Κωδικός GTIN / EAN:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300), ft.Text("5201054001050", size=13, color=ft.Colors.WHITE)]),
            ft.Row([ft.Text("• Χώρα / Προέλευση (GS1):", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300), ft.Text("Ελλάδα 🇬🇷 (GS1 Association Greece)", size=13, color=ft.Colors.WHITE)]),
        ],
        spacing=6,
    )

    def open_skroutz_click(e):
        raw_val = (result_raw_text.value or "").strip()
        skroutz_url = current_result.get("details", {}).get("skroutz_url") or f"https://www.skroutz.gr/search?keyphrase={raw_val}"
        try:
            webbrowser.open(skroutz_url)
        except Exception as ex:
            print(f"[Skroutz] Error: {ex}")

    def open_off_click(e):
        raw_val = (result_raw_text.value or "").strip()
        off_url = current_result.get("details", {}).get("openfoodfacts_url") or f"https://world.openfoodfacts.org/product/{raw_val}"
        try:
            webbrowser.open(off_url)
        except Exception as ex:
            print(f"[OpenFoodFacts] Error: {ex}")

    copy_btn = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.COPY), ft.Text("Αντιγραφή")], tight=True),
        on_click=copy_result_click,
        bgcolor="#1e293b",
        color=ft.Colors.WHITE,
    )
    open_browser_btn = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_BROWSER), ft.Text("Άνοιγμα / Αναζήτηση Google")], tight=True),
        on_click=open_browser_click,
        bgcolor=ft.Colors.BLUE_700,
        color=ft.Colors.WHITE,
    )
    skroutz_btn = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.SHOPPING_CART), ft.Text("Αναζήτηση στο Skroutz")], tight=True),
        on_click=open_skroutz_click,
        bgcolor=ft.Colors.ORANGE_800,
        color=ft.Colors.WHITE,
        visible=True,
    )
    off_btn = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.INVENTORY), ft.Text("Στοιχεία OpenFoodFacts")], tight=True),
        on_click=open_off_click,
        bgcolor=ft.Colors.TEAL_800,
        color=ft.Colors.WHITE,
        visible=True,
    )

    result_tab_view = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FACT_CHECK, color=ft.Colors.AMBER_400, size=28),
                        ft.Text("Έξυπνη Αναγνώριση & Ανάλυση Κώδικα", size=22, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Row(
                    [result_type_badge, result_title_text],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                result_summary_text,
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_300, size=18),
                                    ft.Text("Αναγνωρισμένα Στοιχεία (Smart Detection):", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300),
                                ],
                                spacing=6,
                            ),
                            smart_details_column,
                        ],
                        spacing=8,
                    ),
                    padding=14,
                    bgcolor="#0f172a",
                    border_radius=10,
                    border=ft.Border.all(1, "#334155"),
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Πρωτογενές Περιεχόμενο (Raw Content):", size=12, color=ft.Colors.GREY_400),
                            result_raw_text,
                        ],
                        spacing=4,
                    ),
                    padding=12,
                    bgcolor="#111827",
                    border_radius=8,
                    border=ft.Border.all(1, "#1f2937"),
                ),
                ft.Row([copy_btn, open_browser_btn, skroutz_btn, off_btn], spacing=10, wrap=True),
                ft.Divider(height=10, color="#1e293b"),
                ft.Text("Επεξεργαστής Κώδικα & Δομημένων Δεδομένων:", size=14, weight=ft.FontWeight.W_600),
                ft.Container(
                    content=code_editor_control,
                    border_radius=8,
                    border=ft.Border.all(1, "#334155"),
                ),
                webview_container,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
        ),
        padding=20,
    )

    def update_result_tab(parsed: Dict[str, Any]):
        qr_type = parsed.get("type", "TEXT")
        fmt_name = parsed.get("format", "")
        raw_val = parsed.get("raw", "")

        badge_label = f"{qr_type} ({fmt_name})" if (fmt_name and fmt_name != qr_type) else qr_type
        result_type_badge.content.value = badge_label
        result_title_text.value = parsed.get("title", "Περιεχόμενο Κώδικα")
        result_summary_text.value = parsed.get("summary", "")
        result_raw_text.value = raw_val

        # Populate smart recognition details card
        details = parsed.get("details", {})
        detail_rows = []
        is_light = page.theme_mode == ft.ThemeMode.LIGHT
        key_col = "#0e7490" if is_light else ft.Colors.CYAN_300
        val_col = "#0f172a" if is_light else ft.Colors.WHITE
        fallback_col = "#334155" if is_light else ft.Colors.GREY_300
        skip_keys = {"url", "lookup_url", "skroutz_url", "openfoodfacts_url", "latitude", "longitude", "json_obj", "formatted", "format"}
        for k, v in details.items():
            if k in skip_keys or v is None or v == "":
                continue
            detail_rows.append(
                ft.Row(
                    [
                        ft.Text(f"• {k}:", size=13, weight=ft.FontWeight.BOLD, color=key_col),
                        ft.Text(str(v), size=13, color=val_col, selectable=True),
                    ],
                    spacing=8,
                    wrap=True,
                )
            )
        if not detail_rows:
            detail_rows.append(ft.Text(f"• Τύπος: {qr_type} ({fmt_name})", size=13, color=fallback_col))
        smart_details_column.controls = detail_rows

        # Update CodeEditor
        code_editor_control.value = details.get("formatted", raw_val)
        if qr_type == "JSON":
            code_editor_control.language = fce.CodeLanguage.JSON
        else:
            code_editor_control.language = fce.CodeLanguage.YAML

        # Action buttons visibility
        skroutz_btn.visible = qr_type in ("PRODUCT", "BOOK", "BARCODE")
        off_btn.visible = qr_type == "PRODUCT"

        # WebView / Browser button display
        if qr_type == "URL" and raw_val.startswith("http"):
            if webview_control is not None:
                webview_control.url = raw_val
            webview_container.visible = True
            open_browser_btn.visible = True
        else:
            webview_container.visible = False
            open_browser_btn.visible = True

        safe_update(result_tab_view)

    # ---------------------------------------------------------
    # 7. TAB 3: GENERATOR (QR & Barcodes, RGB Sliders, Color Palette & Customizer)
    # ---------------------------------------------------------
    gen_format_dropdown = ft.Dropdown(
        label="Τύπος Κώδικα (QR ή Barcode)",
        value="QR",
        width=290,
        options=[
            ft.dropdown.Option("QR", "QR Code (2D)"),
            ft.dropdown.Option("CODE128", "Barcode Code-128 (Αλφαριθμητικό)"),
            ft.dropdown.Option("EAN13", "Barcode EAN-13 (12-13 ψηφία προϊόντος)"),
            ft.dropdown.Option("EAN8", "Barcode EAN-8 (7-8 ψηφία)"),
            ft.dropdown.Option("UPCA", "Barcode UPC-A (11-12 ψηφία)"),
            ft.dropdown.Option("CODE39", "Barcode Code-39"),
        ],
    )
    gen_ecc_dropdown = ft.Dropdown(
        label="Διόρθωση Σφαλμάτων (QR ECC)",
        value="M",
        width=230,
        options=[
            ft.dropdown.Option("L", "Χαμηλή (L - 7%)"),
            ft.dropdown.Option("M", "Μεσαία (M - 15%)"),
            ft.dropdown.Option("Q", "Υψηλή (Q - 25%)"),
            ft.dropdown.Option("H", "Μέγιστη (H - 30%)"),
        ],
    )
    gen_data_input = ft.TextField(
        label="Περιεχόμενο QR / Barcode (Κείμενο, Αριθμός, URL ή Δεδομένα)",
        value="https://www.program.gr",
        multiline=True,
        min_lines=2,
        max_lines=4,
    )
    gen_qr_preview = ft.Image(
        src=INITIAL_FRAME_BYTES,
        width=260,
        height=260,
        fit=ft.BoxFit.CONTAIN,
        border_radius=10,
        gapless_playback=True,
    )
    current_pil_qr = None

    # Color & Size State
    qr_fg_color = "#000000"
    qr_bg_color = "#FFFFFF"
    updating_color_controls = False

    fg_color_swatch = ft.Container(
        width=36,
        height=36,
        bgcolor=qr_fg_color,
        border_radius=8,
        border=ft.Border.all(2, ft.Colors.WHITE),
    )
    fg_hex_input = ft.TextField(
        label="Κωδικός Χρώματος (HEX)",
        value="#000000",
        width=165,
        height=45,
        text_size=13,
    )
    bg_color_dropdown = ft.Dropdown(
        label="Χρώμα Φόντου",
        value="#FFFFFF",
        width=210,
        options=[
            ft.dropdown.Option("#FFFFFF", "Λευκό (#FFFFFF)"),
            ft.dropdown.Option("#F8FAFC", "Ανοιχτό Γκρι (#F8FAFC)"),
            ft.dropdown.Option("#FEF9C3", "Παστέλ Κίτρινο (#FEF9C3)"),
            ft.dropdown.Option("#E0F2FE", "Παστέλ Γαλάζιο (#E0F2FE)"),
            ft.dropdown.Option("#DCFCE7", "Παστέλ Πράσινο (#DCFCE7)"),
            ft.dropdown.Option("#FCE7F3", "Παστέλ Ροζ (#FCE7F3)"),
        ],
    )

    # RGB Sliders (0-255) for exact interactive control
    r_val_label = ft.Text("R: 0", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300, width=52)
    g_val_label = ft.Text("G: 0", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_300, width=52)
    b_val_label = ft.Text("B: 0", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300, width=52)

    r_slider = ft.Slider(min=0, max=255, divisions=255, value=0, active_color=ft.Colors.RED_400, expand=True)
    g_slider = ft.Slider(min=0, max=255, divisions=255, value=0, active_color=ft.Colors.GREEN_400, expand=True)
    b_slider = ft.Slider(min=0, max=255, divisions=255, value=0, active_color=ft.Colors.BLUE_400, expand=True)

    # Size & Border Sliders
    box_size_label = ft.Text("Μέγεθος (Box Size): 10", size=12, color=ft.Colors.GREY_300, width=155)
    border_size_label = ft.Text("Περιθώριο (Border): 4", size=12, color=ft.Colors.GREY_300, width=155)
    box_size_slider = ft.Slider(min=4, max=20, divisions=16, value=10, active_color=ft.Colors.PURPLE_400, expand=True)
    border_size_slider = ft.Slider(min=1, max=10, divisions=9, value=4, active_color=ft.Colors.CYAN_400, expand=True)

    color_picker_fg = fcp.ColorPicker(
        color="#000000",
        color_picker_width=280,
        enable_alpha=False,
        hex_input_bar=True,
        picker_area_height_percent=0.65,
        picker_area_border_radius=8,
    )

    preview_bg_container = ft.Container(
        content=gen_qr_preview,
        padding=15,
        bgcolor=qr_bg_color,
        border_radius=12,
        border=ft.Border.all(1, "#334155"),
    )

    def hex_to_rgb_tuple(hex_str: str):
        c = str(hex_str).strip().lstrip("#")
        if len(c) == 8:
            c = c[2:]
        elif len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            return (0, 0, 0)
        try:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        except ValueError:
            return (0, 0, 0)

    def update_generated_qr(e=None):
        nonlocal current_pil_qr
        text = gen_data_input.value or ""
        selected_type = gen_format_dropdown.value or "QR"
        selected_ecc = gen_ecc_dropdown.value or "M"
        b_size = int(box_size_slider.value or 10)
        brd_size = int(border_size_slider.value or 4)
        png_bytes, pil_img = generate_qr_image(
            data=text,
            fill_color=qr_fg_color,
            back_color=qr_bg_color,
            box_size=b_size,
            border=brd_size,
            error_correction=selected_ecc,
            code_type=selected_type,
        )
        if png_bytes:
            gen_qr_preview.src = png_bytes
            current_pil_qr = pil_img
            preview_bg_container.bgcolor = qr_bg_color
            safe_update(gen_qr_preview)
            safe_update(preview_bg_container)

    def sync_color_ui(new_hex: str, source: str = ""):
        nonlocal qr_fg_color, updating_color_controls
        if updating_color_controls:
            return
        updating_color_controls = True
        try:
            r, g, b = hex_to_rgb_tuple(new_hex)
            clean_hex = f"#{r:02X}{g:02X}{b:02X}"
            qr_fg_color = clean_hex

            fg_color_swatch.bgcolor = clean_hex
            safe_update(fg_color_swatch)

            if source != "hex":
                fg_hex_input.value = clean_hex
                safe_update(fg_hex_input)

            if source != "rgb":
                r_slider.value = r
                g_slider.value = g
                b_slider.value = b
                r_val_label.value = f"R: {r}"
                g_val_label.value = f"G: {g}"
                b_val_label.value = f"B: {b}"
                safe_update(r_slider)
                safe_update(g_slider)
                safe_update(b_slider)
                safe_update(r_val_label)
                safe_update(g_val_label)
                safe_update(b_val_label)

            if source != "picker":
                color_picker_fg.color = clean_hex
                safe_update(color_picker_fg)

            update_generated_qr()
        finally:
            updating_color_controls = False

    def on_rgb_slider_change(e):
        r = int(r_slider.value or 0)
        g = int(g_slider.value or 0)
        b = int(b_slider.value or 0)
        r_val_label.value = f"R: {r}"
        g_val_label.value = f"G: {g}"
        b_val_label.value = f"B: {b}"
        safe_update(r_val_label)
        safe_update(g_val_label)
        safe_update(b_val_label)
        sync_color_ui(f"#{r:02X}{g:02X}{b:02X}", source="rgb")

    def on_picker_color_change(e):
        raw_c = getattr(e, "data", None) or color_picker_fg.color
        if raw_c:
            sync_color_ui(str(raw_c), source="picker")

    def on_hex_input_change(e):
        val = (fg_hex_input.value or "").strip().lstrip("#")
        if len(val) == 6:
            try:
                int(val, 16)
                sync_color_ui(f"#{val.upper()}", source="hex")
            except ValueError:
                pass

    def on_bg_color_change(e):
        nonlocal qr_bg_color
        qr_bg_color = bg_color_dropdown.value or "#FFFFFF"
        update_generated_qr()

    def on_size_slider_change(e):
        box_size_label.value = f"Μέγεθος (Box Size): {int(box_size_slider.value or 10)}"
        border_size_label.value = f"Περιθώριο (Border): {int(border_size_slider.value or 4)}"
        safe_update(box_size_label)
        safe_update(border_size_label)
        update_generated_qr()

    def on_format_selected(e):
        val = gen_format_dropdown.value or "QR"
        if val == "EAN13" and not (gen_data_input.value or "").strip().isdigit():
            gen_data_input.value = "520123456789"
            safe_update(gen_data_input)
        elif val == "EAN8" and not (gen_data_input.value or "").strip().isdigit():
            gen_data_input.value = "5201234"
            safe_update(gen_data_input)
        elif val == "UPCA" and not (gen_data_input.value or "").strip().isdigit():
            gen_data_input.value = "01234567890"
            safe_update(gen_data_input)
        gen_ecc_dropdown.disabled = val != "QR"
        safe_update(gen_ecc_dropdown)
        update_generated_qr()

    r_slider.on_change = on_rgb_slider_change
    g_slider.on_change = on_rgb_slider_change
    b_slider.on_change = on_rgb_slider_change
    color_picker_fg.on_color_change = on_picker_color_change
    fg_hex_input.on_change = on_hex_input_change
    bg_color_dropdown.on_select = on_bg_color_change
    box_size_slider.on_change = on_size_slider_change
    border_size_slider.on_change = on_size_slider_change
    gen_data_input.on_change = update_generated_qr
    gen_format_dropdown.on_select = on_format_selected
    gen_ecc_dropdown.on_select = update_generated_qr

    # Preset color swatches for 1-click selection
    PRESET_COLORS = [
        ("#000000", "Μαύρο"),
        ("#1E3A8A", "Σκούρο Μπλε"),
        ("#0F766E", "Πετρόλ"),
        ("#15803D", "Πράσινο"),
        ("#6D28D9", "Μωβ"),
        ("#B91C1C", "Κόκκινο"),
        ("#C2410C", "Πορτοκαλί"),
        ("#334155", "Ανθρακί"),
    ]
    preset_swatches_row = ft.Row(
        controls=[
            ft.Container(
                width=28,
                height=28,
                bgcolor=hex_c,
                border_radius=6,
                border=ft.Border.all(1.5, "#64748b"),
                tooltip=f"{label_c} ({hex_c})",
                ink=True,
                on_click=lambda _, hc=hex_c: sync_color_ui(hc, source="preset"),
            )
            for hex_c, label_c in PRESET_COLORS
        ],
        spacing=8,
        wrap=True,
    )

    # Interactive Location Picker Map for Generator Tab
    gen_map_coords_text = ft.Text(
        "Επιλεγμένο Σημείο: 37.975500, 23.734800 (geo:37.975500,23.734800)",
        size=13,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.CYAN_300,
    )

    map_marker = fm.Marker(
        coordinates=fm.MapLatitudeLongitude(37.9755, 23.7348),
        content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED, size=36),
    )

    def apply_map_location_to_qr(lat: float, lon: float, recenter: bool = False):
        coord = fm.MapLatitudeLongitude(lat, lon)
        map_marker.coordinates = coord
        gen_map_coords_text.value = f"Επιλεγμένο Σημείο: {lat:.6f}, {lon:.6f}  →  geo:{lat:.6f},{lon:.6f}"
        safe_update(gen_map_coords_text)
        safe_update(map_control)
        if recenter:
            try:
                page.run_task(map_control.move_to, destination=coord, zoom=14)
            except Exception:
                pass

        gen_format_dropdown.value = "QR"
        gen_ecc_dropdown.disabled = False
        gen_data_input.value = f"geo:{lat:.6f},{lon:.6f}"
        safe_update(gen_format_dropdown)
        safe_update(gen_ecc_dropdown)
        safe_update(gen_data_input)
        update_generated_qr()

    def on_generator_map_tap(e: fm.MapTapEvent):
        coords = getattr(e, "coordinates", None)
        if coords is not None:
            lat = float(coords.latitude)
            lon = float(coords.longitude)
            apply_map_location_to_qr(lat, lon, recenter=False)

    map_control = fm.Map(
        layers=[
            fm.TileLayer(
                url_template="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                user_agent_package_name="SpyQR/0.2 (+https://github.com/spyalekos/spyQR)",
                evict_error_tile_strategy=fm.TileLayerEvictErrorTileStrategy.DISPOSE,
            ),
            fm.MarkerLayer(markers=[map_marker]),
        ],
        initial_center=fm.MapLatitudeLongitude(37.9755, 23.7348),
        initial_zoom=13.0,
        height=300,
        on_tap=on_generator_map_tap,
        on_secondary_tap=on_generator_map_tap,
        on_long_press=on_generator_map_tap,
    )

    PRESET_LOCATIONS = [
        ("Αθήνα (Σύνταγμα)", 37.9755, 23.7348),
        ("Θεσσαλονίκη (Λευκός Πύργος)", 40.6264, 22.9484),
        ("Πάτρα", 38.2466, 21.7346),
        ("Ηράκλειο Κρήτης", 35.3387, 25.1442),
        ("Λάρισα", 39.6390, 22.4191),
        ("Ιωάννινα", 39.6650, 20.8537),
    ]

    preset_location_buttons = ft.Row(
        controls=[
            ft.Text("Γρήγορη Μετάβαση:", size=12, color=ft.Colors.GREY_400),
            *[
                ft.Button(
                    content=ft.Row([ft.Icon(ft.Icons.PLACE, size=15, color=ft.Colors.RED_300), ft.Text(loc_name, size=12)], tight=True),
                    on_click=lambda _, la=lat_v, lo=lon_v: apply_map_location_to_qr(la, lo, recenter=True),
                    bgcolor="#1e293b",
                    color=ft.Colors.WHITE,
                )
                for loc_name, lat_v, lon_v in PRESET_LOCATIONS
            ],
        ],
        spacing=8,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    map_container = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.MAP, color=ft.Colors.GREEN_400, size=24),
                        ft.Text(
                            "Διαδραστικός Χάρτης Επιλογής Τοποθεσίας (Click-on-Map Geo QR):",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Κάντε κλικ σε οποιοδήποτε σημείο του χάρτη (ή επιλέξτε πόλη) για να δημιουργήσετε αυτόματα QR Code τοποθεσίας GPS (geo:lat,lon)!",
                    size=12,
                    color=ft.Colors.GREY_400,
                ),
                preset_location_buttons,
                ft.Row(
                    [
                        ft.Icon(ft.Icons.MY_LOCATION, color=ft.Colors.CYAN_300, size=18),
                        gen_map_coords_text,
                        ft.Button(
                            content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW, size=15), ft.Text("Δοκιμή στο Google Maps", size=12)], tight=True),
                            on_click=lambda _: webbrowser.open(
                                f"https://www.google.com/maps?q={map_marker.coordinates.latitude},{map_marker.coordinates.longitude}"
                            ),
                            bgcolor=ft.Colors.TEAL_800,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    spacing=10,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=map_control,
                    border_radius=10,
                    border=ft.Border.all(1, "#334155"),
                ),
            ],
            spacing=10,
        ),
        width=1010,
        padding=16,
        bgcolor="#111827",
        border_radius=12,
        border=ft.Border.all(1, "#1f2937"),
    )

    def insert_template_click(template_type: str):
        gen_format_dropdown.value = "QR"
        gen_ecc_dropdown.disabled = False
        if template_type == "WIFI":
            gen_data_input.value = "WIFI:S:MyHomeWiFi;T:WPA;P:MySecretPass123;;"
        elif template_type == "VCARD":
            gen_data_input.value = "BEGIN:VCARD\nVERSION:3.0\nFN:Αλέξανδρος Παπαδόπουλος\nTEL:+306900000000\nEMAIL:info@example.gr\nEND:VCARD"
        elif template_type == "GEO":
            apply_map_location_to_qr(
                float(map_marker.coordinates.latitude),
                float(map_marker.coordinates.longitude),
                recenter=False,
            )
            return
        elif template_type == "EAN13":
            gen_format_dropdown.value = "EAN13"
            gen_ecc_dropdown.disabled = True
            gen_data_input.value = "5201054001050"
        safe_update(gen_format_dropdown)
        safe_update(gen_ecc_dropdown)
        safe_update(gen_data_input)
        update_generated_qr()

    async def save_qr_dialog_click(e):
        if not current_pil_qr:
            return
        try:
            save_path = await file_picker.save_file(
                dialog_title="Αποθήκευση εικόνας QR / Barcode",
                file_name="spyqr_code.png",
                file_type=ft.FilePickerFileType.IMAGE,
                allowed_extensions=["png"],
            )
        except Exception:
            save_path = os.path.join(os.path.expanduser("~"), "spyqr_code.png")

        if save_path:
            if not save_path.lower().endswith(".png"):
                save_path += ".png"
            saved = save_qr_to_file(current_pil_qr, save_path)
            if saved:
                page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text(f"Ο κώδικας αποθηκεύτηκε επιτυχώς στο: {save_path}"),
                        bgcolor=ft.Colors.GREEN_700,
                    )
                )

    update_generated_qr()

    generator_tab_view = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CREATE, color=ft.Colors.PURPLE_400, size=28),
                        ft.Text("Δημιουργός QR Codes & Barcodes", size=22, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Text(
                    "Δημιουργήστε εξατομικευμένα QR codes ή γραμμωτούς κώδικες (EAN-13, Code-128, UPC) με πλήρη έλεγχο χρωμάτων RGB, μεγέθους, περιθωρίου και επιλογή τοποθεσίας από χάρτη.",
                    size=13,
                    color=ft.Colors.GREY_400,
                ),
                ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row([gen_format_dropdown, gen_ecc_dropdown], spacing=12, wrap=True),
                                    gen_data_input,
                                    ft.Row(
                                        [
                                            ft.Text("Γρήγορα Πρότυπα:", size=12, color=ft.Colors.GREY_400),
                                            ft.Button(
                                                content=ft.Row([ft.Icon(ft.Icons.WIFI, size=16), ft.Text("Wi-Fi", size=12)], tight=True),
                                                on_click=lambda _: insert_template_click("WIFI"),
                                                bgcolor="#1e293b",
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.Button(
                                                content=ft.Row([ft.Icon(ft.Icons.CONTACT_MAIL, size=16), ft.Text("Επαφή vCard", size=12)], tight=True),
                                                on_click=lambda _: insert_template_click("VCARD"),
                                                bgcolor="#1e293b",
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.Button(
                                                content=ft.Row([ft.Icon(ft.Icons.LOCATION_ON, size=16), ft.Text("Συντεταγμένες GPS", size=12)], tight=True),
                                                on_click=lambda _: insert_template_click("GEO"),
                                                bgcolor="#1e293b",
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.Button(
                                                content=ft.Row([ft.Icon(ft.Icons.SHOPPING_BAG, size=16), ft.Text("Προϊόν EAN-13", size=12)], tight=True),
                                                on_click=lambda _: insert_template_click("EAN13"),
                                                bgcolor="#1e293b",
                                                color=ft.Colors.WHITE,
                                            ),
                                        ],
                                        spacing=8,
                                        wrap=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Divider(height=10, color="#1e293b"),
                                    ft.Text("Ρυθμιστικά Μεγέθους & Περιθωρίου:", size=14, weight=ft.FontWeight.W_600),
                                    ft.Row([box_size_label, box_size_slider], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                    ft.Row([border_size_label, border_size_slider], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                    ft.Divider(height=10, color="#1e293b"),
                                    ft.Text("Επιλογή Χρώματος & Ρυθμιστικά RGB:", size=14, weight=ft.FontWeight.W_600),
                                    ft.Row(
                                        [
                                            fg_color_swatch,
                                            fg_hex_input,
                                            bg_color_dropdown,
                                        ],
                                        spacing=12,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        wrap=True,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Text("Έτοιμα Χρώματα:", size=12, color=ft.Colors.GREY_400),
                                            preset_swatches_row,
                                        ],
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Row([r_val_label, r_slider], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                                ft.Row([g_val_label, g_slider], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                                ft.Row([b_val_label, b_slider], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                            ],
                                            spacing=2,
                                        ),
                                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                        bgcolor="#0f172a",
                                        border_radius=8,
                                        border=ft.Border.all(1, "#232f47"),
                                    ),
                                    ft.ExpansionTile(
                                        title=ft.Text("Σύνθετη Παλέτα Χρωμάτων (Φάσμα HSV / HEX)", size=13, color=ft.Colors.CYAN_300),
                                        expanded=False,
                                        controls=[
                                            ft.Container(
                                                content=color_picker_fg,
                                                padding=10,
                                                alignment=ft.Alignment(0, 0),
                                            )
                                        ],
                                    ),
                                ],
                                spacing=10,
                            ),
                            width=640,
                            padding=16,
                            bgcolor="#111827",
                            border_radius=12,
                            border=ft.Border.all(1, "#1f2937"),
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Ζωντανή Προεπισκόπηση", size=16, weight=ft.FontWeight.W_600),
                                    preview_bg_container,
                                    ft.Button(
                                        content=ft.Row([ft.Icon(ft.Icons.DOWNLOAD), ft.Text("Αποθήκευση Εικόνας (PNG)")], tight=True),
                                        on_click=save_qr_dialog_click,
                                        bgcolor=ft.Colors.PURPLE_700,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text("Ο κώδικας ενημερώνεται αυτόματα σε κάθε αλλαγή!", size=12, color=ft.Colors.GREY_400),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=15,
                            ),
                            width=350,
                            padding=20,
                            bgcolor="#111827",
                            border_radius=12,
                            border=ft.Border.all(1, "#1f2937"),
                            alignment=ft.Alignment(0, 0),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=20,
                ),
                ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
                map_container,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        ),
        padding=20,
    )

    # ---------------------------------------------------------
    # 8. TAB 4: HISTORY
    # ---------------------------------------------------------
    history_search_input = ft.TextField(
        hint_text="Αναζήτηση στο ιστορικό...",
        prefix_icon=ft.Icons.SEARCH,
        width=300,
        height=40,
    )

    history_datatable = fdt.DataTable2(
        columns=[
            fdt.DataColumn2(label=ft.Text("Ημερομηνία / Ώρα"), size=fdt.DataColumnSize.M),
            fdt.DataColumn2(label=ft.Text("Τύπος"), size=fdt.DataColumnSize.S),
            fdt.DataColumn2(label=ft.Text("Περιεχόμενο"), size=fdt.DataColumnSize.L),
            fdt.DataColumn2(label=ft.Text("Ενέργειες"), size=fdt.DataColumnSize.S),
        ],
        rows=[],
        border=ft.Border.all(1, "#232f47"),
        border_radius=8,
    )

    def refresh_history_tab():
        query = (history_search_input.value or "").lower()
        rows = []
        for item in history_mgr.items:
            raw = item.get("raw_data", "")
            q_type = item.get("qr_type", "TEXT")
            t_str = item.get("timestamp_str", "")
            if query and (query not in raw.lower()) and (query not in q_type.lower()):
                continue

            item_id = item.get("id", "")

            def make_view_handler(target_item):
                def handler(e):
                    parsed = parse_qr_content(target_item.get("raw_data", ""))
                    update_result_tab(parsed)
                    tabs.selected_index = 1
                    page.update()
                return handler

            def make_delete_handler(target_id):
                def handler(e):
                    history_mgr.delete_entry(target_id)
                    refresh_history_tab()
                    refresh_analytics_tab()
                return handler

            rows.append(
                fdt.DataRow2(
                    cells=[
                        ft.DataCell(ft.Text(t_str, size=12)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(q_type, size=11, weight=ft.FontWeight.BOLD),
                                bgcolor=ft.Colors.BLUE_900 if q_type == "URL" else ft.Colors.PURPLE_900,
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                border_radius=4,
                            )
                        ),
                        ft.DataCell(ft.Text(raw[:45] + ("..." if len(raw) > 45 else ""), size=12, selectable=True)),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.VISIBILITY,
                                        icon_size=18,
                                        tooltip="Προβολή",
                                        on_click=make_view_handler(item),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_size=18,
                                        icon_color=ft.Colors.RED_400,
                                        tooltip="Διαγραφή",
                                        on_click=make_delete_handler(item_id),
                                    ),
                                ],
                                tight=True,
                                spacing=0,
                            )
                        ),
                    ]
                )
            )
        history_datatable.rows = rows
        safe_update(history_datatable)

    history_search_input.on_change = lambda _: refresh_history_tab()

    def clear_history_click(e):
        history_mgr.clear_all()
        refresh_history_tab()
        refresh_analytics_tab()
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text("Το ιστορικό καθαρίστηκε!"),
                bgcolor=ft.Colors.BLUE_GREY_700,
                duration=1500,
            )
        )

    history_tab_view = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.HISTORY, color=ft.Colors.TEAL_400, size=28),
                        ft.Text("Ιστορικό Σαρώσεων", size=22, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Row(
                    [
                        history_search_input,
                        ft.Button(
                            content=ft.Row([ft.Icon(ft.Icons.DELETE_FOREVER), ft.Text("Καθαρισμός Όλων")], tight=True),
                            on_click=clear_history_click,
                            bgcolor="#1e293b",
                            color=ft.Colors.RED_300,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                ft.Container(
                    content=history_datatable,
                    bgcolor="#111827",
                    border_radius=8,
                    padding=10,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        ),
        padding=20,
    )

    # ---------------------------------------------------------
    # 9. TAB 5: ANALYTICS (PieChart on top & BarChart Histogram below)
    # ---------------------------------------------------------
    TYPE_NAMES_GR = {
        "PRODUCT": "Προϊόντα",
        "BOOK": "Βιβλία",
        "MAGAZINE": "Περιοδικά",
        "BARCODE": "Κωδικοί Barcode",
        "URL": "Ιστοσελίδες",
        "WIFI": "Δίκτυα Wi-Fi",
        "VCARD": "Επαφές",
        "EVENT": "Ημερολόγιο",
        "GEO": "Τοποθεσίες GPS",
        "PAYMENT": "Πληρωμές IBAN",
        "CRYPTO": "Κρυπτονομίσματα",
        "EMAIL": "Email",
        "SMS": "SMS",
        "TEL": "Τηλέφωνα",
        "JSON": "Δεδομένα JSON",
        "TEXT": "Απλό Κείμενο",
    }

    pie_chart_control = fc.PieChart(
        sections=[
            fc.PieChartSection(
                value=1,
                title="Προϊόντα (1)",
                color=ft.Colors.BLUE_400,
                radius=110,
                title_style=ft.TextStyle(size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ),
        ],
        sections_space=3,
        center_space_radius=55,
        height=320,
        expand=True,
    )

    pie_legend_column = ft.Column(spacing=8)

    bar_chart_control = fc.BarChart(
        groups=[
            fc.BarChartGroup(
                x=0,
                rods=[
                    fc.BarChartRod(
                        from_y=0,
                        to_y=1,
                        color=ft.Colors.BLUE_400,
                        width=38,
                        border_radius=6,
                    )
                ],
            ),
        ],
        left_axis=fc.ChartAxis(
            title=ft.Text("Πλήθος Σαρώσεων", size=12, weight=ft.FontWeight.BOLD),
            title_size=26,
            label_size=32,
            show_labels=True,
        ),
        bottom_axis=fc.ChartAxis(
            label_size=36,
            show_labels=True,
            labels=[
                fc.ChartAxisLabel(value=0, label=ft.Text("PRODUCT", size=12, weight=ft.FontWeight.BOLD)),
            ],
        ),
        horizontal_grid_lines=fc.ChartGridLines(interval=1, color="#334155", width=1),
        min_y=0,
        max_y=5,
        interactive=True,
        height=340,
        expand=True,
    )

    stat_total_scans = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    stat_unique_types = ft.Text("0", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    stat_top_category = ft.Text("-", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)

    def refresh_analytics_tab():
        stats = history_mgr.get_stats()
        total = sum(stats.values())
        stat_total_scans.value = str(total)
        stat_unique_types.value = str(len(stats))

        if stats:
            top_k = max(stats.items(), key=lambda x: x[1])
            gr_top = TYPE_NAMES_GR.get(top_k[0], top_k[0])
            stat_top_category.value = f"{gr_top} ({top_k[1]})"
        else:
            stat_top_category.value = "—"

        colors = [
            ft.Colors.BLUE_500,
            ft.Colors.GREEN_500,
            ft.Colors.ORANGE_500,
            ft.Colors.PURPLE_500,
            ft.Colors.TEAL_500,
            ft.Colors.RED_500,
            ft.Colors.AMBER_600,
            ft.Colors.CYAN_500,
            ft.Colors.PINK_500,
        ]

        sections = []
        bar_groups = []
        bottom_labels = []
        legend_rows = []
        idx = 0
        max_count = max(stats.values()) if stats else 1

        for q_type, count in stats.items():
            col = colors[idx % len(colors)]
            pct = (count / total * 100.0) if total > 0 else 0.0
            gr_label = TYPE_NAMES_GR.get(q_type, q_type)

            sections.append(
                fc.PieChartSection(
                    value=count,
                    title=f"{gr_label}\n{count} ({pct:.0f}%)",
                    color=col,
                    radius=115,
                    title_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                )
            )
            bar_groups.append(
                fc.BarChartGroup(
                    x=idx,
                    rods=[
                        fc.BarChartRod(
                            from_y=0,
                            to_y=count,
                            color=col,
                            width=42,
                            border_radius=6,
                            tooltip=f"{gr_label} ({q_type}): {count} σαρώσεις ({pct:.1f}%)",
                        )
                    ],
                )
            )
            bottom_labels.append(
                fc.ChartAxisLabel(
                    value=idx,
                    label=ft.Container(
                        content=ft.Text(f"{gr_label}", size=12, weight=ft.FontWeight.BOLD),
                        padding=ft.Padding.only(top=6),
                    ),
                )
            )
            is_light = page.theme_mode == ft.ThemeMode.LIGHT
            legend_rows.append(
                ft.Row(
                    [
                        ft.Container(width=16, height=16, bgcolor=col, border_radius=4),
                        ft.Text(f"{gr_label} ({q_type}):", size=13, weight=ft.FontWeight.BOLD, color="#0f172a" if is_light else ft.Colors.WHITE),
                        ft.Text(f"{count} σαρώσεις ({pct:.1f}%)", size=13, color="#475569" if is_light else ft.Colors.GREY_400),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            idx += 1

        if not sections:
            sections = [
                fc.PieChartSection(
                    value=1,
                    title="Χωρίς Δεδομένα",
                    color=ft.Colors.GREY_700,
                    radius=110,
                    title_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                )
            ]
            bar_groups = [
                fc.BarChartGroup(
                    x=0,
                    rods=[fc.BarChartRod(from_y=0, to_y=0, color=ft.Colors.GREY_700, width=40, border_radius=6)],
                )
            ]
            bottom_labels = [
                fc.ChartAxisLabel(value=0, label=ft.Text("Χωρίς Δεδομένα", size=12)),
            ]
            legend_rows = [
                ft.Text("Δεν υπάρχουν καταγεγραμμένες σαρώσεις ακόμα.", size=13, color=ft.Colors.GREY_400),
            ]

        pie_chart_control.sections = sections
        pie_legend_column.controls = legend_rows
        bar_chart_control.groups = bar_groups
        bar_chart_control.bottom_axis.labels = bottom_labels
        bar_chart_control.max_y = float(max(max_count + 1, 4))

        safe_update(stat_total_scans)
        safe_update(stat_unique_types)
        safe_update(stat_top_category)
        safe_update(pie_chart_control)
        safe_update(pie_legend_column)
        safe_update(bar_chart_control)

    analytics_tab_view = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.BAR_CHART, color=ft.Colors.INDIGO_400, size=28),
                        ft.Text("Στατιστικά & Ανάλυση Σαρώσεων", size=22, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Σύνολο Σαρώσεων", size=13, color=ft.Colors.GREY_400),
                                    stat_total_scans,
                                ],
                                spacing=4,
                            ),
                            padding=16,
                            bgcolor="#111827",
                            border_radius=10,
                            border=ft.Border.all(1, "#1f2937"),
                            width=220,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Διαφορετικές Κατηγορίες", size=13, color=ft.Colors.GREY_400),
                                    stat_unique_types,
                                ],
                                spacing=4,
                            ),
                            padding=16,
                            bgcolor="#111827",
                            border_radius=10,
                            border=ft.Border.all(1, "#1f2937"),
                            width=220,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("Δημοφιλέστερη Κατηγορία", size=13, color=ft.Colors.GREY_400),
                                    stat_top_category,
                                ],
                                spacing=4,
                            ),
                            padding=16,
                            bgcolor="#111827",
                            border_radius=10,
                            border=ft.Border.all(1, "#1f2937"),
                            width=300,
                        ),
                    ],
                    spacing=15,
                    wrap=True,
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                # TOP: Large Pie Chart with Legend
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.PIE_CHART, color=ft.Colors.CYAN_400, size=22),
                                    ft.Text("Κατανομή Σαρώσεων ανά Κατηγορία (Διάγραμμα Πίτας)", size=17, weight=ft.FontWeight.BOLD),
                                ],
                                spacing=8,
                            ),
                            ft.Divider(height=8, color="#1f2937"),
                            ft.Row(
                                [
                                    ft.Container(
                                        content=pie_chart_control,
                                        width=460,
                                        height=330,
                                        alignment=ft.Alignment(0, 0),
                                    ),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Text("Υπόμνημα Κατηγοριών:", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
                                                pie_legend_column,
                                            ],
                                            spacing=10,
                                        ),
                                        padding=16,
                                        bgcolor="#0f172a",
                                        border_radius=10,
                                        border=ft.Border.all(1, "#232f47"),
                                        expand=True,
                                    ),
                                ],
                                spacing=25,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=12,
                    ),
                    padding=20,
                    bgcolor="#111827",
                    border_radius=12,
                    border=ft.Border.all(1, "#1f2937"),
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                # BOTTOM: Large Histogram / Bar Chart below Pie Chart
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.EQUALIZER, color=ft.Colors.AMBER_400, size=22),
                                    ft.Text("Ιστόγραμμα Συχνότητας ανά Κατηγορία Κώδικα", size=17, weight=ft.FontWeight.BOLD),
                                ],
                                spacing=8,
                            ),
                            ft.Divider(height=8, color="#1f2937"),
                            ft.Container(
                                content=bar_chart_control,
                                height=350,
                                padding=ft.Padding.only(top=15, right=20, left=5, bottom=5),
                            ),
                        ],
                        spacing=12,
                    ),
                    padding=20,
                    bgcolor="#111827",
                    border_radius=12,
                    border=ft.Border.all(1, "#1f2937"),
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
        ),
        padding=20,
    )

    # ---------------------------------------------------------
    # 10. TAB 6: HELP & USER GUIDE (Βοήθεια)
    # ---------------------------------------------------------
    def build_help_card(title: str, desc: str, icon: str, accent_color: str = ft.Colors.CYAN_400):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, color=accent_color, size=26),
                    ft.Column(
                        [
                            ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text(desc, size=12, color=ft.Colors.GREY_300),
                        ],
                        spacing=3,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=12,
            ),
            padding=14,
            bgcolor="#111827",
            border_radius=10,
            border=ft.Border.all(1, "#1f2937"),
        )

    help_tab_view = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.HELP_OUTLINE, color=ft.Colors.CYAN_400, size=28),
                        ft.Text("Οδηγός Χρήσης & Βοήθεια (SpyQR)", size=22, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Text(
                    "Πώς λειτουργεί η έξυπνη σάρωση, η αυτόματη αναγνώριση περιεχομένου και η δημιουργία QR & Barcodes:",
                    size=13,
                    color=ft.Colors.GREY_400,
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                ft.Text("1. Τρόποι Σάρωσης (Καρτέλα «Σαρωτής»)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_300),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            build_help_card(
                                "Ζωντανή Κάμερα (Webcam)",
                                "Πατήστε «Έναρξη Κάμερας» και κρατήστε το QR Code ή το Barcode μέσα στο πλαίσιο σκόπευσης. Για γραμμωτούς κώδικες (1D Barcodes), ευθυγραμμίστε τις γραμμές με την οριζόντια γραμμή οδηγού.",
                                ft.Icons.VIDEOCAM,
                                ft.Colors.BLUE_400,
                            ),
                            col=4,
                        ),
                        ft.Container(
                            build_help_card(
                                "Φόρτωση από Αρχείο Εικόνας",
                                "Πατήστε «Φόρτωση Εικόνας...» για να επιλέξετε φωτογραφία ή screenshot (PNG, JPG, BMP, WebP) από τον υπολογιστή σας.",
                                ft.Icons.UPLOAD_FILE,
                                ft.Colors.PURPLE_400,
                            ),
                            col=4,
                        ),
                        ft.Container(
                            build_help_card(
                                "Σάρωση από Πρόχειρο (Clipboard)",
                                "Κάντε αντιγραφή (Copy / Win+Shift+S) οποιοδήποτε QR ή Barcode από την οθόνη σας και πατήστε «Από Πρόχειρο (Clipboard)».",
                                ft.Icons.CONTENT_PASTE,
                                ft.Colors.TEAL_400,
                            ),
                            col=4,
                        ),
                    ],
                    spacing=12,
                    run_spacing=12,
                ),
                ft.Divider(height=12, color="#1e293b"),
                ft.Text("2. Τι Αναγνωρίζει Αυτόματα το SpyQR (Smart Detection)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            build_help_card(
                                "🛒 Εμπορικά Προϊόντα (EAN-13 / EAN-8 / UPC-A)",
                                "Αναγνωρίζει αυτόματα ότι πρόκειται για προϊόν λιανικής, εντοπίζει τη χώρα προέλευσης GS1 (π.χ. 520 = Ελλάδα 🇬🇷), αναζητά αυτόματα την ονομασία και τη μάρκα του προϊόντος online (OpenFoodFacts / OpenBeautyFacts) και προσφέρει άμεσο κουμπί αναζήτησης στο Skroutz & Google!",
                                ft.Icons.SHOPPING_BAG,
                                ft.Colors.GREEN_400,
                            ),
                            col=6,
                        ),
                        ft.Container(
                            build_help_card(
                                "📚 Βιβλία (ISBN-13) & Περιοδικά (ISSN)",
                                "Ξεχωρίζει αυτόματα τους κωδικούς βιβλίων (978/979) και περιοδικών/εφημερίδων (977), αναζητώντας τίτλο και συγγραφέα μέσω της OpenLibrary.",
                                ft.Icons.MENU_BOOK,
                                ft.Colors.AMBER_400,
                            ),
                            col=6,
                        ),
                        ft.Container(
                            build_help_card(
                                "📦 Βιομηχανικά Barcodes (Code-128, Code-39, ITF)",
                                "Αναγνωρίζει σειριακούς αριθμούς αποθήκης, vouchers ταχυμεταφορών (courier) και ετικέτες logistics.",
                                ft.Icons.INVENTORY_2,
                                ft.Colors.ORANGE_400,
                            ),
                            col=6,
                        ),
                        ft.Container(
                            build_help_card(
                                "🌐 Ιστοσελίδες, Gov.gr / ΑΑΔΕ, YouTube & Social",
                                "Καταλαβαίνει αν ένας σύνδεσμος είναι κρατικό έγγραφο/απόδειξη (gov.gr / ΑΑΔΕ), βίντεο YouTube, ηλεκτρονικό κατάστημα ή κοινωνικό δίκτυο.",
                                ft.Icons.LANGUAGE,
                                ft.Colors.LIGHT_BLUE_400,
                            ),
                            col=6,
                        ),
                        ft.Container(
                            build_help_card(
                                "📶 Δίκτυα Wi-Fi & 👤 Κάρτες Επαφών (vCard)",
                                "Εξάγει αυτόματα το όνομα δικτύου (SSID), τον κωδικό πρόσβασης Wi-Fi και την ασφάλεια, ή το ονοματεπώνυμο, τηλέφωνο και email επαφής.",
                                ft.Icons.WIFI,
                                ft.Colors.PURPLE_300,
                            ),
                            col=6,
                        ),
                        ft.Container(
                            build_help_card(
                                "📍 Τοποθεσίες GPS, 📅 Εκδηλώσεις, 💳 IBAN & JSON",
                                "Προβάλλει γεωγραφικές συντεταγμένες σε διαδραστικό χάρτη, αναγνωρίζει ραντεβού ημερολογίου (vEvent), τραπεζικές πληρωμές SEPA/IBAN, τηλέφωνα, SMS, Email και δομημένα δεδομένα JSON.",
                                ft.Icons.LOCATION_ON,
                                ft.Colors.RED_400,
                            ),
                            col=6,
                        ),
                    ],
                    spacing=12,
                    run_spacing=12,
                ),
                ft.Divider(height=12, color="#1e293b"),
                ft.Text("3. Δημιουργία QR Codes & Barcodes (Καρτέλα «Δημιουργός»)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_300),
                build_help_card(
                    "Πώς να φτιάξετε δικό σας QR ή Barcode",
                    "Επιλέξτε τον επιθυμητό τύπο από το μενού (QR Code 2D, Barcode Code-128, EAN-13, EAN-8, UPC-A ή Code-39), πληκτρολογήστε το περιεχόμενο ή τον αριθμό, διαλέξτε χρώμα από την παλέτα και πατήστε «Αποθήκευση Εικόνας (PNG)».",
                    ft.Icons.CREATE,
                    ft.Colors.PURPLE_400,
                ),
                ft.Divider(height=20, color="#1e293b"),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.QR_CODE_2, color=ft.Colors.CYAN_400, size=20),
                                    ft.Text(f"{APP_NAME} v{__version__}", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                                    ft.Text("•", color=ft.Colors.GREY_600),
                                    ft.Text(APP_DESCRIPTION, size=13, color=ft.Colors.GREY_400),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Row(
                                [
                                    ft.Text("Ανάπτυξη / Δημιουργός:", size=13, color=ft.Colors.GREY_400),
                                    ft.TextButton(
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=ft.Colors.CYAN_400),
                                                ft.Text("SpyAlekos (alekos.program.gr)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_400),
                                            ],
                                            tight=True,
                                            spacing=5,
                                        ),
                                        on_click=lambda _: webbrowser.open("https://alekos.program.gr"),
                                        tooltip="Επίσκεψη στην ιστοσελίδα του δημιουργού (https://alekos.program.gr)",
                                    ),
                                    ft.Text("•", color=ft.Colors.GREY_600),
                                    ft.TextButton(
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.CODE, size=16, color=ft.Colors.LIGHT_BLUE_300),
                                                ft.Text("GitHub", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_300),
                                            ],
                                            tight=True,
                                            spacing=4,
                                        ),
                                        on_click=lambda _: webbrowser.open("https://github.com/spyalekos"),
                                        tooltip="GitHub: https://github.com/spyalekos",
                                    ),
                                ],
                                spacing=4,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    bgcolor="#111827",
                    border_radius=10,
                    border=ft.Border.all(1, "#1f2937"),
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        ),
        padding=20,
    )

    # ---------------------------------------------------------
    # 11. NAVIGATION, THEME INVERSION & APP SHELL
    # ---------------------------------------------------------
    def on_tab_change(e):
        if tabs.selected_index == 3:
            refresh_history_tab()
        elif tabs.selected_index == 4:
            refresh_analytics_tab()

    tabs = ft.Tabs(
        length=6,
        selected_index=0,
        animation_duration=250,
        on_change=on_tab_change,
        expand=True,
        content=ft.Column(
            [
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Σαρωτής", icon=ft.Icons.QR_CODE_SCANNER),
                        ft.Tab(label="Αποτέλεσμα", icon=ft.Icons.FACT_CHECK),
                        ft.Tab(label="Δημιουργός", icon=ft.Icons.CREATE),
                        ft.Tab(label="Ιστορικό", icon=ft.Icons.HISTORY),
                        ft.Tab(label="Στατιστικά", icon=ft.Icons.BAR_CHART),
                        ft.Tab(label="Βοήθεια", icon=ft.Icons.HELP_OUTLINE),
                    ],
                ),
                ft.TabBarView(
                    controls=[
                        scanner_tab_view,
                        result_tab_view,
                        generator_tab_view,
                        history_tab_view,
                        analytics_tab_view,
                        help_tab_view,
                    ],
                    expand=True,
                ),
            ],
            expand=True,
            spacing=0,
        ),
    )

    # Bidirectional Color Inversion Map (Dark <-> Light) for all Controls
    DARK_TO_LIGHT_BG = {
        "#090d16": "#e2e8f0",
        "#0f172a": "#f1f5f9",
        "#111827": "#ffffff",
        "#141a29": "#f8fafc",
        "#1e293b": "#e2e8f0",
    }
    LIGHT_TO_DARK_BG = {v: k for k, v in DARK_TO_LIGHT_BG.items()}
    LIGHT_TO_DARK_BG["#e2e8f0"] = "#1e293b"

    DARK_TO_LIGHT_BORDER = {
        "#1f2937": "#cbd5e1",
        "#232f47": "#cbd5e1",
        "#334155": "#94a3b8",
        "#1e293b": "#cbd5e1",
    }
    LIGHT_TO_DARK_BORDER = {
        "#cbd5e1": "#1f2937",
        "#94a3b8": "#334155",
    }

    DARK_TO_LIGHT_TEXT = {
        ft.Colors.WHITE: "#0f172a",
        ft.Colors.GREY_300: "#334155",
        ft.Colors.GREY_400: "#475569",
        ft.Colors.GREY_500: "#64748b",
        ft.Colors.LIGHT_BLUE_200: "#0369a1",
        ft.Colors.LIGHT_BLUE_300: "#0284c7",
        ft.Colors.CYAN_300: "#0e7490",
        ft.Colors.AMBER_300: "#b45309",
        ft.Colors.PURPLE_300: "#6d28d9",
        ft.Colors.GREEN_300: "#15803d",
        ft.Colors.RED_300: "#b91c1c",
    }
    LIGHT_TO_DARK_TEXT = {v: k for k, v in DARK_TO_LIGHT_TEXT.items()}

    PROTECTED_CONTAINERS = {
        fg_color_swatch,
        preview_bg_container,
        result_type_badge,
        *preset_swatches_row.controls,
    }

    def invert_control_tree(ctrl: Any, to_light: bool):
        """Recursively inverts background, border, and text/icon colors across all UI controls."""
        if ctrl is None or ctrl in PROTECTED_CONTAINERS:
            return

        # 1. Container & Control background colors
        if hasattr(ctrl, "bgcolor") and isinstance(ctrl.bgcolor, str):
            bg_low = ctrl.bgcolor.lower()
            if to_light and bg_low in DARK_TO_LIGHT_BG:
                ctrl.bgcolor = DARK_TO_LIGHT_BG[bg_low]
            elif not to_light and bg_low in LIGHT_TO_DARK_BG:
                ctrl.bgcolor = LIGHT_TO_DARK_BG[bg_low]

        # 2. Borders
        if hasattr(ctrl, "border") and ctrl.border is not None:
            for side_name in ("top", "bottom", "left", "right"):
                side = getattr(ctrl.border, side_name, None)
                if side and isinstance(getattr(side, "color", None), str):
                    sc = side.color.lower()
                    if to_light and sc in DARK_TO_LIGHT_BORDER:
                        side.color = DARK_TO_LIGHT_BORDER[sc]
                    elif not to_light and sc in LIGHT_TO_DARK_BORDER:
                        side.color = LIGHT_TO_DARK_BORDER[sc]

        # 3. Divider & Text / Button colors
        if isinstance(ctrl, ft.Divider) and isinstance(ctrl.color, str):
            dc = ctrl.color.lower()
            if to_light and dc in DARK_TO_LIGHT_BORDER:
                ctrl.color = DARK_TO_LIGHT_BORDER[dc]
            elif not to_light and dc in LIGHT_TO_DARK_BORDER:
                ctrl.color = LIGHT_TO_DARK_BORDER[dc]
        elif hasattr(ctrl, "color") and ctrl.color is not None:
            if not isinstance(ctrl, ft.Button) or ctrl.bgcolor in ("#1e293b", "#e2e8f0"):
                if to_light and ctrl.color in DARK_TO_LIGHT_TEXT:
                    ctrl.color = DARK_TO_LIGHT_TEXT[ctrl.color]
                elif not to_light and ctrl.color in LIGHT_TO_DARK_TEXT:
                    ctrl.color = LIGHT_TO_DARK_TEXT[ctrl.color]

        # 4. Recurse into child controls
        if hasattr(ctrl, "content") and ctrl.content is not None:
            invert_control_tree(ctrl.content, to_light)
        if hasattr(ctrl, "title") and isinstance(ctrl.title, ft.Control):
            invert_control_tree(ctrl.title, to_light)
        if hasattr(ctrl, "controls") and ctrl.controls:
            for child in ctrl.controls:
                invert_control_tree(child, to_light)
        if hasattr(ctrl, "rows") and ctrl.rows:
            for row in ctrl.rows:
                if hasattr(row, "cells") and row.cells:
                    for cell in row.cells:
                        invert_control_tree(getattr(cell, "content", None), to_light)

    theme_toggle_btn = ft.IconButton(
        icon=ft.Icons.LIGHTBULB,
        icon_color=ft.Colors.AMBER_400,
        tooltip="Αντιστροφή Χρωμάτων Εφαρμογής (Dark / Light Invert)",
    )

    def toggle_theme_invert(e):
        to_light = page.theme_mode == ft.ThemeMode.DARK
        page.theme_mode = ft.ThemeMode.LIGHT if to_light else ft.ThemeMode.DARK
        page.bgcolor = "#f1f5f9" if to_light else "#0b0f19"
        app_bar.bgcolor = "#e2e8f0" if to_light else "#090d16"
        theme_toggle_btn.icon = ft.Icons.DARK_MODE if to_light else ft.Icons.LIGHTBULB
        theme_toggle_btn.icon_color = ft.Colors.INDIGO_700 if to_light else ft.Colors.AMBER_400
        code_editor_control.code_theme = fce.CodeTheme.GITHUB if to_light else fce.CodeTheme.VS2015
        bar_chart_control.horizontal_grid_lines = fc.ChartGridLines(
            interval=1,
            color="#cbd5e1" if to_light else "#334155",
            width=1,
        )

        invert_control_tree(app_bar, to_light)
        invert_control_tree(tabs, to_light)
        invert_control_tree(camera_placeholder, to_light)
        page.update()

    theme_toggle_btn.on_click = toggle_theme_invert

    app_bar = ft.AppBar(
        leading=ft.Icon(ft.Icons.QR_CODE_2, color=ft.Colors.CYAN_400, size=30),
        title=ft.Row(
            [
                ft.Text(APP_NAME, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Container(
                    content=ft.Text(f"v{__version__}", size=11, color=ft.Colors.CYAN_200, weight=ft.FontWeight.BOLD),
                    bgcolor="#0e7490",
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
                ft.Text("•", size=12, color=ft.Colors.GREY_600),
                ft.TextButton(
                    content=ft.Text("by SpyAlekos", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.CYAN_300),
                    on_click=lambda _: webbrowser.open("https://alekos.program.gr"),
                    tooltip="Δημιουργός: SpyAlekos (https://alekos.program.gr)",
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        actions=[
            theme_toggle_btn,
            ft.IconButton(
                icon=ft.Icons.HELP_OUTLINE,
                tooltip="Βοήθεια & Οδηγίες Χρήσης",
                on_click=lambda _: setattr(tabs, "selected_index", 5) or page.update(),
            ),
        ],
        bgcolor="#090d16",
    )

    # Clean shutdown of camera when app window closes
    def on_window_event(e):
        if e.data == "close":
            scanner_engine.stop()

    page.window.on_event = on_window_event

    # Early rendering
    page.appbar = app_bar
    page.add(tabs)
    refresh_history_tab()
    refresh_analytics_tab()
    page.update()

    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass


if __name__ == "__main__":
    assets_dir = get_assets_path()
    ft.run(main, assets_dir=assets_dir)
