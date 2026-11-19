"""Prepare thesis figures from the existing browser evidence and Mermaid flowcharts."""

import argparse
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


DOCS = Path(__file__).resolve().parents[1]
TARGET = DOCS / "generated/szakdolgozat-abraterv"
HOST = "http://thesis-figures.local"


REPLAY = """flowchart TB
    store["Tárolt körök és telemetria"] --> prep["Teljes tartományú mintavétel"]
    prep --> clock["Közös lejátszási óra<br/>Indítás, sebesség, ugrás"]
    clock --> frame["Térkép és autók<br/>~32 ms"]
    clock --> read["Idő, sorrend, időköz<br/>~240 ms"]
    clock --> review["Egyéb elemzési jel<br/>~2 s"]
    read --> strategy["Stratégiai pillanatkép<br/>5 s-os versenyidő-ablak"]
    classDef main fill:#e4eef6,stroke:#385c7c,color:#172737
    classDef panel fill:#f4f7f9,stroke:#668094,color:#172737
    class store,prep,clock main
    class frame,read,review,strategy panel
"""

STRATEGY = """flowchart TB
    raw["Körök, pozíció, telemetria,<br/>zászlók és időjárás"] --> cut["Döntési pillanatkép<br/>Csak az addig ismert adatok"]
    ctx["Korábbi futamok, szabályok<br/>és kalibrációs feltételek"] --> cut

    cut --> pace["Tiszta tempó,<br/>gumikor és keverék"]
    cut --> gaps["Közös szektorátlépések<br/>és riválisok időköze"]
    cut --> pit["Bokszlátogatások<br/>és nettó időveszteség"]
    cut --> obs["Friss pozíció,<br/>incidens és pályaállapot"]

    pace --> tyres["Gumigörbék és<br/>esőgumi-váltás"]
    gaps --> window["Riválisra számított<br/>visszatérési helyzet"]
    pit --> window
    pit --> risk["SC/VSC esélye és<br/>feltételes bokszköltség"]
    obs --> risk
    obs --> physics["Pályafelület és<br/>szélviszonyok becslése"]

    tyres --> plans["Korlátozott stratégiai keresés<br/>Maradás, kiállás és időzítés"]
    window --> plans
    risk --> plans
    plans --> panels["Stratégiai és mérnöki panelek<br/>Javaslat, eltérés, bizonyíték"]
    physics --> panels

    classDef main fill:#e4eef6,stroke:#385c7c,color:#172737
    classDef derived fill:#f4f7f9,stroke:#668094,color:#172737
    classDef output fill:#f4ead4,stroke:#8a713b,color:#271f12
    class raw,ctx,cut main
    class pace,gaps,pit,obs,tyres,window,risk,physics derived
    class plans,panels output
"""

BUILDER = """flowchart TB
    catalog["Panelkatalógus<br/>Adatigény, méret és elérhetőség"] --> editor["Elrendezésszerkesztő<br/>Rács, előnézet és beállítások"]
    editor --> api["Mentési API<br/>Geometria és tulajdonos ellenőrzése"]
    api --> store["Saját vagy kedvenc<br/>elrendezés"]
    store --> workspace["Munkamenetnézet<br/>Csak illeszkedő panelek"]
    classDef main fill:#e4eef6,stroke:#385c7c,color:#172737
    classDef output fill:#f4ead4,stroke:#8a713b,color:#271f12
    class catalog,editor,api,store main
    class workspace output
"""

MAP = """flowchart TB
    asset["Pályafájl<br/>Középvonal, ismert szélesség"] --> road["Illesztés egy<br/>teljes referencia-körhöz"]
    reference["Tárolt helyzetminták"] --> road
    reference --> cars["Autóhelyzet az aktuális<br/>lejátszási időpontban"]
    reports["Boksz-, zászló-<br/>és időjárási adatok"] --> layers["Bokszutca és<br/>választható rétegek"]
    road --> view["Pályatérkép<br/>Teljes kör vagy nagyítás"]
    cars --> view
    layers --> view
    classDef main fill:#e4eef6,stroke:#385c7c,color:#172737
    classDef output fill:#f4ead4,stroke:#8a713b,color:#271f12
    class asset,reference,reports,road,cars,layers main
    class view output
"""


def flowcharts(dist):
    html = """<!doctype html><meta charset='utf-8'><style>
        html { background: white } body { margin:0; width:max-content }
        #diagram { padding:14px } #diagram svg { display:block }
        </style><main id='diagram'></main>
        <script type='module'>
        import mermaid from '/mermaid.esm.min.mjs';
        mermaid.initialize({startOnLoad:false, theme:'base',
          fontFamily:'Arial, sans-serif', themeVariables:{fontSize:'24px', lineColor:'#567087'},
          flowchart:{htmlLabels:true, useMaxWidth:false, curve:'linear', nodeSpacing:22, rankSpacing:23, padding:8}});
        window.draw = async (source) => {
          const {svg} = await mermaid.render('thesis', source);
          document.getElementById('diagram').innerHTML = svg;
        };
        </script>"""

    def route_file(route):
        name = route.request.url.removeprefix(HOST).lstrip("/")
        if not name:
            route.fulfill(body=html, content_type="text/html; charset=utf-8")
            return
        path = (dist / name).resolve()
        if path.is_relative_to(dist) and path.is_file():
            route.fulfill(path=path, content_type="application/javascript")
        else:
            route.abort()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 2200, "height": 1600}, device_scale_factor=2)
        page.route(f"{HOST}/**", route_file)
        diagrams = (
            (REPLAY, "visszajatszas-ora.png"),
            (STRATEGY, "strategia-adatut.png"),
            (BUILDER, "elrendezes-adatut.png"),
            (MAP, "terkep-retegek.png"),
        )
        for source, filename in diagrams:
            page.goto(HOST)
            page.wait_for_function("typeof window.draw === 'function'")
            page.evaluate("source => window.draw(source)", source)
            page.locator("#diagram").screenshot(path=TARGET / filename)
        browser.close()


def screenshots():
    crops = {
        "felulet-visszajatszas.png": ("timing-tower/desktop-replay-dark.png", (246, 119, 1510, 919)),
        "felulet-strategiai-javaslat.png": ("replay-strategy/strategy-call.png", (0, 0, 554, 402)),
        "felulet-incidens.png": ("replay-strategy/incident-forecast.png", (0, 0, 554, 373)),
        "felulet-silverstone.png": ("replay-strategy/silverstone-crossover.png", (0, 0, 534, 445)),
        "felulet-mobil-ido.png": ("timing-tower/mobile-replay-dark.png", (0, 185, 390, 843)),
        "felulet-elrendezes.png": ("replay-strategy/builder-practice-desktop.png", (224, 53, 1414, 947)),
    }
    for filename, (source, bounds) in crops.items():
        with Image.open(DOCS / "testing" / source) as image:
            assert bounds[2] <= image.width and bounds[3] <= image.height
            image.crop(bounds).convert("RGB").save(TARGET / filename, optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mermaid_dist", type=Path, help="The dist folder of the installed Mermaid package")
    args = parser.parse_args()
    TARGET.mkdir(parents=True, exist_ok=True)
    flowcharts(args.mermaid_dist.resolve())
    screenshots()
