"""Turn a built page body into Markdown, for the files AI agents read (llms.txt, *.md copies).

Stdlib only. It handles the HTML this site uses: headings, paragraphs, lists, tables, code blocks,
definition lists, figures and the callout/card/pinout wrappers. Navigation, share buttons and other
page chrome are dropped.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP_CLASSES = {"share-row", "kicker", "copy"}
SKIP_TAGS = {"script", "style", "nav", "button", "svg"}
BLOCK = {"p", "ul", "ol", "table", "pre", "figure", "dl", "h1", "h2", "h3", "h4", "div", "details"}


class _MD(HTMLParser):
    def __init__(self, page_url: str, local_md: bool):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.local_md = local_md
        self.out: list[str] = []
        self.skip = 0
        self.skip_stack: list[bool] = []
        self.link: list[str | None] = []
        self.lists: list[list] = []  # [kind, counter]
        self.pre = False
        self.row: list[str] | None = None
        self.table: list[list[str]] = []
        self.cell: list[str] | None = None
        self.callout: str | None = None
        self.in_dt = False
        self.span_close: list[str] = []
        self.strong_first = False
        self.after_first = False

    # ---- helpers ----------------------------------------------------------------------------
    def emit(self, text: str) -> None:
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(text)
        else:
            self.out.append(text)

    def newline(self) -> None:
        if self.skip or self.cell is not None or not self.out:
            return
        if not "".join(self.out[-2:]).endswith("\n"):
            self.out.append("\n")

    def blank(self) -> None:
        if self.skip or self.cell is not None:
            return
        joined = "".join(self.out[-3:])
        if not joined.endswith("\n\n") and self.out:
            self.out.append("\n" if joined.endswith("\n") else "\n\n")

    def url(self, href: str) -> str:
        if href.startswith(("mailto:", "tel:", "javascript:")):
            return href
        full = urljoin(self.page_url, href) if self.page_url else href
        path, hash_, frag = full.partition("#")
        if self.local_md and path.endswith(".html") and self.page_url and \
                path.startswith(self.page_url.split("/", 3)[0] + "//" + self.page_url.split("/", 3)[2]):
            path = path[:-5] + ".md"
        elif self.local_md and path.endswith("/") and self.page_url and \
                path.startswith(self.page_url.split("/", 3)[0] + "//" + self.page_url.split("/", 3)[2]):
            path += "index.md"
        return path + hash_ + frag

    # ---- parser callbacks ---------------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        skip = tag in SKIP_TAGS or bool(classes & SKIP_CLASSES) or a.get("aria-hidden") == "true"
        void = tag in {"br", "img", "hr", "meta", "link", "input"}
        if not void:
            self.skip_stack.append(skip)
        if skip and not void:
            self.skip += 1
        if self.skip:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self.blank()
            self.emit("#" * int(tag[1]) + " ")
        elif tag == "p":
            self.blank()
        elif tag in {"ul", "ol"}:
            self.blank() if not self.lists else self.emit("\n")
            self.lists.append([tag, 0])
        elif tag == "li":
            kind = self.lists[-1] if self.lists else ["ul", 0]
            kind[1] += 1
            marker = f"{kind[1]}. " if kind[0] == "ol" else "- "
            self.emit("\n" if "".join(self.out[-1:]) and not "".join(self.out[-1:]).endswith("\n") else "")
            self.emit("  " * (len(self.lists) - 1) + marker)
        elif tag == "pre":
            self.blank()
            self.emit("```\n")
            self.pre = True
        elif tag == "code" and not self.pre:
            self.emit("`")
        elif tag in {"strong", "b"}:
            self.strong_first = bool(self.out) and bool(re.fullmatch(r"\s*(?:\d+\.|-) ", self.out[-1]))
            self.emit("**")
        elif tag in {"em", "i"}:
            self.emit("*")
        elif tag == "small":
            self.emit(" (")
        elif tag == "a":
            href = a.get("href")
            self.link.append(self.url(href) if href else None)
            self.emit("[")
        elif tag == "br":
            self.emit("  \n" if self.cell is None else " ")
        elif tag == "img":
            if a.get("alt"):
                self.emit(f"*[Image: {a['alt']}]*")
        elif tag == "table":
            self.blank()
            self.table = []
        elif tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell = []
        elif tag == "dt":
            self.newline()
            self.emit("- **")
            self.in_dt = True
        elif tag == "dl":
            self.blank()
        elif tag == "dd":
            self.emit(": ")
        elif tag == "figcaption":
            self.blank()
            self.emit("*")
        elif tag == "div" and "callout" in classes:
            self.blank()
            self.emit("> ")
            self.callout = "> "
        elif tag in {"div", "details", "figure"}:
            self.blank()
        elif tag == "span":
            if "badge" in classes or "pin" in classes or "tag" in classes:
                self.emit("[")
                self.span_close.append("] ")
            elif "title" in classes and self.callout:
                self.emit("**")
                self.span_close.append("**\n> ")
            else:
                self.span_close.append("")

    def handle_endtag(self, tag):
        void = tag in {"br", "img", "hr", "meta", "link", "input"}
        if void:
            return
        skipped = self.skip_stack.pop() if self.skip_stack else False
        if skipped:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag in {"h1", "h2", "h3", "h4", "p"}:
            self.emit("\n")
        elif tag in {"ul", "ol"}:
            self.lists.pop()
            self.emit("\n")
        elif tag == "pre":
            self.pre = False
            text = "".join(self.out)
            if not text.endswith("\n"):
                self.emit("\n")
            self.emit("```\n")
        elif tag == "code" and not self.pre:
            self.emit("`")
        elif tag in {"strong", "b"}:
            self.emit("**")
            self.after_first = self.strong_first
            self.strong_first = False
        elif tag in {"em", "i"}:
            self.emit("*")
        elif tag == "small":
            self.emit(")")
        elif tag == "a":
            href = self.link.pop() if self.link else None
            self.emit(f"]({href})" if href else "]")
        elif tag in {"td", "th"} and self.cell is not None:
            text = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|")
            if self.row is not None:
                self.row.append(text)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table":
            self.flush_table()
        elif tag == "dt":
            self.emit("**")
            self.in_dt = False
        elif tag == "dd":
            self.emit("\n")
        elif tag == "dl":
            self.emit("\n")
        elif tag == "figcaption":
            self.emit("*\n")
        elif tag == "div" and self.callout is not None:
            self.callout = None
            self.emit("\n")
        elif tag == "span":
            if self.span_close:
                self.emit(self.span_close.pop())

    def handle_data(self, data):
        if self.skip:
            return
        if self.pre:
            self.emit(data)
            return
        text = re.sub(r"\s+", " ", data)
        if self.after_first and text and not text[0].isspace() and text[0].isalnum():
            self.emit(". ")
        self.after_first = False
        if not text.strip() and (not self.out or self.out[-1].endswith("\n")) and self.cell is None:
            return
        if self.callout and self.out and self.out[-1].endswith("\n") and not text.strip() == "":
            self.emit(self.callout)
        self.emit(text)

    def flush_table(self) -> None:
        rows = [r for r in self.table if r]
        self.table = []
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        self.out.append("\n".join(lines) + "\n\n")


def html_to_markdown(body: str, page_url: str = "", local_md: bool = True) -> str:
    parser = _MD(page_url, local_md)
    parser.feed(body)
    parser.close()
    text = "".join(parser.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Badge/pin brackets were opened as "[" without a link: close them with their text, plain.
    return text.strip() + "\n"
