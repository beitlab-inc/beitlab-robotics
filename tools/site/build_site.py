#!/usr/bin/env python3
"""Build the Beitlab Robotics website (site/ -> build/site/) for GitHub Pages.

Sources live in site/:
  site.json            name, optional repo_url, linkedin_url and base_url, and the docs navigation
  _layouts/*.html      page shells; {{content}}, {{title}}, {{root}} ... are filled in here
  pages/**/*.html      one file per page, starting with a <!--meta ... --> block
  assets/              CSS, JS and images, copied as they are

Inside a page or layout:
  {{root}}             relative path to the site root ("", "../", "../../"), so the site works
                       both at user.github.io/repo/ and on a custom domain
  {{repo:PATH}}        copies the product file PATH into the site (files/PATH) and gives its URL. It is
                       read from the sibling project, or from site/product/PATH when that project is
                       not checked out (CI)
  {{size:PATH}}        that file's size, e.g. "4.2 MB"
  {{include:NAME}}     the shared fragment site/_layouts/NAME (header, footer)
  {{mdtable:PATH}}     the first Markdown table in repository file PATH, as HTML (generated lists)
  <!--optional--> ... <!--/optional-->
                       dropped, with a note, when a {{repo:}} file inside it does not exist
                       (large videos, for example, may not be checked in)

The build fails on a missing required file, an unknown placeholder, or a local link or #anchor
that does not resolve. Run:  python3 tools/site/build_site.py [--serve] [--posters]
"""

from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import re
import shutil
import sys
from datetime import date
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROBOT_ROOT = Path(os.environ.get("ROBOT_ROOT", ROOT.parent / "Balanced_robot")).resolve()
BOARD_ROOT = Path(os.environ.get("BOARD_ROOT", ROOT.parent / "Robotics_board")).resolve()
SITE = ROOT / "site"
# Copies of the product files the pages link to, for builds without the sibling projects (CI).
# A file in the sibling project is always used when it exists, so a local build sees fresh outputs.
PRODUCT = SITE / "product"
OUT = ROOT / "build" / "site"

