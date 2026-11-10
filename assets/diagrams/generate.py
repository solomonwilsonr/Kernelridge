"""Generate the animated "spec sheet" README illustrations.

Each figure is a self-contained SVG laid out like an engineering drawing:
an isometric line drawing on an isometric grid (left), numbered callouts
leading to a results panel built from real Kernelridge output (right), and
a title block along the bottom, on a white sheet. A dark palette is kept
in PALETTES for anyone who wants a dark variant.

Animation is plain CSS + SMIL (no scripts) on a looping 12 s storyline:
callout leaders draw in, signal packets travel along them, result rows slide
in, status chips stamp down in order, a highlight sweeps the rows, then it
all retracts and replays. ``prefers-reduced-motion`` shows the finished frame.

No third-party dependencies. Run from the repository root:

    python assets/diagrams/generate.py
"""

from __future__ import annotations

import math
from pathlib import Path

W, H = 1200, 620
OUT = Path(__file__).resolve().parent
TOTAL = 5

PALETTES = {
    "light": {
        "paper": "#ffffff", "grid": "#eaeef2", "frame": "#9aa6b2",
        "ink": "#1d2733", "soft": "#6b7785", "faint": "#b8c1cb",
        "top": "#ffffff", "left": "#f1f4f7", "right": "#e1e7ed",
        "accent": "#1f8a7a", "accent_soft": "#1f8a7a16",
        "pass": "#2f8a57", "review": "#c4861a", "unknown": "#7d8794",
        "fail": "#c2463b", "warn_fill": "#f6dfb0", "hot_fill": "#f4c9c2",
        "chip_text": "#ffffff", "bar": "#1d2733", "bar_text": "#e8eef3",
    },
    "dark": {
        "paper": "#0f1720", "grid": "#1c2733", "frame": "#3a4a5a",
        "ink": "#d9e2ea", "soft": "#8e9cab", "faint": "#3c4b5a",
        "top": "#1c2834", "left": "#17212c", "right": "#121b24",
        "accent": "#4cc2ad", "accent_soft": "#4cc2ad26",
        "pass": "#3fae72", "review": "#e0a43a", "unknown": "#8d98a5",
        "fail": "#e0645a", "warn_fill": "#5a4520", "hot_fill": "#5e2a26",
        "chip_text": "#0f1720", "bar": "#d9e2ea", "bar_text": "#0f1720",
    },
}

STATUS = {  # chip label -> palette key
    "PASS": "pass", "FAIL": "fail", "REVIEW": "review", "UNKNOWN": "unknown",
    "RUNTIME": "accent", "CHANGED": "fail", "INVALIDATED": "review",
    "REUSED": "pass", "RESERVED": "accent", "SELECTED": "pass",
    "SKIPPED": "unknown", "PROPOSED": "review", "DIGEST": "accent",
    "SIGNED": "pass", "STORED": "accent", "UNSIGNED": "unknown",
}


# --------------------------------------------------------------------------
# isometric projection
# --------------------------------------------------------------------------

class Iso:
    def __init__(self, s: float, ox: float, oy: float):
        self.s, self.ox, self.oy = s, ox, oy

    def p(self, x, y, z):
        return (self.ox + (x - y) * 0.866 * self.s,
                self.oy + (x + y) * 0.5 * self.s - z * self.s)

    def pts(self, *q):
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in (self.p(*v) for v in q))

    def line(self, a, b, cls):
        (x1, y1), (x2, y2) = self.p(*a), self.p(*b)
        return f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'

    def box(self, x, y, z, dx, dy, dz, extra="", hidden=False):
        x1, y1, z1 = x + dx, y + dy, z + dz
        out = []
        if hidden:
            out += [self.line((x, y, z), (x1, y, z), "hid"),
                    self.line((x, y, z), (x, y1, z), "hid"),
                    self.line((x, y, z), (x, y, z1), "hid")]
        out += [
            f'<polygon class="f t {extra}" points="{self.pts((x, y, z1), (x1, y, z1), (x1, y1, z1), (x, y1, z1))}"/>',
            f'<polygon class="f l {extra}" points="{self.pts((x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1))}"/>',
            f'<polygon class="f r {extra}" points="{self.pts((x1, y, z), (x1, y1, z), (x1, y1, z1), (x1, y, z1))}"/>',
        ]
        return "\n".join(out)

    def m_left(self, x, y, z):
        """local (u right, v up) on the y=const face; origin at (x, y, z)."""
        s = self.s
        ex, ey = self.p(x, y, z)
        return f"matrix({.866*s:.3f},{.5*s:.3f},0,{-s:.3f},{ex:.1f},{ey:.1f})"

    def m_right(self, x, y, z):
        """local (u right, v up) on the x=const face; u runs toward -y."""
        s = self.s
        ex, ey = self.p(x, y, z)
        return f"matrix({.866*s:.3f},{-.5*s:.3f},0,{-s:.3f},{ex:.1f},{ey:.1f})"

    def m_top(self, x, y, z):
        """local (u along +x, v along +y) on the z=const face."""
        s = self.s
        ex, ey = self.p(x, y, z)
        return f"matrix({.866*s:.3f},{.5*s:.3f},{-.866*s:.3f},{.5*s:.3f},{ex:.1f},{ey:.1f})"


NS = 'vector-effect="non-scaling-stroke"'


