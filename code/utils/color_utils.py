#colors_utils.py
"""
Color utility functions for theme generation and accessibility checks.

Includes helpers to:
- Parse hex colors and convert to RGB
- Compute relative luminance and WCAG contrast ratio
- Convert between hex, Lab, and LCH color spaces
- Compute Delta E (CIEDE2000) using colormath

These utilities are used by `theme_manager.py` to ensure distinct and
accessible colors for pitch, lines, offside, and arrows.
"""
import re
from typing import Tuple
from colormath import color_diff_matrix
from colormath.color_diff import _get_lab_color1_vector, _get_lab_color2_matrix
from colormath.color_objects import sRGBColor, LabColor, LCHabColor
from colormath.color_conversions import convert_color

HEX_RE = re.compile(r'^#?([0-9a-fA-F]{6})$')

def hex_to_rgb(hexstr: str) -> Tuple[float, float, float]:
    """Convert a hex color string to normalized RGB tuple.

    Parameters
    ----------
    hexstr : str
        Hex color string, with or without leading '#'.

    Returns
    -------
    tuple[float, float, float]
        (r, g, b) in [0, 1].

    Raises
    ------
    ValueError
        If input is not a valid 6-digit hex color.
    """
    m = HEX_RE.match(hexstr)
    if not m:
        raise ValueError(f"Invalid hex color: {hexstr}")
    h = m.group(1)
    return tuple(int(h[i:i+2], 16)/255.0 for i in (0, 2, 4))

def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    """Compute relative luminance per WCAG for an sRGB triple.

    Parameters
    ----------
    rgb : tuple[float, float, float]
        sRGB values in [0, 1].

    Returns
    -------
    float
        Relative luminance.
    """
    def lin(c):
        return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    Rl, Gl, Bl = (lin(c) for c in rgb)
    return 0.2126*Rl + 0.7152*Gl + 0.0722*Bl

def contrast_ratio(c1: str, c2: str) -> float:
    """Compute the WCAG contrast ratio between two hex colors.

    Parameters
    ----------
    c1, c2 : str
        Hex colors.

    Returns
    -------
    float
        Contrast ratio in [1, 21].
    """
    L1 = relative_luminance(hex_to_rgb(c1))
    L2 = relative_luminance(hex_to_rgb(c2))
    return (max(L1, L2) + 0.05) / (min(L1, L2) + 0.05)

def hex_to_lab(hexstr: str) -> Tuple[float, float, float]:
    """Convert a hex color to CIE Lab.

    Parameters
    ----------
    hexstr : str
        Hex color string.

    Returns
    -------
    tuple[float, float, float]
        (L, a, b) triple.
    """
    rgb = sRGBColor(*hex_to_rgb(hexstr), is_upscaled=False)
    lab: LabColor = convert_color(rgb, LabColor)
    return (lab.lab_l, lab.lab_a, lab.lab_b)

def delta_e_lab(lab1, lab2) -> float:
    """Compute CIEDE2000 ΔE between two Lab colors.

    Parameters
    ----------
    lab1, lab2 : tuple[float, float, float] | LabColor
        Either tuples (L, a, b) or LabColor instances.

    Returns
    -------
    float
        ΔE00 value.
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
    """Patched CIEDE2000 using colormath vectorized internals for speed.

    Parameters
    ----------
    color1, color2 : LabColor
        Colors in Lab space.
    Kl, Kc, Kh : float, default 1
        Weighting factors.

    Returns
    -------
    float
        ΔE00 value.
    """
    color1_vector = _get_lab_color1_vector(color1)
    color2_matrix = _get_lab_color2_matrix(color2)
    delta_e = color_diff_matrix.delta_e_cie2000(
        color1_vector, color2_matrix, Kl=Kl, Kc=Kc, Kh=Kh)[0]

    return delta_e.item()

def hex_to_lch(hexstr: str) -> Tuple[float, float, float]:
    """Convert a hex color to CIE LCHab.

    Parameters
    ----------
    hexstr : str
        Hex color string.

    Returns
    -------
    tuple[float, float, float]
        (L, C, H) triple.
    """
    rgb = sRGBColor(*hex_to_rgb(hexstr), is_upscaled=False)
    lab = convert_color(rgb, LabColor)
    lch: LCHabColor = convert_color(lab, LCHabColor)
    return (lch.lch_l, lch.lch_c, lch.lch_h)

def lch_to_hex(l: float, c: float, h: float) -> str | None:
    """Convert LCHab to a hex string if in gamut; return None otherwise.

    Parameters
    ----------
    l, c, h : float
        LCHab components.

    Returns
    -------
    str | None
        Hex color string or None if outside sRGB gamut.
    """
    lch = LCHabColor(l, c, h)
    rgb = convert_color(lch, sRGBColor)
    hex_code = rgb.get_rgb_hex()
    # Validity check
    if isinstance(hex_code, str) and HEX_RE.fullmatch(hex_code):
        return hex_code
    return None
