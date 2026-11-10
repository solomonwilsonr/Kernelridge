"""Generate the animated blueprint-style README illustrations.

Each illustration is a self-contained SVG: an isometric line drawing on a
drafting grid, four callouts on diagonal leader lines, and CSS/SMIL
animation (leader lines draw in, labels fade up, then ambient motion loops).
No third-party dependencies; run from the repository root:

    python assets/diagrams/generate.py
"""

from __future__ import annotations

import math
from pathlib import Path

W, H = 1024, 640
CX, CY = 512, 330

INK = "#2c2c2a"
SOFT = "#8f8c82"
SAGE = "#9aae8c"
PAPER = "#f8f6ef"
GRID = "#e7e3d7"
DOT = "#d6d1c1"
FACE_TOP = "#fdfcf8"
FACE_LEFT = "#f2efe6"
FACE_RIGHT = "#e8e4d8"
AMBER = "#d9a441"
RED = "#c4675a"
GREY = "#a9a69c"

OUT = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# isometric helpers
# --------------------------------------------------------------------------

class Iso:
    def __init__(self, s: float, ox: float = CX, oy: float = CY):
        self.s, self.ox, self.oy = s, ox, oy

    def p(self, x: float, y: float, z: float) -> tuple[float, float]:
        s = self.s
        return (
            self.ox + (x - y) * 0.866 * s,
            self.oy + (x + y) * 0.5 * s - z * s,
        )

    def pts(self, *xyz: tuple[float, float, float]) -> str:
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in (self.p(*q) for q in xyz))

    def box(self, x, y, z, dx, dy, dz, cls="solid", hidden=True) -> str:
        """Isometric box: top, front-left (y+dy) and front-right (x+dx) faces."""
        x1, y1, z1 = x + dx, y + dy, z + dz
        top = self.pts((x, y, z1), (x1, y, z1), (x1, y1, z1), (x, y1, z1))
        left = self.pts((x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1))
        right = self.pts((x1, y, z), (x1, y1, z), (x1, y1, z1), (x1, y, z1))
        out = []
        if hidden:
            # hidden back edges, drawn as construction dashes
            a, b, c = self.p(x, y, z), self.p(x1, y, z), self.p(x, y1, z)
            d = self.p(x, y, z1)
            for q in (b, c, d):
                out.append(
                    f'<line class="hidden" x1="{a[0]:.1f}" y1="{a[1]:.1f}" '
                    f'x2="{q[0]:.1f}" y2="{q[1]:.1f}"/>'
                )
        out += [
            f'<polygon class="{cls} top" points="{top}"/>',
            f'<polygon class="{cls} left" points="{left}"/>',
            f'<polygon class="{cls} right" points="{right}"/>',
        ]
        return "\n".join(out)

    def face_left(self, x, y, z) -> str:
        """SVG matrix mapping local (u right, v up) onto the y=const face."""
        s = self.s
        ex, ey = self.p(x, y, z)
        return f"matrix({0.866*s:.3f},{0.5*s:.3f},0,{-s:.3f},{ex:.1f},{ey:.1f})"

    def face_right(self, x, y, z) -> str:
        """SVG matrix mapping local (u right, v up) onto the x=const face.

        (x, y, z) is the face's front-left corner; u runs toward -y.
        """
        s = self.s
        ex, ey = self.p(x, y, z)
        return f"matrix({0.866*s:.3f},{-0.5*s:.3f},0,{-s:.3f},{ex:.1f},{ey:.1f})"

    def face_top(self, x, y, z) -> str:
        """SVG matrix mapping local (u along +x, v along +y) onto z=const."""
        s = self.s
        ex, ey = self.p(x, y, z)
        return (
            f"matrix({0.866*s:.3f},{0.5*s:.3f},{-0.866*s:.3f},{0.5*s:.3f},"
            f"{ex:.1f},{ey:.1f})"
        )


# --------------------------------------------------------------------------
# shared drafting-sheet scaffold
# --------------------------------------------------------------------------