def face_text(transform, x, y, size, text, fill, weight="400"):
    """Text on an isometric face; local v points up, so flip y for glyphs."""
    return (f'<g transform="{transform}"><g transform="translate({x} {y}) scale(1,-1)">'
            f'<text class="mono" font-size="{size}" font-weight="{weight}" style="fill:{fill}">{text}</text></g></g>')


# --------------------------------------------------------------------------
# sheet scaffold
# --------------------------------------------------------------------------

def css(P: dict) -> str:
    return f"""
text {{ font-family: "Inter", "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif; fill: {P['ink']}; }}
.mono {{ font-family: "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace; }}
.soft {{ fill: {P['soft']}; }}
.acc {{ fill: {P['accent']}; }}
.f {{ stroke: {P['ink']}; stroke-width: 1.3; stroke-linejoin: round; }}
.t {{ fill: {P['top']}; }} .l {{ fill: {P['left']}; }} .r {{ fill: {P['right']}; }}
.wire {{ stroke: {P['ink']}; stroke-width: 1.3; fill: none; stroke-linecap: round; }}
.thin {{ stroke: {P['ink']}; stroke-width: .9; fill: none; }}
.hid {{ stroke: {P['soft']}; stroke-width: .9; stroke-dasharray: 3 4; fill: none; }}
.rule {{ stroke: {P['faint']}; stroke-width: 1; stroke-dasharray: 2 4; }}

/* One 12 s storyline that loops: leaders draw, rows slide in, chips stamp,
   everything holds, then retracts in the same order and starts again. */
.lead {{ fill: none; stroke: {P['accent']}; stroke-width: 1.4;
         stroke-dasharray: 1; stroke-dashoffset: 1;
         animation: draw 12s cubic-bezier(.6,0,.2,1) infinite both; }}
.row  {{ opacity: 0; animation: row 12s cubic-bezier(.2,.7,.2,1) infinite both; }}
.chip {{ opacity: 0; transform-box: fill-box; transform-origin: center;
         animation: stamp 12s cubic-bezier(.3,1.5,.5,1) infinite both; }}
.hs   {{ opacity: 0; animation: hs 12s ease-out infinite both; }}
.in   {{ opacity: 0; animation: in .6s ease-out forwards; }}
.hot  {{ transform-box: fill-box; transform-origin: center;
         animation: hot 2.4s ease-out infinite; }}
.cursor {{ animation: blink 1s steps(1) infinite; }}
.sweep {{ opacity: 0; animation: sweep 12s ease-in-out infinite both; }}

@keyframes draw  {{ 0% {{ stroke-dashoffset: 1; }} 7%,84% {{ stroke-dashoffset: 0; }} 91%,100% {{ stroke-dashoffset: -1; }} }}
@keyframes row   {{ 0% {{ opacity: 0; transform: translateX(16px); }} 5%,84% {{ opacity: 1; transform: none; }}
                    90%,100% {{ opacity: 0; transform: translateX(-8px); }} }}
@keyframes stamp {{ 0% {{ opacity: 0; transform: scale(1.8); }} 3.5%,84% {{ opacity: 1; transform: scale(1); }}
                    89%,100% {{ opacity: 0; transform: scale(.85); }} }}
@keyframes hs    {{ 0% {{ opacity: 0; }} 3%,86% {{ opacity: 1; }} 92%,100% {{ opacity: 0; }} }}
@keyframes in    {{ to {{ opacity: 1; }} }}
@keyframes hot   {{ 0% {{ transform: scale(1); opacity: .7; }} 70%,100% {{ transform: scale(2.6); opacity: 0; }} }}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
@keyframes sweep {{ 0%,30% {{ opacity: 0; transform: translateY(0); }} 33% {{ opacity: 1; transform: translateY(0); }}
                    64% {{ opacity: 1; transform: translateY(272px); }} 68%,100% {{ opacity: 0; transform: translateY(272px); }} }}
@media (prefers-reduced-motion: reduce) {{
  *, .lead, .row, .chip, .hs, .in, .sweep {{ animation: none !important; }}
  .row, .chip, .hs, .in {{ opacity: 1 !important; }}
  .lead {{ stroke-dashoffset: 0 !important; }}
  .sweep {{ opacity: 0 !important; }}
}}
"""


def backdrop(P: dict) -> str:
    gw = 24 * math.sqrt(3)
    ticks = []
    for x in range(40, W - 20, 24):
        ln = 7 if (x - 40) % 120 == 0 else 3.5
        ticks.append(f'<line x1="{x}" y1="16" x2="{x}" y2="{16 + ln}"/>')
    for y in range(40, H - 70, 24):
        ln = 7 if (y - 40) % 120 == 0 else 3.5
        ticks.append(f'<line x1="16" y1="{y}" x2="{16 + ln}" y2="{y}"/>')
    return f"""
<defs>
  <pattern id="iso" width="{gw:.3f}" height="24" patternUnits="userSpaceOnUse">
    <path d="M0 0 L{gw:.3f} 24 M0 24 L{gw:.3f} 0 M0 12 L{gw/2:.3f} 24 M{gw/2:.3f} 0 L{gw:.3f} 12"
          stroke="{P['grid']}" stroke-width=".8" fill="none"/>
  </pattern>
  <linearGradient id="fadeR" x1="0" x2="1">
    <stop offset="0" stop-color="{P['paper']}" stop-opacity="0"/>
    <stop offset=".18" stop-color="{P['paper']}" stop-opacity=".94"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{H}" fill="{P['paper']}"/>
<rect x="16" y="16" width="{W-32}" height="{H-32}" fill="url(#iso)"/>
<rect x="560" y="16" width="{W-576}" height="{H-32}" fill="url(#fadeR)"/>
<rect x="9" y="9" width="{W-18}" height="{H-18}" fill="none" stroke="{P['frame']}" stroke-width="1"/>
<rect x="16" y="16" width="{W-32}" height="{H-32}" fill="none" stroke="{P['frame']}" stroke-width="1.6"/>
<g stroke="{P['frame']}" stroke-width="1">{''.join(ticks)}</g>
"""


