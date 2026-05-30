#!/usr/bin/env python3
"""Export one Dzen article to .md via Playwright (real browser + JS).

Usage:
  python tools/dzen_playwright_export.py "https://dzen.ru/a/..." -o path/to/article.md

First run: browser opens — log in to Yandex if Dzen asks. Session is saved in 05data/playwright_dzen_profile/.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "05data" / "playwright_dzen_profile"

EXTRACT_JS = """
() => {
  const skipExact = new Set([
    'Главная','Подписки','Найти','Новости','Статьи','Видео','Ролики',
    'Дети в сети','Видеоигры','Детям','Войти','Подписаться','Понятно',
    'Нравится','Комментировать','Поделиться','Не нравится','Показать ещё',
  ]);
  const skipPartial = ['Рекламу можно отключить', 'С подпиской Дзен Про', 'cookie'];

  const h1Candidates = [...document.querySelectorAll('h1')].filter(h => {
    const t = (h.innerText || '').trim();
    return t.length > 15 && !skipPartial.some(p => t.includes(p));
  });
  const h1 = h1Candidates[0];
  if (!h1) return { error: 'h1 not found — login or open article URL (/a/...)' };

  let root = h1.closest('.page_article') || h1.parentElement;
  for (let i = 0; i < 12 && root; i++) {
    const t = root.innerText || '';
    if (t.length > 2500 && (t.includes('Аннотация') || t.includes('МОДУЛЬ') || t.includes('УРОК'))) break;
    root = root.parentElement;
  }
  if (!root) root = h1.parentElement;

  const nodes = root.querySelectorAll('h1,h2,h3,p,li');
  const blocks = [];
  const seen = new Set();
  for (const n of nodes) {
    let text = (n.innerText || '').trim().replace(/\\s+/g, ' ');
    if (text.length < 2 || seen.has(text)) continue;
    if (skipExact.has(text)) continue;
    if (skipPartial.some(p => text.includes(p))) continue;
    if (/^https?:\\/\\//.test(text)) continue;
    seen.add(text);
    blocks.push({ tag: n.tagName.toLowerCase(), text });
  }

  return {
    title: h1.innerText.trim(),
    url: location.href,
    blocks,
    bodyLen: (root.innerText || '').length,
  };
}
"""


def classify_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if path.startswith("a/"):
        return "article"
    if path.startswith("id/"):
        return "channel"
    return "unknown"


def blocks_to_markdown(title: str, url: str, blocks: list[dict]) -> str:
    lines = [f"# {title}", "", f"Source: {url}", ""]
    for b in blocks:
        tag, text = b["tag"], b["text"]
        if tag == "h1":
            continue
        if tag == "h2":
            lines.extend(["", f"## {text}", ""])
        elif tag == "h3":
            lines.extend(["", f"### {text}", ""])
        elif tag == "li":
            lines.append(f"- {text}")
        else:
            lines.extend([text, ""])
    return "\n".join(lines).strip() + "\n"


def is_sso_page(page) -> bool:
    url = page.url
    content = page.content()
    return "sso." in url or "passport.yandex" in url or "sso.dzen.ru" in content[:8000]


def wait_for_article(page, timeout_sec: int = 120) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if is_sso_page(page):
            print("[INFO] Login page detected — sign in to Yandex in the browser window.")
            page.wait_for_timeout(2000)
            continue
        try:
            page.wait_for_selector("h1", timeout=5000)
        except Exception:
            page.wait_for_timeout(1500)
            continue
        data = page.evaluate(EXTRACT_JS)
        if data.get("blocks") and len(data["blocks"]) > 5:
            return
        page.wait_for_timeout(1500)
    raise TimeoutError("Article content did not load. Check URL (/a/...) and login.")


def export_article(
    url: str,
    output: Path,
    profile_dir: Path,
    headless: bool,
    timeout_sec: int,
) -> Path:
    from playwright.sync_api import sync_playwright

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            locale="ru-RU",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        print(f"[INFO] Opening {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        wait_for_article(page, timeout_sec=timeout_sec)

        data = page.evaluate(EXTRACT_JS)
        if data.get("error"):
            context.close()
            raise RuntimeError(data["error"])

        md = blocks_to_markdown(data["title"], data.get("url", url), data["blocks"])
        output.write_text(md, encoding="utf-8")
        safe_title = data["title"][:80].encode("ascii", "replace").decode("ascii")
        print(f"[OK] Title: {safe_title}...")
        print(f"[OK] Blocks: {len(data['blocks'])}, body ~{data.get('bodyLen', 0)} chars")
        print(f"[OK] Saved: {output}")
        context.close()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Dzen article to Markdown via Playwright")
    parser.add_argument("url", help="Article URL https://dzen.ru/a/...")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .md path (default: 03experiments/dzen_scrape/<slug>.md)",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="Browser profile dir (keeps Yandex login)",
    )
    parser.add_argument("--headless", action="store_true", help="Headless (use after login works)")
    parser.add_argument("--timeout", type=int, default=120, help="Wait for content, seconds")
    args = parser.parse_args()

    if classify_url(args.url) != "article":
        print("[WARN] URL looks like channel, not article. Use Share -> Copy link (/a/...).")
        print("       Example: https://dzen.ru/a/agn86z3LoXbDuwvM")

    slug = urlparse(args.url).path.rstrip("/").split("/")[-1] or "article"
    output = args.output or (ROOT / "03experiments" / "dzen_scrape" / f"{slug}.md")

    try:
        export_article(args.url, output, args.profile, args.headless, args.timeout)
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
