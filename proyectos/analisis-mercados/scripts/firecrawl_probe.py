#!/usr/bin/env python3
"""
Prueba aislada de Firecrawl (sin tocar pipeline principal).
Uso:
  python scripts/firecrawl_probe.py --url https://example.com/news

Variables opcionales:
  FIRECRAWL_API_KEY=...
  FIRECRAWL_BASE_URL=https://api.firecrawl.dev
  FIRECRAWL_TIMEOUT_SEC=12
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import request, error


def read_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def firecrawl_scrape(url: str, api_key: str, base_url: str, timeout_sec: int) -> dict:
    endpoint = f"{base_url.rstrip('/')}/v1/scrape"
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba segura de Firecrawl")
    parser.add_argument("--url", required=True, help="URL a analizar")
    parser.add_argument("--out", default="data/firecrawl_probe_latest.json", help="Salida JSON")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    read_env_file(Path("C:/Users/Fernando/.openclaw/.env"))
    read_env_file(root / ".env")

    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    base_url = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev").strip()
    timeout_sec = int(os.getenv("FIRECRAWL_TIMEOUT_SEC", "12"))

    if not api_key:
        print("FALTA FIRECRAWL_API_KEY en entorno/.env")
        return 2

    try:
        result = firecrawl_scrape(args.url, api_key, base_url, timeout_sec)
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        print(f"HTTPError {e.code}: {body[:600]}")
        return 3
    except Exception as e:
        print(f"ERROR: {e}")
        return 4

    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md = (
        (result.get("data") or {}).get("markdown")
        if isinstance(result, dict)
        else None
    )
    chars = len(md) if isinstance(md, str) else 0
    print(f"OK firecrawl_probe | chars_markdown={chars} | out={out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