def title_block(P, fig_no, fig_name, command) -> str:
    y0, y1 = H - 62, H - 16
    xs = [16, 220, 470, 1060, W - 16]
    cells = [
        (xs[0] + 20, f'<tspan class="acc" font-weight="700" letter-spacing="2.5">KERNELRIDGE</tspan>'),
        (xs[1] + 20, f'<tspan class="soft">FIG.</tspan> {fig_no:02d} <tspan class="soft">·</tspan> {fig_name}'),
        (xs[2] + 20, f'<tspan class="mono soft">$ </tspan><tspan class="mono">{command}</tspan>'),
        (xs[3] + 20, f'<tspan class="soft">SHEET</tspan> {fig_no}/{TOTAL}'),
    ]
    out = [f'<rect x="16" y="{y0}" width="{W-32}" height="{y1-y0}" fill="{P["paper"]}" stroke="{P["frame"]}" stroke-width="1.6"/>']
    for x in xs[1:-1]:
        out.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{P["frame"]}" stroke-width="1"/>')
    for x, t in cells:
        out.append(f'<text x="{x}" y="{y0 + 28}" font-size="14" letter-spacing=".3">{t}</text>')
    return "\n".join(out)


PANEL_X = 640
ROW_Y = [196, 264, 332, 400]
FAN_X0, FAN_X1 = 528, 596


def chip(P, label, x_right, y, delay) -> str:
    w = 8.6 * len(label) + 24
    color = P[STATUS[label]]
    return (
        f'<g class="chip" style="animation-delay:{delay:.2f}s">'
        f'<rect x="{x_right - w:.0f}" y="{y - 13}" width="{w:.0f}" height="26" rx="13" fill="{color}"/>'
        f'<text class="mono" x="{x_right - w / 2:.0f}" y="{y + 4.5}" text-anchor="middle" font-size="12.5" '
        f'font-weight="700" letter-spacing=".6" style="fill:{P['chip_text']}">{label}</text></g>'
    )


def panel(P, kicker, heading, rows, hotspots, summary) -> str:
    """rows: (key, value, status); hotspots: (x, y) on the drawing, one per row."""
    right = W - 48
    out = [
        f'<text class="in mono acc" style="animation-delay:.1s" x="{PANEL_X}" y="84" font-size="13" letter-spacing="2.5">{kicker}</text>',
        f'<text class="in" style="animation-delay:.2s" x="{PANEL_X}" y="120" font-size="27" font-weight="650" letter-spacing="-.3">{heading}</text>',
        f'<line class="in" style="animation-delay:.3s" x1="{PANEL_X}" y1="146" x2="{right}" y2="146" stroke="{P["ink"]}" stroke-width="1.4"/>',
        f'<rect class="sweep" x="{PANEL_X - 8}" y="{ROW_Y[0] - 28}" width="{right - PANEL_X + 16}" height="56" rx="8" fill="{P["accent_soft"]}"/>',
    ]
    for i, ((key, val, status), (hx, hy)) in enumerate(zip(rows, hotspots)):
        ry = ROW_Y[i]
        d = 0.6 + i * 0.45
        # Horizontal out to a shared column, fan to the row, then in. With
        # hotspots ordered top-to-bottom like the rows, leaders never cross.
        out.append(
            f'<path id="lead{i}" class="lead" pathLength="1" style="animation-delay:{d:.2f}s" '
            f'd="M{hx:.1f} {hy:.1f} H{FAN_X0} L{FAN_X1} {ry} H{PANEL_X - 4}"/>'
        )
        # a signal packet runs hotspot -> row three times per 12 s cycle
        out.append(
            f'<circle r="3.4" fill="{P["accent"]}" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;.02;.26;.3;1" '
            f'dur="4s" begin="{d + 1.0:.2f}s" repeatCount="indefinite"/>'
            f'<animateMotion dur="4s" begin="{d + 1.0:.2f}s" repeatCount="indefinite" '
            f'keyPoints="0;1;1" keyTimes="0;.28;1" calcMode="linear">'
            f'<mpath href="#lead{i}" xlink:href="#lead{i}"/></animateMotion></circle>'
        )
        out.append(
            f'<g class="hs" style="animation-delay:{max(d - .2, 0):.2f}s">'
            f'<circle class="hot" cx="{hx:.1f}" cy="{hy:.1f}" r="6" fill="none" stroke="{P["accent"]}" stroke-width="1.5" style="animation-delay:{d + 1.2:.2f}s"/>'
            f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="5.5" fill="{P["paper"]}" stroke="{P["accent"]}" stroke-width="2"/>'
            f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="2" fill="{P["accent"]}"/></g>'
        )
        out.append(
            f'<g class="row" style="animation-delay:{d + .55:.2f}s">'
            f'<circle cx="{PANEL_X + 12}" cy="{ry}" r="12" fill="{P["ink"]}"/>'
            f'<text class="mono" x="{PANEL_X + 12}" y="{ry + 4.5}" text-anchor="middle" font-size="12.5" font-weight="700" style="fill:{P['paper']}">{i + 1}</text>'
            f'<text class="mono" x="{PANEL_X + 38}" y="{ry - 4}" font-size="16" font-weight="600">{key}</text>'
            f'<text class="soft" x="{PANEL_X + 38}" y="{ry + 17}" font-size="14">{val}</text>'
            f'<line class="rule" x1="{PANEL_X}" y1="{ry + 34}" x2="{right}" y2="{ry + 34}"/></g>'
        )
        out.append(chip(P, status, right, ry, d + 1.0))
    sy = 458
    sd = 0.6 + len(rows) * 0.45 + 0.9
    out.append(
        f'<g class="row" style="animation-delay:{sd:.2f}s">'
        f'<rect x="{PANEL_X}" y="{sy}" width="{right - PANEL_X}" height="44" rx="6" fill="{P["bar"]}"/>'
        f'<text class="mono" x="{PANEL_X + 18}" y="{sy + 27.5}" font-size="14.5" style="fill:{P['bar_text']}">'
        f'<tspan style="fill:{P['accent']}">→ </tspan>{summary}'
        f'<tspan class="cursor" style="fill:{P['accent']}"> ▍</tspan></text></g>'
    )
    return "\n".join(out)


