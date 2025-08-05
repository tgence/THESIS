# theme_manager.py
from typing import Dict
from utils.color_utils import hex_to_lab, contrast_ratio, delta_e_lab, hex_to_lch, lch_to_hex
from config import BALL_COLOR

FALLBACK = ["#08711a", "#E4E4E4", "#FF40FF", "#000000"]
CLASSIC_GRASS = "#08711a"
CLASSIC_LINE = "#E4E4E4"
BW_GRASS_IF_LIGHT = "#292929"
BW_GRASS_IF_DARK = "#E4E4E4"
BW_LINE_IF_LIGHT = "#E4E4E4"
BW_LINE_IF_DARK = "#292929"

def is_light(hexcolor):
    r, g, b = int(hexcolor[1:3],16), int(hexcolor[3:5],16), int(hexcolor[5:7],16)
    return (0.299*r + 0.587*g + 0.114*b)/255.0 > 0.7

def majority_light(colors):
    lights = sum(is_light(c) for c in colors)
    return lights >= 2  # majorité sur 4

class ThemeManager:
    def __init__(self, use_petroff: bool = True, cr_target: float = 3.0, de_min: float = 20.0):
        self.use_petroff = use_petroff
        self.cr_target = cr_target # Contraste minimum entre herbe et ligne
        self.de_min = de_min # Delta E minimum entre les couleurs

    def fallback(self) -> Dict[str, str]:
        return {"grass": FALLBACK[0], "line": FALLBACK[1], "offside": FALLBACK[2], "arrow": FALLBACK[3]}

    def generate(self, mode: str, home_hex: str, away_hex: str, home_sec: str, away_sec: str) -> Dict[str, str]:
        home = "#" + home_hex.lstrip("#")
        away = "#" + away_hex.lstrip("#")
        home_sec = "#" + home_sec.lstrip("#")
        away_sec = "#" + away_sec.lstrip("#")
        all_teams = [home, away, home_sec, away_sec]
        ball = BALL_COLOR

        # === CLASSIC ===
        if mode.upper() == "CLASSIC":
            grass = CLASSIC_GRASS
            line  = CLASSIC_LINE
            forbidden = [grass, line, ball] + all_teams
            offside = self._find_distinct_color(forbidden)
            arrow   = self._find_distinct_color(forbidden + [offside])
            return {"grass": grass, "line": line, "offside": offside, "arrow": arrow}

        # === BLACK & WHITE ===
        if mode.upper() == "BLACK & WHITE":
            # 1. Évalue luminosité des 4 couleurs d'équipe
            if majority_light(all_teams):
                grass = BW_GRASS_IF_LIGHT
                line = BW_LINE_IF_LIGHT
            else:
                grass = BW_GRASS_IF_DARK
                line = BW_LINE_IF_DARK
            forbidden = [grass, line, ball] + all_teams
            # Génère des candidats bien différents pour offside/arrow (roue chromatique)
            offside = self._find_distinct_color(forbidden, chroma=80, luminance=80)
            arrow = self._find_distinct_color(forbidden + [offside], chroma=80, luminance=50)
            return {"grass": grass, "line": line, "offside": offside, "arrow": arrow}

        # Sécurité: fallback si aucun mode reconnu
        return self.fallback()

    def _find_distinct_color(self, reference_colors, chroma=45, luminance=60, threshold=35):
        forbidden_labs = [hex_to_lab(c) for c in reference_colors]
        best = None
        best_min_dist = -1

        for step in [60, 30, 15, 5]:
            candidates = [lch_to_hex(luminance, chroma, h) for h in range(0, 360, step)]
            candidates = [c for c in candidates if c]
            scored_candidates = []
            for c in candidates:
                c_lab = hex_to_lab(c)
                min_dist = min([delta_e_lab(c_lab, ref_lab) for ref_lab in forbidden_labs])
                scored_candidates.append((min_dist, c))

    
            ok = [(d, c) for d, c in scored_candidates if d > threshold]
            if ok:
                # Choisir la couleur dont le min_dist est le plus grand (donc la plus sûre)
                ok.sort(reverse=True)
                return ok[0][1]

            # Mémorise le meilleur trouvé même si < threshold (pour fallback)
            if scored_candidates:
                max_candidate = max(scored_candidates)
                if max_candidate[0] > best_min_dist:
                    best_min_dist = max_candidate[0]
                    best = max_candidate[1]

        # Fallback si rien n'est > threshold, on prend le "moins pire"
        return best
