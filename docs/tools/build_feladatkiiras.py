from pathlib import Path

from build_feladatkiiras_word import build_documents

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'
TITLE_HU = 'Forma-1 telemetria elemző alkalmazás készítése'
TITLE_EN = 'Development of a Formula 1 Telemetry Analysis App'
STUDENT = 'Novák József Pál'
NEPTUN = '______'
SUPERVISOR = 'Albert István, mérnöktanár'
HEAD = 'Dr. Charaf Hassan'
DATE = 'Budapest, 2026. október 8.'
TASK_HEADING = 'A hallgató feladatának a következőkre kell kiterjednie:'
INTRO = (
    'Egy Forma–1-es versenyen a sorrend mellett az is érdekes, hogyan '
    'alakulnak a pilóták közötti küzdelmek. A tempókülönbségek, a gumihasználat '
    'és a távolságok változása megmutathatja, ki zárkózik fel, hol alakul ki '
    'csata, vagy hogyan változik egy pilóta teljesítménye az etap során. '
    'Az ilyen összefüggések a futamot követő nézőnek és a részletesebb '
    'műszaki elemzést végző felhasználónak egyaránt hasznosak.'
)
TECHNOLOGY = (
    'A nyilvánosan elérhető verseny- és telemetriaadatokra épülő '
    'webalkalmazásban az áttekintő és a részletes elemzések közös felületre '
    'kerülhetnek. A React támogatja az interaktív, szabadon összeállítható '
    'panelek kezelését. A Pythonban végzett számításokhoz közvetlenül '
    'felhasználhatók a FastF1 adatai; a feldolgozott eredményeket a FastAPI '
    'teszi elérhetővé a felület számára. Az adatok és a felhasználói '
    'beállítások tárolására PostgreSQL szolgál.'
)
GOAL = (
    'A szakdolgozat célja a PitWall Insights webalkalmazás elkészítése. '
    'Az alkalmazás a pilóták adatainak összehasonlításával és az alapadatokból '
    'számított összetett metrikákkal segít megérteni a pályán történő '
    'változásokat. A visszajátszás, a testreszabható dashboard és az AI-panelek '
    'a felhasználó igényéhez igazítható elemzést támogatnak. Egyes funkciók '
    'előfizetési szinthez kötött hozzáféréssel használhatók.'
)
TASKS = [
    'Mutassa be a Forma–1-es verseny- és telemetriaadatok felhasználási '
    'lehetőségeit, valamint az alkalmazás elkészítéséhez választott technológiákat.',
    'Valósítsa meg egy vagy több pilóta adatainak betöltését, '
    'összehasonlítását és visszajátszását. Számítson és jelenítsen meg '
    'az alapadatokból származtatott metrikákat a tempó, a pilóták közötti '
    'különbségek, az üldözési helyzetek és a gumihasználat elemzéséhez. '
    'Az eredmények legyenek közérthető áttekintésben és részletesebb '
    'elemzőnézetekben is elérhetők.',
    'Készítsen elrendezésszerkesztőt, amelyben a panelek kiválaszthatók, '
    'átrendezhetők és átméretezhetők, tartalmuk pedig versenyző és kör szerint '
    'beállítható. Biztosítsa a felhasználói fiókokhoz tartozó elrendezések '
    'mentését és visszatöltését.',
    'Alakítson ki előfizetési szinteket a panelek, mentett elrendezések '
    'és AI-funkciók elérésének szabályozására. A jogosultságokat a szerver '
    'is ellenőrizze; a fizetés, csomagváltás és lemondás tesztkörnyezetben '
    'legyen kipróbálható.',
    'Integráljon AI-paneleket, amelyek a feldolgozott telemetriaadatokból '
    'szöveges magyarázatot adnak a kiválasztott elemzési feladathoz és '
    'panelbeállításokhoz. A magyarázatok segítsék a grafikonok és mérőszámok '
    'értelmezését, és legyen azonosítható, milyen adatokra épülnek.',
    'Készítsen működő kezdőoldalt, frissíthető pilóta- és konstruktőri '
    'bajnoki tabellát, valamint egyszerű hírfolyamot az eredeti forrásokra '
    'mutató hivatkozásokkal.',
    'Tesztelje az adatfeldolgozást, a fő felhasználói folyamatokat '
    'és a hozzáférési szabályokat. Értékelje az AI-magyarázatok pontosságát, '
    'válaszidejét és költségét, és dokumentálja a megvalósítást és '
    'az alkalmazás futtatását.',
]



if __name__ == '__main__':
    build_documents(ROOT, {
        'title_hu': TITLE_HU, 'title_en': TITLE_EN,
        'student': STUDENT, 'neptun': NEPTUN,
        'supervisor': SUPERVISOR, 'head': HEAD,
        'date': DATE, 'task_heading': TASK_HEADING,
    }, [INTRO, TECHNOLOGY, GOAL], TASKS)
