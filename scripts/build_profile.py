"""Build the neofetch-style profile card (dark_mode.svg / light_mode.svg)
and the link buttons, pulling live numbers from the GitHub API.

Standard library only. Token comes from ACCESS_TOKEN or GITHUB_TOKEN.

    python scripts/build_profile.py            # fetch stats + render
    python scripts/build_profile.py --offline  # render from cached stats
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
USER = "nikhilswain"
JOINED = dt.date(2018, 6, 5)  # "uptime" counts from here

# ---------------------------------------------------------------- content
HEADER = "zero@zerro.dev"
SECTIONS = [
    [
        ("OS", "Windows, Linux"),
        ("Uptime", "{uptime}"),
        ("Host", "zerro.dev"),
        ("Kernel", "Frontend Developer"),
        ("IDE", "VSCode, Cursor, Claude Code"),
    ],
    [
        ("Languages.Code", "TypeScript, JavaScript"),
        ("Languages.Web", "HTML, CSS, Tailwind, Sass"),
        ("Stack.Frontend", "React, Next.js, Astro"),
        ("Stack.Backend", "Node.js, NestJS, Express"),
        ("Stack.Data", "PostgreSQL, MongoDB, Supabase"),
    ],
    [
        ("Focus.Day", "SaaS, dev tools, UI engineering"),
        ("Focus.Night", "Game dev"),
        ("Loop", "ship -> break -> fix -> repeat"),
        ("Motto", "Hesitation is defeat"),
    ],
]
CONTACT = [
    ("Email", "nikhilswain36@gmail.com"),
    ("X", "@iamn1khil"),
    ("LinkedIn", "nikhil-kumar-swain"),
    ("Portfolio", "zerro.dev"),
]

BUTTONS = [
    ("portfolio", "PORTFOLIO", "https://zerro.dev"),
    ("linkedin", "LINKEDIN", "https://www.linkedin.com/in/nikhil-kumar-swain-408110152/"),
    ("x", "X / TWITTER", "https://x.com/iamn1khil"),
    ("email", "EMAIL", "mailto:nikhilswain36@gmail.com"),
]

THEMES = {
    "dark": dict(bg="#0d1117", card="#161b22", border="#30363d", key="#ffa657",
                 value="#a5d6ff", dot="#616e7f", text="#c9d1d9", add="#3fb950",
                 dele="#f85149", ink="#2f3742", ink_char=".", accent="#ffa657"),
    "light": dict(bg="#ffffff", card="#f6f8fa", border="#d0d7de", key="#953800",
                  value="#0a3069", dot="#8c959f", text="#24292f", add="#1a7f37",
                  dele="#cf222e", ink="#24292f", ink_char=None, accent="#bc4c00"),
}

FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
TEXT_SIZE = 15
LINE_H = 20
CHAR_W = TEXT_SIZE * 0.602  # monospace advance
TEXT_COLS = 58               # width of the info panel in characters
ART_SIZE = 10
ART_LINE_H = 11


# ---------------------------------------------------------------- stats
def token():
    return os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def request(url, body=None):
    headers = {"Authorization": f"bearer {token()}", "User-Agent": "profile-card",
               "Accept": "application/vnd.github+json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read() or b"null")


def gql(query, **variables):
    _, res = request("https://api.github.com/graphql", {"query": query, "variables": variables})
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    return res["data"]


def fetch_stats():
    repos, cursor = [], None
    while True:
        d = gql("""query($login:String!,$after:String){user(login:$login){
              followers{totalCount}
              repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){totalCount}
              repositories(ownerAffiliations:OWNER, privacy:PUBLIC, first:100, after:$after){
                pageInfo{hasNextPage endCursor}
                nodes{name stargazerCount isFork}}}}""", login=USER, after=cursor)["user"]
        page = d["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    commits = 0
    for year in range(JOINED.year, dt.date.today().year + 1):
        c = gql("""query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
              contributionsCollection(from:$from,to:$to){totalCommitContributions restrictedContributionsCount}}}""",
                login=USER, **{"from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        cc = c["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]

    added = deleted = 0
    for repo in (r for r in repos if not r["isFork"]):
        url = f"https://api.github.com/repos/{USER}/{repo['name']}/stats/contributors"
        for _ in range(8):  # GitHub answers 202 while it computes the stats
            try:
                status, body = request(url)
            except urllib.error.HTTPError:
                status, body = 0, None
                break
            if status == 200:
                break
            time.sleep(3)
        for author in body or []:
            if (author.get("author") or {}).get("login", "").lower() == USER.lower():
                added += sum(w["a"] for w in author["weeks"])
                deleted += sum(w["d"] for w in author["weeks"])

    return {
        "repos": len(repos),
        "contributed": d["repositoriesContributedTo"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": d["followers"]["totalCount"],
        "commits": commits,
        "added": added,
        "deleted": deleted,
    }


def uptime(today=None):
    today = today or dt.date.today()
    y, m, d = today.year - JOINED.year, today.month - JOINED.month, today.day - JOINED.day
    if d < 0:
        m -= 1
        prev = (today.replace(day=1) - dt.timedelta(days=1))
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(y, 'year')}, {plural(m, 'month')}, {plural(d, 'day')}"


# ---------------------------------------------------------------- svg helpers
def span(text, cls):
    return f'<tspan class="{cls}">{escape(text)}</tspan>'


def kv_line(key, value, width=TEXT_COLS):
    """'. Key: ....... value' padded to the panel width."""
    keyparts = key.split(".")
    key_len = len(key) + 1  # ':'
    dots = width - 2 - key_len - 2 - len(value)
    out = span(". ", "dot")
    for i, part in enumerate(keyparts):
        if i:
            out += span(".", "text")
        out += span(part, "key")
    out += span(":", "text") + " " + span("." * max(dots, 2), "dot") + " " + span(value, "value")
    return out


def rule_line(title, width=TEXT_COLS):
    prefix = f"- {title} " if title else ""
    return span("- ", "text") + span(title + " ", "text") + span("—" * (width - len(prefix) - 2) + "-", "dot")


def stats_lines(s):
    f = lambda n: f"{n:,}"
    lines = []
    left = f"Repos: {'.' * 6} {f(s['repos'])} {{Contributed: {f(s['contributed'])}}}"
    right = f"Stars: {f(s['stars'])}"
    pad = TEXT_COLS - 2 - len(left) - 3 - len(right)
    lines.append(span(". ", "dot") + span("Repos", "key") + span(":", "text") + " " + span("." * 6, "dot")
                 + " " + span(f(s["repos"]), "value") + " " + span("{", "text") + span("Contributed", "key")
                 + span(": ", "text") + span(f(s["contributed"]), "value") + span("}", "text")
                 + span(" | ", "text") + span("Stars", "key") + span(":", "text") + " "
                 + span("." * max(pad - 1, 1), "dot") + " " + span(f(s["stars"]), "value"))

    left = f"Commits: {f(s['commits'])}"
    right = f"Followers: {f(s['followers'])}"
    half = (TEXT_COLS - 2) // 2
    pad_l = half - len("Commits: ") - len(f(s["commits"])) - 2
    pad_r = TEXT_COLS - 2 - half - len(" | ") - len("Followers: ") - len(f(s["followers"])) - 1
    lines.append(span(". ", "dot") + span("Commits", "key") + span(":", "text") + " "
                 + span("." * max(pad_l, 1), "dot") + " " + span(f(s["commits"]), "value")
                 + span(" | ", "text") + span("Followers", "key") + span(":", "text") + " "
                 + span("." * max(pad_r, 1), "dot") + " " + span(f(s["followers"]), "value"))

    net = s["added"] - s["deleted"]
    tail = f"{f(net)} ( {f(s['added'])}++, {f(s['deleted'])}-- )"
    pad = TEXT_COLS - 2 - len("Lines of Code: ") - len(tail) - 1
    lines.append(span(". ", "dot") + span("Lines of Code", "key") + span(":", "text") + " "
                 + span("." * max(pad, 1), "dot") + " " + span(f(net), "value") + span(" ( ", "text")
                 + span(f"{f(s['added'])}++", "add") + span(", ", "text")
                 + span(f"{f(s['deleted'])}--", "del") + span(" )", "text"))
    return lines


def info_lines(stats):
    lines = [span(HEADER, "head") + " " + span("-" + "—" * (TEXT_COLS - len(HEADER) - 3) + "-", "dot")]
    for i, section in enumerate(SECTIONS):
        if i:
            lines.append(span(".", "dot"))
        for k, v in section:
            lines.append(kv_line(k, v.format(uptime=uptime())))
    lines.append(span(".", "dot"))
    lines.append(rule_line("Contact"))
    lines += [kv_line(k, v) for k, v in CONTACT]
    lines.append(span(".", "dot"))
    lines.append(rule_line("GitHub Stats"))
    lines += stats_lines(stats)
    return lines


def adjust(hex_, theme):
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    if theme == "light":  # darken so yellows/skin survive on white
        r, g, b = (int(c * 0.72) for c in (r, g, b))
    q = lambda c: min(255, (c // 12) * 12)  # quantise -> fewer tspans
    return "#%02x%02x%02x" % (q(r), q(g), q(b))


def art_lines(theme, colours):
    art = json.loads((ASSETS / "ascii.json").read_text())
    out = []
    for row in art["cells"]:
        runs, cur, buf = [], None, ""
        for ch, col in row:
            if col == "ink" and colours["ink_char"]:
                ch = colours["ink_char"]  # dark theme: black areas stay dark
            elif theme == "light" and col not in (None, "ink"):
                # on white, light pixels should be sparse glyphs, not dense ones
                r_, g_, b_ = (int(col[i:i + 2], 16) for i in (1, 3, 5))
                lum = (0.299 * r_ + 0.587 * g_ + 0.114 * b_) / 255
                ramp = ".:-=+*#"
                ch = ramp[min(len(ramp) - 1, int((1 - lum) * len(ramp) * 1.6))]
            c = None if ch == " " else (colours["ink"] if col == "ink" else adjust(col, theme))
            if c != cur and buf:
                runs.append((cur, buf))
                buf = ""
            cur = c
            buf += ch
        if buf:
            runs.append((cur, buf))
        out.append("".join(escape(t) if c is None else f'<tspan fill="{c}">{escape(t)}</tspan>' for c, t in runs))
    return out, art["cols"], art["rows"]


def render_card(theme, stats):
    c = THEMES[theme]
    lines = info_lines(stats)
    art, cols, rows = art_lines(theme, c)

    pad = 28
    art_w = cols * ART_SIZE * 0.602
    art_h = rows * ART_LINE_H
    text_x = pad + art_w + 36
    text_w = TEXT_COLS * CHAR_W
    width = round(text_x + text_w + pad)
    text_h = (len(lines) + 2) * LINE_H
    height = round(max(art_h, text_h) + pad * 2)
    art_y = pad + (height - pad * 2 - art_h) / 2 + ART_SIZE

    cursor_y = pad + LINE_H * (len(lines) + 1) + TEXT_SIZE
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="{FONT}">',
           "<style>",
           f".key{{fill:{c['key']}}}.value{{fill:{c['value']}}}.dot{{fill:{c['dot']}}}"
           f".text{{fill:{c['text']}}}.add{{fill:{c['add']}}}.del{{fill:{c['dele']}}}"
           f".head{{fill:{c['key']};font-weight:700}}",
           "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}.cursor{animation:blink 1.1s steps(1) infinite}",
           "</style>",
           f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="{c["card"]}" stroke="{c["border"]}"/>',
           f'<text x="{pad}" y="{art_y:.1f}" font-size="{ART_SIZE}" xml:space="preserve" fill="{c["text"]}">']
    for i, line in enumerate(art):
        svg.append(f'<tspan x="{pad}" dy="{0 if i == 0 else ART_LINE_H}">{line}</tspan>')
    svg.append("</text>")
    svg.append(f'<text x="{text_x:.1f}" y="{pad + TEXT_SIZE}" font-size="{TEXT_SIZE}" xml:space="preserve" class="text">')
    for i, line in enumerate(lines):
        svg.append(f'<tspan x="{text_x:.1f}" dy="{0 if i == 0 else LINE_H}">{line}</tspan>')
    svg.append("</text>")
    svg.append(f'<text x="{text_x:.1f}" y="{cursor_y}" font-size="{TEXT_SIZE}" fill="{c["accent"]}">&gt;</text>')
    svg.append(f'<rect class="cursor" x="{text_x + CHAR_W * 2:.1f}" y="{cursor_y - TEXT_SIZE + 2}" '
               f'width="{CHAR_W:.1f}" height="{TEXT_SIZE + 2}" fill="{c["value"]}"/>')
    svg.append("</svg>")
    return "\n".join(svg)


ICONS = {
    # 24x24 line icons
    "portfolio": '<rect x="2" y="3" width="20" height="14" rx="1.5"/><path d="M6 8l3 2-3 2M11 12h5M8 21h8M12 17v4"/>',
    "linkedin": '<rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 10v7M7 7v.01M11 17v-7M11 13a3 3 0 0 1 6 0v4"/>',
    "x": '<path d="M4 4l16 16M20 4L4 20"/>',
    "email": '<rect x="2" y="5" width="20" height="14" rx="1.5"/><path d="M2 6l10 7 10-7"/>',
}


def render_button(theme, key, label):
    c = THEMES[theme]
    w, h = 220, 56
    text_w = len(label) * 15 * 0.602
    group_w = 24 + 12 + text_w
    x0 = (w - group_w) / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="8" fill="{c["card"]}" stroke="{c["border"]}" stroke-width="2"/>'
            f'<rect x="10" y="{h - 6}" width="{w - 20}" height="3" rx="1.5" fill="{c["accent"]}"/>'
            f'<g transform="translate({x0:.1f} {(h - 24) / 2 - 1})" fill="none" stroke="{c["accent"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[key]}</g>'
            f'<text x="{x0 + 36:.1f}" y="{h / 2 + 4}" font-size="15" letter-spacing="1" fill="{c["text"]}">{escape(label)}</text>'
            "</svg>")


def main():
    cache = ASSETS / "stats.json"
    stats = json.loads(cache.read_text()) if cache.exists() else None
    if "--offline" not in sys.argv:
        try:
            stats = fetch_stats()
            cache.write_text(json.dumps(stats, indent=2) + "\n")
        except Exception as e:  # keep the last good numbers
            print(f"stats fetch failed, using cache: {e}", file=sys.stderr)
    if stats is None:
        sys.exit("no stats available")

    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render_card(theme, stats), encoding="utf-8")
        for key, label, _ in BUTTONS:
            (ASSETS / f"btn_{key}_{theme}.svg").write_text(render_button(theme, key, label), encoding="utf-8")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
