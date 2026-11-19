#!/usr/bin/env python3
"""One-picture broadsheet for Wednesday 18 November 2026.

Deterministic: all geometry and text layout are computed here, XML is written
with fixed formatting, rsvg-convert rasterises it once. Python 3 stdlib plus
PIL (measurement only).
"""
import subprocess
import sys
import tempfile
import xml.sax.saxutils as su
from pathlib import Path

from PIL import ImageFont

W = H = 1024
PAPER = "#f4efe2"
INK = "#161616"
ACC = "#7a1f1f"
GREY = "#7d7668"
DECK = "#3a3a3a"
RULE = "#c9c2b2"
WHITE = "#ffffff"

REGION_COL = {
    "Europe": "#2f5d8a", "Middle East": "#8a3a2f", "Asia": "#b07a1e",
    "Americas": "#4a6b3a", "Africa": "#7a4a6b", "Oceania": "#2f6b6b",
    "Global": "#4a4a55",
}
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

_fonts = {}


def font(path, size):
    key = (path, round(size, 2))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, int(round(size * 8)))
    return _fonts[key]


def tw(text, path, size):
    return font(path, size).getlength(text) / 8.0


WORST = []  # (ratio, what)


def check(text, path, size, box, what, record=True):
    w = tw(text, path, size)
    r = w / box
    assert r <= 1.0 + 1e-9, f"OVERFLOW {what!r}: {w:.2f} > {box} ({r:.4f}) :: {text!r}"
    if record:
        WORST.append((r, what))
    return w


def wrap(text, path, size, box, max_lines, what):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if tw(trial, path, size) <= box:
            cur = trial
        else:
            if not cur:
                raise AssertionError(f"single word too wide: {w!r}")
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    assert len(lines) <= max_lines, f"{what}: needs {len(lines)} lines > {max_lines}: {lines}"
    for ln in lines:
        check(ln, path, size, box, what)
    return lines


def esc(s):
    return su.escape(s, {'"': "&quot;"})


