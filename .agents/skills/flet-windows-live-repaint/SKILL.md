---
name: flet-windows-live-repaint
description: >-
  Solves Flet Windows Desktop UI repaint freezes (where camera streams, images, or progress
  bars only update after switching window focus) and prevents the Flutter 'valid src value
  must be specified' red error box on dynamic ft.Image controls.
---

# Flet Windows Desktop Live Repaint & Dynamic Image Streaming

## 1. Symptoms
1. **Window Focus Repaint Freeze**: Clicking a button to start a camera stream, image processing, or background task updates the internal state, but the Flet Windows Desktop window does not visually update until the user switches active applications (Alt+Tab / focus change) or resizes the window.
2. **Red Error Box (`valid src value must be specified.`)**: Mounting an `ft.Image` initialized with `src=b""` or `src=""` before the first frame arrives triggers a red Flutter error screen.

## 2. Root Cause
- On Windows Desktop, calling `page.update()` or `control.update()` from a standard OS thread (`threading.Thread`) runs outside Flet's main `asyncio` event loop. When the window is idle, the Flutter desktop engine does not schedule a frame (`scheduleFrame()`) until an OS window message (focus/blur/resize) arrives.
- Flutter's `Image` widget rejects empty byte strings (`b""`) or empty strings (`""`) at build time.

## 3. Definitive 4-Part Solution

### Part A: Non-Empty Initial 1x1 PNG & `gapless_playback=True`
Never initialize `ft.Image` with `src=b""` or `src=""`. Always provide a valid 1x1 PNG byte constant and enable `gapless_playback=True`:

```python
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
    gapless_playback=True,
)
```

### Part B: 1px Window Width Nudge (`force_window_repaint`)
When swapping containers (e.g., `camera_placeholder` -> `camera_view`), nudge `page.window.width` by `+1px` and restore it to force an immediate OS-level WM_SIZE redraw message:

```python
def force_window_repaint():
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
```

### Part C: Active `ft.ProgressRing` Ticker
Keep a small `ft.ProgressRing(visible=True)` visible in the UI while the stream or background task is active. An active animation forces Flutter's engine to run a continuous 60fps `scheduleFrame()` ticker.

### Part D: Main Event Loop Coroutine (`page.run_task` + `asyncio.to_thread`)
Never push UI updates from `threading.Thread`. Run the worker as an `async def` coroutine via `page.run_task()`, offloading only the blocking frame grab/I/O to `asyncio.to_thread()`:

```python
async def camera_async_worker():
    success = await asyncio.to_thread(scanner_engine.open_camera, 0)
    if not success:
        return

    while scanner_engine.is_running():
        frame_bytes, scan_event = await asyncio.to_thread(scanner_engine.grab_frame)
        if frame_bytes:
            on_frame_received(frame_bytes)
        if scan_event:
            on_scan_detected(*scan_event)
        await asyncio.sleep(0.015)  # Yields to Flet event loop to flush socket patches (<16ms)
```
