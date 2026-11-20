"""Export the Hungarian subscription design with its Enterprise Architect figures."""
import asyncio
import base64
import re
from pathlib import Path

from markdown_it import MarkdownIt
from playwright.async_api import async_playwright

DOCS = Path(__file__).resolve().parents[1]
ARCHITECTURE = DOCS / "architecture"
SLUG = "PitWall-Insights-elofizetes-fejlesztoi-dokumentacio"
DIAGRAM = re.compile(r'<p><img src="([^\"]+\.png)" alt="([^\"]+)"\s*/?></p>')


def embed_diagram(match):
    path, caption = match.groups()
    encoded = base64.b64encode((ARCHITECTURE / path).read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{encoded}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'


async def export():
    first, content = (ARCHITECTURE / "14-subscriptions.md").read_text(encoding="utf-8").split("\n", 1)
    markdown = MarkdownIt("commonmark").enable("table")
    body = DIAGRAM.sub(embed_diagram, markdown.render(content))
    body = re.sub(r'href="(\d\d-[^\"]+\.md)"', r'href="https://github.com/JozsefN/PitWall-Insights/blob/main/docs/architecture/\1"', body)
    html = f"""<!doctype html>
<html lang="hu"><meta charset="utf-8"><title>PitWall Insights · Előfizetés</title>
<style>
@page {{ size: A4; margin: 14mm 13mm; }}
body {{ font: 10.5pt/1.43 'Segoe UI', Arial, sans-serif; color: #192830; margin: auto; max-width: 185mm; }}
.cover {{ break-after: page; padding-top: 43mm; }}
.cover h1 {{ font-size: 36pt; color: #084842; margin: 0 0 4mm; line-height: 1.14; }}
.cover p {{ font-size: 15pt; max-width: 140mm; }}
h2, h3 {{ color: #084842; break-after: avoid; }}
h2 {{ margin-top: 1.2em; }} p {{ margin: 0.55em 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 3mm 0; }}
thead {{ background: #e0efeb; }} th, td {{ text-align: left; border: 1px solid #c6d6d3; padding: 1.8mm; vertical-align: top; }}
tr, figure, pre {{ break-inside: avoid; }}
figure {{ margin: 4mm 0; text-align: center; }} figure img {{ max-width: 100%; max-height: 76mm; }}
figcaption {{ font-size: 9.5pt; color: #325453; }}
a {{ color: #025c55; }} code {{ font-size: 0.88em; overflow-wrap: anywhere; }}
pre {{ white-space: pre-wrap; padding: 2mm; background: #eef5f3; }}
</style>
<section class="cover"><h1>PitWall Insights</h1><p>{first.removeprefix('# ')}<br>Fejlesztői dokumentáció</p>
<p>2026. november 20. · main</p><p>Csomagszabályok, PostgreSQL-adatmodell, Stripe Sandbox és Google-azonosítás.</p></section>
{body}</html>"""
    path = DOCS / f"{SLUG}.html"
    path.write_text(html, encoding="utf-8")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.goto(path.as_uri())
        await page.pdf(path=DOCS / f"{SLUG}.pdf", print_background=True, prefer_css_page_size=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(export())