def sheet(P, *, title, desc, drawing, extra_css, fig_no, fig_name, command,
          kicker, heading, rows, hotspots, summary) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">{title}</title>
<desc id="d">{desc}</desc>
<style>{css(P)}{extra_css}</style>
{backdrop(P)}
<g class="in">
{drawing}
</g>
{panel(P, kicker, heading, rows, hotspots, summary)}
{title_block(P, fig_no, fig_name, command)}
</svg>
"""


# --------------------------------------------------------------------------
# FIG 1 — preflight: RISC-V chip, missing vector extension
# --------------------------------------------------------------------------

def fig_preflight(P):
    iso = Iso(20, 300, 200)
    d = [iso.box(0, 0, 0, 10, 10, .5, hidden=True)]
    for i in range(5):  # traces
        y = 1.0 + i * .55
        d.append(f'<polyline class="trace" points="{iso.pts((.4, y, .5), (2.0, y, .5), (2.0 - i * .3, y + 6.0, .5))}"/>')
    for i in range(7):  # pins
        t = 2.9 + i * .7
        d.append(f'<polyline class="thin" points="{iso.pts((t, 7.5, .5), (t, 8.2, .5))}"/>')
        d.append(f'<polyline class="thin" points="{iso.pts((7.5, t, .5), (8.2, t, .5))}"/>')
    # the missing "v" socket
    d.append(f'<polygon class="vslot" points="{iso.pts((8.4, .6, .5), (9.6, .6, .5), (9.6, 1.8, .5), (8.4, 1.8, .5))}"/>')
    vx, vy = iso.p(9.0, 1.2, .5)
    d.append(f'<text class="mono vmark" x="{vx:.1f}" y="{vy + 5:.1f}" text-anchor="middle" font-size="14" font-weight="700">v</text>')
    # glibc package
    d.append(iso.box(8.6, 6.4, .5, 1.0, 2.6, .5))
    d.append(face_text(iso.m_right(9.6, 9.0, .5), .3, .13, ".3", "libc", P["soft"], "700"))
    # SoC
    d.append(iso.box(2.5, 2.5, .5, 5, 5, 1.0))
    m = iso.m_top(2.5, 2.5, 1.5)
    d.append(f"""<g transform="{m}">
  <rect x=".6" y=".6" width="3.8" height="3.8" fill="none" stroke="{P['ink']}" stroke-width="1" {NS}/>
  <rect class="die" x=".6" y=".6" width="3.8" height="3.8" fill="{P['accent']}"/>
  <circle cx="1.05" cy="1.05" r=".15" fill="{P['ink']}"/>
  <text x="2.5" y="2.6" text-anchor="middle" font-size=".95" font-weight="700">RV64</text>
  <text class="mono" x="2.5" y="3.4" text-anchor="middle" font-size=".42" style="fill:{P['soft']}">imafdc · lp64d</text>
</g>""")
    d.append(face_text(iso.m_left(2.5, 7.5, .5), .3, .3, ".42", "riscv-lab-001", P["soft"]))
    extra = f"""