BASE_CSS = f"""
text {{ font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        fill: {INK}; font-size: 21px; letter-spacing: .1px; }}
.mono {{ font-family: "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace;
         font-size: 15px; fill: {SOFT}; }}
.solid {{ stroke: {INK}; stroke-width: 1.4; stroke-linejoin: round; }}
.top {{ fill: {FACE_TOP}; }} .left {{ fill: {FACE_LEFT}; }} .right {{ fill: {FACE_RIGHT}; }}
.wire {{ fill: none; stroke: {INK}; stroke-width: 1.3; stroke-linejoin: round; }}
.thin {{ fill: none; stroke: {INK}; stroke-width: .9; }}
.hidden {{ stroke: {SOFT}; stroke-width: .8; stroke-dasharray: 3 4; }}
.cons {{ stroke: {SOFT}; stroke-width: .9; fill: none; }}
.dash {{ stroke: {SOFT}; stroke-width: .8; stroke-dasharray: 2 5; fill: none; }}
.node {{ fill: {SAGE}; }}
.ring {{ fill: {PAPER}; stroke: {INK}; stroke-width: 1.3; }}

.lead {{ fill: none; stroke: {INK}; stroke-width: 1.2;
         stroke-dasharray: 1; stroke-dashoffset: 1;
         animation: draw 1.1s cubic-bezier(.6,0,.2,1) forwards; }}
.fade {{ opacity: 0; animation: fade .7s ease-out forwards; }}
.rise {{ opacity: 0; animation: rise .8s ease-out forwards; }}
.obj  {{ opacity: 0; animation: fade 1s ease-out .1s forwards; }}
.float {{ animation: float 6s ease-in-out 1.2s infinite; }}
.pulse {{ transform-box: fill-box; transform-origin: center;
          animation: pulse 3.2s ease-in-out infinite; }}

@keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
@keyframes fade {{ to {{ opacity: 1; }} }}
@keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }}
                   to {{ opacity: 1; transform: none; }} }}
@keyframes float {{ 0%,100% {{ transform: translateY(0); }}
                    50% {{ transform: translateY(-5px); }} }}
@keyframes pulse {{ 0%,100% {{ transform: scale(1); opacity: .85; }}
                    50% {{ transform: scale(1.6); opacity: .35; }} }}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation-duration: 1ms !important; animation-iteration-count: 1 !important;
       animation-delay: 0s !important; }}
}}
"""


def grid() -> str:
    return f"""
<defs>
  <pattern id="dots" width="32" height="32" patternUnits="userSpaceOnUse">
    <circle cx="16" cy="16" r="1" fill="{DOT}"/>
  </pattern>
  <pattern id="grid" width="128" height="128" patternUnits="userSpaceOnUse" x="0" y="10">
    <path d="M128 0H0V128" fill="none" stroke="{GRID}" stroke-width="1"/>
  </pattern>
</defs>
<rect width="{W}" height="{H}" fill="{PAPER}"/>
<rect width="{W}" height="{H}" fill="url(#dots)"/>
<rect width="{W}" height="{H}" fill="url(#grid)"/>
"""


def construction() -> str:
    """Frame lines, axis and sage nodes echoing a drafting layout."""
    L, R, T, B = 300, 724, 196, 470
    parts = [
        # horizontal axis with inward arrows
        f'<line class="cons" x1="10" y1="{CY}" x2="{L-14}" y2="{CY}"/>',
        f'<line class="cons" x1="{R+14}" y1="{CY}" x2="{W-10}" y2="{CY}"/>',
        f'<path class="cons" d="M{L-24} {CY-5} L{L-14} {CY} L{L-24} {CY+5}"/>',
        f'<path class="cons" d="M{R+24} {CY-5} L{R+14} {CY} L{R+24} {CY+5}"/>',
        # frame top and bottom
        f'<line class="cons" x1="{L}" y1="{T}" x2="{R}" y2="{T}"/>',
        f'<line class="cons" x1="{L}" y1="{B}" x2="{R}" y2="{B}"/>',
        # verticals
        f'<line class="cons" x1="200" y1="{T+60}" x2="200" y2="{B+60}"/>',
        f'<line class="cons" x1="{W-200}" y1="{T}" x2="{W-200}" y2="{B}"/>',
        f'<line class="cons" x1="{L+96}" y1="{T}" x2="{L+96}" y2="{T+60}"/>',
        f'<line class="cons" x1="{R-96}" y1="{B-60}" x2="{R-96}" y2="{B}"/>',
    ]
    nodes = [
        (10, CY), (W - 10, CY), (200, CY), (W - 200, CY),
        (L, T), (L + 96, T), (R, T), (W - 200, T),
        (L, B), (R - 96, B), (R, B), (200, B), (200, B + 60),
    ]
    for i, (x, y) in enumerate(nodes):
        delay = 1.4 + (i % 5) * 0.55
        parts.append(
            f'<circle class="node pulse" cx="{x}" cy="{y}" r="4.5" '
            f'style="animation-delay:{delay:.2f}s"/>'
        )
    parts.append(f'<circle cx="{CX - 20}" cy="{T}" r="2.4" fill="{INK}"/>')
    return f'<g class="fade" style="animation-delay:.05s">{"".join(parts)}</g>'


