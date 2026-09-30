#!/usr/bin/env python3
"""Capture the CPU-only P06 UI through real local Chrome, using isolated ports."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ui" / "refit-p09"
APP_PORT = 19106
CDP_PORT = 19107


def wait_url(url: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"Local service did not start: {url}")


def main() -> None:
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("Existing Chrome is required for actual browser captures")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p06-ui-cdp-") as browser_dir:
        server = subprocess.Popen(
            ["python3", "-m", "equipment_desk.server", "--port", str(APP_PORT)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        browser = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--remote-allow-origins=*", f"--remote-debugging-port={CDP_PORT}",
             f"--user-data-dir={browser_dir}", "about:blank"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_url(f"http://127.0.0.1:{APP_PORT}/api/health")
            wait_url(f"http://127.0.0.1:{CDP_PORT}/json/version")
            health = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{APP_PORT}/api/health", timeout=3).read())
            if health.get("model_enabled") is not False:
                raise RuntimeError("Refit capture requires model_enabled=false")
            for extra in ([], ["--policy-only"]):
                subprocess.run(
                    ["python3", "scripts/browser_check.py", "--port", str(APP_PORT),
                     "--cdp-port", str(CDP_PORT), "--output", str(OUT), *extra],
                    cwd=ROOT, check=True,
                )
        finally:
            browser.terminate()
            server.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()