.trace {{ fill: none; stroke: {P['soft']}; stroke-width: .9; stroke-dasharray: 5 4; animation: flow 1.6s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -18; }} }}
.die {{ opacity: 0; animation: die 4s ease-in-out 2.5s infinite; }}
@keyframes die {{ 0%,100% {{ opacity: 0; }} 45%,55% {{ opacity: .22; }} }}
.vslot {{ fill: {P['hot_fill']}; stroke: {P['fail']}; stroke-width: 1.5; stroke-dasharray: 4 3; animation: vs 1.6s steps(1) 2.5s infinite; }}
.vmark {{ fill: {P['fail']}; animation: vs 1.6s steps(1) 2.5s infinite; }}
@keyframes vs {{ 50% {{ opacity: .25; }} }}
"""
    hot = [iso.p(6, 2.5, 1.5), iso.p(9.0, 1.2, .5), iso.p(7.5, 6.5, 1.0), iso.p(9.6, 7.6, .8)]
    return dict(
        title="Kernelridge preflight",
        desc="A RISC-V board whose chip exposes imafdc on lp64d with glibc 2.38. "
             "The release requires the vector extension v, so preflight fails the "
             "isa_extensions rule and the overall decision is FAIL, exit 1.",
        drawing="\n".join(d), extra_css=extra,
        fig_name="PREFLIGHT", command="kernelridge preflight --target --release",
        kicker="01 · STATIC PREFLIGHT", heading="Find the mismatch before deploy",
        rows=[("architecture", "riscv64  =  riscv64", "PASS"),
              ("isa_extensions", "release needs v · target has imafdc", "FAIL"),
              ("abi", "lp64d  =  lp64d", "PASS"),
              ("library.glibc", "2.38  =  2.38", "PASS")],
        hotspots=hot,
        summary="decision: FAIL · exit 1 · remediation attached",
    )


# --------------------------------------------------------------------------
# FIG 2 — verdicts: inspection frame, decision precedence
# --------------------------------------------------------------------------

def fig_verdicts(P):
    iso = Iso(17, 300, 215)
    z0, h, n = -3, 10, 10
    d = []
    for a, b in [((0, 0, z0), (n, 0, z0)), ((0, 0, z0), (0, n, z0)), ((0, 0, z0), (0, 0, z0 + h))]:
        d.append(iso.line(a, b, "hid"))
    d.append(iso.box(3, 3, z0, 4, 4, 4.4))
    m = iso.m_left(3, 7, z0)
    d.append(f'<g transform="{m}"><path d="M0 3.3 H4 M2 4.4 V3.3" fill="none" stroke="{P["ink"]}" stroke-width="1" {NS}/></g>')
    d.append(face_text(m, .35, 1.0, ".55", "release", P["soft"]))
    m = iso.m_top(3, 3, z0 + 4.4)
    d.append(f'<g transform="{m}"><path d="M2 0 V4" fill="none" stroke="{P["ink"]}" stroke-width="1" {NS}/></g>')
    # an empty, dashed inventory slot (what UNKNOWN looks like)
    d.append(f'<polygon class="hole" points="{iso.pts((7.6, 1, z0), (9.4, 1, z0), (9.4, 2.8, z0), (7.6, 2.8, z0))}"/>')
    plane = iso.pts((0, 0, z0), (n, 0, z0), (n, n, z0), (0, n, z0))
    d.append(f'<polygon class="scan" points="{plane}" fill="{P["accent"]}" fill-opacity=".14" stroke="{P["accent"]}" stroke-width="1.6"/>')
    for a, b in [((n, 0, z0), (n, n, z0)), ((0, n, z0), (n, n, z0)), ((n, 0, z0), (n, 0, z0 + h)),
                 ((0, n, z0), (0, n, z0 + h)), ((n, n, z0), (n, n, z0 + h)), ((0, 0, z0 + h), (n, 0, z0 + h)),
                 ((0, 0, z0 + h), (0, n, z0 + h)), ((n, 0, z0 + h), (n, n, z0 + h)), ((0, n, z0 + h), (n, n, z0 + h))]:
        d.append(iso.line(a, b, "wire"))
    for c in [(n, n, z0 + h), (0, n, z0 + h), (n, 0, z0 + h), (n, n, z0), (0, 0, z0 + h)]:
        x, y = iso.p(*c)
        d.append(f'<rect x="{x-4:.1f}" y="{y-4:.1f}" width="8" height="8" fill="{P["paper"]}" stroke="{P["ink"]}" stroke-width="1.2"/>')
    span = h * iso.s
    extra = f"""
.scan {{ animation: scan 5s ease-in-out 2s infinite; }}
@keyframes scan {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-{span:.0f}px); }} }}
.hole {{ fill: none; stroke: {P['unknown']}; stroke-width: 1.3; stroke-dasharray: 4 3; }}
"""
    hot = [iso.p(5, 7, z0 + 4.4), iso.p(8.5, 1.9, z0), iso.p(n, 6, z0), iso.p(n, n, z0)]
    return dict(
        title="Kernelridge verdicts",
        desc="A release inside a wireframe inspection frame with a scanning plane. "
             "Decision precedence: any FAIL wins, then UNKNOWN for missing inventory, "
             "then REVIEW for a static match; only a sandboxed runtime experiment goes further.",
        drawing="\n".join(d), extra_css=extra,
        fig_name="VERDICTS", command="kernelridge preflight ... ; echo $?",
        kicker="02 · NO OPTIMISTIC PASS", heading="Honest verdicts, in order",
        rows=[("any rule mismatched", "missing extension / ABI / version is named", "FAIL"),
              ("inventory missing", "ISA or ABI not in verified data", "UNKNOWN"),
              ("everything matches", "static metadata only · approval required", "REVIEW"),
              ("experiment run", "sandboxed smoke test is the real evidence", "RUNTIME")],
        hotspots=hot,
        summary="FAIL > UNKNOWN > REVIEW · static match ≠ PASS",
    )


# --------------------------------------------------------------------------
# FIG 3 — invalidation: revision + evidence stack, transitive propagation
# --------------------------------------------------------------------------

def fig_invalidation(P):
    iso = Iso(17, 300, 175)
    d = []
    levels = [5.6, 2.4, -.8, -4.0]
    names = ["revision", "e1 · libraries", "e2 · depends_on e1", "e3 · abi"]
    for idx in reversed(range(4)):
        z = levels[idx]
        x, dd = (0, 10) if idx == 0 else (1, 8)
        d.append(f'<g class="s{idx}">{iso.box(x, x, z, dd, dd, 1.1)}</g>')
        d.append(face_text(iso.m_left(x, x + dd, z), .35, .35, ".5", names[idx], P["soft"]))
        if idx:
            for u in (3, 7):
                a, b = iso.p(9, u, z + 1.1), iso.p(9, u, levels[idx - 1])
                cls = "dep idle" if idx == 3 else "dep"
                d.append(f'<line class="{cls}" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')
    m = iso.m_top(0, 0, levels[0] + 1.1)
    d.append(f'<g transform="{m}"><text class="mono" x="1.6" y="5.4" font-size=".62" font-weight="700" style="fill:{P["fail"]}">glibc 2.38 → 2.39</text></g>')
    extra = f"""
