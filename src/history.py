"""Scan history management with SecureStorage and disk fallback."""

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional
import flet as ft
import flet_secure_storage as fss


class HistoryManager:
    """Manages scan history persistence using flet-secure-storage with local disk fallback."""

    STORAGE_KEY = "spyqr_scan_history_v1"
    FALLBACK_FILE = os.path.join(os.path.expanduser("~"), ".spyqr_history.json")

    def __init__(self, page: ft.Page, secure_storage: Optional[fss.SecureStorage] = None):
        self.page = page
        self.secure_storage = secure_storage
        self.items: List[Dict[str, Any]] = []
        self._load_fallback()

    def _load_fallback(self) -> None:
        """Loads history from disk fallback if available, or seeds demo entries."""
        if os.path.exists(self.FALLBACK_FILE):
            try:
                with open(self.FALLBACK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        # Clean any legacy demo entries referencing flet.dev
                        cleaned = [
                            it for it in data
                            if "flet.dev" not in str(it.get("raw_data", ""))
                            and '"engine": "Flet' not in str(it.get("raw_data", ""))
                        ]
                        if cleaned:
                            self.items = cleaned
                            return
            except Exception as e:
                print(f"[HistoryManager] Fallback load error: {e}")

        now = time.time()
        self.items = [
            {
                "id": f"qr_{int(now * 1000)}_1",
                "timestamp_epoch": now - 120,
                "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 120)),
                "qr_type": "PRODUCT",
                "raw_data": "5201054001050",
                "metadata": {"Κατηγορία": "Εμπορικό Προϊόν Λιανικής", "Πρότυπο Barcode": "EAN-13"},
            },
            {
                "id": f"qr_{int(now * 1000)}_2",
                "timestamp_epoch": now - 600,
                "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 600)),
                "qr_type": "GEO",
                "raw_data": "geo:37.9755,23.7348",
                "metadata": {"latitude": 37.9755, "longitude": 23.7348},
            },
            {
                "id": f"qr_{int(now * 1000)}_3",
                "timestamp_epoch": now - 1800,
                "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 1800)),
                "qr_type": "URL",
                "raw_data": "https://www.gov.gr",
                "metadata": {"url": "https://www.gov.gr"},
            },
        ]
        self._save_fallback()

    def _save_fallback(self) -> None:
        """Saves current items to disk fallback."""
        try:
            with open(self.FALLBACK_FILE, "w", encoding="utf-8") as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[HistoryManager] Fallback save error: {e}")

    async def load_history_async(self) -> List[Dict[str, Any]]:
        """Asynchronously loads history from SecureStorage."""
        if self.secure_storage:
            try:
                raw = await self.secure_storage.get(self.STORAGE_KEY)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        self.items = data
                        return self.items
            except Exception as e:
                print(f"[HistoryManager] SecureStorage load exception: {e}")
        return self.items

    async def save_history_async(self) -> None:
        """Asynchronously saves history to SecureStorage and fallback."""
        self._save_fallback()
        if self.secure_storage:
            try:
                payload = json.dumps(self.items, ensure_ascii=False)
                await self.secure_storage.set(self.STORAGE_KEY, payload)
            except Exception as e:
                print(f"[HistoryManager] SecureStorage save exception: {e}")

    def add_entry(
        self,
        raw_data: str,
        qr_type: str = "TEXT",
        metadata: Optional[Dict[str, Any]] = None,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Any]:
        """Adds a newly scanned QR code entry to history."""
        # Avoid duplicate consecutive scans within 3 seconds
        current_time = time.time()
        if self.items:
            last = self.items[0]
            if last.get("raw_data") == raw_data and (current_time - last.get("timestamp_epoch", 0) < 3.0):
                return last

        entry = {
            "id": f"qr_{int(current_time * 1000)}",
            "timestamp_epoch": current_time,
            "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),
            "qr_type": qr_type,
            "raw_data": raw_data,
            "metadata": metadata or {},
        }
        self.items.insert(0, entry)
        if len(self.items) > 500:
            self.items = self.items[:500]

        self._save_fallback()
        if self.secure_storage:
            try:
                self.page.run_task(self.save_history_async)
            except Exception:
                pass

        if on_saved:
            on_saved()
        return entry

    def delete_entry(self, entry_id: str) -> None:
        """Removes an entry by ID."""
        self.items = [item for item in self.items if item.get("id") != entry_id]
        self._save_fallback()
        if self.secure_storage:
            try:
                self.page.run_task(self.save_history_async)
            except Exception:
                pass

    def clear_all(self) -> None:
        """Clears all history entries."""
        self.items.clear()
        self._save_fallback()
        if self.secure_storage:
            try:
                self.page.run_task(self.save_history_async)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, int]:
        """Computes count of items per QR type."""
        stats: Dict[str, int] = {}
        for item in self.items:
            t = item.get("qr_type", "TEXT")
            stats[t] = stats.get(t, 0) + 1
        return stats
