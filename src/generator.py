"""Custom QR Code & 1D Barcode generator with color customization and file export."""

import base64
import io
from typing import Optional, Tuple
from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q

try:
    import barcode
    from barcode.writer import ImageWriter
    HAS_BARCODE_GEN = True
except ImportError:
    HAS_BARCODE_GEN = False


def normalize_hex_color(color_val: str, default: str = "#000000") -> str:
    """Normalizes hex color strings (including 8-char Flutter #AARRGGBB or 6-char #RRGGBB) to #RRGGBB."""
    if not color_val:
        return default
    c = str(color_val).strip().lstrip("#")
    if len(c) == 8:
        # Flutter ColorPicker returns AARRGGBB -> strip AA to get RRGGBB
        c = c[2:]
    elif len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return default
    try:
        int(c, 16)
        return f"#{c.upper()}"
    except ValueError:
        return default


def generate_qr_image(
    data: str,
    fill_color: str = "#000000",
    back_color: str = "#FFFFFF",
    box_size: int = 10,
    border: int = 4,
    error_correction: str = "M",
    code_type: str = "QR",
) -> Tuple[Optional[bytes], Optional[Image.Image]]:
    """Generates a QR code or 1D Barcode (EAN-13, EAN-8, UPC-A, Code128, Code39) image and returns (png_bytes, PIL_Image)."""
    if not data:
        return None, None

    fg_hex = normalize_hex_color(fill_color, "#000000")
    bg_hex = normalize_hex_color(back_color, "#FFFFFF")

    ctype = (code_type or "QR").upper()
    if ctype != "QR" and HAS_BARCODE_GEN:
        try:
            bmap = {
                "CODE128": "code128",
                "CODE39": "code39",
                "EAN13": "ean13",
                "EAN8": "ean8",
                "UPCA": "upca",
            }
            bname = bmap.get(ctype, "code128")
            clean_data = data.strip()
            # Ensure valid numeric length for EAN/UPC if user typed arbitrary text
            if bname == "ean13":
                digits = "".join(ch for ch in clean_data if ch.isdigit())
                clean_data = (digits + "520123456789")[:12]
            elif bname == "ean8":
                digits = "".join(ch for ch in clean_data if ch.isdigit())
                clean_data = (digits + "5201234")[:7]
            elif bname == "upca":
                digits = "".join(ch for ch in clean_data if ch.isdigit())
                clean_data = (digits + "01234567890")[:11]

            writer = ImageWriter()
            b_obj = barcode.get(bname, clean_data, writer=writer)
            buf = io.BytesIO()
            mod_height = max(8.0, float(box_size) * 1.4)
            quiet_z = max(1.0, float(border))
            write_opts = {
                "foreground": fg_hex,
                "background": bg_hex,
                "module_height": mod_height,
                "module_width": 0.35,
                "quiet_zone": quiet_z,
                "font_size": 10,
                "text_distance": 4.0,
            }
            try:
                b_obj.write(buf, options=write_opts)
            except Exception:
                buf = io.BytesIO()
                write_opts["write_text"] = False
                b_obj.write(buf, options=write_opts)
            buf.seek(0)
            img = Image.open(buf).convert("RGB")
            out_buf = io.BytesIO()
            img.save(out_buf, format="PNG")
            return out_buf.getvalue(), img
        except Exception as e:
            print(f"[Generator] Barcode generation fallback to QR due to: {e}")

    ec_map = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }
    ec = ec_map.get(error_correction.upper(), ERROR_CORRECT_M)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ec,
        box_size=max(2, int(box_size)),
        border=max(0, int(border)),
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fg_hex, back_color=bg_hex).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), img


def save_qr_to_file(img: Image.Image, file_path: str) -> bool:
    """Saves PIL Image to the specified disk path."""
    try:
        img.save(file_path)
        return True
    except Exception as e:
        print(f"[Generator] Save error: {e}")
        return False