.dep {{ stroke: {P['ink']}; stroke-width: 1.2; stroke-dasharray: 3 3; animation: flow 1.2s linear infinite; }}
.dep.idle {{ stroke: {P['soft']}; animation: none; }}
@keyframes flow {{ to {{ stroke-dashoffset: -12; }} }}
.s0 .t {{ animation: c-t 7s ease-in-out 2s infinite; }}
.s0 .l, .s0 .r {{ animation: c-s 7s ease-in-out 2s infinite; }}
.s1 .t, .s2 .t {{ animation: w-t 7s ease-in-out infinite; }}
.s1 .l, .s1 .r, .s2 .l, .s2 .r {{ animation: w-s 7s ease-in-out infinite; }}
.s1 polygon {{ animation-delay: 2.8s; }}
.s2 polygon {{ animation-delay: 3.6s; }}
@keyframes c-t {{ 0%,4%,75%,100% {{ fill: {P['top']}; }} 12%,60% {{ fill: {P['hot_fill']}; }} }}
@keyframes c-s {{ 0%,4%,75%,100% {{ fill: {P['right']}; }} 12%,60% {{ fill: {P['hot_fill']}; }} }}
@keyframes w-t {{ 0%,4%,64%,100% {{ fill: {P['top']}; }} 12%,50% {{ fill: {P['warn_fill']}; }} }}
@keyframes w-s {{ 0%,4%,64%,100% {{ fill: {P['right']}; }} 12%,50% {{ fill: {P['warn_fill']}; }} }}
"""
    hot = [iso.p(10, 5, levels[0] + .55), iso.p(9, 5, levels[1] + .55),
           iso.p(9, 5, levels[2] + .55), iso.p(9, 5, levels[3] + .55)]
    return dict(
        title="Kernelridge invalidation",
        desc="A revision slab above three evidence slabs joined by depends_on links. "
             "glibc changes from 2.38 to 2.39: evidence assuming libraries is invalidated, "
             "the record that depends on it follows transitively, and unrelated ABI evidence is reused.",
        drawing="\n".join(d), extra_css=extra,
        fig_name="INVALIDATION", command="kernelridge invalidate --before --after --evidence",
        kicker="03 · EVIDENCE INVALIDATION", heading="Stale proof never gets reused",
        rows=[("changed_paths", "libraries.glibc: 2.38 → 2.39", "CHANGED"),
              ("e1 assumes libraries", "touched by the change", "INVALIDATED"),
              ("e2 depends_on e1", "propagated to a fixpoint", "INVALIDATED"),
              ("e3 assumes abi", "untouched · dependencies_complete", "REUSED")],
        hotspots=hot,
        summary="incomplete dependency coverage ⇒ always revalidate",
    )


# --------------------------------------------------------------------------
# FIG 4 — experiment plan: a 7-minute budget track
# --------------------------------------------------------------------------

def fig_plan(P):
    iso = Iso(22, 230, 170)
    d = [iso.box(0, 3, 0, 7.4, 3.4, .5, hidden=True)]
    for i in range(8):
        x = .2 + i
        d.append(f'<polyline class="thin" style="stroke:{P["soft"]}" points="{iso.pts((x, 3.2, .5), (x, 6.2, .5))}"/>')
        d.append(face_text(iso.m_left(x - .1, 6.4, 0), 0, .1, ".34", str(i), P["soft"]))
    d.append(f'<g class="drop b1">{iso.box(.2, 3.4, .5, 2, 2.6, 1.6, extra="acc-f")}</g>')
    d.append(f'<g class="drop b2">{iso.box(2.2, 3.4, .5, 5, 2.6, 1.0)}</g>')
    d.append(f'<g class="drop b1">{face_text(iso.m_left(.35, 6.0, .5), 0, .65, ".36", "smoke", P["ink"], "700")}</g>')
    d.append(f'<g class="drop b2">{face_text(iso.m_left(2.4, 6.0, .5), 0, .4, ".36", "vector-diagnosis", P["ink"])}</g>')
    # rejected 20-minute block: overruns the end of the budget track
    gx0, gx1, gz = 7.8, 14.0, .5
    d.append(
        f'<g class="ghost">'
        f'<polygon class="g" points="{iso.pts((gx0, 3.4, gz + 1.2), (gx1, 3.4, gz + 1.2), (gx1, 6, gz + 1.2), (gx0, 6, gz + 1.2))}"/>'
        f'<polygon class="g" points="{iso.pts((gx1, 3.4, gz), (gx1, 6, gz), (gx1, 6, gz + 1.2), (gx1, 3.4, gz + 1.2))}"/>'
        f'<polygon class="g" points="{iso.pts((gx0, 6, gz), (gx1, 6, gz), (gx1, 6, gz + 1.2), (gx0, 6, gz + 1.2))}"/>'
        f'{face_text(iso.m_left(gx0 + .3, 6, gz), 0, .45, ".36", "physical-board · 20 min", P["soft"])}</g>'
    )
    end = iso.p(7.4, 6.6, 0), iso.p(7.4, 2.6, 0)
    d.append(f'<line x1="{end[0][0]:.1f}" y1="{end[0][1]:.1f}" x2="{end[1][0]:.1f}" y2="{end[1][1]:.1f}" stroke="{P['fail']}" stroke-width="1.6" stroke-dasharray="4 3"/>')
    # budget bracket
    a, b = iso.p(.2, 7.4, 0), iso.p(7.2, 7.4, 0)
    d.append(f'<path class="thin" style="stroke:{P["accent"]}" d="M{a[0]:.1f} {a[1]:.1f} L{b[0]:.1f} {b[1]:.1f}"/>')
    d.append(face_text(iso.m_left(2.6, 7.4, -.6), 0, 0, ".42", "budget = 7 min", P["accent"], "700"))
    extra = f"""
