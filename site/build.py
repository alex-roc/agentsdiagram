"""Build the generated parts of the website: docs/ -> site/docs/, examples/ -> site/demo/.

    uv run --group site python site/build.py

The Markdown in docs/ is the single source (GitHub shows the same files). Links between pages
are rewritten to .html, links to other repository files point to GitHub, and a paragraph that
is only a "▶ … /demo/x.html" link becomes an embedded live demo. The landing page (index.html)
is hand-written. Output folders are gitignored; .github/workflows/pages.yml runs this script.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import markdown
from pydantic import TypeAdapter

from agentsdiagram.analyze import analyze
from agentsdiagram.edit import plan_edit
from agentsdiagram.ir import EditRequest
from agentsdiagram.render.html import render as render_html

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DOCS = ROOT / "docs"
REPO = "https://github.com/alex-roc/agentsdiagram"
BASE_URL = "https://alex-roc.github.io/agentsdiagram/"

# (section, [(source relative to docs/, title in the navigation)])
PAGES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Start", [("getting-started.md", "Getting started")]),
    (
        "Tutorials",
        [
            ("tutorials/01-one-smolagents-agent.md", "1. One smolagents agent"),
            ("tutorials/02-one-pydantic-ai-agent.md", "2. One PydanticAI agent"),
            ("tutorials/03-teams-of-agents.md", "3. Teams of agents"),
            ("tutorials/04-plan-before-you-code.md", "4. Plan before you code"),
            ("tutorials/05-edit-from-the-diagram.md", "5. Edit from the diagram"),
            ("tutorials/06-ci-and-docs.md", "6. Diagrams in CI and docs"),
            ("tutorials/07-coding-agents.md", "7. With coding agents"),
        ],
    ),
    (
        "Guides",
        [
            ("editing.md", "Plan and edit"),
            ("cli.md", "Command line"),
            ("vscode.md", "VS Code extension"),
        ],
    ),
    (
        "Reference",
        [
            ("adapters/smolagents.md", "smolagents coverage"),
            ("adapters/pydantic_ai.md", "PydanticAI coverage"),
            ("ir.md", "IR and diagnostics"),
            ("architecture.md", "Architecture"),
            ("adding-a-framework.md", "Adding a framework"),
        ],
    ),
]

DEMOS = {
    "hello-smolagents": ("hello_smolagents", "hello_smolagents (smolagents)"),
    "hello-pydantic-ai": ("hello_pydantic_ai", "hello_pydantic_ai (PydanticAI)"),
    "research-team": ("research_team", "research_team (smolagents)"),
    "support-desk": ("support_desk", "support_desk (PydanticAI)"),
}

# Tutorial 4, replayed: the planning demo is made by the planner itself.
PLANNING = [
    {
        "op": "add_agent",
        "framework": "smolagents",
        "name": "booker",
        "file": "travel/agent.py",
        "parent": "smolagents:agent:travel.agent.assistant",
        "description": "Finds and books flights and hotels.",
    },
    {
        "op": "add_tool",
        "agent": "smolagents:agent:travel.agent.booker",
        "name": "search_flights",
        "params": "origin: str, destination: str, date: str",
        "returns": "list[dict]",
        "description": "Flights between two cities on a date.",
    },
    {"op": "add_mcp", "agent": "smolagents:agent:travel.agent.booker", "url": "https://maps.example.com/mcp"},
]


@dataclass
class Page:
    source: str  # relative to docs/
    title: str
    section: str

    @property
    def out(self) -> str:  # relative to site/docs/
        return self.source.removesuffix(".md") + ".html"


def all_pages() -> list[Page]:
    return [Page(src, title, section) for section, items in PAGES for src, title in items]


# ---------------------------------------------------------------------- demos


def build_demos() -> None:
    out = SITE / "demo"
    out.mkdir(parents=True, exist_ok=True)
    for slug, (folder, title) in DEMOS.items():
        project = analyze(ROOT / "examples" / folder)
        (out / f"{slug}.html").write_text(render_html(project, title=title), encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text('[project]\nname = "travel"\n')
        shutil.copytree(ROOT / "examples" / "hello_smolagents", root / "travel")
        adapter = TypeAdapter(EditRequest)
        for request in PLANNING:
            plan_edit(root, adapter.validate_python(request)).write()
        project = analyze(root)
        title = "travel (smolagents), planned"
        (out / "planning.html").write_text(render_html(project, title=title), encoding="utf-8")
    print(f"demos: {', '.join([*DEMOS, 'planning'])}")


# ---------------------------------------------------------------------- docs

THEME_SCRIPT = """<script>
  try {
    var t = localStorage.getItem("agentsdiagram.theme");
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
  } catch (e) {}
