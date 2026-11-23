"""Assemble static web + data bundle into ./www for Capacitor Android APK build."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
WWW_DIR = ROOT / "www"


def main() -> None:
    if WWW_DIR.exists():
        shutil.rmtree(WWW_DIR)

    shutil.copytree(WEB_DIR, WWW_DIR)
    if DATA_DIR.exists():
        shutil.copytree(DATA_DIR, WWW_DIR / "data")

    remote_data_url = os.getenv("REMOTE_DATA_URL", "").strip()
    if remote_data_url:
        index_path = WWW_DIR / "index.html"
        html = index_path.read_text(encoding="utf-8")
        inject_tag = (
            f"  <script>window.BDE_REMOTE_DATA_URL = {json.dumps(remote_data_url)};</script>\n"
        )
        target = '  <script src="js/app.js" defer></script>'
        if target in html:
            html = html.replace(target, inject_tag + target, 1)
            index_path.write_text(html, encoding="utf-8")
            print(f"Injected REMOTE_DATA_URL={remote_data_url} into www/index.html")

    print(f"Prepared Capacitor web bundle at: {WWW_DIR}")


if __name__ == "__main__":
    main()