META_RE = re.compile(r"\A\s*<!--meta\s*\n(.*?)\n\s*-->\s*\n", re.S)
OPTIONAL_RE = re.compile(r"<!--optional-->(.*?)<!--/optional-->", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)(?::([^}]+))?\s*\}\}")
H2_RE = re.compile(r'<h2 id="([^"]+)"[^>]*>(.*?)</h2>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def md_inline(text: str) -> str:
    text = html.escape(text.strip())
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def md_table(markdown: str, where: str) -> str:
    """The first Markdown table in a file, as the site's HTML table."""
    rows = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        sys.exit(f"{where}: no Markdown table found")
    cells = [[c for c in r.strip("|").split("|")] for r in rows]
    head, body = cells[0], [r for r in cells[2:]]
    th = "".join(f"<th>{md_inline(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def parse_meta(text: str, path: Path) -> tuple[dict, str]:
    m = META_RE.match(text)
    if not m:
        sys.exit(f"{path}: missing <!--meta ... --> block")
    meta = {}
    for line in m.group(1).splitlines():
        if line.strip():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    for key in ("title", "description", "layout"):
        if key not in meta:
            sys.exit(f"{path}: meta has no '{key}'")
    return meta, text[m.end():]


class Builder:
    def __init__(self, config: dict):
        self.config = config
        self.copied: dict[str, Path] = {}
        self.dropped: list[str] = []
        self.nav = [item for group in config["docs_nav"] for item in group["items"]]

    # ---- repository files -------------------------------------------------------------------
    def repo_file(self, rel: str) -> Path:
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            sys.exit(f"Invalid product asset path: {rel}")
        owner = BOARD_ROOT if path.parts[0] == "hardware" else ROBOT_ROOT
        if path.parts[0] not in {"hardware", "design", "docs"}:
            sys.exit(f"Unsupported product asset path: {rel}")
        src = (owner / path).resolve()
        if not src.is_relative_to(owner):
            sys.exit(f"Product asset escapes its source project: {rel}")
        if not src.is_file() and (PRODUCT / path).is_file():
            return PRODUCT / path
        return src

    def copy_repo(self, rel: str) -> str:
        src = self.repo_file(rel)
        if not src.is_file():
            raise FileNotFoundError(rel)
        dst = OUT / "files" / rel
        if rel not in self.copied:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            self.copied[rel] = dst
        return "files/" + rel

    # ---- templating ---------------------------------------------------------------------------
    def fill(self, text: str, values: dict, root: str, where: str) -> str:
        def optional(m: re.Match) -> str:
            block = m.group(1)
            for name, arg in PLACEHOLDER_RE.findall(block):
                if name in ("repo", "size") and not self.repo_file(arg.strip()).is_file():
                    self.dropped.append(f"{where}: {arg.strip()} (optional block left out)")
                    return ""
            return block

        text = OPTIONAL_RE.sub(optional, text)

        def sub(m: re.Match) -> str:
            name, arg = m.group(1), (m.group(2) or "").strip()
            if name == "root":
                return root
            if name == "include":
                return self.fill((SITE / "_layouts" / arg).read_text(encoding="utf-8"), values, root, where)
            if name == "repo":
                try:
                    return root + self.copy_repo(arg)
                except FileNotFoundError:
                    sys.exit(f"{where}: required file {arg} does not exist (wrap it in <!--optional-->)")
            if name == "mdtable":
                src = self.repo_file(arg)
                if not src.is_file():
                    sys.exit(f"{where}: {{{{mdtable:{arg}}}}}: no such file")
                return md_table(src.read_text(encoding="utf-8"), f"{where}: {arg}")
            if name == "size":
                src = self.repo_file(arg)
                if not src.is_file():
                    sys.exit(f"{where}: {{{{size:{arg}}}}}: no such file")
                return human_size(src.stat().st_size)
            if name in values:
                return values[name]
            sys.exit(f"{where}: unknown placeholder {m.group(0)}")

        # Two passes: layouts insert {{content}}, whose own placeholders were filled already.
        return PLACEHOLDER_RE.sub(sub, text)

    def sidebar(self, current: str) -> str:
        parts = []
        for group in self.config["docs_nav"]:
            parts.append(f'<div class="side-group"><p class="side-title">{html.escape(group["title"])}</p><ul>')
            for item in group["items"]:
                active = ' aria-current="page"' if item["page"] == current else ""
                parts.append(f'<li><a href="{{{{root}}}}{item["page"]}"{active}>{html.escape(item["label"])}</a></li>')
            parts.append("</ul></div>")
        return "\n".join(parts)

    def toc(self, content: str) -> str:
        items = [(i, TAG_RE.sub("", t).strip()) for i, t in H2_RE.findall(content)]
        if not items:
            return ""
        links = "\n".join(f'<li><a href="#{i}">{html.escape(html.unescape(t))}</a></li>' for i, t in items)
        return f'<nav class="toc" aria-label="On this page"><p class="side-title">On this page</p><ul>{links}</ul></nav>'

    def pager(self, current: str) -> str:
        pages = [i["page"] for i in self.nav]
        if current not in pages:
            return ""
        k = pages.index(current)
        out = ['<nav class="pager" aria-label="Previous and next">']
        if k > 0:
            p = self.nav[k - 1]
            out.append(f'<a class="prev" href="{{{{root}}}}{p["page"]}"><span>Previous</span>{html.escape(p["label"])}</a>')
        else:
            out.append("<span></span>")
        if k + 1 < len(pages):
            n = self.nav[k + 1]
            out.append(f'<a class="next" href="{{{{root}}}}{n["page"]}"><span>Next</span>{html.escape(n["label"])}</a>')
        out.append("</nav>")
        return "".join(out)

    def build_page(self, path: Path) -> None:
        rel = path.relative_to(SITE / "pages").as_posix()
        meta, body = parse_meta(path.read_text(encoding="utf-8"), path)
        depth = rel.count("/")
        root = "../" * depth
        cfg = self.config
        if rel == "404.html":
            # GitHub Pages serves 404.html at whatever path was missing, so relative links break;
            # use the site's absolute address once it is known, else the domain root.
            root = cfg["base_url"].rstrip("/") + "/" if cfg.get("base_url") else "/"
        repo_link = (f'<a class="nav-ext" href="{html.escape(cfg["repo_url"])}">GitHub</a>'
                     if cfg.get("repo_url") else "")
        linkedin = html.escape(cfg.get("linkedin_url") or "")
        linkedin_link = (f'<a class="nav-ext" href="{linkedin}" target="_blank" rel="noopener">LinkedIn</a>'
                         if linkedin else "")
        canonical = (f'<link rel="canonical" href="{html.escape(cfg["base_url"].rstrip("/") + "/" + rel.removesuffix("index.html"))}">'
                     if cfg.get("base_url") else "")
        values = {
            "title": html.escape(meta["title"]),
            "description": html.escape(meta["description"]),
            "site_name": html.escape(cfg["name"]),
            "year": str(date.today().year),
            "built": date.today().isoformat(),
            "repo_link": repo_link,
            "linkedin": linkedin,
            "linkedin_link": linkedin_link,
            "canonical": canonical,
            "section": meta.get("section", ""),
            "page": rel,
        }
        content = self.fill(body, values, root, rel)
        layout = (SITE / "_layouts" / f'{meta["layout"]}.html').read_text(encoding="utf-8")
        values.update({
            "sidebar": self.fill(self.sidebar(rel), values, root, rel),
            "toc": self.toc(content),
            "pager": self.fill(self.pager(rel), values, root, rel),
            "nav_" + meta.get("section", "none"): ' aria-current="page"',
        })
        for key in ("nav_home", "nav_robot", "nav_board", "nav_docs"):
            values.setdefault(key, "")
        page = self.fill(layout.replace("{{content}}", "\0CONTENT\0"), values, root, f"{rel} (layout)")
        page = page.replace("\0CONTENT\0", content)
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(page, encoding="utf-8")

    # ---- checks -----------------------------------------------------------------------------
    def check_links(self) -> list[str]:
        errors = []
        ids: dict[Path, set[str]] = {}
        # 404.html uses absolute links (see build_page); everything else must resolve relatively.
        pages = [p for p in OUT.rglob("*.html")
                 if "files" not in p.relative_to(OUT).parts and p.name != "404.html"]

        def anchors(p: Path) -> set[str]:
            if p not in ids:
                ids[p] = set(re.findall(r'\sid="([^"]+)"', p.read_text(encoding="utf-8")))
            return ids[p]

        for page in pages:
            text = page.read_text(encoding="utf-8")
            for attr, url in re.findall(r'\s(href|src|poster|srcset)="([^"]*)"', text):
                url = html.unescape(url).split(" ")[0]
                if not url or re.match(r"^[a-z]+:", url) or url.startswith("//"):
                    continue
                target, _, frag = url.partition("#")
                dest = page if not target else (page.parent / target).resolve()
                if target and dest.is_dir():
                    dest = dest / "index.html"
                if not dest.exists():
                    errors.append(f"{page.relative_to(OUT)}: {attr}={url} not found")
                elif frag and dest.suffix == ".html" and frag not in anchors(dest):
                    errors.append(f"{page.relative_to(OUT)}: #{frag} not found in {dest.relative_to(OUT)}")
        return errors

    def run(self) -> None:
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        shutil.copytree(SITE / "assets", OUT / "assets")
        for page in sorted((SITE / "pages").rglob("*.html")):
            self.build_page(page)
        (OUT / ".nojekyll").write_text("")
        if self.config.get("base_url"):
            base = self.config["base_url"].rstrip("/")
            urls = sorted(p.relative_to(OUT).as_posix().removesuffix("index.html")
                          for p in OUT.rglob("*.html") if p.name != "404.html" and "files" not in p.parts)
            (OUT / "sitemap.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join(f"  <url><loc>{base}/{u}</loc></url>\n" for u in urls) + "</urlset>\n")
        errors = self.check_links()
        total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
        print(f"site: {len(list(OUT.rglob('*.html')))} pages, {len(self.copied)} repository files, "
              f"{human_size(total)} -> {OUT.relative_to(ROOT)}")
        for note in self.dropped:
            print(f"  note: {note}")
        if errors:
            print("\n".join("  error: " + e for e in errors))
            sys.exit(f"site: {len(errors)} broken link(s)")


def make_posters() -> None:
    """Refresh the video stills in site/assets/img from the videos in site/assets/video (needs opencv)."""
    import cv2

    video = SITE / "assets" / "video"
    img = SITE / "assets/img"
    jobs = [  # (video, second, crop x0, y0, x1, y1 in 1920x1080, width, output)
        ("beitlab_balance_robot_v1_promo.mp4", 52.0, 360, 30, 1560, 990, 1200, "hero-robot.jpg"),       # hero (46.5-53.5 s), front view
        ("beitlab_balance_robot_v1_promo.mp4", 52.0, 0, 0, 1920, 1080, 1280, "promo-poster.jpg"),
    ]
    for name, t, x0, y0, x1, y1, width, out in jobs:
        cap = cv2.VideoCapture(str(video / name))
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            sys.exit(f"posters: cannot read {name} at {t} s")
        frame = frame[y0:y1, x0:x1]
        h = round(frame.shape[0] * width / frame.shape[1])
        cv2.imwrite(str(img / out), cv2.resize(frame, (width, h), interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 84])
        print(f"posters: {out} from {name} at {t} s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--serve", action="store_true", help="serve build/site on http://localhost:8000 after building")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--posters", action="store_true", help="refresh the video stills first (needs opencv)")
    args = ap.parse_args()
    if args.posters:
        make_posters()
    Builder(json.loads((SITE / "site.json").read_text(encoding="utf-8"))).run()
    if args.serve:
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print(f"serving http://localhost:{args.port}/ (Ctrl-C to stop)")
        with http.server.ThreadingHTTPServer(("", args.port), handler) as srv:
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
