"""
Offline, dependency-free static accessibility and responsive-markup auditor for
rendered HTML pages (WCAG 2.1 AA safety net; no axe-core, no network).
Used by tests and by `make a11y`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any


@dataclass(order=True)
class Issue:
    rule: str
    severity: str  # "error" or "warning"
    message: str
    snippet: str = ""
    page: str = ""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    text: str = ""
    children: list[Node] = field(default_factory=list)
    parent: Node | None = None

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def full_text(self) -> str:
        parts = [self.text]
        for ch in self.children:
            parts.append(ch.full_text())
        return " ".join(p.strip() for p in parts if p.strip()).strip()

    def iter_descendants(self):
        for ch in self.children:
            yield ch
            yield from ch.iter_descendants()

    def has_ancestor(self, tag_or_class: str) -> bool:
        cur = self.parent
        while cur is not None:
            if cur.tag == tag_or_class or tag_or_class in cur.classes():
                return True
            cur = cur.parent
        return False

    def snippet_str(self) -> str:
        attr_str = " ".join(f'{k}="{v}"' for k, v in list(self.attrs.items())[:4])
        return f"<{self.tag}{' ' + attr_str if attr_str else ''}>"


VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack: list[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}
        node = Node(tag_l, attr_dict, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag_l not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}
        node = Node(tag_l, attr_dict, parent=self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag_l:
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1].text += data


def _is_focusable(node: Node) -> bool:
    if "disabled" in node.attrs:
        return False
    tabindex = node.attrs.get("tabindex")
    if tabindex is not None:
        try:
            if int(tabindex) < 0:
                return False
        except ValueError:
            pass
    if node.tag == "a" and "href" in node.attrs:
        return True
    if node.tag in ("button", "select", "textarea", "summary"):
        return True
    if node.tag == "input" and node.get("type", "text").lower() != "hidden":
        return True
    if tabindex is not None:
        try:
            return int(tabindex) >= 0
        except ValueError:
            return False
    return False


def _accessible_name(
    node: Node, id_map: dict[str, Node], labels_by_for: dict[str, list[Node]]
) -> str:
    aria_label = node.get("aria-label").strip()
    if aria_label:
        return aria_label
    labelledby = node.get("aria-labelledby").strip()
    if labelledby:
        parts = [id_map[ref].full_text() for ref in labelledby.split() if ref in id_map]
        if any(parts):
            return " ".join(p for p in parts if p)
    node_id = node.get("id").strip()
    if node_id and node_id in labels_by_for:
        txt = " ".join(lbl.full_text() for lbl in labels_by_for[node_id]).strip()
        if txt:
            return txt
    cur = node.parent
    while cur is not None:
        if cur.tag == "label":
            txt = cur.full_text()
            if txt:
                return txt
        cur = cur.parent
    for img in node.iter_descendants():
        if img.tag == "img" and img.get("alt").strip():
            return img.get("alt").strip()
    txt = node.full_text()
    if txt:
        return txt
    if node.tag == "input" and node.get("type", "").lower() in ("submit", "button", "reset"):
        return node.get("value").strip()
    return ""


def audit_html(html: str, page: str = "") -> list[Issue]:
    """Parse an HTML document and evaluate all A11Y-01..22 and R-01..08 rules."""
    parser = TreeBuilder()
    parser.feed(html)
    root = parser.root
    all_nodes = list(root.iter_descendants())
    issues: list[Issue] = []

    def add(rule: str, message: str, node: Node | None = None, severity: str = "error") -> None:
        snip = node.snippet_str() if node is not None else ""
        issues.append(Issue(rule=rule, severity=severity, message=message, snippet=snip, page=page))

    # Build ID map & duplicate ID check (A11Y-10)
    id_map: dict[str, Node] = {}
    labels_by_for: dict[str, list[Node]] = {}
    for n in all_nodes:
        nid = n.get("id").strip()
        if nid:
            if nid in id_map:
                add("A11Y-10", f"Duplicate id={nid!r}.", n)
            else:
                id_map[nid] = n
        if n.tag == "label":
            for_id = n.get("for").strip()
            if for_id:
                labels_by_for.setdefault(for_id, []).append(n)

    # A11Y-01: html has non-empty lang
    html_nodes = [n for n in all_nodes if n.tag == "html"]
    if not html_nodes or not html_nodes[0].get("lang").strip():
        add(
            "A11Y-01",
            "<html> element must have a non-empty lang attribute.",
            html_nodes[0] if html_nodes else None,
        )

    # A11Y-02: non-empty title
    title_nodes = [n for n in all_nodes if n.tag == "title"]
    if not title_nodes or not title_nodes[0].full_text():
        add(
            "A11Y-02",
            "Document must have a non-empty <title>.",
            title_nodes[0] if title_nodes else None,
        )

    # A11Y-03 & A11Y-04: headings
    headings = [n for n in all_nodes if n.tag in ("h1", "h2", "h3", "h4", "h5", "h6")]
    h1s = [n for n in headings if n.tag == "h1"]
    if len(h1s) != 1:
        add(
            "A11Y-03",
            f"Expected exactly 1 <h1>, found {len(h1s)}.",
            h1s[1] if len(h1s) > 1 else None,
        )
    prev_level: int | None = None
    for h in headings:
        lvl = int(h.tag[1])
        if prev_level is not None and lvl > prev_level + 1:
            add("A11Y-04", f"Heading level skipped from <h{prev_level}> to <h{lvl}>.", h)
        prev_level = lvl

    # A11Y-05: landmarks (1 main, 1 header, 1 footer, named navs when > 1)
    mains = [n for n in all_nodes if n.tag == "main" or n.get("role") == "main"]
    headers = [
        n
        for n in all_nodes
        if n.tag == "header" and not n.has_ancestor("article") and not n.has_ancestor("section")
    ]
    footers = [
        n
        for n in all_nodes
        if n.tag == "footer" and not n.has_ancestor("article") and not n.has_ancestor("section")
    ]
    navs = [n for n in all_nodes if n.tag == "nav" or n.get("role") == "navigation"]
    if len(mains) != 1:
        add("A11Y-05", f"Expected 1 <main> landmark, found {len(mains)}.")
    if len(headers) != 1:
        add("A11Y-05", f"Expected 1 top-level <header> landmark, found {len(headers)}.")
    if len(footers) != 1:
        add("A11Y-05", f"Expected 1 top-level <footer> landmark, found {len(footers)}.")
    if len(navs) > 1:
        for nv in navs:
            if not (nv.get("aria-label").strip() or nv.get("aria-labelledby").strip()):
                add(
                    "A11Y-05",
                    "When multiple <nav> landmarks exist, each must have aria-label or aria-labelledby.",
                    nv,
                )

    # A11Y-06: first focusable element is a skip link whose #target exists
    focusables = [n for n in all_nodes if _is_focusable(n)]
    if not focusables:
        add("A11Y-06", "Page has no focusable elements.")
    else:
        first_f = focusables[0]
        href = first_f.get("href").strip()
        if first_f.tag != "a" or not href.startswith("#") or href[1:] not in id_map:
            add(
                "A11Y-06",
                "First focusable element must be a skip link whose #target id exists.",
                first_f,
            )

    # A11Y-07 & A11Y-22: form controls have accessible names (including inside tables)
    for n in all_nodes:
        if n.tag in ("input", "select", "textarea"):
            itype = n.get("type", "text").lower() if n.tag == "input" else ""
            if itype in ("hidden", "submit", "button", "reset"):
                continue
            name = _accessible_name(n, id_map, labels_by_for)
            if not name:
                if n.has_ancestor("table"):
                    add("A11Y-22", "Form input inside a table is missing an accessible label.", n)
                else:
                    add("A11Y-07", f"Form control <{n.tag}> is missing an accessible label.", n)

    # A11Y-08: buttons and links have accessible names (title alone is an error)
    for n in all_nodes:
        if n.tag in ("button", "a") or (
            n.tag == "input" and n.get("type", "").lower() in ("submit", "button")
        ):
            if n.tag == "a" and "href" not in n.attrs:
                continue
            name = _accessible_name(n, id_map, labels_by_for)
            if not name:
                add(
                    "A11Y-08",
                    f"<{n.tag}> has no accessible name (title alone is not sufficient).",
                    n,
                )

    # A11Y-09: img has alt
    for n in all_nodes:
        if n.tag == "img":
            if "alt" not in n.attrs:
                add("A11Y-09", "<img> is missing alt attribute.", n)
            elif (
                n.get("alt") == ""
                and n.get("role") != "presentation"
                and n.get("aria-hidden") != "true"
            ):
                add(
                    "A11Y-09",
                    "Empty alt on <img> requires role='presentation' or aria-hidden='true'.",
                    n,
                )

    # A11Y-11: aria-labelledby, aria-describedby, aria-controls, and label-for targets exist
    for n in all_nodes:
        for attr in ("aria-labelledby", "aria-describedby", "aria-controls"):
            val = n.get(attr).strip()
            if val:
                for ref in val.split():
                    if ref not in id_map:
                        add("A11Y-11", f"{attr} references missing id={ref!r}.", n)
        if n.tag == "label":
            for_ref = n.get("for").strip()
            if for_ref and for_ref not in id_map:
                add("A11Y-11", f"<label for={for_ref!r}> references a missing id.", n)

    # A11Y-12: th has scope or headers; data tables have caption or aria-label
    for tbl in (n for n in all_nodes if n.tag == "table"):
        t_classes = tbl.classes()
        is_static = "table-static" in t_classes
        has_caption = any(ch.tag == "caption" and ch.full_text() for ch in tbl.children)
        has_aria = bool(tbl.get("aria-label").strip() or tbl.get("aria-labelledby").strip())
        if not is_static and not (has_caption or has_aria):
            add(
                "A11Y-12",
                "Data <table> must have a non-empty <caption> or aria-label/aria-labelledby.",
                tbl,
            )
        for th in (d for d in tbl.iter_descendants() if d.tag == "th"):
            if not (th.get("scope").strip() or th.get("headers").strip()):
                add("A11Y-12", "<th> is missing scope or headers attribute.", th)

    # A11Y-13: no tabindex > 0
    for n in all_nodes:
        if "tabindex" in n.attrs:
            try:
                if int(n.get("tabindex")) > 0:
                    add("A11Y-13", f"tabindex={n.get('tabindex')!r} is greater than 0.", n)
            except ValueError:
                add("A11Y-13", f"Invalid tabindex={n.get('tabindex')!r}.", n)

    # A11Y-14: target="_blank" has rel containing noopener
    for n in all_nodes:
        if n.tag == "a" and n.get("target").lower() == "_blank":
            rels = set(n.get("rel").lower().split())
            if "noopener" not in rels:
                add("A11Y-14", 'target="_blank" link must include rel="noopener".', n)

    # A11Y-15 & R-01: viewport meta exists and allows zoom
    viewports = [n for n in all_nodes if n.tag == "meta" and n.get("name").lower() == "viewport"]
    if not viewports:
        add("A11Y-15", "Missing <meta name='viewport'>.")
        add("R-01", "Missing <meta name='viewport'>.")
    else:
        content = viewports[0].get("content").lower()
        if "user-scalable=no" in content or "user-scalable=0" in content:
            add("A11Y-15", "Viewport meta must not disable user scaling.", viewports[0])
        m = re.search(r"maximum-scale\s*=\s*([0-9.]+)", content)
        if m and float(m.group(1)) < 2.0:
            add("A11Y-15", "Viewport maximum-scale must not be below 2.", viewports[0])

    # A11Y-16: inputs for email, full_name, tel, and passwords have matching autocomplete
    for n in all_nodes:
        if n.tag == "input":
            itype = n.get("type", "text").lower()
            iname = n.get("name", "").lower()
            ac = n.get("autocomplete", "").strip()
            if itype in ("email", "password", "tel") or iname in (
                "email",
                "full_name",
                "contact_phone",
                "password",
                "current_password",
                "new_password",
            ):
                if not ac:
                    add(
                        "A11Y-16", f"Input {iname or itype!r} is missing autocomplete attribute.", n
                    )

    # A11Y-17: iframe and object have a title
    for n in all_nodes:
        if n.tag in ("iframe", "object") and not n.get("title").strip():
            add("A11Y-17", f"<{n.tag}> is missing a non-empty title attribute.", n)

    # A11Y-18: modals have role dialog or aria-modal, aria-labelledby and a close control
    for n in all_nodes:
        if "modal" in n.classes():
            has_role = n.get("role") == "dialog" or n.get("aria-modal") == "true"
            has_lbl = bool(n.get("aria-labelledby").strip() or n.get("aria-label").strip())
            has_close = any(
                "btn-close" in d.classes() or d.get("data-bs-dismiss") == "modal"
                for d in n.iter_descendants()
            )
            if not (has_role and has_lbl and has_close):
                add(
                    "A11Y-18",
                    "Modal must have role='dialog'/aria-modal, aria-labelledby, and a close control.",
                    n,
                )

    # A11Y-19: flash container has aria-live and alerts have role="alert"
    for n in all_nodes:
        if "alert" in n.classes() and "error-summary" not in n.classes():
            if n.get("role") != "alert":
                add("A11Y-19", "Alert element must have role='alert'.", n)
            has_live_parent = False
            cur = n.parent
            while cur is not None:
                if cur.get("aria-live") in ("polite", "assertive"):
                    has_live_parent = True
                    break
                cur = cur.parent
            if not has_live_parent and n.get("aria-live") not in ("polite", "assertive"):
                add("A11Y-19", "Flash alert must sit inside an aria-live region.", n)

    # A11Y-20: offcanvas & collapse toggles have aria-controls, accessible name, and aria-expanded on collapse
    for n in all_nodes:
        toggle = n.get("data-bs-toggle")
        if toggle in ("offcanvas", "collapse"):
            controls = n.get("aria-controls").strip()
            name = _accessible_name(n, id_map, labels_by_for)
            if not controls or not name:
                add(
                    "A11Y-20", f"{toggle} toggle must have aria-controls and an accessible name.", n
                )
            if toggle == "collapse" and n.get("aria-expanded") not in ("true", "false"):
                add("A11Y-20", "Collapse toggle must have aria-expanded='true' or 'false'.", n)

    # A11Y-21: badges have visible text
    for n in all_nodes:
        if "badge" in n.classes() and not n.full_text():
            add(
                "A11Y-21",
                "Badge element must contain visible text (colour cannot be the only signal).",
                n,
            )

    # R-02 & R-03 & R-08: responsive table contract
    for tbl in (n for n in all_nodes if n.tag == "table"):
        t_classes = tbl.classes()
        if "table-static" not in t_classes and not tbl.has_ancestor("table-responsive"):
            add("R-03", "Data <table> must be wrapped inside a .table-responsive container.", tbl)
        for cell in (d for d in tbl.iter_descendants() if d.tag in ("th", "td")):
            if any(
                c == "d-none" or c.startswith("d-") and c.endswith("-none") for c in cell.classes()
            ):
                add("R-08", "Table column cell must not be hidden with d-none utilities.", cell)
        if "table-stack" in t_classes:
            if tbl.get("role") != "table":
                add("R-02", "table.table-stack must have role='table'.", tbl)
            headers_txt: list[str] = []
            thead = next((ch for ch in tbl.children if ch.tag == "thead"), None)
            if thead is not None:
                if thead.get("role") != "rowgroup":
                    add("R-02", "thead in table.table-stack must have role='rowgroup'.", thead)
                ths = [d for d in thead.iter_descendants() if d.tag == "th"]
                for th in ths:
                    if th.get("role") != "columnheader":
                        add("R-02", "th in table.table-stack must have role='columnheader'.", th)
                    headers_txt.append(th.full_text())
            tbody = next((ch for ch in tbl.children if ch.tag == "tbody"), None)
            if tbody is not None:
                if tbody.get("role") != "rowgroup":
                    add("R-02", "tbody in table.table-stack must have role='rowgroup'.", tbody)
                for tr in (ch for ch in tbody.children if ch.tag == "tr"):
                    if tr.get("role") != "row":
                        add("R-02", "tr in table.table-stack must have role='row'.", tr)
                    tds = [ch for ch in tr.children if ch.tag == "td"]
                    for idx, td in enumerate(tds):
                        if td.get("role") != "cell":
                            add("R-02", "td in table.table-stack must have role='cell'.", td)
                        d_lbl = td.get("data-label").strip()
                        if not d_lbl:
                            add("R-02", "td in table.table-stack is missing data-label.", td)
                        elif (
                            idx < len(headers_txt)
                            and headers_txt[idx]
                            and d_lbl != headers_txt[idx]
                        ):
                            add(
                                "R-02",
                                f"td data-label={d_lbl!r} does not match header {headers_txt[idx]!r}.",
                                td,
                            )

    # R-04: no inline style sets a fixed width > 320px
    for n in all_nodes:
        style = n.get("style")
        if style:
            for m in re.finditer(r"(?<![a-z-])width\s*:\s*([0-9.]+)px", style, re.I):
                if float(m.group(1)) > 320.0:
                    add("R-04", f"Inline style sets fixed width {m.group(1)}px > 320px.", n)

    # R-05: action buttons inside .td-actions or booking/cancel forms have btn-xs-block
    for n in all_nodes:
        if "btn" in n.classes():
            if n.has_ancestor("td-actions") and "btn-xs-block" not in n.classes():
                add("R-05", "Button inside .td-actions must include class 'btn-xs-block'.", n)

    # R-06: admin pages contain #adminSidebar with offcanvas-lg and a toggler pointing to it
    is_admin_page = any(
        n.tag == "nav" and n.get("aria-label") == "Admin" for n in all_nodes
    ) or page.startswith("/admin")
    if is_admin_page:
        sb = id_map.get("adminSidebar")
        has_toggler = any(
            n.get("data-bs-toggle") == "offcanvas" and n.get("data-bs-target") == "#adminSidebar"
            for n in all_nodes
        )
        if sb is None or "offcanvas-lg" not in sb.classes() or not has_toggler:
            add("R-06", "Admin page must have #adminSidebar.offcanvas-lg and an offcanvas toggler.")

    # R-07: every navbar-expand-lg has a toggler with aria-controls, aria-expanded and aria-label
    for nav in (n for n in all_nodes if "navbar-expand-lg" in n.classes()):
        togglers = [d for d in nav.iter_descendants() if "navbar-toggler" in d.classes()]
        if togglers:
            t = togglers[0]
            if not (
                t.get("aria-controls").strip()
                and t.get("aria-expanded") in ("true", "false")
                and t.get("aria-label").strip()
            ):
                add(
                    "R-07",
                    "navbar-toggler must have aria-controls, aria-expanded, and aria-label.",
                    t,
                )

    issues.sort()
    return issues


def crawl(
    app: Any, roles: dict[str, Any], page_urls: dict[str, list[str]]
) -> dict[str, list[Issue]]:
    """Crawl GET URLs per role with test clients and return {page: [Issue]}."""
    results: dict[str, list[Issue]] = {}
    for role, client in roles.items():
        for url in page_urls.get(role, []):
            resp = client.get(url, follow_redirects=False)
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or "text/html" not in ctype:
                continue
            html_text = resp.get_data(as_text=True)
            key = f"{role}:{url}"
            results[key] = audit_html(html_text, page=url)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static accessibility & responsive auditor.")
    parser.add_argument(
        "--demo", action="store_true", help="Seed demo data on a temp DB and audit all role pages."
    )
    parser.add_argument(
        "--role", choices=["admin", "examiner", "student", "public"], help="Filter by role."
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    args = parser.parse_args(argv)

    if not args.demo:
        print(
            "Usage: python scripts/a11y_audit.py --demo [--role ROLE] [--format text|json]",
            file=sys.stderr,
        )
        return 2

    import tempfile
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import scripts.seed_demo_data as seed_demo
    from app import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "a11y_demo.db"
        app = create_app("testing")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
        with app.app_context():
            seed_demo.main(app)

        # Build logged-in clients and URL lists
        pub_client = app.test_client()
        roles_map = {"public": pub_client}
        urls_map = {"public": ["/login", "/register", "/api/v1/docs"]}

        if args.role:
            roles_map = {k: v for k, v in roles_map.items() if k == args.role}

        report = crawl(app, roles_map, urls_map)

    all_issues = [iss for iss_list in report.values() for iss in iss_list]
    errors = [iss for iss in all_issues if iss.severity == "error"]

    if args.format == "json":
        print(json.dumps([asdict(i) for i in all_issues], indent=2))
    else:
        print(
            f"Audited {len(report)} pages: {len(errors)} errors, {len(all_issues) - len(errors)} warnings."
        )
        for iss in all_issues:
            print(f"[{iss.severity.upper()}] {iss.page} {iss.rule}: {iss.message} {iss.snippet}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