# corner callout geometry: (start near object) -> (ring)
CALLOUTS = {
    "tl": ((392, 250), (150, 98)),
    "tr": ((632, 250), (874, 98)),
    "bl": ((392, 418), (150, 548)),
    "br": ((632, 418), (874, 548)),
}


def callout(corner: str, lines: list[str], delay: float, swatch: str | None = None) -> str:
    (x1, y1), (x2, y2) = CALLOUTS[corner]
    ang = math.atan2(y2 - y1, x2 - x1)
    r = 7.5
    ex, ey = x2 - math.cos(ang) * r, y2 - math.sin(ang) * r
    # arrowhead just before the ring
    ah = 11
    a1 = (ex - ah * math.cos(ang - 0.38), ey - ah * math.sin(ang - 0.38))
    a2 = (ex - ah * math.cos(ang + 0.38), ey - ah * math.sin(ang + 0.38))
    mid = ((x1 + x2) / 2, (y1 + y2) / 2)

    top = corner[0] == "t"
    left = corner[1] == "l"
    anchor = "start" if left else "end"
    tx = x2 - 70 if left else x2 + 70
    tx = max(tx, 48) if left else min(tx, W - 48)
    lh = 25
    if top:
        ty0 = y2 - 22 - lh * (len(lines) - 1)
    else:
        ty0 = y2 + 38
    spans = "".join(
        f'<tspan x="{tx}" y="{ty0 + i * lh}">{t}</tspan>' for i, t in enumerate(lines)
    )
    sw = ""
    if swatch:
        # swatch sits on the outer side of the first line, so no text metrics needed
        sx = tx - 22 if left else tx + 10
        sw = f'<rect x="{sx}" y="{ty0 - 15}" width="12" height="12" rx="2" fill="{swatch}" class="swatch"/>'
    return f"""
<g>
  <path class="lead" pathLength="1" style="animation-delay:{delay:.2f}s"
        d="M{x1} {y1} L{ex:.1f} {ey:.1f}"/>
  <circle class="node" cx="{mid[0]:.1f}" cy="{mid[1]:.1f}" r="4.5"/>
  <g class="fade" style="animation-delay:{delay + .9:.2f}s">
    <path class="thin" d="M{a1[0]:.1f} {a1[1]:.1f} L{ex:.1f} {ey:.1f} L{a2[0]:.1f} {a2[1]:.1f}"/>
    <circle class="ring" cx="{x2}" cy="{y2}" r="{r}"/>
  </g>
  <g class="rise" style="animation-delay:{delay + 1.0:.2f}s">
    {sw}<text text-anchor="{anchor}">{spans}</text>
  </g>
  <circle r="3" fill="{SAGE}" opacity="0">
    <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.85;1"
             dur="3.6s" begin="{delay + 2:.1f}s" repeatCount="indefinite"/>
    <animateMotion dur="3.6s" begin="{delay + 2:.1f}s" repeatCount="indefinite"
                   path="M{x2} {y2} L{x1} {y1}" keyPoints="0;1;1" keyTimes="0;.7;1"
                   calcMode="linear"/>
  </circle>
</g>"""


