# color_utils.py
import re
from typing import Tuple
from colormath import color_diff_matrix
from colormath.color_diff import _get_lab_color1_vector, _get_lab_color2_matrix
from colormath.color_objects import sRGBColor, LabColor, LCHabColor
from colormath.color_conversions import convert_color

HEX_RE = re.compile(r'^#?([0-9a-fA-F]{6})$')

def hex_to_rgb(hexstr: str) -> Tuple[float, float, float]:
    m = HEX_RE.match(hexstr)
    if not m:
        raise ValueError(f"Invalid hex color: {hexstr}")
    h = m.group(1)
    return tuple(int(h[i:i+2], 16)/255.0 for i in (0, 2, 4))

def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    def lin(c): return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    Rl, Gl, Bl = (lin(c) for c in rgb)
    return 0.2126*Rl + 0.7152*Gl + 0.0722*Bl

def contrast_ratio(c1: str, c2: str) -> float:
    L1 = relative_luminance(hex_to_rgb(c1))
    L2 = relative_luminance(hex_to_rgb(c2))
    return (max(L1, L2) + 0.05) / (min(L1, L2) + 0.05)

def hex_to_lab(hexstr: str) -> Tuple[float, float, float]:
    rgb = sRGBColor(*hex_to_rgb(hexstr), is_upscaled=False)
    lab: LabColor = convert_color(rgb, LabColor)
    return (lab.lab_l, lab.lab_a, lab.lab_b)

def delta_e_lab(lab1, lab2) -> float:
    """
    Compare n'importe quoi : tuple (l, a, b) ou LabColor.
    """
    def to_labcolor(x):
        if isinstance(x, LabColor):
            return x
        elif isinstance(x, tuple) and len(x) == 3:
            return LabColor(*x)
        else:
            raise ValueError("lab1/lab2 must be LabColor or tuple of (l,a,b)")
    return delta_e_cie2000_patched(to_labcolor(lab1), to_labcolor(lab2))

def delta_e_cie2000_patched(color1, color2, Kl=1, Kc=1, Kh=1):
    color1_vector = _get_lab_color1_vector(color1)
    color2_matrix = _get_lab_color2_matrix(color2)
    delta_e = color_diff_matrix.delta_e_cie2000(
        color1_vector, color2_matrix, Kl=Kl, Kc=Kc, Kh=Kh)[0]

    return delta_e.item()

def hex_to_lch(hexstr: str) -> Tuple[float, float, float]:
    rgb = sRGBColor(*hex_to_rgb(hexstr), is_upscaled=False)
    lab = convert_color(rgb, LabColor)
    lch: LCHabColor = convert_color(lab, LCHabColor)
    return (lch.lch_l, lch.lch_c, lch.lch_h)

def lch_to_hex(l: float, c: float, h: float) -> str | None:
    """
    Convertit LCHab en hex (str) si valide, sinon None.
    """
    lch = LCHabColor(l, c, h)
    rgb = convert_color(lch, sRGBColor)
    hex_code = rgb.get_rgb_hex()
    # Check validité :
    if isinstance(hex_code, str) and HEX_RE.fullmatch(hex_code):
        return hex_code
    return None