</script>"""

MARK = (
    '<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7"/>'
    '<path d="M10 10.5 22 16 10 21.5"/><circle cx="10" cy="10.5" r="3.2"/><circle cx="22" cy="16" r="3.2"/>'
    '<circle cx="10" cy="21.5" r="3.2"/></svg>'
)
THEME_BUTTON = (
    '<button class="theme" type="button" id="theme" aria-label="Switch to dark theme">'
    '<svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 '
    '10.5 10.5Z"/></svg><svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
    '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
    "</svg></button>"
)
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' "
    "height='32' rx='7' fill='%235b5bd6'/%3E%3Cpath d='M10 10.5 22 16 10 21.5' fill='none' stroke='%23fff' "
    "stroke-width='2'/%3E%3Ccircle cx='10' cy='10.5' r='3.2' fill='%23fff'/%3E%3Ccircle cx='22' cy='16' r='3.2' "
    "fill='%23fff'/%3E%3Ccircle cx='10' cy='21.5' r='3.2' fill='%23fff'/%3E%3C/svg%3E"
)


def rel(from_out: str, to_site_path: str) -> str:
    """Relative URL from a page in site/docs/<from_out> to site/<to_site_path>."""
    start = (SITE / "docs" / from_out).parent
    return Path(os.path.relpath(SITE / to_site_path, start)).as_posix()


def rewrite_links(body: str, page: Page, sources: set[str]) -> str:
    here = (DOCS / page.source).parent

    def fix(match: re.Match) -> str:
        attr, url = match.group(1), html.unescape(match.group(2))
        if re.match(r"^[a-z]+:|^#|^//", url):
            if url.startswith(BASE_URL):  # absolute links to this site stay inside it
                return f'{attr}="{rel(page.out, url.removeprefix(BASE_URL) or "index.html")}"'
            return match.group(0)
        path, _, anchor = url.partition("#")
        target = (here / path).resolve()
        anchor = f"#{anchor}" if anchor else ""
        try:
            in_docs = target.relative_to(DOCS).as_posix()
        except ValueError:
            in_docs = None
        if in_docs in sources:
            return f'{attr}="{rel(page.out, "docs/" + in_docs.removesuffix(".md") + ".html")}{anchor}"'
        if in_docs is not None and in_docs.startswith("images/"):
            return f'{attr}="{rel(page.out, "docs/" + in_docs)}"'
        repo_path = target.relative_to(ROOT).as_posix()
        kind = "tree" if target.is_dir() else "blob"
        return f'{attr}="{REPO}/{kind}/main/{repo_path}{anchor}"'

    return re.sub(r'(href|src)="([^"]+)"', fix, body)


def embed_demos(body: str, page: Page) -> str:
    def demo(match: re.Match) -> str:
        url, label = match.group(1), match.group(2)
        name = url.rsplit("/", 1)[-1]
        src = rel(page.out, f"demo/{name}")
        title = html.escape(re.sub(r"<[^>]+>", "", label).replace("▶", "").strip())
        return (
            f'<figure class="live"><iframe src="{src}" title="{title}" loading="lazy"></iframe>'
            "<figcaption><span>Live diagram, generated from the example by "
            '<span class="mono">agentsdiagram scan</span>.</span> '
            f'<a href="{src}" target="_blank" rel="noopener">Open full screen</a></figcaption></figure>'
        )

    return re.sub(r'<p><a href="([^"]*/demo/[^"]+\.html)">(▶[^<]*)</a></p>', demo, body)


def nav(current: Page, pages: list[Page]) -> str:
    parts = []
    for section, _ in PAGES:
        items = []
        for p in pages:
            if p.section != section:
                continue
            here = ' aria-current="page"' if p is current else ""
            items.append(f'<li><a href="{rel(current.out, "docs/" + p.out)}"{here}>{html.escape(p.title)}</a></li>')
        parts.append(f"<h2>{section}</h2><ul>{''.join(items)}</ul>")
    return "".join(parts)


def describe(body: str) -> str:
    match = re.search(r"<p>(.*?)</p>", body, re.S)
    text = re.sub(r"<[^>]+>", "", match.group(1)) if match else ""
    text = " ".join(html.unescape(text).split())
    return text[:200].rsplit(" ", 1)[0] + "…" if len(text) > 200 else text


def render_page(page: Page, pages: list[Page], sources: set[str]) -> str:
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "codehilite", "sane_lists"],
        extension_configs={
            "codehilite": {"css_class": "hl", "guess_lang": False},
            "toc": {"permalink": "#", "permalink_class": "anchor", "permalink_title": "Link to this section"},
        },
    )
    text = (DOCS / page.source).read_text(encoding="utf-8")
    body = md.convert(text)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    heading = re.sub(r"<[^>]+>", "", h1.group(1)).replace("#", "").strip() if h1 else page.title
    body = embed_demos(rewrite_links(body, page, sources), page)
    index = pages.index(page)
    prev_page = pages[index - 1] if index > 0 else None
    next_page = pages[index + 1] if index + 1 < len(pages) else None
    pager = '<nav class="pager" aria-label="Previous and next">'
    for cls, label, other in (("prev", "Previous", prev_page), ("next", "Next", next_page)):
        if other is not None:
            href = rel(page.out, "docs/" + other.out)
            pager += f'<a class="{cls}" href="{href}"><span>{label}</span>{html.escape(other.title)}</a>'
    pager += "</nav>"
    home = rel(page.out, "index.html")
    css = rel(page.out, "style.css")
    description = html.escape(describe(body))
    url = f"{BASE_URL}docs/{page.out}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(heading)} · agentsdiagram</title>
<meta name="description" content="{description}">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{html.escape(heading)} · agentsdiagram">
<meta property="og:description" content="{description}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE_URL}og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{FAVICON}">
{THEME_SCRIPT}
<link rel="stylesheet" href="{css}">
</head>
<body class="docs-page">
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap top-row">
    <a class="brand" href="{home}" aria-label="agentsdiagram home">{MARK}<span>agentsdiagram</span></a>
    <nav class="nav" aria-label="Main">
      <a href="{rel(page.out, "docs/getting-started.html")}">Docs</a>
      <a href="{rel(page.out, "docs/tutorials/01-one-smolagents-agent.html")}">Tutorials</a>
      <a href="{REPO}">GitHub</a>
      {THEME_BUTTON}
    </nav>
  </div>
</header>
<div class="wrap docs">
  <details class="docs-nav" open>
    <summary>Documentation</summary>
    <nav aria-label="Documentation">{nav(page, pages)}</nav>
  </details>
  <main id="main" class="prose">
    {body}
    <p class="edit"><a href="{REPO}/edit/main/docs/{page.source}">Edit this page on GitHub</a></p>
    {pager}
  </main>
</div>
<footer class="foot">
  <div class="wrap foot-row">
    <span>MIT © 2026 Alex Ojeda Copa</span>
    <span class="foot-links"><a href="{REPO}">GitHub</a><a href="{REPO}/blob/main/CHANGELOG.md">Changelog</a><a href="https://pypi.org/project/agentsdiagram/">PyPI</a></span>
  </div>
</footer>
<script src="{rel(page.out, "site.js")}"></script>
</body>
</html>
"""


def build_docs() -> None:
    out = SITE / "docs"
    if out.exists():
        shutil.rmtree(out)
    pages = all_pages()
    sources = {p.source for p in pages}
    for page in pages:
        target = out / page.out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_page(page, pages, sources), encoding="utf-8")
    shutil.copytree(DOCS / "images", out / "images")
    (out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=getting-started.html">'
        '<link rel="canonical" href="getting-started.html"><title>agentsdiagram docs</title>'
        '<a href="getting-started.html">Getting started</a>\n',
        encoding="utf-8",
    )
    urls = [BASE_URL, *[f"{BASE_URL}docs/{p.out}" for p in pages]]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )
    print(f"docs: {len(pages)} pages")


if __name__ == "__main__":
    build_demos()
    build_docs()