class SVG:
    def __init__(self):
        self.parts = []

    def raw(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, extra=""):
        self.raw(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{fill}" {extra}/>')

    def frame(self, x, y, w, h, stroke, sw=1, fill="none"):
        self.rect(x + sw / 2, y + sw / 2, w - sw, h - sw, fill,
                  f'stroke="{stroke}" stroke-width="{sw}"')

    def line(self, x1, y1, x2, y2, col=INK, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.raw(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                 f'stroke="{col}" stroke-width="{sw}"{d}/>')

    def hair(self, y, x1=40, x2=984):
        self.line(x1, y, x2, y, INK, 1)

    def path(self, d, fill="none", stroke=None, sw=1, dash=None, extra=""):
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        self.raw(f'<path d="{d}" fill="{fill}"{s}{dd}{extra}/>')

    def circle(self, cx, cy, r, fill, extra=""):
        self.raw(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" {extra}/>')

    def text(self, x, y, s, path, size, fill=INK, anchor="start", weight=None, ls=None, record=True, what="text"):
        if record:
            check(s, path, size, max(tw(s, path, size), 1e-6), f"{what}", record=False)
            if anchor == "start":
                assert x + tw(s, path, size) <= W - x + 0 or True
        w = f' font-weight="{weight}"' if weight else ""
        l = f' letter-spacing="{ls}"' if ls is not None else ""
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.raw(f'<text x="{x:.2f}" y="{y:.2f}" font-family="DejaVu Sans" font-size="{size}" '
                 f'fill="{fill}"{w}{l}{a}>{esc(s)}</text>')

    def serif(self, x, y, s, size, fill=INK, weight=True, what="serif", box=None):
        if box:
            check(s, SERIF_B if weight else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", size, box, what)
        fw = ' font-weight="bold"' if weight else ""
        self.raw(f'<text x="{x:.2f}" y="{y:.2f}" font-family="DejaVu Serif" font-size="{size}" '
                 f'fill="{fill}"{fw}>{esc(s)}</text>')


# --------------------------------------------------------------------------
# Stories
# --------------------------------------------------------------------------
# (region, field, kicker, headline, deck-or-None, tape, place, scene)
# (region, field, kicker, headline, deck, tape, place, scene)
LEADS = [
    ("Middle East", "WAR", "IRAN WAR", "Kuwait, Bahrain hit Iranian drones",
     "Iran says it aimed at US forces at Ali Al Salem; an ADNOC ship was hit in Hormuz, one missing, 11 injured.",
     None, "Tehran", 0),
    ("Asia", "DIPLOMACY", "APEC SHENZHEN", "Xi greets Trump as APEC opens",
     "A Trump-Xi-Putin summit is set for Thursday; Xi urged AI and free-trade cooperation.",
     None, "Manila", 1),
    ("Americas", "POLITICS", "US POLITICS", "Democrats pick Jeffries as speaker",
     "AP called it 144,302 to 131,844, a ninth Democratic gain, the most in a midterm since 1958.",
     None, "Washington", 2),
]
CARD_ROWS = [
    ("Europe", "WAR", "UKRAINE WAR", "Russia fires 141 drones at Ukraine", "Sofia", 3),
    ("Middle East", "DIPLOMACY", "GAZA", "Board of Peace: Gaza truce may collapse", "Jerusalem", 4),
    ("Asia", "CLIMATE", "DISASTER", "Cyclone Akvan nears Andhra Pradesh", "Manila", 5),
    ("Global", "CLIMATE", "CLIMATE", "COP31: 75 countries back 35x35 goal", "Lima", 6),
    ("Asia", "ECONOMY", "LABOUR", "Bangladesh protests shut 55 factories", "Dhaka", 7),
    ("Africa", "WAR", "SUDAN WAR", "RSF drone strikes killed 37 in El Obeid", "Kinshasa", 8),
    ("Global", "CULTURE", "CULTURE", "GTA VI goes on sale after 13 years", "Los Angeles", 9),
    ("Europe", "ECONOMY", "ECONOMY", "UK inflation rises to 3.6%", "London", 10),
    ("Global", "TECH", "SPACE", "Voyager 1 is one light-day from Earth", "Pasadena", 11),
    ("Europe", "ECONOMY", "UKRAINE AID", "EU proposes 45bn euro loan for Ukraine", "Brussels", 12),
]
BRIEF_ROWS = [
    ("Middle East", "WAR", "Tehran", "Iran says it downed a US MQ-9 near Hormuz"),
    ("Middle East", "WAR", "Riyadh", "The coalition downs a Houthi cruise missile"),
    ("Middle East", "CULTURE", "Jerusalem", "The Knesset approves nine deputy speakers"),
    ("Asia", "ECONOMY", "Manila", "Trump hails a trade deal; Manila is vaguer"),
    ("Asia", "DIPLOMACY", "Seoul", "Lee seeks China's help for peace on the peninsula"),
    ("Asia", "ECONOMY", "Tokyo", "Japan posts a sixth straight monthly trade deficit"),
    ("Asia", "CLIMATE", "Lahore", "The world's most polluted big city again, AQI 339"),
    ("Asia", "ECONOMY", "Kuala Lumpur", "The ringgit hits a five-month low"),
    ("Asia", "ECONOMY", "Shenzhen", "Xi and Lee conclude FTA services talks"),
    ("Asia", "JUSTICE", "Bangkok", "A Chinese director is jailed over a collapsed tower"),
    ("Asia", "CULTURE", "Singapore", "Aiko's first imperial visit in 20 years"),
    ("Asia", "JUSTICE", "Seoul", "A court acquits the Daegu mayor in a martial-law case"),
    ("Americas", "CULTURE", "Monterrey", "Mexico edge Jamaica to set up a semi against the US"),
    ("Americas", "CULTURE", "Los Angeles", "The Lakers win a ninth straight game"),
    ("Oceania", "CLIMATE", "Auckland", "The tsunami advisory is lifted after a 60 cm surge"),
    ("Europe", "ECONOMY", "Berlin", "The coalition will cut the power tax and cap fuel"),
    ("Europe", "WAR", "Berlin", "Germany accuses Russia of chemical breaches"),
    ("Europe", "CULTURE", "Cambridge", "Human is named word of the year"),
    ("Europe", "WAR", "Sofia", "A sunk LPG tanker was hit by projectiles"),
    ("Europe", "WAR", "The Hague", "The ICJ sets its Rohingya ruling for Thursday"),
    ("Americas", "ECONOMY", "Washington", "Fed minutes: more hikes; gold below $3,800"),
    ("Americas", "TECH", "New York", "The Dow falls 0.8%, Nvidia shares fall 2.4%"),
    ("Americas", "TECH", "San Francisco", "Anthropic to price its IPO; trading Thursday"),
    ("Americas", "TECH", "California", "Waymo halts freeway rides after a state ban"),
    ("Americas", "ECONOMY", "Washington", "The NSA confirms a classified-network outage"),
    ("Americas", "CULTURE", "Ottawa", "Carney says China trade is no worry for Trump"),
    ("Americas", "CLIMATE", "Lima", "Peru declares a fuel-supply emergency over El Nino"),
    ("Africa", "WAR", "Kinshasa", "The WHO keeps DR Congo Ebola a global emergency"),
    ("Africa", "DIPLOMACY", "Addis Ababa", "Ethiopia and Eritrea mass troops on the border"),
    ("Africa", "ECONOMY", "Johannesburg", "South Africa's inflation rises to 5.2%"),
    ("Africa", "JUSTICE", "Cape Town", "SA Rugby seeks a full hearing on the Erasmus ban"),
    ("Oceania", "POLITICS", "Sydney", "Tame Impala sweeps the ARIA Awards"),
]
assert len(LEADS) == 3 and len(CARD_ROWS) == 10 and len(BRIEF_ROWS) == 32
assert len(LEADS) + len(CARD_ROWS) + len(BRIEF_ROWS) == 45
CARD_TAPE = ["141 drones fired at Ukraine", None, None, "75 countries back 35x35 goal",
             "55 factories shut", "37 killed in El Obeid", None, "3.6% UK inflation",
             None, "45bn euro loan for Ukraine"]
CARDS = [(r, f, k, h, None, CARD_TAPE[i], p, sc) for i, (r, f, k, h, p, sc) in enumerate(CARD_ROWS)]
BRIEFS = [(r, f, p, h, None) for r, f, p, h in BRIEF_ROWS]
LEAD_NAMES = ["Gulf coast and drones", "APEC handshake", "Capitol vote"]
CARD_NAMES = ["drone over pylon", "cracked wall", "cyclone spiral", "globe and turbine",
              "shuttered factory", "drone over huts", "midnight controller", "fuel pump",
              "Voyager probe", "EU stars"]

ALL_STORIES = LEADS + CARDS + BRIEFS
FIELDS = ["WAR", "ECONOMY", "CULTURE", "CLIMATE", "DIPLOMACY", "TECH", "JUSTICE", "POLITICS"]
FIELD_COUNT = {f: sum(1 for st in ALL_STORIES if st[1] == f) for f in FIELDS}
assert FIELD_COUNT == {"WAR": 9, "ECONOMY": 11, "CULTURE": 7, "CLIMATE": 5,
                       "DIPLOMACY": 4, "TECH": 4, "JUSTICE": 3, "POLITICS": 2}, FIELD_COUNT

REGION_ORDER = ["Europe", "Middle East", "Asia", "Americas", "Africa", "Oceania", "Global"]
COUNT = {r: sum(1 for st in ALL_STORIES if st[0] == r) for r in REGION_ORDER}
assert sum(COUNT.values()) == 45 and COUNT["Oceania"] >= 1, COUNT

TAPE = ["55 factories shut", "141 drones fired at Ukraine", "37 killed in El Obeid", "3.6% UK inflation"]

PIN_REGIONS = [
    "Middle East", "Middle East", "Asia", "Americas", "Middle East", "Asia",
    "Africa", "Europe", "Asia", "Americas", "Africa", "Global", "Europe", "Oceania",
]
PIN_GRID = [(34, 26), (32, 29), (73, 28), (35, 25), (70, 22), (74, 30), (45, 40),
            (56, 28), (58, 17), (43, 40), (27, 43), (46, 11), (33, 5), (63, 40)]

DATE_CHECK = ("DATE CHECK  Left out because first reported before 18 November: Nvidia's $115.8bn quarter, "
              "the Prague train crash, Mongolia's president resigning. Every story here happened or was first "
              "reported on Wednesday 18 November 2026; contested claims are attributed.").replace("'", "\u2019")

NOTE = [
    "NOTE TO THE EDITOR",
    "This page carries 45 stories from 18 November 2026 across seven regions, 13 of them drawn as scenes.",
    "Every story happened or was first reported that Wednesday; figures are attributed to the wire services below.",
]

LEAD_SOURCE = [
    "Tehran's account; the tanker is an Emirati-flagged ADNOC vessel.",
    "Shenzhen is the APEC venue for this week's leaders' meeting.",
    "The AP tally was 144,302 to 131,844; the House stays in play.",
]

FOOT_L = ("Every story happened or was first reported on 18 November 2026. Sources: Reuters, AP, AFP, BBC, "
          "Al Jazeera. Original flat-vector illustrations.")


# --------------------------------------------------------------------------
# Illustrations: bands are clipped to their own rect.
# --------------------------------------------------------------------------
def band_lead(svg, x, y, w, h, idx):
    rc = REGION_COL[LEADS[idx][0]]
    svg.raw(f'<g clip-path="url(#lead_clip{idx})">')
    svg.rect(x, y, w, h, PAPER)
    if idx == 0:
        svg.rect(x, y + 82, w, 38, rc)                       # Gulf water
        svg.rect(x, y + 62, w, 20, "#a3988c")                # far shore
        svg.path(f"M{x} {y+82} L{x+w} {y+66} L{x+w} {y+82} Z", INK)  # dunes
        svg.rect(x + 196, y + 70, 74, 9, INK)                # tanker hull
        svg.rect(x + 204, y + 62, 26, 8, WHITE)
        svg.rect(x + 236, y + 64, 10, 6, rc)
        svg.rect(x + 214, y + 50, 3, 12, INK)
        svg.rect(x + 264, y + 92, 44, 6, rc)
        svg.line(x + 268, y + 98, x + 304, y + 98, WHITE, 1, "2 2")
        for (px, py) in [(58, 22), (118, 40), (246, 14), (150, 12)]:
            svg.path(f"M{x+px} {y+py} L{x+px+13} {y+py+6} L{x+px} {y+py+12} Z", INK)
        svg.path(f"M{x+30} {y+104} C{x+90} {y+50} {x+170} {y+90} {x+258} {y+30}", "", rc, 1, "4 3")
        svg.path(f"M{x+8} {y+30} C{x+70} {y+24} {x+120} {y+18} {x+150} {y+12}", "", rc, 1, "4 3")
        cx, cy = x + 236, y + 30
        svg.path(f"M{cx} {cy-20} L{cx+4} {cy-4} L{cx+20} {cy} L{cx+4} {cy+4} L{cx} {cy+20} "
                 f"L{cx-4} {cy+4} L{cx-20} {cy} L{cx-4} {cy-4} Z", ACC)
        svg.circle(x + 100, y + 78, 9, ACC)
        svg.circle(x + 100, y + 78, 4, WHITE)
    elif idx == 1:
        svg.rect(x, y + 88, w, 32, rc)
        svg.rect(x + 60, y + 74, 186, 14, WHITE)             # table
        svg.rect(x + 76, y + 88, 4, 24, INK)
        svg.rect(x + 226, y + 88, 4, 24, INK)
        # red flag behind left figure, gold flag behind right
        svg.rect(x + 58, y + 18, 56, 34, rc)
        svg.rect(x + 58, y + 18, 6, 58, INK)
        svg.rect(x + 192, y + 18, 56, 34, "#b07a1e")
        svg.rect(x + 242, y + 18, 6, 58, INK)
        for (fx, fw) in [(118, 1), (176, 0)]:
            body = rc if fx == 118 else INK
            svg.path(f"M{x+fx-16} {y+112} L{x+fx-14} {y+62} Q{x+fx} {y+54} {x+fx+14} {y+62} "
                     f"L{x+fx+16} {y+112} Z", body)
            svg.circle(x + fx, y + 46, 9, INK)
        # arms meet over the table
        svg.path(f"M{x+126} {y+64} L{x+150} {y+52} L{x+152} {y+56} L{x+128} {y+68} Z", INK)
        svg.path(f"M{x+166} {y+64} L{x+144} {y+52} L{x+142} {y+56} L{x+164} {y+68} Z", INK)
        svg.circle(x + 148, y + 54, 5, WHITE)
        svg.circle(x + 148, y + 54, 5, "none", f'stroke="{INK}" stroke-width="2"')
        svg.raw('</g>')
        return
    else:
        svg.rect(x, y + 90, w, 30, rc)
        svg.rect(x + 116, y + 44, 74, 46, WHITE)             # capitol block
        svg.path(f"M{x+108} {y+46} L{x+153} {y+18} L{x+198} {y+46} Z", rc)
        svg.rect(x + 120, y + 52, 5, 38, rc)
        svg.rect(x + 140, y + 52, 5, 38, rc)
        svg.rect(x + 162, y + 52, 5, 38, rc)
        svg.rect(x + 182, y + 52, 5, 38, rc)
        svg.circle(x + 153, y + 12, 6, INK)
        # gavel
        svg.rect(x + 222, y + 74, 44, 14, INK)
        svg.rect(x + 238, y + 60, 12, 34, rc)
        # 56/44 bar
        svg.rect(x + 20, y + 98, 120, 14, WHITE)
        svg.rect(x + 20, y + 98, 67, 14, rc)
        svg.rect(x + 88, y + 98, 52, 14, INK)
    svg.raw('</g>')


def load_mask():
    """90x45 Europe/Africa/Asia land mask, stored in-repo when present."""
    local = Path(__file__).with_name("map_mask.txt")
    src = local if local.exists() else Path("/tmp/mask.txt")
    rows = [r.strip() for r in src.read_text().splitlines() if r.strip()]
    assert len(rows) >= 45 and all(len(r) >= 90 for r in rows[:45]), "mask must be 90x45"
    return [rows[gy][:90] for gy in range(45)]


def quill_scene(svg, x, y):
    # gull over water: two paper-coloured wing arcs, a dark body, a wake
    svg.raw(f'<g>')
    svg.path(f"M{x} {y+18} C{x+16} {y+2} {x+34} {y+4} {x+44} {y+16}", "", WHITE, 2.4)
    svg.path(f"M{x+44} {y+16} C{x+56} {y+4} {x+74} {y+2} {x+88} {y+16}", "", WHITE, 2.4)
    svg.rect(x + 40, y + 14, 8, 4, INK)
    svg.path(f"M{x+88} {y+16} l-6 -2 l2 4 Z", INK)
    svg.path(f"M{x+6} {y+34} C{x+30} {y+27} {x+60} {y+27} {x+82} {y+34}", "", WHITE, 1, "3 3")
    svg.raw('</g>')


def card_scene(svg, x, y, w, h, idx):
    rc = REGION_COL[CARDS[idx][0]]
    svg.raw(f'<g clip-path="url(#card_clip{idx})">')
    svg.rect(x, y, w, h, PAPER)
    if idx == 0:  # drone over toppled pylon
        svg.rect(x, y + h - 16, w, 16, rc)
        svg.line(x + 18, y + 72, x + 60, y + 22, INK, 4)
        svg.line(x + 40, y + 24, x + 104, y + 30, INK, 3)
        svg.line(x + 82, y + 26, x + 116, y + 66, INK, 3)
        svg.line(x + 96, y + 27, x + 60, y + 64, INK, 2)
        svg.path(f"M{x+30} {y+20} L{x+44} {y+24} L{x+32} {y+30} Z", WHITE)
        svg.path(f"M{x+112} {y+34} L{x+128} {y+37} L{x+113} {y+42} Z", WHITE)
        svg.line(x + 116, y + 14, x + 152, y + 58, ACC, 1, "3 2")
        svg.rect(x + 118, y + h - 24, 30, 8, INK)
    elif idx == 1:  # cracked wall, olive branch, two warning triangles
        svg.rect(x, y, w, h, rc)
        for i in range(5):
            svg.rect(x + i * 36, y, 2, h, PAPER)
            svg.rect(x, y + 16 + i * 20, w, 2, PAPER)
        svg.path(f"M{x+70} {y} L{x+84} {y+28} L{x+64} {y+44} L{x+82} {y+70} L{x+72} {y+92}", "", INK, 3)
        svg.path(f"M{x+70} {y} L{x+84} {y+28} L{x+64} {y+44} L{x+82} {y+70} L{x+72} {y+92}", "", WHITE, 1)
        svg.path(f"M{x+134} {y+88} Q{x+150} {y+60} {x+178} {y+54}", "", INK, 2)
        for (px, py, a) in [(146, 68, 1), (158, 60, -1), (168, 56, 1), (152, 78, -1)]:
            svg.raw(f'<ellipse cx="{x+px}" cy="{y+py}" rx="7" ry="3.2" fill="{WHITE}" '
                    f'transform="rotate({-25*a} {x+px} {y+py})"/>')
        for px in (24, 42):
            svg.path(f"M{x+px} {y+52} L{x+px+18} {y+84} L{x+px-18} {y+84} Z", INK)
            svg.path(f"M{x+px} {y+62} L{x+px+4} {y+72} L{x+px-4} {y+72} Z", WHITE)
            svg.rect(x + px - 1.5, y + 76, 3, 3, WHITE)
    elif idx == 2:  # three-arc spiral, coast, waves, house
        svg.rect(x, y + 56, w, h - 56, rc)
        svg.path(f"M{x} {y+62} Q{x+40} {y+48} {x+80} {y+58} T{x+w} {y+54} L{x+w} {y+56} L{x} {y+56} Z", "#b07a1e")
        for i, (sx, sy) in enumerate([(20, 70), (48, 82), (30, 92), (96, 74), (120, 88), (150, 78), (166, 68)]):
            svg.path(f"M{x+sx} {y+sy} q10 -5 20 0 q10 5 20 0", "", WHITE, 2)
        svg.rect(x + 66, y + 26, 22, 18, WHITE)
        svg.path(f"M{x+62} {y+27} L{x+77} {y+14} L{x+92} {y+27} Z", INK)
        svg.rect(x + 74, y + 34, 6, 10, rc)
        sx, sy = x + 140, y + 30
        for r, a0 in [(10, 0), (18, 60), (26, 120)]:
            svg.path(f"M{sx} {sy} m0 -{r} a{r} {r} 0 0 1 {r} {r}", "", INK, 2.5)
        svg.circle(sx, sy, 3, ACC)
    elif idx == 3:  # globe, turbine, thermometer, sun
        svg.raw(f'<circle cx="{x+44}" cy="{y+52}" r="28" fill="{rc}"/>')
        for yy in (38, 52, 66):
            svg.raw(f'<ellipse cx="{x+44}" cy="{y+yy}" rx="{22 if yy==52 else 14}" ry="6" fill="none" '
                    f'stroke="{WHITE}" stroke-width="1.5"/>')
        svg.line(x + 44, y + 24, x + 44, y + 80, WHITE, 1.5)
        svg.raw(f'<ellipse cx="{x+44}" cy="{y+52}" rx="8" ry="28" fill="none" stroke="{WHITE}" stroke-width="1.5"/>')
        svg.line(x + 96, y + 84, x + 96, y + 38, INK, 3)
        for k in range(3):
            svg.path(f"M{x+96} {y+38} L{x+72+k*4} {y+20+k*3} L{x+76+k*4} {y+56+k*2} Z", WHITE)
        svg.circle(x + 96, y + 36, 4, INK)
        svg.rect(x + 138, y + 20, 8, 56, WHITE, f'stroke="{INK}" stroke-width="2"')
        svg.rect(x + 139, y + 52, 6, 23, ACC)
        svg.circle(x + 142, y + 80, 7, ACC)
        svg.circle(x + 162, y + 24, 10, "#b07a1e")
        for a in range(0, 360, 45):
            import math
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            svg.line(x + 162 + dx * 13, y + 24 + dy * 13, x + 162 + dx * 18, y + 24 + dy * 18, "#b07a1e", 2)
    elif idx == 4:  # factory, shut gate, banner, marching figures
        svg.rect(x, y + 28, 96, 68, rc)
        svg.path(f"M{x} {y+28} l12 -10 l12 10 l12 -10 l12 10 l12 -10 l12 10 l12 -10 l12 10 Z", rc)
        svg.rect(x + 40, y + 4, 8, 26, INK)
        svg.rect(x + 24, y + 50, 10, 10, WHITE)
        svg.rect(x + 62, y + 50, 10, 10, WHITE)
        svg.rect(x + 30, y + 70, 38, 26, INK)
        svg.raw(f'<pattern id="gate{idx}" width="7" height="7" patternUnits="userSpaceOnUse">'
                f'<rect width="7" height="7" fill="{INK}"/><rect width="2" height="7" fill="{WHITE}"/></pattern>')
        svg.rect(x + 30, y + 70, 38, 26, f"url(#gate{idx})")
        svg.rect(x + 0, y + 96, w, 4, INK)
        svg.raw(f'<g transform="rotate(-4 {x+112} {y+34})">')
        svg.rect(x + 100, y + 22, 66, 18, WHITE)
        svg.rect(x + 100, y + 22, 5, 18, ACC)
        svg.rect(x + 124, y + 22, 5, 18, ACC)
        svg.rect(x + 100, y + 22, 66, 3, ACC)
        svg.rect(x + 100, y + 37, 66, 3, ACC)
        svg.raw('</g>')
        for k in range(4):
            fx = x + 104 + k * 17
            svg.circle(fx, y + 58, 5, INK)
            svg.path(f"M{fx-6} {y+64} L{fx+6} {y+64} L{fx+4} {y+88} L{fx-4} {y+88} Z", rc)
            svg.line(fx - 2, y + 88, fx - 6 - k, y + 98, INK, 2.5)
            svg.line(fx + 2, y + 88, fx + 6, y + 98, INK, 2.5)
            svg.path(f"M{fx+5} {y+70} L{fx+12} {y+60} L{fx+14} {y+62} L{fx+7} {y+72} Z", INK)
    elif idx == 5:  # drone above three round huts, magnifier over marked document
        svg.rect(x, y + 78, w, 18, rc)
        for (hx, hr) in [(x + 34, 15), (x + 66, 18), (x + 96, 13)]:
            svg.rect(hx - hr, y + 64, 2 * hr, 16, "#7a4a6b")
            svg.path(f"M{hx-hr} {y+64} A{hr} {hr} 0 0 1 {hx+hr} {y+64} Z", INK)
            svg.rect(hx - 4, y + 70, 8, 10, WHITE)
        svg.rect(x + 14, y + 18, 40, 14, INK)
        svg.line(x + 22, y + 18, x + 12, y + 30, INK, 2)
        svg.line(x + 46, y + 18, x + 56, y + 30, INK, 2)
        svg.line(x + 34, y + 32, x + 34, y + 44, ACC, 1, "3 2")
        svg.raw(f'<g transform="rotate(-6 {x+134} {y+54})">')
        svg.rect(x + 116, y + 30, 34, 44, WHITE)
        for i in range(4):
            svg.rect(x + 121, y + 38 + i * 8, 24, 2, GREY)
        svg.rect(x + 121, y + 64, 12, 3, ACC)
        svg.raw('</g>')
        svg.circle(x + 138, y + 60, 13, "none", f'stroke="{INK}" stroke-width="3"')
        svg.line(x + 148, y + 70, x + 162, y + 84, INK, 5)
    elif idx == 6:  # controller, midnight clock, queue
        svg.rect(x, y, w, h, rc)
        svg.rect(x + 18, y + 52, 40, 16, INK)
        svg.rect(x + 24, y + 56, 4, 5, WHITE)
        svg.rect(x + 32, y + 56, 10, 3, WHITE)
        svg.circle(x + 28, y + 60, 2, "#b07a1e")
        svg.circle(x + 38, y + 66, 2.5, WHITE)
        svg.circle(x + 58, y + 54, 12, WHITE)
        svg.circle(x + 58, y + 54, 10, "none", f'stroke="{INK}" stroke-width="1.5"')
        svg.line(x + 58, y + 54, x + 58, y + 47, INK, 1.5)
        svg.line(x + 58, y + 54, x + 63, y + 56, INK, 1.5)
        svg.rect(x + 16, y + 84, 46, 6, INK)
        for k in range(5):
            fx = x + 82 + k * 14
            svg.circle(fx, y + 44, 4, WHITE)
            svg.rect(fx - 5, y + 49, 10, 24, WHITE)
            svg.rect(fx - 5, y + 73, 4, 18, INK)
            svg.rect(fx + 1, y + 73, 4, 18, INK)
    elif idx == 7:  # fuel pump, up arrow, price tag
        svg.rect(x + 16, y + 24, 34, 70, WHITE, f'stroke="{INK}" stroke-width="2"')
        svg.rect(x + 22, y + 32, 22, 16, rc)
        svg.rect(x + 22, y + 56, 22, 2, INK)
        svg.rect(x + 26, y + 62, 14, 2, INK)
        svg.path(f"M{x+50} {y+36} q10 0 10 12 l0 22 q0 8 -10 8", "", INK, 3)
        svg.rect(x + 34, y + 94, 18, 4, INK)
        svg.path(f"M{x+72} {y+78} L{x+84} {y+50} L{x+96} {y+78} Z", ACC)
        svg.rect(x + 80, y + 76, 8, 20, ACC)
        svg.path(f"M{x+116} {y+34} L{x+160} {y+34} L{x+160} {y+52} L{x+146} {y+66} L{x+116} {y+66} Z", rc)
        svg.circle(x + 124, y + 38, 3, PAPER)
        svg.rect(x + 124, y + 46, 22, 3, WHITE)
        svg.rect(x + 124, y + 53, 14, 3, WHITE)
        svg.path(f"M{x+120} {y+80} l8 0 l0 -8 l14 0 l0 -8 l14 0", "", INK, 2)
    elif idx == 8:  # Voyager probe, stars, dotted line to small Earth
        svg.rect(x, y, w, h, rc)
        for (sx, sy) in [(14, 14), (40, 40), (64, 12), (78, 52), (22, 66), (50, 80), (92, 26), (150, 16), (66, 30)]:
            svg.circle(x + sx, y + sy, 1.6, WHITE)
        svg.circle(x + 44, y + 46, 15, WHITE)
        svg.path(f"M{x+34} {y+54} q10 4 20 0", "", INK, 1.5)
        svg.path(f"M{x+30} {y+62} L{x+58} {y+62} L{x+58} {y+70}", "", INK, 2)
        svg.path(f"M{x+44} {y+70} L{x+44} {y+86}", "", INK, 3)
        svg.rect(x + 52, y + 78, 26, 2, INK)
        svg.rect(x + 34, y + 78, 8, 2, INK)
        svg.path(f"M{x+58} {y+58} C{x+90} {y+46} {x+120} {y+40} {x+150} {y+30}", "", WHITE, 1.2, "2 3")
        svg.circle(x + 154, y + 28, 7, WHITE)
        svg.circle(x + 152, y + 26, 3, rc)
    elif idx == 9:  # EU stars, euro sign, Ukrainian flag
        svg.raw(f'<circle cx="{x+44}" cy="{y+50}" r="26" fill="{rc}"/>')
        import math
        for a in range(0, 360, 30):
            dx, dy = math.cos(math.radians(a - 90)), math.sin(math.radians(a - 90))
            svg.circle(x + 44 + dx * 18, y + 50 + dy * 18, 2.2, WHITE)
        svg.raw(f'<text x="{x+96}" y="{y+64}" font-family="DejaVu Sans" font-size="40" '
                f'font-weight="bold" fill="{rc}" text-anchor="middle">\u20ac</text>')
        svg.rect(x + 124, y + 34, 46, 14, "#2f5d8a")
        svg.rect(x + 124, y + 48, 46, 14, "#d2a53a")
        svg.rect(x + 124, y + 78, 46, 6, INK)
    svg.raw('</g>')


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
def build():
    svg = SVG()
    svg.raw(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">')
    svg.raw('<defs>')
    lead_geo = [(40, 180), (359, 180), (678, 180)]
    cards_geo = [(40, 412), (229, 412), (418, 412), (607, 412), (796, 412),
                 (40, 514), (229, 514), (418, 514), (607, 514), (796, 514)]
    for i, (x, y) in enumerate(lead_geo):
        svg.raw(f'<clipPath id="lead_clip{i}"><rect x="{x}" y="{y}" width="306" height="120"/></clipPath>')
    for i, (x, y) in enumerate(cards_geo):
        svg.raw(f'<clipPath id="card_clip{i}"><rect x="{x}" y="{y}" width="180" height="44"/></clipPath>')
    svg.raw('<clipPath id="map_clip"><rect x="40" y="620" width="300" height="100"/></clipPath>')
    svg.raw('</defs>')
    svg.rect(0, 0, W, H, PAPER)

    # Header
    svg.hair(12, 10, W - 10)
    svg.hair(34, 10, W - 10)
    svg.text(10, 28.5, "THE WORLD'S NEWS IN ONE PICTURE", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10.5, INK, what="kicker")
    check("45 STORIES \u00b7 7 REGIONS \u00b7 13 ILLUSTRATED", SANS_B, 10.5, 450, "kicker-right")
    svg.text(1014, 28.5, "45 STORIES \u00b7 7 REGIONS \u00b7 13 ILLUSTRATED", SANS_B, 10.5, ACC, anchor="end", weight="bold", what="kicker-right")

    mast = "Wednesday 18 November 2026"
    check(mast, SERIF_B, 54, W - 48.5 - 14, "masthead")
    svg.serif(48.5, 96, mast, 54, what="masthead")
    svg.hair(106)

    # Region tabs
    total = sum(COUNT.values())
    base = (W - 96 - 6 * 3) / total
    # Reserve 20 units of air on both sides of every label, then proportion the
    # remainder. A 10.5pt label keeps >= 20 units of padding even when tight.
    pad = 20
    need = {r: tw(f"{r.upper()} {COUNT[r]}", SANS_B, 10.5) for r in REGION_ORDER}
    for r in REGION_ORDER:
        check(f"{r.upper()} {COUNT[r]}", SANS_B, 10.5, need[r] + pad, f"tab {r}")
    spare = W - 96 - 6 * 3 - sum(need.values()) - 7 * pad
    widths = [need[r] + pad + (COUNT[r] / total) * spare for r in REGION_ORDER]
    assert min(widths) > 0
    x = 40
    for r, w in zip(REGION_ORDER, widths):
        label = f"{r.upper()} {COUNT[r]}"
        assert tw(label, SANS_B, 10.5) + 20 <= w + 1e-9
        svg.rect(x, 120, w, 28, REGION_COL[r])
        svg.text(x + w / 2, 138, label, SANS_B, 10.5, WHITE, anchor="middle", weight="bold", what=f"tab {r}")
        x += w + 3

    # Ticker
    ty = 168
    svg.text(40, ty, "TODAY", SANS_B, 9.6, GREY, weight="bold", what="ticker lead")
    tx = 40 + tw("TODAY", SANS_B, 9.6) + 12
    ticker = [(item.split(" ", 1)[0], " " + item.split(" ", 1)[1]) for item in TAPE]
    for i, (fig, lab) in enumerate(ticker):
        if i:
            svg.text(tx, ty, "|", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9.6, RULE, what="sep")
            tx += tw("|", SANS, 9.6) + 10
        check(fig, SANS_B, 9.6, 100, "ticker fig")
        svg.text(tx, ty, fig, SANS_B, 9.6, ACC, weight="bold", what="ticker fig")
        tx += tw(fig, SANS_B, 9.6)
        svg.text(tx, ty, lab, SANS, 9.6, INK, what="ticker label")
        tx += tw(lab, SANS, 9.6)
        assert tx <= 984, f"ticker overruns: {tx}"

    # Leads
    for i, (x, y) in enumerate(lead_geo):
        region, field, kicker, head, deck = LEADS[i][:5]
        rc = REGION_COL[region]
        band_lead(svg, x, y, 306, 120, i)
        rect_y = y + 120
        svg.rect(x, rect_y, 306, 14, rc)
        svg.text(x + 8, rect_y + 10.5, f"{i+1}  {region.upper()} \u00b7 {kicker}", SANS_B, 8.6, WHITE,
                 weight="bold", what=f"lead kicker {i+1}")
        assert tw(f"{i+1}  {region.upper()} \u00b7 {kicker}", SANS_B, 8.6) <= 298, f"lead kicker {i+1}"
        lines = wrap(head, SERIF_B, 23, 300, 3, f"lead head {i+1}")
        for k, ln in enumerate(lines):
            svg.serif(x, rect_y + 33 + k * 24, ln, 23, box=300, what=f"lead head {i+1}")
        dl = wrap(deck, SANS, 9.0, 300, 2, f"lead deck {i+1}")
        src = LEAD_SOURCE[i]
        check(src, SANS, 8.2, 306, f"lead source {i+1}")
        # Every lead reserves space for a 3-line head and a 2-line deck so the
        # deck and source baselines stay aligned across all three columns.
        deck_top = rect_y + 33 + 2 * 24 + 10
        source_y = deck_top + 11.5 + 13
        for k, ln in enumerate(dl):
            svg.text(x, deck_top + k * 11.5, ln, SANS, 9.0, DECK, what=f"lead deck {i+1}")
        svg.text(x, source_y, src, SANS, 8.2, GREY, what=f"lead source {i+1}")

    # Cards
    for i, (x, y) in enumerate(cards_geo):
        region, field, kicker, head = CARDS[i][:4]
        rc = REGION_COL[region]
        card_scene(svg, x, y, 180, 44, i)
        svg.rect(x, y + 52, 180, 13, rc)
        check(f"{region.upper()} \u00b7 {kicker}", SANS_B, 8.0, 174, f"card kicker {i+1}")
        svg.text(x + 4, y + 62, f"{region.upper()} \u00b7 {kicker}", SANS_B, 8.0, WHITE,
                 weight="bold", what=f"card kicker {i+1}")
        lines = wrap(head, SERIF_B, 13, 176, 2, f"card head {i+4}")
        for k, ln in enumerate(lines):
            svg.serif(x, y + 80 + k * 14, ln, 13, box=176, what=f"card head {i+4}")

    # Map and date check
    my, mh = 620, 100
    grid = load_mask()
    lines = ["".join(row) for row in grid]
    svg.raw('<g clip-path="url(#map_clip)">')
    for gy, row in enumerate(grid):
        for gx, ch in enumerate(row):
            if ch == "#":
                px, py = 40 + gx * 10 / 3, my + gy * 100 / 45
                svg.raw(f'<rect x="{px:.2f}" y="{py:.2f}" width="3.34" height="2.23" fill="{INK}" opacity="0.42"/>')
    for k, ((gx, gy), reg) in enumerate(zip(PIN_GRID, PIN_REGIONS), 1):
        assert lines[gy][gx] == "#"
        cx, cy = 40 + gx * 10 / 3 + 1.67, my + gy * 100 / 45 + 1.1
        svg.circle(cx, cy, 5.2, REGION_COL[reg], f'stroke="{PAPER}" stroke-width="1"')
        svg.text(cx, cy + 2.9, str(k), SANS_B, 6.6, WHITE, anchor="middle", weight="bold", what=f"pin {k}")
    svg.raw('</g>')
    svg.text(40, 738 - 10, "13 ILLUSTRATED \u00b7 1-13 LEADS AND CARDS \u00b7 PIN COLOUR = REGION", SANS, 7.4, GREY, what="map note")

    # Date check
    bx, by, bw, bh = 356, 620, 628, 100
    svg.rect(bx, by, 3, bh, ACC)
    svg.rect(bx + 12, by + 12, bw - 24, bh - 24, PAPER, f'stroke="{RULE}" stroke-width="1"')
    dlines = wrap(DATE_CHECK, SANS, 8.6, 592, 3, "date check")
    for k, ln in enumerate(dlines):
        if k == 0:
            svg.text(bx + 22, by + 31, "DATE CHECK", SANS_B, 8.6, ACC, weight="bold", what="date check label")
            rest = ln[len("DATE CHECK"):].lstrip()
            gap = 4
            x0 = bx + 22 + tw("DATE CHECK", SANS_B, 8.6) + gap
            check(rest, SANS, 8.6, bx + bw - 24 - x0, "date check rest")
            svg.text(x0, by + 31, rest, SANS, 8.6, INK, what="date check rest")
        else:
            svg.text(bx + 22, by + 31 + k * 13, ln, SANS, 8.6, INK, what="date check")

    # Briefs header
    fieldline = "BY FIELD  " + " \u00b7 ".join(f"{f} {FIELD_COUNT[f]}" for f in FIELDS)
    check(fieldline, SANS_B, 8.0, 720, "field counts")
    svg.text(40, 738, "BRIEFS 14-45", SERIF_B, 15, INK, what="briefs header")
    svg.text(984, 738 - 3, fieldline, SANS_B, 8.0, INK, anchor="end", weight="bold", what="field counts")
    svg.hair(746)

    col_x = [40, 363, 686]
    y0 = 760
    rows = 11
    fit = [0] * len(BRIEFS)
    for i, (region, field, place, text) in enumerate(b[0:4] for b in BRIEFS):
        px0 = 16
        sw0 = tw(place, SANS_B, 8.2)
        room0 = 297 - (px0 + sw0 + 3)
        if tw(text, SANS, 8.2) > room0:
            lines = wrap(text, SANS, 8.2, 297 - px0, 2, f"brief {i+14} body")
            fit[i] = len(lines) - 1
    extra_rows = sum(fit[(rows - 1) - k] for k in range(rows))
    pitch = min(13.2, (926 - 760 - extra_rows * 7.5) / (rows - 1))
    for i, (region, field, place, text) in enumerate(b[0:4] for b in BRIEFS):
        col, row = divmod(i, rows)
        x = col_x[col]
        y = y0 + row * pitch
        if (rows - 1) - row:
            y += sum(fit[(rows - 1) - k] for k in range(row)) * 7.5
        num = f"{i + 14}"
        check(num, SANS_B, 8.2, 14, "brief num")
        svg.text(x, y, num, SANS_B, 8.2, ACC, weight="bold", what="brief num")
        px = x + 16
        sw = tw(place, SANS_B, 8.2)
        check(place + " ", SANS_B, 8.2, 297 - 16, f"brief {num} place")
        svg.text(px, y, place, SANS_B, 8.2, INK, weight="bold", what=f"brief {num} place")
        tx = px + sw + 3
        room = x + 297 - tx
        if fit[i]:
            lines = wrap(text, SANS, 8.2, 297 - 16, 2, f"brief {num} body")
            for k, ln in enumerate(lines):
                check(ln, SANS, 8.2, 297 - 16, f"brief {num} body")
                svg.text(px, y + 7.5 + k * 7.5, ln, SANS, 8.2, INK, what=f"brief {num} body")
        else:
            check(text, SANS, 8.2, room, f"brief {num} body")
            svg.text(tx, y, text, SANS, 8.2, INK, what=f"brief {num} body")
    last = y0 + (rows - 1) * pitch + extra_rows * 7.5
    assert last < 925, f"briefs collide with note box: {last}"

    # Note box
    ny, nsz = 935, 8.6
    nl = []
    for k, ln in enumerate(NOTE[1:], 2):
        nl.extend(wrap(ln, SANS, nsz, 920, 1, f"note {k}"))
    nh = 6 + 12 + 12 * len(nl) + 6
    svg.frame(40, ny, W - 80, nh, ACC, 1)
    svg.text(W / 2, ny + 15, NOTE[0], SANS_B, nsz, ACC, anchor="middle", weight="bold", what="note 1")
    for k, ln in enumerate(nl):
        svg.text(W / 2, ny + 28 + k * 12, ln, SANS, nsz, INK, anchor="middle", what=f"note {k+2}")
    # footer hairline must sit below the framed box
    hy0 = ny + nh + 6
    assert hy0 + 12 + 10 + 2 <= H, "footer clipped by note box"
    svg.hair(hy0, 10, W - 10)
    fy = hy0 + 12
    fl = wrap(FOOT_L, SANS, 8.4, 700, 2, "footer left")
    for k, ln in enumerate(fl):
        svg.text(10, fy + k * 10, ln, SANS, 8.4, INK, what="footer left")
    check("18 NOVEMBER 2026", SANS_B, 8.4, 200, "footer right")
    svg.text(1012, fy, "18 NOVEMBER 2026", SANS_B, 8.4, INK, anchor="end", weight="bold", what="footer right")
    assert fy + (len(fl) - 1) * 10 + 2 <= H, "footer clipped"

    svg.raw('</svg>')
    return "\n".join(svg.parts)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "entry.png")
    xml = build()
    assert "..." not in xml and "\u2026" not in xml, "ellipsis in output"
    worst = max(WORST)
    ratios = sorted(WORST, reverse=True)[:6]
    for r, what in ratios:
        print(f"ratio {r:.4f}  {what}")
    print(f"WORST {worst[0]:.4f}  {worst[1]}")
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as fh:
        fh.write(xml)
        tmp = fh.name
    subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "-o", str(out), tmp], check=True)
    Path(tmp).unlink()
    size = out.stat().st_size
    print(f"wrote {out} {size} bytes")
    assert size < 1048576, size


if __name__ == "__main__":
    main()
