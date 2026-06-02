"""Render the public marketing pages to a static site for GitHub Pages.

The portal (FastAPI + DB) is NOT deployable to Pages — this only emits
the two static pages: landing (/) and /demo.

Usage:
    python scripts/build_static.py [--out dist] [--base /resumetool/]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "resumetool" / "server" / "templates"
STATIC = ROOT / "src" / "resumetool" / "server" / "static"

PAGES = [
    ("landing.html", "index.html", "landing"),
    ("demo.html", "demo/index.html", "demo"),
]

BRAND_URL = "https://expphoto.github.io/resumetool/"


def build(out_dir: Path, base_href: str) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    for template_name, out_rel, body_class in PAGES:
        tpl = env.get_template(template_name)
        html = tpl.render(
            request=None,
            body_class=body_class,
            base_href=base_href,
            live_stats=None,
            brand_url=BRAND_URL,
        )

        html = html.replace('href="/dashboard"', 'href="/#contact"')

        out_path = out_dir / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"  wrote {out_rel}  ({len(html):,} bytes)")

    static_dest = out_dir / "static"
    shutil.copytree(STATIC, static_dest)
    for f in sorted(static_dest.iterdir()):
        print(f"  wrote static/{f.name}  ({f.stat().st_size:,} bytes)")

    (out_dir / ".nojekyll").touch()
    print("  wrote .nojekyll")

    if base_href and base_href != "/":
        cname = base_href.strip("/").split("/")[0]
        if "." in cname and not cname.startswith("localhost"):
            (out_dir / "CNAME").write_text(cname)
            print(f"  wrote CNAME -> {cname}")

    print(f"\nBuilt {sum(1 for _ in out_dir.rglob('*') if _.is_file())} files into {out_dir}/")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="dist", help="Output directory (default: dist)")
    p.add_argument(
        "--base",
        default="/resumetool/",
        help="<base href> for the site (default: /resumetool/ — for GitHub Pages project sites)",
    )
    args = p.parse_args()
    out_dir = (ROOT / args.out).resolve()
    return build(out_dir, args.base)


if __name__ == "__main__":
    sys.exit(main())