def sheet(title: str, desc: str, obj: str, callouts: str, css: str = "", caption: str = "") -> str:
    cap = ""
    if caption:
        cap = (
            f'<text class="mono fade" style="animation-delay:.4s" x="{CX}" '
            f'y="38" text-anchor="middle">{caption}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">{title}</title>
<desc id="d">{desc}</desc>
<style>{BASE_CSS}{css}</style>
{grid()}
{construction()}
<g class="obj"><g class="float">
{obj}
</g></g>
{callouts}
{cap}
</svg>
"""


# --------------------------------------------------------------------------
# 1. preflight: an isometric RISC-V chip on a board
# --------------------------------------------------------------------------

def preflight() -> str:
    iso = Iso(20, CX, CY - 60)
    parts = [iso.box(0, 0, 0, 10, 10, 0.5)]
    # traces on the board
    for i in range(4):
        y = 1.2 + i * 0.6
        parts.append(f'<polyline class="thin trace" points="{iso.pts((0.4, y, .5), (2.4, y, .5))}"/>')
        parts.append(f'<polyline class="thin trace" points="{iso.pts((7.6, 10 - y, .5), (9.6, 10 - y, .5))}"/>')
    # pins along the two visible chip edges
    for i in range(7):
        t = 2.9 + i * 0.7
        parts.append(f'<polyline class="thin" points="{iso.pts((t, 7.5, .5), (t, 8.2, .5))}"/>')
        parts.append(f'<polyline class="thin" points="{iso.pts((7.5, t, .5), (8.2, t, .5))}"/>')
        parts.append(f'<polyline class="hidden" points="{iso.pts((t, 2.5, .5), (t, 1.8, .5))}"/>')
    parts.append(iso.box(2.5, 2.5, 0.5, 5, 5, 1.0, hidden=False))
    # die markings on the chip top
    m = iso.face_top(2.5, 2.5, 1.5)
    parts.append(f"""
<g transform="{m}">
  <rect x=".7" y=".7" width="3.6" height="3.6" fill="none" stroke="{INK}" stroke-width="1" vector-effect="non-scaling-stroke"/>
  <rect class="die" x=".7" y=".7" width="3.6" height="3.6" fill="{SAGE}"/>
  <circle cx="1.15" cy="1.15" r=".16" fill="{INK}"/>
  <text x="2.5" y="2.55" text-anchor="middle" style="font-size:.95px;font-weight:600;letter-spacing:.04px">RV64</text>
  <text x="2.5" y="3.35" text-anchor="middle" style="font-size:.5px;fill:{SOFT}">imafdc · lp64d</text>
</g>""")
    # missing "v" slot: a dashed empty socket on the board
    parts.append(f'<polygon class="vslot" points="{iso.pts((0.8, 7.2, .5), (2.0, 7.2, .5), (2.0, 8.4, .5), (0.8, 8.4, .5))}"/>')
    vx, vy = iso.p(1.4, 7.8, .5)
    parts.append(f'<text class="vmark" x="{vx:.1f}" y="{vy + 5:.1f}" text-anchor="middle" style="font-size:13px;font-weight:600">v</text>')
    css = f"""
.die {{ opacity: 0; animation: die 4s ease-in-out 2s infinite; }}
@keyframes die {{ 0%,100% {{ opacity: 0; }} 40%,60% {{ opacity: .28; }} }}
.vslot {{ fill: none; stroke: {RED}; stroke-width: 1.3; stroke-dasharray: 3 3;
          animation: blink 2s steps(1) 3s infinite; }}
.vmark {{ fill: {RED}; animation: blink 2s steps(1) 3s infinite; }}
@keyframes blink {{ 50% {{ opacity: .15; }} }}
.trace {{ stroke: {SOFT}; stroke-dasharray: 4 3; animation: flow 1.4s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -14; }} }}
"""
    co = (
        callout("tl", ["riscv64 / lp64d"], 0.5)
        + callout("tr", ["requires: i m v"], 0.8)
        + callout("bl", ["glibc 2.38", "exact match"], 1.1)
        + callout("br", ["FAIL before", "it ships"], 1.4)
    )
    return sheet(
        "Kernelridge preflight",
        "An isometric RISC-V chip on a board. The release requires the vector "
        "extension, which the target lacks, so preflight reports FAIL before deploy.",
        "\n".join(parts), co, css, "kernelridge preflight --target --release",
    )


# --------------------------------------------------------------------------
# 2. verdicts: a wireframe inspection frame scanning a release artifact
# --------------------------------------------------------------------------

def verdicts() -> str:
    iso = Iso(15, CX, CY - 10)
    x0, y0, z0, d, h = 0, 0, -3, 10, 10
    P = lambda x, y, z: iso.p(x, y, z)
    # wireframe cube edges
    back = [((x0, y0, z0), (x0 + d, y0, z0)), ((x0, y0, z0), (x0, y0 + d, z0)),
            ((x0, y0, z0), (x0, y0, z0 + h))]
    front = [
        ((x0 + d, y0, z0), (x0 + d, y0 + d, z0)), ((x0, y0 + d, z0), (x0 + d, y0 + d, z0)),
        ((x0 + d, y0, z0), (x0 + d, y0, z0 + h)), ((x0, y0 + d, z0), (x0, y0 + d, z0 + h)),
        ((x0 + d, y0 + d, z0), (x0 + d, y0 + d, z0 + h)),
        ((x0, y0, z0 + h), (x0 + d, y0, z0 + h)), ((x0, y0, z0 + h), (x0, y0 + d, z0 + h)),
        ((x0 + d, y0, z0 + h), (x0 + d, y0 + d, z0 + h)), ((x0, y0 + d, z0 + h), (x0 + d, y0 + d, z0 + h)),
    ]
    parts = []
    for a, b in back:
        pa, pb = P(*a), P(*b)
        parts.append(f'<line class="hidden" x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}"/>')
    # artifact inside: a small package box
    parts.append(iso.box(3, 3, z0, 4, 4, 4.2, hidden=False))
    m = iso.face_left(3, 7, z0)
    parts.append(f'<g transform="{m}"><path d="M0 3.2 H4 M2 4.2 V3.2" fill="none" stroke="{INK}" stroke-width="1" vector-effect="non-scaling-stroke"/></g>')
    m = iso.face_top(3, 3, z0 + 4.2)
    parts.append(f'<g transform="{m}"><path d="M2 0 V4" fill="none" stroke="{INK}" stroke-width="1" vector-effect="non-scaling-stroke"/></g>')
    # scanning plane
    plane = iso.pts((x0, y0, z0), (x0 + d, y0, z0), (x0 + d, y0 + d, z0), (x0, y0 + d, z0))
    parts.append(f'<g class="scan"><polygon points="{plane}" fill="{SAGE}" fill-opacity=".22" stroke="{SAGE}" stroke-width="1.6"/></g>')
    for a, b in front:
        pa, pb = P(*a), P(*b)
        parts.append(f'<line class="wire" x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}"/>')
    # corner brackets
    for c in [(x0 + d, y0 + d, z0 + h), (x0, y0 + d, z0 + h), (x0 + d, y0, z0 + h), (x0 + d, y0 + d, z0)]:
        px, py = P(*c)
        parts.append(f'<rect x="{px - 4:.1f}" y="{py - 4:.1f}" width="8" height="8" fill="{PAPER}" stroke="{INK}" stroke-width="1.1"/>')
    span = h * iso.s
    css = f"""