.acc-f.t {{ fill: {P['accent']}; fill-opacity: .55; }}
.acc-f.l, .acc-f.r {{ fill: {P['accent']}; fill-opacity: .35; }}
.drop {{ opacity: 0; animation: drop .8s cubic-bezier(.3,1.4,.5,1) forwards; }}
.b1 {{ animation-delay: 1.0s; }} .b2 {{ animation-delay: 1.9s; }}
@keyframes drop {{ from {{ opacity: 0; transform: translateY(-60px); }} to {{ opacity: 1; transform: none; }} }}
.g {{ fill: none; stroke: {P['soft']}; stroke-width: 1.2; stroke-dasharray: 5 4; }}
.ghost {{ animation: hover 3s ease-in-out 2s infinite; }}
@keyframes hover {{ 0%,100% {{ transform: translateX(0); opacity: .95; }} 50% {{ transform: translateX(6px); opacity: .4; }} }}
"""
    hot = [iso.p(2.2, 4.7, 2.1), iso.p(7.2, 4.7, 1.5), iso.p(11, 4.7, gz + 1.2), iso.p(7.4, 6.6, 0)]
    return dict(
        title="Kernelridge experiment plan",
        desc="A seven-minute budget track. The mandatory 2-minute smoke test is reserved "
             "first, the 5-minute vector diagnosis fills the rest, and the 20-minute "
             "physical-board run is left out. Status PROPOSED, approval required.",
        drawing="\n".join(d), extra_css=extra,
        fig_name="EXPERIMENT PLAN", command="kernelridge experiment plan --budget-minutes 7",
        kicker="04 · EXPERIMENT PLANNER", heading="Spend the test budget wisely",
        rows=[("smoke", "2 min · mandatory, reserved first", "RESERVED"),
              ("vector-diagnosis", "5 min · gain × severity × relevance / cost", "SELECTED"),
              ("physical-board", "20 min · does not fit the budget", "SKIPPED"),
              ("budget", "7 / 7 minutes used", "PROPOSED")],
        hotspots=hot,
        summary="approval_required: true · infeasible ⇒ BLOCKED",
    )


# --------------------------------------------------------------------------
# FIG 5 — attestation: a vault holding the signed digest
# --------------------------------------------------------------------------

# Canonical digest of the report for examples/compatible-release.json.
DIGEST = "b9c9c2ae3166…f9e424ef0f4a"


def fig_attestation(P):
    iso = Iso(17, 300, 175)
    d = []
    for fx, fy in ((.4, 9.0), (9.0, 9.0), (9.0, .4)):
        d.append(iso.box(fx, fy, -.6, .6, .6, .6))
    d.append(iso.box(0, 0, 0, 10, 10, 9, hidden=True))
    m = iso.m_left(0, 10, 0)
    ticks = "".join(
        f'<line x1="{4.6 + 1.35*math.cos(a):.3f}" y1="{4.5 + 1.35*math.sin(a):.3f}" '
        f'x2="{4.6 + (1.62 if i % 3 == 0 else 1.5)*math.cos(a):.3f}" y2="{4.5 + (1.62 if i % 3 == 0 else 1.5)*math.sin(a):.3f}" '
        f'stroke="{P["ink"]}" stroke-width=".8" {NS}/>'
        for i, a in enumerate(j * math.pi / 15 for j in range(30))
    )
    d.append(f"""<g transform="{m}">
  <rect x=".7" y=".7" width="8.4" height="7.6" rx=".15" fill="none" stroke="{P['ink']}" stroke-width="1.3" {NS}/>
  <rect x="1.1" y="1.1" width="7.6" height="6.8" fill="none" stroke="{P['soft']}" stroke-width=".8" stroke-dasharray="3 4" {NS}/>
  {ticks}
  <circle cx="4.6" cy="4.5" r="1.25" fill="{P['top']}" stroke="{P['ink']}" stroke-width="1.2" {NS}/>
  <g>
    <animateTransform attributeName="transform" type="rotate" dur="7s" begin="1.5s" repeatCount="indefinite"
      values="0 4.6 4.5;110 4.6 4.5;110 4.6 4.5;-70 4.6 4.5;-70 4.6 4.5;25 4.6 4.5;25 4.6 4.5;0 4.6 4.5"
      keyTimes="0;.14;.24;.42;.52;.66;.8;1" calcMode="spline"
      keySplines=".5 0 .2 1;0 0 1 1;.5 0 .2 1;0 0 1 1;.5 0 .2 1;0 0 1 1;.5 0 .2 1"/>
    <circle cx="4.6" cy="4.5" r=".8" fill="{P['left']}" stroke="{P['ink']}" stroke-width="1" {NS}/>
    <line x1="4.6" y1="4.5" x2="4.6" y2="5.25" stroke="{P['ink']}" stroke-width="1.5" {NS}/>
  </g>
  <rect x="8.85" y="5.6" width=".45" height="1.3" rx=".1" fill="{P['top']}" stroke="{P['ink']}" stroke-width="1" {NS}/>
  <rect x="8.85" y="2.1" width=".45" height="1.3" rx=".1" fill="{P['top']}" stroke="{P['ink']}" stroke-width="1" {NS}/>
  <circle class="lock" cx="7.6" cy="1.6" r=".26"/>
