# A feladatkiírás AI-detektoros ellenőrzése

## Aktuális szöveg – 2026. október 8.

A bevezető és az első két feladatpont a végső alkalmazás elemzési céljaihoz igazodott: pilóták közötti különbségek, üldözési helyzetek, gumihasználat, számított metrikák, közérthető és részletes elemzőnézetek. A végleges szöveget három szolgáltatással ellenőriztem.

**A ZeroGPT 6,7%-os AI-jelzést adott a teljes aktuális szövegre.** Az ennél az eszköznél kért 50% alatti cél teljesült. A [képernyőkép](feladatkiiras-zerogpt-race-analysis-final-2026-10-08.png) és a [szolgáltatás válasza](feladatkiiras-zerogpt-race-analysis-final-2026-10-08.json) az aktuális változathoz tartozik.

| Eszköz | Eredmény | A vizsgálat értelmezése |
| --- | --- | --- |
| ZeroGPT | **6,7%** | Teljes szöveg; a válaszban visszakapott szöveg tartalmát ellenőriztem. Magyar nyelvet azonosított. |
| Smodin | **93% a felületen** | Az API 48,63%-ot és csak az első 1069 karakter elemzését adta vissza. Az eltérés és a részleges elemzés miatt ebből nem állapítható meg a teljes dokumentum pontszáma. |
| AIDetego, Academic mód | **100%** | A teljes szöveget beküldtem, de a magyar bemenetet spanyolként (ES) azonosította. |

A ZeroGPT 344 szót és 2962 karaktert jelzett a felületen. A beküldött szöveg a három bevezető bekezdést, a feladatlista felvezetését és mind a hét feladatpontot tartalmazta. Név, Neptun-kód, konzulensi adatok és intézményi fejléc nem kerültek a vizsgálatokba. Az archivált bemenetek SHA-256 azonosítója megegyezik a végleges szövegfájl törzsével; a Windows-sorvégeket is megtartottam az összevetéshez.

További bizonyítékok: [Smodin-képernyőkép](feladatkiiras-smodin-race-analysis-final-2026-10-08.png), [Smodin-válasz](feladatkiiras-smodin-race-analysis-final-2026-10-08.json), [AIDetego-képernyőkép](feladatkiiras-aidetego-race-analysis-final-2026-10-08.png), [AIDetego-eredmény](feladatkiiras-aidetego-race-analysis-final-2026-10-08.json).

A végső célbekezdés egyszerűsítése előtti október 8-i változat ZeroGPT-eredménye 15,5% volt. Ez is szerepel a [mérési fájlban](feladatkiiras-ai-meresek.json), külön szövegazonosítóval. A jelenlegi DOCX és PDF a 6,7%-os mérés szövegét tartalmazza. A detektorok jelzései nem a szerzőség bizonyítékai; a szöveg AI-val támogatott szerkesztéssel készült.

## Korábbi vizsgálatok – 2026. október 6.

Az alábbi pontszámok a korábbi szövegekre vonatkoznak, nem az aktuális dokumentumra.

Dátum: 2026. október 6.

**Az október 6-i változat AI-paneljeinek általánosítása után 0%-os AI-jelzést adott a ZeroGPT a teljes szövegre.** Az 50% alatti cél ennél a szolgáltatásnál akkor teljesült; más detektorokra ez nem jelent garanciát. A [futtatás képernyőképe](feladatkiiras-zerogpt-ai-panelek.png) az akkori dokumentumhoz tartozik.

A legutóbbi ZeroGPT-vizsgálat a teljes feladatszövegre futott le: a bevezetőre és mind a nyolc feladatpontra. A szolgáltatás válaszában visszakapott szöveg tartalmát összevetettem a beküldött változattal. A felület 3098 karaktert és 407 szót jelzett. Név, Neptun-kód és konzulensi adatok nem kerültek a vizsgálatba.

Az alábbi összehasonlítás az AI-panelek általánosítása előtti változatokra vonatkozik. A korábbi fejlesztői változat is 0%-ot kapott a ZeroGPT-nél, az azt megelőző szöveg 6,8%-ot. Az új AI-megfogalmazással csak a ZeroGPT-vizsgálatot ismételtem meg; a többi szolgáltatás korábbi eredménye nem az aktuális szöveg mérése.

| Detektor | Korábbi változat | Fejlesztői változat az AI-panelek általánosítása előtt | Megjegyzés |
| --- | --- | --- | --- |
| [ZeroGPT](https://www.zerogpt.com/) | 6,8% | **0%** | Teljes szöveg, sikeres vizsgálat. |
| [AIDetego](https://aidetego.com/analyze), Academic mód | 100% | 100% | A magyar szöveget mindkét esetben spanyolként (ES) azonosította. |
| [Smodin](https://smodin.io/hu/ai-tartalomdetektor) | Nem vizsgáltam | 85% a felületen | A szolgáltatás válasza csak az első 1084 karakter elemzését tartalmazta, arra 0-s értéket adott. A felületi és a visszakapott eredmény eltér; ezt nem tekintem igazolt, teljes szövegre vonatkozó mérésnek. |

A detektorok eredményei eltérnek. Az AIDetego [saját leírása](https://aidetego.com/how-it-works) szerint elsősorban angol és német szövegeken működik, más nyelveken kevésbé pontos. A 0% a ZeroGPT adott vizsgálatának eredménye, nem az emberi szerzőség bizonyítéka.

Képernyőképek:

- ZeroGPT: [előző változat, 6,8%](feladatkiiras-zerogpt-elozo.png), [új változat, 0%](feladatkiiras-zerogpt-uj.png).
- AIDetego: [előző változat](feladatkiiras-ai-atfogalmazott.png), [új változat](feladatkiiras-ai-developer.png).
- Smodin: [a felületen megjelenő eredmény](feladatkiiras-smodin-uj.png).

A vizsgálatok adatait és a beküldött szövegek SHA-256 azonosítóit a [mérési fájl](feladatkiiras-ai-meresek.json) tartalmazza.

Az [Isgen](https://isgen.ai/hu) szervere „Unusual request detected. Please try again” hibával elutasította az ellenőrzést (HTTP 400). Innen nincs pontszám. A Preds bejelentkezést kér; ott nem történt vizsgálat.

A szövegben több megszokott fejlesztői kifejezés szerepel, például frontend, backend, dashboard, layout builder, replay és sandbox. A vállalt funkciók megmaradtak, az opcionális elemek nem kerültek bele. A szöveg AI-val támogatott szerkesztéssel készült.