.scan {{ animation: scan 4.8s ease-in-out 1.6s infinite; }}
@keyframes scan {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-{span:.0f}px); }} }}
.swatch {{ transform-box: fill-box; transform-origin: center; animation: tick 6s ease-in-out infinite; }}
@keyframes tick {{ 0%,20%,100% {{ transform: scale(1); }} 8% {{ transform: scale(1.45); }} }}
"""
    co = (
        callout("tl", ["PASS", "runtime check only"], 0.5, SAGE)
        + callout("tr", ["REVIEW", "static match"], 0.8, AMBER)
        + callout("bl", ["UNKNOWN", "not in inventory"], 1.1, GREY)
        + callout("br", ["FAIL", "mismatch named"], 1.4, RED)
    )
    # stagger the swatch ticks
    co = co.replace('class="swatch"', 'class="swatch" style="animation-delay:{}s"', 4)
    for i, dl in enumerate((3.0, 4.5, 6.0, 7.5)):
        co = co.replace('animation-delay:{}s', f"animation-delay:{dl}s", 1)
    return sheet(
        "Kernelridge verdicts",
        "A release artifact inside a wireframe inspection frame with a scan "
        "plane. Four outcomes: PASS only from a runtime check, REVIEW for a "
        "static match, UNKNOWN for missing inventory, FAIL for a named mismatch.",
        "\n".join(parts), co, css, "no optimistic PASS",
    )


# --------------------------------------------------------------------------
# 3. invalidation: stacked evidence slabs; a change propagates downward
# --------------------------------------------------------------------------

def invalidation() -> str:
    iso = Iso(15, CX, CY - 10)
    parts = []
    levels = [(5.4, "rev"), (2.4, "e1"), (-0.6, "e2"), (-3.6, "e3")]
    for i, (z, tag) in enumerate(reversed(levels)):
        idx = len(levels) - 1 - i
        x = 1 if idx else 0
        dd = 8 if idx else 10
        parts.append(f'<g class="slab s{idx}">')
        parts.append(iso.box(x, x, z, dd, dd, 1.0, cls="solid", hidden=False))
        m = iso.face_left(x, x + dd, z)
        parts.append(
            f'<g transform="{m}"><text x=".5" y="-.3" transform="scale(1,-1)" '
            f'style="font-size:.62px;fill:{SOFT}">{"revision" if idx == 0 else "evidence " + tag}</text></g>'
        )
        parts.append("</g>")
        if idx:
            # depends_on links to the slab above
            for u in (3, 7):
                a, b = iso.p(u, 9, z + 1.0), iso.p(u, 9, levels[idx - 1][0])
                parts.append(f'<line class="dep d{idx}" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')
    # draw order: bottom slab first so upper slabs overlap correctly
    css = f"""