</g>""")
    d.append(face_text(m, 1.5, 7.2, ".46", "ed25519", P["soft"]))
    m = iso.m_right(10, 10, 0)
    d.append(f"""<g transform="{m}">
  <rect x="1.2" y="5.0" width="7.6" height="1.9" fill="{P['paper']}" stroke="{P['ink']}" stroke-width="1" {NS}/>
  <rect x="2.2" y="2.2" width="5.6" height=".45" fill="{P['ink']}" opacity=".8"/>
</g>""")
    d.append(face_text(m, 1.55, 6.25, ".44", "sha256", P["soft"]))
    d.append(face_text(m, 1.55, 5.5, ".44", DIGEST, P["ink"]))
    # a report sheet dropping into the slot on the right face
    sheet_m = iso.m_right(10, 10, 0)
    d.append(f"""<g transform="{sheet_m}"><g class="paper">
  <rect x="2.6" y="2.45" width="4.8" height="3.2" fill="{P['top']}" stroke="{P['ink']}" stroke-width="1" {NS}/>
  <path d="M3.1 4.9 h3.2 M3.1 4.3 h2.4 M3.1 3.7 h2.9" stroke="{P['soft']}" stroke-width="1" {NS}/>
</g></g>""")
    extra = f"""
.lock {{ animation: lock 7s ease-in-out 1.5s infinite; fill: {P['review']}; }}
@keyframes lock {{ 0%,78% {{ fill: {P['review']}; }} 86%,100% {{ fill: {P['pass']}; }} }}
.paper {{ opacity: 0; animation: post 7s ease-in 1.5s infinite; }}
@keyframes post {{ 0% {{ opacity: 0; transform: translateY(2.2px); }} 10% {{ opacity: 1; transform: translateY(2.2px); }}
                   45% {{ opacity: 1; transform: translateY(0); }} 55%,100% {{ opacity: 0; transform: translateY(0); }} }}
"""
    hot = [iso.p(10, 6, 6.4), iso.p(4.6, 10, 4.5), iso.p(10, 3, 2.4), iso.p(7.6, 10, 1.6)]
    return dict(
        title="Kernelridge attestation",
        desc="A vault with a turning combination dial and a SHA-256 digest plate; a report "
             "is posted into its slot. The report is canonicalised and hashed, signed with "
             "Ed25519 through the system openssl, saved to a local SQLite store, and reported "
             "as unsigned when openssl is missing.",
        drawing="\n".join(d), extra_css=extra,
        fig_name="ATTESTATION", command="kernelridge attest --input --private",
        kicker="05 · SIGNED REPORTS", heading="Tamper-evident, never over-claimed",
        rows=[("report", "canonical JSON → sha256 digest", "DIGEST"),
              ("attest --private key.pem", "Ed25519 via the system openssl", "SIGNED"),
              ("store save --db", "local SQLite history, keyed by digest", "STORED"),
              ("no openssl on PATH", "signed: false, with an explicit note", "UNSIGNED")],
        hotspots=hot,
        summary="verify --public key.pub → valid: true",
    )


FIGURES = [
    ("preflight", fig_preflight),
    ("verdicts", fig_verdicts),
    ("invalidation", fig_invalidation),
    ("experiment-plan", fig_plan),
    ("attestation", fig_attestation),
]


def main() -> None:
    P = PALETTES["light"]
    for old in OUT.glob("*.svg"):
        old.unlink()
    for no, (name, fn) in enumerate(FIGURES, 1):
        svg = sheet(P, fig_no=no, **fn(P))
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
        print(f"wrote assets/diagrams/{name}.svg")


if __name__ == "__main__":
    main()