.dep {{ stroke: {INK}; stroke-width: 1.1; stroke-dasharray: 3 3; animation: flow 1.2s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -12; }} }}
.slab .top {{ animation: stale-t 7s ease-in-out infinite; }}
.slab .left {{ animation: stale-l 7s ease-in-out infinite; }}
.slab .right {{ animation: stale-r 7s ease-in-out infinite; }}
.s0 polygon {{ animation-name: changed !important; animation-delay: 2.0s; }}
.s1 polygon {{ animation-delay: 2.9s; }}
.s2 polygon {{ animation-delay: 3.8s; }}
.s3 polygon {{ animation-delay: 4.7s; }}
@keyframes changed {{ 0%,4%,70%,100% {{ fill: {FACE_TOP}; }} 12%,55% {{ fill: #efc9bf; }} }}
@keyframes stale-t {{ 0%,4%,58%,100% {{ fill: {FACE_TOP}; }} 12%,45% {{ fill: #f6e3b8; }} }}
@keyframes stale-l {{ 0%,4%,58%,100% {{ fill: {FACE_LEFT}; }} 12%,45% {{ fill: #efd8a5; }} }}
@keyframes stale-r {{ 0%,4%,58%,100% {{ fill: {FACE_RIGHT}; }} 12%,45% {{ fill: #e6cc92; }} }}
"""
    co = (
        callout("tl", ["revision changed"], 0.5)
        + callout("tr", ["depends_on", "to a fixpoint"], 0.8)
        + callout("bl", ["incomplete deps", "→ revalidate"], 1.1)
        + callout("br", ["stale evidence", "flagged, not reused"], 1.4)
    )
    return sheet(
        "Kernelridge invalidation",
        "A revision slab above three stacked evidence slabs linked by "
        "depends_on edges; a change highlights each dependent slab in turn.",
        "\n".join(parts), co, css, "kernelridge invalidate --before --after --evidence",
    )


# --------------------------------------------------------------------------
# 4. attestation: a safe holding the signed report digest
# --------------------------------------------------------------------------

def attestation() -> str:
    iso = Iso(16, CX, CY - 20)
    parts = []
    # feet
    for fx, fy in ((0.4, 9.0), (9.0, 9.0), (9.0, 0.4)):
        parts.append(iso.box(fx, fy, -0.6, 0.6, 0.6, 0.6, hidden=False))
    parts.append(iso.box(0, 0, 0, 10, 10, 9))
    # door on the front-left face (local u: 0..10, v: 0..9)
    m = iso.face_left(0, 10, 0)
    ns = 'vector-effect="non-scaling-stroke"'
    ticks = "".join(
        f'<line x1="{4.6 + 1.35*math.cos(a):.3f}" y1="{4.5 + 1.35*math.sin(a):.3f}" '
        f'x2="{4.6 + 1.55*math.cos(a):.3f}" y2="{4.5 + 1.55*math.sin(a):.3f}" stroke="{INK}" stroke-width=".8" {ns}/>'
        for a in (i * math.pi / 12 for i in range(24))
    )
    parts.append(f"""
<g transform="{m}">
  <rect x=".7" y=".7" width="8.4" height="7.6" fill="none" stroke="{INK}" stroke-width="1.3" {ns}/>
  <rect x="1.1" y="1.1" width="7.6" height="6.8" fill="none" stroke="{SOFT}" stroke-width=".8" stroke-dasharray="3 4" {ns}/>
  <line x1="4.6" y1="1.1" x2="4.6" y2="7.9" stroke="{SOFT}" stroke-width=".7" stroke-dasharray="2 5" {ns}/>
  <line x1="1.1" y1="4.5" x2="8.7" y2="4.5" stroke="{SOFT}" stroke-width=".7" stroke-dasharray="2 5" {ns}/>
  {ticks}
  <circle cx="4.6" cy="4.5" r="1.25" fill="{FACE_TOP}" stroke="{INK}" stroke-width="1.2" {ns}/>
  <g>
    <animateTransform attributeName="transform" type="rotate" dur="7s" begin="1.8s"
      repeatCount="indefinite" values="0 4.6 4.5;95 4.6 4.5;95 4.6 4.5;-60 4.6 4.5;-60 4.6 4.5;30 4.6 4.5;30 4.6 4.5;0 4.6 4.5"
      keyTimes="0;.15;.25;.42;.52;.66;.8;1" calcMode="spline"
      keySplines=".5 0 .2 1;0 0 1 1;.5 0 .2 1;0 0 1 1;.5 0 .2 1;0 0 1 1;.5 0 .2 1"/>
    <circle cx="4.6" cy="4.5" r=".8" fill="{FACE_LEFT}" stroke="{INK}" stroke-width="1" {ns}/>
    <line x1="4.6" y1="4.5" x2="4.6" y2="5.25" stroke="{INK}" stroke-width="1.4" {ns}/>
    <circle cx="4.6" cy="4.5" r=".18" fill="{INK}"/>
  </g>
  <rect x="8.85" y="5.6" width=".45" height="1.3" rx=".1" fill="{FACE_TOP}" stroke="{INK}" stroke-width="1" {ns}/>
  <rect x="8.85" y="2.1" width=".45" height="1.3" rx=".1" fill="{FACE_TOP}" stroke="{INK}" stroke-width="1" {ns}/>
  <circle class="lock" cx="7.6" cy="7.3" r=".22" fill="{SAGE}"/>
</g>""")
    # digest plate on the right face
    m = iso.face_right(10, 10, 0)
    parts.append(f"""
<g transform="{m}">
  <rect x="1.6" y="5.2" width="6.8" height="1.6" fill="none" stroke="{INK}" stroke-width=".9" {ns}/>
  <g transform="translate(2.0 5.8) scale(1,-1)"><text style="font-size:.5px;font-family:Menlo,Consolas,monospace;fill:{SOFT}">sha256:9f2c…e41a</text></g>
  <line x1="2.2" y1="1.2" x2="7.8" y2="1.2" stroke="{SOFT}" stroke-width=".7" stroke-dasharray="2 5" {ns}/>
</g>""")
    css = f"""
.lock {{ animation: lock 7s ease-in-out 1.8s infinite; }}
@keyframes lock {{ 0%,78% {{ fill: {AMBER}; }} 86%,100% {{ fill: {SAGE}; }} }}
"""
    co = (
        callout("tl", ["sha256 canonical", "digest"], 0.5)
        + callout("tr", ["ed25519 via", "system openssl"], 0.8)
        + callout("bl", ["local sqlite", "history"], 1.1)
        + callout("br", ["never claims", "signed when not"], 1.4)
    )
    return sheet(
        "Kernelridge attestation",
        "An isometric safe with a rotating combination dial, holding a report "
        "digest: SHA-256 canonical digest, Ed25519 signature via openssl, "
        "local SQLite history, and an honest unsigned fallback.",
        "\n".join(parts), co, css, "kernelridge attest --input --private",
    )


def main() -> None:
    for name, fn in {
        "preflight": preflight,
        "verdicts": verdicts,
        "invalidation": invalidation,
        "attestation": attestation,
    }.items():
        (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print(f"wrote assets/diagrams/{name}.svg")


if __name__ == "__main__":
    main()
