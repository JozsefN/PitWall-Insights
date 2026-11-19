"""Apply the reviewed, reader-oriented wording to the thesis working source."""

from pathlib import Path
import re


SOURCE = Path(__file__).resolve().parents[1] / 'PitWall-Insights-szakdolgozat-munkavaltozat.md'

TITLES = {
    '1.3': 'A fejlesztés menete és a dolgozat felépítése',
    '2': 'Az alkalmazáshoz szükséges szakmai alapok',
    '2.3': 'Az adatok időbeli összehangolása',
    '2.4': 'A felület és a háttérben végzett munka kapcsolata',
    '2.5': 'Az adatok tárolása és ismételt felhasználása',
    '3': 'Az alkalmazás megtervezése',
    '3.1': 'A használat menete és az elvárt működés',
    '3.2': 'A feladatok szétosztása az alkalmazás részei között',
    '3.3': 'Az edzések és futamok közös adatmodellje',
    '3.4': 'Az indítható visszajátszás feltételei',
    '4': 'Az adatbetöltés fejlesztése',
    '4.1': 'Az első változat: minden adat betöltése egy lépésben',
    '4.2': 'Az alapadatok és a részletes telemetria szétválasztása',
    '4.3': 'A kiválasztott nézethez szükséges adatok betöltése',
    '4.4': 'Az ismétlődő feldolgozás megszüntetése',
    '4.5': 'Nagy adatmennyiség hatékony tárolása',
    '4.6': 'Elakadások, párhuzamos kérések és hibajelzések',
    '5': 'Visszajátszás és testreszabható elemzőfelület',
    '5.1': 'A teljes futam megjelenítése',
    '5.2': 'A közös lejátszási idő és a megjelenített adatok',
    '5.3': 'A pályatérkép és a pilótaválasztás összehangolása',
    '5.4': 'A szerkeszthető elemzőfelület kialakítása',
    '5.5': 'Elrendezések mentése és a módosítások védelme',
    '5.6': 'A felület használata különböző képernyőméreteken',
    '6': 'Számított mutatók és stratégiai elemzések',
    '6.1': 'Tempó, egyenletesség és köridőváltozás',
    '6.2': 'A számítások bővítése és az eredmények értelmezése',
    '6.3': 'Pilóták közötti különbségek és gumihasználat',
    '6.4': 'A vizsgált pillanatban már ismert adatok használata',
    '6.5': 'Lehetséges kiállási tervek összehasonlítása',
    '6.6': 'Korábbi eredmények felhasználása újraszámítás helyett',
    '8.3': 'A visszajátszás elindításához szükséges idő',
    '8.4': 'A számítások ideje és az előrejelzések hibája',
    '9.1': 'A felület szerepe a hibakeresésben',
}

TEXT = {
'1.2': '''Az alkalmazást úgy alakítottam ki, hogy a felhasználó először edzést vagy futamot, majd pilótákat és megjelenítendő adatokat választhasson. Az adatok táblázatokban, grafikonokon és egy mozgó pályatérképen jelennek meg. A visszajátszás megállítható, gyorsítható, és egy kiválasztott pillanatra is lehet ugrani. Az elemzőfelület több különálló panelből áll; ezek elrendezését a felhasználó a saját igényeihez igazíthatja.

A fejlesztésben hamar fontos kérdés lett, mennyit kell várni az első használható nézetre. Egy teljes futam részletes adatainak betöltése hosszú lehet, miközben a felhasználó esetleg csak két pilóta egy-egy körét szeretné megnézni. Ezért fokozatos adatbetöltést valósítottam meg: előbb a választáshoz és az egyszerűbb elemzésekhez szükséges adatok érkeznek meg, a részletes mérések pedig akkor, amikor valamelyik panel ténylegesen igényli őket.

Elkészítettem a bejelentkezést, az adatbetöltést, a visszajátszást, az elrendezésszerkesztőt és a számításokat végző szolgáltatásokat. Az AI-panelek, az előfizetési szabályok és a tesztfizetés még további fejlesztést igényelnek. A dolgozatban ezeket külön jelölöm, hogy a megvalósított eredmények és a következő feladatok egyértelműen elváljanak.''',
'1.3': '''Az alkalmazás készítését az adatok feltérképezésével és az első megjelenítési ötletek összegyűjtésével kezdtem. A korai projektjegyzetben köridőgrafikonok, pilóta-összehasonlítások, pályatérképek és további számítási lehetőségek szerepelnek. A fejlesztés során ezekből választottam ki a megvalósítható funkciókat. Több elképzelést az adatok elérhetősége vagy az első próbák tapasztalatai miatt módosítani kellett. [1]

A munkát önálló labor keretében kezdtem el. A dolgozat a teljes alkalmazás megtervezését és megvalósítását követi végig, az első változattól a későbbi javításokig. Különösen az adatbetöltés, a visszajátszás és a szerkeszthető felület fejlesztését mutatom be részletesen, mert ezeknél több megoldást is át kellett dolgoznom.

Először a megértéshez szükséges adatokat és technológiákat ismertetem, majd levezetem az alkalmazás felépítését. Ezután a megvalósítás fontosabb döntései, a felmerült hibák és a javítások következnek. A számított mutatók bemutatását mérések és tesztek egészítik ki. A dolgozat végén összegzem az eredményeket és a még nyitott feladatokat.''',
'2.1': '''A felhasználó az alkalmazásban egy adott edzés vagy futam adatait nyitja meg. Az adatforrás ezt az egységet sessionnek nevezi. A továbbiakban ezt a kifejezést csak akkor használom, ha a forrás vagy a program egy konkrét elemére hivatkozom. Az adatokat elsősorban a FastF1 nevű Python-könyvtárral érem el. A körök és szektorok időeredményei mellett autóhoz tartozó méréseket, pályapozíciókat, gumihasználatot, időjárást és versenyirányítási üzeneteket dolgozok fel.

Telemetria alatt az autó működéséről és mozgásáról időrendben rögzített méréseket értem. Egy ilyen mérési sorban például a sebességhez az is hozzátartozik, hogy mikor mérték. A köridő ezzel szemben egy teljes kör eredménye, az etap pedig ugyanazon gumiszettel teljesített körök sorozata. Ezek összekapcsolásából lehet megvizsgálni, hogyan alakult egy pilóta teljesítménye.

Az adatok nem minden esetben alkalmasak az eredetileg felvetett számításokra. A gumi fizikai kopása vagy az autó üzemanyagtömege például nem határozható meg megbízhatóan pusztán a köridőből. Ezért mindig megkülönböztetem a közvetlenül rendelkezésre álló adatot és az abból készített becslést. Egy etap lassuló köridői jelezhetnek változást, de annak okát önmagukban még nem bizonyítják.

[Kiegészítendő: az adatforrások összehasonlítása és a használt mezők hivatalos dokumentációjának hivatkozásai.]''',
'2.3': '''Egy grafikonon vagy pályatérképen csak akkor hasonlítható össze két pilóta, ha az adataik ugyanahhoz a versenyhelyzethez tartoznak. Minden méréshez ezért időadatot is tárolok. Ez jelzi, hogy mikor rögzítették az adott sebességet vagy pozíciót; ezt nevezem a mérés időbélyegének.

Az egyes adatok nem feltétlenül azonos időközönként érkeznek. Előfordulhat például, hogy az egyik pilótáról a lejátszás 20. másodpercéhez, a másikról pedig csak valamivel korábbról van pozíciómérés. A megjelenítésnél ilyenkor meg kell határoznom, melyik adat használható még, és mikor kell már hiányzó vagy elavult adatot jelezni. A példában szereplő időpont csak szemléltetés; a tényleges időközöket a forrás adatai határozzák meg.

A források az időpontokat eltérő módon is jelölhetik. Egy üzenet tartalmazhat UTC szerinti óra-perc-másodperc értéket, míg egy telemetriaminta a forrás által választott kezdőpont óta eltelt milliszekundumot adja meg. Mielőtt ezeket együtt használom, ugyanarra az időszámításra kell átváltanom őket. A kezdőpontot a forrásból kell meghatározni; nem helyettesíthetem automatikusan a tervezett rajt időpontjával.

A visszajátszásnál az adatok mennyisége is számít. A tárolt mérésekből a megjelenítéshez ritkább sorozatot is választhatok. Ez a mintavételezés: meghatározott időközönként kérek egy tényleges megfigyelést, miközben az eredeti részletes adatok megmaradnak. Az alkalmazott időközt és a hiányzó adatok kezelését a visszajátszás megvalósításánál mutatom be.''',
'2.4': '''Az alkalmazásnak van egy böngészőben futó felülete és egy szerveren futó része. A felületet React és TypeScript segítségével készítettem. Itt választja ki a felhasználó a pilótákat, itt rendezi el a paneleket, és itt vezérli a visszajátszást. A szerver fogadja az adatkéréseket, eléri az adatbázist, és elvégzi a szükséges feldolgozást. A kettő közötti kéréseket a FastAPI-val kialakított szolgáltatás kezeli.

A felületen kétféle információt kezelek külön. Az egyik a felhasználó pillanatnyi választása, például a kijelölt pilóta, kör vagy lejátszási időpont. Ezeket több panel is használja, ezért közös helyen tárolom, és a React Context megoldásával teszem elérhetővé a paneleknek. Így egy pilótaváltás minden érintett nézetben ugyanazt jelenti. [8]

A másik csoport a szervertől lekért adat, például a körök listája vagy a betöltés állapota. Ezek lekérését, újrafelhasználását és a hozzájuk tartozó várakozási vagy hibaállapotot a TanStack Query segítségével kezelem. Ez eltér a pilótaválasztás tárolásától: a lekért adat frissülhet, átmenetileg hiányozhat, és egy sikertelen kérés után újra be kell tölteni. [9]

Egy hosszabb adatbetöltés közben a szervernek más kéréseket is ki kell szolgálnia. Emiatt az előkészítést külön futó háttérfolyamatra bíztam. Ezt a programban workernek nevezem. A feldolgozandó munkát egy eltárolt feladatleírás, azaz job azonosítja. A felület lekérdezheti, hogy ez a feladat várakozik, dolgozik vagy már befejeződött. A részletes adatbetöltési folyamatot a megvalósításnál követem végig.''',
'2.5': '''A beolvasott adatokat PostgreSQL-adatbázisban tárolom. A pilóták, körök, etapok és mérések kapcsolatait az SQLAlchemy segítségével írtam le. Amikor a tárolási szerkezeten változtatok, az Alembic kezeli az adatbázis módosításához szükséges lépéseket. Így a program újabb változatához tartozó táblákat és mezőket nem kell kézzel, külön-külön létrehozni.

A betöltés gyorsításában többféle újrafelhasználásnak van szerepe. A FastF1 elmentheti a már letöltött forrásfájlokat a lemezre. A feldolgozó folyamat rövid ideig megtarthatja a már beolvasott adathalmazt a memóriában. Az alkalmazás adatbázisa pedig megőrzi azokat a méréseket, amelyeket már a saját tárolási formájára alakítottam át. Ezeket gyorsítótárnak, angol nevén cache-nek nevezem, de mindegyik más munkát takarít meg.

Ha egy korábbi letöltés fájljai már rendelkezésre állnak, attól még lehet feladat azok értelmezése és adatbázisba írása. Ha viszont a mérések már az adatbázisban is megvannak, az olvasásuk elegendő lehet. A betöltési idők összehasonlításakor ezért mindig leírom, mely adatok álltak rendelkezésre a próba kezdetén.''',
'3.1': '''A tervezést a felhasználó lépéseiből indítottam ki. Először ki kell választania egy edzést vagy futamot, majd el kell döntenie, mely pilóták és adatok érdeklik. Innen vagy egy adott kör részletes vizsgálatához jut el, vagy elindítja a teljes verseny visszajátszását. Mindkét esetben ugyanazokat a versenyadatokat használja, csak más nézetben és más részletességgel.

Ebből azt a követelményt vezettem le, hogy egy nézetváltás ne indítsa újra szükségtelenül ugyanannak az adatnak a betöltését. Ugyanilyen fontos, hogy a felület jelezze, mire vár, és hiba esetén legyen érthető, mi akadályozza a továbblépést. A személyes elrendezéseknek a felhasználó fiókjához kell tartozniuk, a közös versenyadatokat viszont több bejelentkezett felhasználó is használhatja.

A feladatkiírás alapján az alkalmazás az adatmegjelenítésen túl számított mutatókat, szerkeszthető felületet, AI-magyarázatokat és előfizetési lehetőséget is céloz. A megvalósítás sorrendjében előre vettem azokat az alapokat, amelyekre a többi funkció épül: az adatbetöltést, a tárolást, a pilóták kiválasztását és a visszajátszást.''',
'3.2': '''A rendszer felépítésében elkülönítettem az adatok megszerzését, feldolgozását, tárolását, elemzését és megjelenítését. Az adatforráshoz kapcsolódó rész feladata a FastF1 használata. Egy másik rész a kapott adatokat az alkalmazás egységes formájára alakítja. A tárolást végző rész ismeri a pilóták, körök és mérések adatbázisbeli kapcsolatait. A számítások ezekre az eltárolt adatokra épülnek.

Ez a felosztás a változtatásokat is kezelhetőbbé teszi. Amikor az adatbázisba írást gyorsítottam, nem kellett átírnom a grafikonok adatkéréseit. Egy új mutató hozzáadása pedig nem követeli meg a forrásletöltés módosítását. A paneleknek azt kell tudniuk, milyen adatot kérnek és milyen állapotban van a feldolgozás; a letöltés és a tárolás részletei a szerver feladatai. [3, 5]

[Kiegészítendő: az alkalmazás fő részeit és kapcsolatait bemutató áttekintő ábra. Az összetettebb feldolgozó szolgáltatások osztálydiagramja a részletes műszaki leírást egészíti ki.]''',
'3.3': '''Egy edzésen vagy futamon belül minden pilótához körök, etapok és időrendben rögzített mérések tartoznak. Ezekhez közös adatmodellt alakítottam ki. Az elemzés és a visszajátszás ugyanazokra a rekordokra hivatkozik, ezért nem kell ugyanazt a futamot külön betölteni mindkét használati módhoz.

A részletes adatok kisebb egységekben is előkészíthetők. Egy ilyen egységhez hozzátartozik, hogy melyik futamról, pilótáról, adattípusról és időtartományról van szó. Például az egyik kérés egy adott pilóta egyetlen körének sebességadatait igényli, a másik ugyanannak a pilótának a teljes futam alatti pozícióit. Ha a nagyobb tartomány már rendelkezésre áll, a belőle kért kisebb részhez nincs szükség újabb teljes betöltésre.

A személyes felületet ettől külön tárolom. Az elrendezés a panelek típusát, beállításait, helyét és méretét írja le, és a tulajdonos fiókjához kapcsolódik. Ugyanaz a közös versenyadat így több, egymástól független felhasználói összeállításban is megjelenhet.

[Kiegészítendő: az adatbázis sémadiagramja az edzések, pilóták, körök és telemetriaminták, valamint a személyes elrendezések kapcsolataival.]''',
'3.4': '''A visszajátszást akkor tekintem indíthatónak, ha a kiválasztott pilóták adatai megjeleníthetők, a lejátszási idő végigjárható, és a nézet a futam végét is lefedi. A háttérfeladat sikeres lezárása önmagában nem elegendő: előfordulhat, hogy nem érkezett használható adat, vagy a lekérés csak a futam egy részét adta vissza.

A felhasználó szempontjából a várakozás oka is lényeges. Meg kell különböztetnem a még sorban álló munkát, az aktív feldolgozást, a nem futó háttérszolgáltatást és a forrásadat hibáját. Az elérhető forrásadatokból indított teljes mezőnyös visszajátszáshoz három percen belüli előkészítési célt használtam. A méréseknél külön megadom, mely adatok voltak már letöltve. [4]

A feladatkiírás követelményeinek ellenőrzését a tesztelési fejezethez kötöm. Az adatbetöltést teljes futamot lefedő adatkérésekkel, az elrendezéseket mentés és visszatöltés után, a fiókok elkülönítését pedig eltérő felhasználókkal kell vizsgálni. Az AI és a fizetés ellenőrzése csak a tényleges megvalósítás után zárható le.''',
'4.1': '''Az első változatban a felhasználó kiválasztott egy edzést vagy futamot, a szerver pedig egyetlen folyamatban végigment az összes szükséges lépésen. Betöltötte az adatokat a FastF1 segítségével, átalakította őket az alkalmazás saját formájára, majd elmentette az eredményt az adatbázisba. Ez egyszerűen követhető megoldás volt, és az első működő nézetek elkészítéséhez megfelelő alapot adott.

A részletes telemetria bekapcsolásával viszont jelentősen megnőtt a munka mennyisége. Egy teljes futamhoz pilótánként sok sebesség- és pozíciómérés tartozik. A felhasználó ilyenkor az adatok előkészítésére várt akkor is, ha később csak két pilótát vagy egyetlen kört nyitott meg. A probléma tehát az volt, hogy túl sok munkát kellett befejezni az első használható nézet előtt.

A későbbi, háttérfeladatokra bontott változat egyik próbájánál tizenöt perc elteltével sem jutottam használható visszajátszáshoz. Ehhez a próbához nincs a későbbi mérésekkel azonos részletességű naplóm, ezért az időadatból nem számolok gyorsulási arányt. A tapasztalat azonban világossá tette, hogy a feldolgozás szervezésén kívül annak tényleges lépéseit és adatmennyiségét is át kell vizsgálnom.''',
'4.2': '''Először azt választottam szét, hogy mi kell az edzés vagy futam megnyitásához, és mi kell egy részletes panel működéséhez. A pilóták névsora, a köridők és az etapok már sok alapművelethez elegendők. A folyamatos sebesség- és pozíciómérések ennél lényegesen több adatot jelentenek, ezért ezeket később töltöm be.

Az első, kisebb adatcsomagot a program core importnak nevezi. Ezzel a felület eljuthat a pilóta- és körválasztásig anélkül, hogy minden részletes mérés már az adatbázisban lenne. Amikor a felhasználó megnyit egy telemetriagrafikont vagy visszajátszást kér, az alkalmazás ellenőrzi az ahhoz szükséges részletes adatokat.

A hosszabb munkát külön háttérfolyamat végzi. A szerver eltárolja a feladatleírást, a feldolgozó pedig felveszi a sorban várakozó munkát. A felület közben az állapotát kérdezi le. Így a várakozás nem egyetlen nyitva tartott adatkérésen múlik, és más felhasználói műveletek is kiszolgálhatók.

Ettől a számítás és az adatbázisba írás még nem lett automatikusan gyorsabb. A háttérfeladat a hosszú művelet követését és elkülönítését oldotta meg. A feldolgozott adatok mennyiségét és az egyes lépések költségét külön kellett csökkentenem.''',
'4.3': '''A következő lépés az volt, hogy a panel csak azt az adatot kérje, amelyre valóban szüksége van. Egy kör sebességgrafikonjához például a kiválasztott pilóta adott körének autóadatai kellenek. A teljes mezőny pályatérképéhez ezzel szemben több pilóta pozíciójára, hosszabb időtartományban van szükség. A két kérés feldolgozási igénye eltér.

A kérés érkezésekor a szerver először megnézi, van-e már megfelelő adat az adatbázisban. Ha van, a panel lekérheti. Ha nincs, létrejön az előkészítési feladat, és a felület jelzi a várakozást. Ezt a hiányzó adatok előállítását nevezi a kód materializálásnak; a dolgozatban a továbbiakban telemetria-előkészítésként hivatkozom rá.

A már előkészített adatot másik panel vagy használati mód is átveheti. Ha egy pilóta körének méréseit az elemzőnézet betöltötte, azokat nézetváltáskor nem törlöm. Az azonos adatot igénylő panelek így nem indítanak egymástól független teljes feldolgozást.

![A panel adatkérésétől az adatbázisban tárolt mérésekig vezető feldolgozás.](generated/szakdolgozat-abraterv/adatbetoltes.png)''',
'4.4': '''Az igény szerinti betöltés után is maradt egy kevésbé látható költség. A korábbi megoldás minden új háttérfeladatnál ismét beolvasta a teljes edzés vagy futam forrásadatait. A telemetria átalakítása minden pilótán végighaladt, noha az adott panel esetleg csak kettőre volt kíváncsi. A végén már kevesebb adatot tároltam, de az előtte elvégzett munka még mindig túl nagy volt. [2, 3]

Ezen két ponton változtattam. A feldolgozó folyamat megtartja a legutóbb sikeresen beolvasott adathalmazt, így az azonos futamra vonatkozó következő feladat felhasználhatja azt. Emellett már az átalakítás előtt érvényesítem, mely pilóták és mely adattípusok szükségesek. A nem kért mérésekből nem készülnek feleslegesen az alkalmazás saját adatszerkezetei.

A memóriában csak egy ilyen adathalmaz marad meg. Másik futam betöltésekor ezt lecserélem, kényszerített frissítéskor pedig újra kérem a forrást. Hiányos vagy sikertelen betöltést nem tartok meg sikeresként, különben egy újrapróbálkozás ugyanazt a hibás eredményt kapná vissza.

A változtatásnak van egy fontos határa. A FastF1 maga továbbra is az egész edzés vagy futam telemetriafolyamát olvassa be. A pilóták kiválasztása nem teszi automatikusan kisebbé ezt a külső letöltést. A javítással a saját átalakítási, feldolgozási és tárolási munkát szűkítettem a szükséges adatokra.''',
'4.5': '''A beolvasott méréseket az adatbázisba is el kell juttatni. A korábbi megoldás kötegekbe rendezte a sorokat, majd ezeket paraméteres beszúró műveletekkel adta át a PostgreSQL-nek. Nagyobb mennyiségnél ez az írási lépés is jelentős időt igényelt, ezért a módját külön átdolgoztam.

A javított változatban a PostgreSQL nagy adatmennyiségekhez készített COPY eljárását használom. Ez sok rekordot egy összefüggő adatfolyamként tud átvenni, ahelyett hogy a programnak minden köteghez hasonló beszúrási munkát kellene végeznie. A PostgreSQL dokumentációja ezt kifejezetten tömeges adatbetöltésre javasolja. [10]

A méréseket először egy ideiglenes táblába küldöm. Innen egy adatbázison belüli művelettel kerülnek a végleges táblákba. Az ideiglenes tábla az adott műveletsorhoz tartozik, ezért hiba esetén a teljes írás visszavonható. Ezt a közösen sikeresnek vagy sikertelennek tekintett műveletsort tranzakciónak nevezik.

A végleges táblák továbbra is ellenőrzik az adatok kapcsolatait és az ismétlődést. Egy mérés nem hivatkozhat nem létező futamra vagy pilótára, a korábban eltárolt sor pedig nem kerül be újra. Az új rekordokat ténylegesen megszámolom, így a feladat állapota a valóban elmentett adatokból számolható. A gyorsítás mellett ezek az ellenőrzések is megmaradtak. [2]

A tárolás átvizsgálásakor hiányzó indexeket is javítottam. Az index olyan keresési segédszerkezet, amely például egy pilóta megadott körének méréseihez gyorsabban vezeti el az adatbázist. A szükséges indexek egy része a program modelljében már szerepelt, a használt adatbázisban viszont még nem volt jelen. A sémát módosító lépések ezeket létrehozzák. A korábbi ellenőrzés a körre szűrt keresésnél az új index használatát is igazolta. [4]''',
'4.6': '''A lassúnak látszó működés mögött nem minden esetben lassú számítás állt. Az egyik hibánál a feladatok bekerültek a várakozási sorba, de nem indult el az őket feldolgozó háttérfolyamat. A felület ezért folyamatosan azt jelezte, hogy az adatok készülnek, miközben valójában nem volt, ami elvégezze a munkát.

A javításban a feldolgozó rendszeres életjelet ír az adatbázisba. Ebből a szerver külön meg tudja állapítani, hogy fut-e a háttérszolgáltatás, és mikor jelentkezett utoljára. Az indítási folyamatot is ehhez igazítottam: az adatkéréseket kiszolgáló szerver mellett a feldolgozónak is el kell indulnia. A felület így már más üzenetet adhat a várakozó munkára és a hiányzó szolgáltatásra.

Egy másik hibánál az üres telemetria is sikeres betöltésnek minősülhetett. Ha egy kért adattípus egyáltalán nem érkezik meg, abból nem lesz használható visszajátszás. Ugyanakkor egy kiesett pilóta olyan köréhez, amelyet nem teljesített, szabályosan sem tartozik mérés. Ezért megkülönböztetem a forrás betöltési hibáját és az ellenőrzött, valóban üres részletet. A korábbi hibásan késznek jelölt adatok újraellenőrzéséhez külön adatbázis-javítás készült. [3]

Több panel egyszerre is kérheti ugyanazt az adatrészletet. Ha mindegyik csak annyit ellenőrizne, hogy az adat még nincs kész, rövid időn belül több azonos munka is indulhatna. Ennek megelőzésére az ellenőrzést és a feladat létrehozását az adott futamhoz kötött zárolás védi. A soron következő kérés már a közben létrehozott munkát találja meg.

Hasonló védelem tartozik a közös adatok írásához is. A hosszabb feldolgozás közben frissülő életjel pedig segít megkülönböztetni a még működő, de lassabb munkát az elakadt feladattól. Ezek a javítások a gyorsabb betöltés mellett annak megbízhatóságát is javították.''',
'4.7': '''A betöltési idő értékelésénél külön kell választanom három helyzetet. Az elsőben a szükséges mérések már az alkalmazás adatbázisában vannak; ilyenkor azok lekérésére és a felület felépülésére vár a felhasználó. A másodikban a forrásfájlok korábban már letöltődtek, de a saját adatbázisba még elő kell készítenem a méréseket. A harmadikban a fájlokat is újonnan kell megszerezni a külső szolgáltatótól.

A rögzített teljes mezőnyös mérés a második helyzetet vizsgálta. A korábbi forrásfájlok rendelkezésre álltak, az alkalmazás adatbázisa viszont még nem tartalmazta a szükséges telemetriát. Ebben a próbában 93,687 másodperc után fejeződtek be a kezdeti visszajátszási adatkérések. Az eredményt ezekkel a feltételekkel használom a tesztelési fejezetben. [4]

Egy másik futam adatainál hozzáférési hiba is jelentkezett a külső forrásnál. Ilyenkor a helyes működés az, hogy az alkalmazás érthetően jelzi a hibát. Egy elérhetetlen forrást a gyorsabb adatbázis-írás sem tud pótolni, ezért ezt az esetet nem számítom sikeres új letöltési mérésnek.''',
'5.1': '''Az adatok előkészítése után azt is ellenőriznem kellett, hogy a visszajátszás valóban végig tud-e menni a futamon. A korábbi felület a pilótánkénti telemetriából az első húszezer sort kérte le. Egy hosszabb versenyhez ennél több mérés tartozott, ezért a válasz sikeres lehetett úgy is, hogy a futam vége már nem szerepelt benne.

Az idővonalhoz eközben sok nyers időrekordot töltöttem le. A lejátszás vezérléséhez viszont elsősorban arra van szükség, hogy mikor kezdődik és mikor ér véget a megjelenített időszak. Ezt külön, kisebb válaszban adom át a felületnek. A böngésző ebből építi fel a vezérlés időpontjait, a telemetria lekérését pedig a teljes vizsgált időtartományra állítom be. [2, 3]''',
'5.2': '''A pályatérképnek és a pilótakártyáknak ugyanazt a pillanatot kell mutatniuk. Ehhez közös lejátszási időt használok. Az indítás, megállítás, gyorsítás és időbeli ugrás ezt az értéket módosítja, a panelek pedig ehhez választják ki a megjelenítendő adatot.

A teljes futam áttekintéséhez nincs szükség minden tárolt mérés elküldésére. A megjelenítéshez legalább 500 milliszekundumonként választok mintát, hosszabb edzés vagy futam esetén pedig nagyobb időközt használok. Így a válasz korlátozott méretű marad, de a kiválasztott minták a teljes időszakot lefedik. A pontos záró időpontot a lejátszási órához akkor is hozzáadom, ha nem esik egy szokásos lépésre.

A ritkítás kizárólag a visszajátszás megjelenítését érinti. Az adatbázisban megmaradnak az eredeti részletes mérések, amelyekből egy kiválasztott kör később sűrűbb grafikonon is vizsgálható. A végpont megtartását és a lekért minták számának korlátját külön tesztek ellenőrzik.''',
'5.3': '''A pálya alakja lejátszás közben nem változik, ezért felesleges lenne minden időlépésnél újra felépíteni. A körökhöz tartozó geometriát a felület megtartja, és a lejátszási idő változásakor a pilóták aktuális helyzetét keresi meg rajta. A közösen lekért adatokból a panelek ugyanazt a változatlan pályaleírást használhatják.

A pilótaválasztásnál egy betöltési sorrendből adódó hibát is javítottam. A megnyitott oldal címe már tartalmazhatta a kiválasztott pilóták azonosítóját, miközben a névsor még nem érkezett meg a szervertől. Az üres listán végzett korai ellenőrzés emiatt törölhette az egyébként helyes választást. Egyes esetekben így a kívánt szűk adatkérés helyett szélesebb betöltés indulhatott.

Az ellenőrzést ezért a névsor betöltése utánra tettem. Ettől a pilótaválasztás megmarad a kezdeti várakozás alatt is. A hiba azt is megmutatta, hogy a felület működése közvetlenül befolyásolhatja, mennyi munkát kérünk a szervertől.''',
'5.4': '''Az első elemzőfelületek előre összeállított nézetek voltak. A felhasználó ezek közül választhatott, de a panelek elhelyezését nem alakíthatta szabadon. A későbbi változatban olyan szerkesztőt készítettem, amelyben maga választhatja ki, rendezheti át és méretezheti a megjelenítendő elemeket.

Ehhez külön kezeltem egy panel működését és annak elrendezését. A köridőgrafikon például ugyanaz a megjelenítőelem marad akkor is, ha több példányban kerül a felületre, eltérő pilóta- vagy körbeállításokkal. Az ilyen újrahasználható elemet a kódban widgetnek nevezem. Az elrendezés azt írja le, mely példányok szerepelnek az oldalon, és mekkora helyet foglalnak el. A teljes összeállított elemzőfelületre a dashboard elnevezést használom. [7]

A szerkesztő tizenkét oszlopos rácsra illeszti a paneleket. A méretet és elhelyezést egérrel, billentyűzettel vagy számszerű mezőkben is meg lehet adni. Az ütköző, túl kicsi vagy a területen kívülre kerülő elhelyezést ellenőrzöm. Ugyanezeket a szabályokat a szerver is ismeri, ezért egy hibás mentési kérést akkor is elutasíthat, ha az nem a szerkesztőből érkezik.

![A szerkesztőben kiválasztható panelek és az összeállított elemzőfelület.](testing/layout-builder-editor.png)''',
'5.5': '''A mentésnél a panelek helye mellett a beállításaikat is meg kell őriznem. Külön azonosítót adok az egyes példányoknak, ezért ugyanaz a widget többször is használható egymástól függetlenül. A gyári elrendezés módosítása helyett a felhasználó saját másolatot készíthet, amely nem változtatja meg a közös sablont.

A szerkesztés közben a korábbi állapotokhoz vissza lehet lépni. Sikertelen mentésnél a még el nem mentett összeállítás a felületen marad, és újra próbálható a művelet. A nézet elhagyása előtt jelzem az el nem mentett módosításokat. Ezekkel azt szerettem volna elkerülni, hogy egy félbeszakadt kérés miatt elvesszen a felhasználó munkája.

Az elrendezések előnézete egyszerűsített rajzot mutat a panelek típusáról és arányairól. Ehhez nincs szükség valódi futamadatok lekérésére; a kiválasztó ezért akkor is használható, ha még nincs megnyitott verseny. A tényleges grafikonok a betöltött edzés vagy futam nézetében jelennek meg.

A személyes elrendezés tulajdonosát a szerver a bejelentkezésből állapítja meg. A kliens által küldött tulajdonosazonosítóra nem hagyatkozik. A böngészőben megőrzött személyes adatok is fiókonként különülnek el, így egy másik felhasználó bejelentkezésekor nem jelenhet meg az előző fiók elrendezéslistája.''',
'5.6': '''A paneleket akkor is használhatóvá kellett tennem, ha a szerkesztő kisebb kijelzőn jelenik meg. A tervezéshez rögzített szélességű felületet használok, amelyet a böngésző a rendelkezésre álló helyhez kicsinyít. Az egérrel végzett húzást vissza kell számítani erre a tervezési méretre, különben a panel máshová kerülne, mint ahová a felhasználó mozdítja.

Minden widgethez méretkorlátok tartoznak. Egy táblázatnak vagy pályatérképnek meghatározott helyre van szüksége az olvasható megjelenítéshez; a szerkesztő ezért nem engedi korlátlanul összenyomni ezeket. A keskeny elemzőnézetben a panelek egymás alá rendeződnek, és a tartalmuk a tényleges mérethez igazodhat. A korábbi böngészős ellenőrzések több képernyőszélességen is végigjárták ezt a folyamatot.''',
'6.1': '''Az első számított mutatókat köridőkből készítettem. A tempóérték a közelmúlt használható köreinek idejét hasonlítja össze a kiválasztott pilóták között. Az egyenletesség azt jelzi, mennyire térnek el a körök a jellemző időtől. Ehhez a mediántól, vagyis a sorba rendezett köridők középső értékétől vett abszolút eltéréseket használom. A köridőtrend pedig két egymást követő időszak összevetésével mutatja a javulást vagy romlást.

A pontszám jelentése függ attól, kiket hasonlítok össze. Két pilóta között számított viszonyítás nem feltétlenül ugyanaz, mint a teljes mezőnyben kapott érték. A kiválasztott pilótákat és köröket ezért az eredmény mellett is meg kell őriznem.

Az első változat nem korrigálta a köridőt az üzemanyagra, a forgalomra, a gumi korára és az időjárásra. Ezek szerepeltek a korai ötletek között, de a számított értékben csak a ténylegesen megvalósított korrekcióra lehet hivatkozni. A hiányukat az eredmény figyelmeztetése jelzi.''',
'6.2': '''Az újabb számításokat közös katalógusba rendeztem. Minden bejegyzéshez azonosító, mértékegység, szükséges bemenet és értelmezési leírás tartozik. A megvalósított általános elemzési réteg tíz csoportban 137 definíciót, a külön stratégiai réteg további 67 definíciót tartalmaz. Ez nem ugyanennyi kész képernyőpanel: egy számítás több pilótára is adhat választ, és a megjelenítőelemek száma ettől független. [5, 6]

A számításokat úgy alakítottam ki, hogy az előkészített adatokon dolgozzanak, és ne indítsanak közben új forrásletöltést. A válaszhoz hozzátartozik, mennyi adat állt rendelkezésre és milyen korlátokkal értelmezhető az eredmény. Ha egy bemenet hiányzik, ezt külön állapot jelzi; a hiányt nem helyettesítem automatikusan nullával.

A stratégiai eredményeknél azt is megkülönböztetem, hogy megfigyelt adatról, abból pontosan kiszámítható értékről, becslésről vagy megadott feltételezésről van-e szó. Így a felület és a későbbi szöveges magyarázat is jelezheti, milyen bizonyíték áll egy szám mögött.''',
'6.3': '''A pilóták közötti különbség többféleképpen érthető. Az egy időpontban mért pozícióikból térbeli távolság számítható. Ha viszont azt vizsgálom, mekkora időkülönbséggel haladtak át ugyanazon a szektorhatáron, akkor azonos helyen megfigyelt időbeli eltérést kapok. Az üldözési helyzetek értelmezésénél fontos, hogy a két mennyiséget ne keverjem össze.

A megfelelő kör- és szektorátlépéseket ezért egymáshoz rendelem. Csak azokat a megfigyeléseket használom, amelyek a vizsgált pillanatig mindkét pilótánál megtörténtek. A különbség változásából becslés készíthető a felzárkózásra, de az előrejelzés feltételeit is közölni kell.

A gumikhoz kapcsolódó számításoknál egy másik korlát jelent meg. Ha az adatokban a gumi kora és a futam előrehaladása együtt változik, a modell nem tudja megbízhatóan eldönteni, melyik mennyire befolyásolta a köridőt. Ilyenkor nem közlök külön gumi- vagy üzemanyaghatást leíró együtthatót. Az ellenőrzéshez használt Miami-adatoknál a program is ezt a bizonytalan helyzetet jelezte. [6]

[Kiegészítendő: néhány kiválasztott mutató képlete, kézzel ellenőrizhető számpéldája és eredményábrája.]''',
'6.4': '''Egy korábbi versenyhelyzet elemzésénél csak azokból az adatokból szabad következtetni, amelyek addigra már rendelkezésre állhattak. Ha a visszajátszás egy kör közepén tart, annak végső köridőjét még nem használhatom. Ugyanígy egy későbbi leggyorsabb kör sem szolgálhat automatikusan a korábbi helyzet viszonyítási alapjául.

A stratégiai kéréshez ezért megadok egy vizsgált időpontot. A lekérés és a számítás is kiszűri az ezt követő megfigyeléseket. A tesztekben a jövőbeli köröket és pozíciókat szándékosan megváltoztatom, majd újra kiszámítom a korábbi helyzetet. Az eredménynek ilyenkor változatlannak kell maradnia.

Ehhez a versenyirányítási üzenetek időpontját is helyesen kellett kezelni. Az első megoldásban problémát okozott, ha az UTC-időt nem a forrás tényleges kezdőpontjához igazítottam. A javítás után ezt a kezdőpontot használom, a pilótához rendelést pedig a forrás rajtszámmezője alapján végzem. Ha a kezdőpont még nem áll rendelkezésre, nem készítek feltételezett időpontot. A részletes telemetria későbbi beolvasása után a kapcsolódó üzenetek külön frissíthetők.

A történeti adatoknak ettől még marad korlátjuk: a szolgáltató egyes jelzéseket a verseny után is javíthatott. A jelenlegi adatbázis nem őrzi minden ilyen javítás eredeti érkezési sorrendjét. A vizsgált események időpontját tudom figyelembe venni, a teljes eredeti adatközlés menetét nem állítom helyre.''',
'6.5': '''A stratégiai alaprétegben kiállás nélküli, egy- és kétkiállásos terveket tudok összehasonlítani. A program a támogatott lehetőségeket felsorolja, majd a modell szerint szükséges idő alapján rangsorolja őket. Ehhez többek között a gumiszettek, a gumikhoz tartozó feltételezett tempóváltozás, a kiállási veszteség és az alkalmazott szabályok is szükségesek.

A megadott feltételek meghatározzák az eredményt. Ha például a gumi viselkedését szemléltető görbével írom le, a legjobbként visszaadott terv erre a görbére érvényes. A valós versenyadatokon végzett korábbi próbában a keresés egy részéhez kifejezetten ilyen, mesterségesen megadott bemeneteket használtam. Ez a számítás és a teljes feldolgozási út működését mutatja meg, de nem bizonyítja a valódi futam legjobb stratégiáját. [6]''',
'6.6': '''Egy nagyobb számítás eredményét megőrzöm, hogy azonos kérésnél ne kelljen mindent újra elvégezni. A mentett eredményhez hozzátartozik a kiválasztott pilóták és időszak leírása, a számítás változata és a felhasznált adatok állapota. Ha ezek közül valamelyik megváltozik, a korábbi válasz már nem feltétlenül használható fel.

Az elemzést a visszajátszás indításától elkülönítettem. Egy mutató számítása nem kezd hiányzó telemetriát letölteni, a lejátszásnak pedig nem kell megvárnia a nagyobb elemzés eredményét. A hiányzó bemenet az elemzés válaszában jelenik meg.

A költségesebb számítások egyidejű futását korlátozom, hogy ne terheljék túl a szervert. A már kiszámított eredmény lekérése és a kisebb, egy pillanatra vonatkozó állapotlekérés ettől külön kiszolgálható. Ez segít megtartani a használhatóságot akkor is, amikor egy másik kérés több munkát igényel. [5]''',
'7.3': '''A szerkesztő már tartalmazza a widgetek hozzáférési címkéit és ezek szűrését, de a jelenlegi megvalósított elemek ingyenesek. A fizetős szűrő üres listája még nem előfizetési szolgáltatás. A személyes elrendezések tulajdonosát a szerver már ellenőrzi; a csomaghoz kötött használati korlátokat és a fizetési kapcsolatot még ki kell alakítanom. [7]

[Kidolgozandó: a ténylegesen megvalósított előfizetési szintek, szerveroldali ellenőrzések, tesztfizetés, csomagváltás és lemondás.]''',
'7.4': '''A kezdőoldal és a navigáció elkészült. A bajnoki tabellához, a hírfolyamhoz és a külön élő versenynézethez jelenleg előkészített, helyőrző oldalak tartoznak. Ezeken a funkció helye és tervezett szerepe látható, a teljes szolgáltatás még nincs bekötve.

A történeti adatok visszajátszása ettől külön, működő folyamat. A már eltárolt verseny lejátszása nem jelenti azt, hogy az alkalmazás az éppen zajló futam adatait folyamatosan fogadja. A két használati módot a további fejlesztés és az értékelés során is megkülönböztetem.''',
'8.1': '''A számítások ellenőrzéséhez olyan bemeneteket állítok össze, amelyekre az eredmény a programtól függetlenül is meghatározható. Állandó sebességnél például ismert az eltelt idő alatt megtett út. Előre megadott szektorátlépésekből pedig kézzel is kiszámítható két pilóta időkülönbsége. Ezekkel összevethető a program válasza.

A munkaváltozat összeállításához 33, adatbázist nem igénylő backendtesztet futtattam le sikeresen a numerikus, stratégiai és kiegészítő számításokhoz. A felület 14 meglévő egységtesztje is sikeres volt. Utóbbiak az elrendezési szabályokat, a lejátszási idő végpontját, a mintaszám korlátját és a bejelentkezés megújításának időzítését is vizsgálják. Ezek a próbák a teljes adatbázisos és böngészős ellenőrzést nem helyettesítik.''',
'8.2': '''A korábbi teljes ellenőrzésekben valódi adatbázison is vizsgáltam az írást, annak visszavonását, az ismételt kéréseket és a párhuzamos feldolgozást. A személyes adatoknál eltérő fiókokkal ellenőriztem, hogy az egyik felhasználó ne férhessen hozzá a másik elrendezéseihez. A böngészős próbák a szerkesztést, mentést és a visszajátszás kezelését is végigjárták. [4, 7]

A stratégiai alapréteg ellenőrzési jegyzőkönyve 66 sikeres backendtesztet rögzít. Ezt a korábbi teljes futtatás eredményeként közlöm. A most elvégzett szűkebb tesztkör és az összes integrációs ellenőrzés között különbséget teszek. [6]

[Kiegészítendő: a végleges változat teljes tesztfuttatása és a feladatkiírás minden pontjához rendelt ellenőrzés, a pontos környezettel és eredményekkel.]''',
'8.5': '''A közölt időadatok egy helyi környezetben végzett esettanulmányhoz tartoznak. Az értékelésnél meg kell őriznem, melyik programváltozat futott, milyen adatok álltak már rendelkezésre, és volt-e más terhelés a gépen. A numerikus tesztek ismételt futtatása önmagában nem frissíti a korábbi teljesítményméréseket.

A végső összehasonlításhoz azonos feltételekkel, többször megismételt próbák szükségesek. Ezekből a jellemző idő mellett az ingadozás is megadható. Az AI-funkciókat majd külön kell vizsgálni: egy magyarázatnál a válasz gyorsasága mellett az is számít, hogy a leírt állítás valóban következik-e a felhasznált adatokból.

[Kiegészítendő: a leadás előtti ismételt mérések és a még fejlesztés alatt álló funkciók ellenőrzése.]''',
'9.1': '''A fejlesztés során a felületet arra is használtam, hogy lássam, hol akad el a háttérben végzett munka. Egy végtelen betöltésjelzés vagy a lejátszás korai megállása másképp tette láthatóvá a problémát, mint egy önmagában sikeres adatkérés. Ezt a megközelítést már a korai projektjegyzetben is fontosnak tartottam. [1]

A hibák javításához ezért a szerver állapotjelzéseit is pontosítanom kellett. A sorban álló feladat, az aktív feldolgozás, a hiányzó feldolgozó és a forráshiba külön helyzetet jelent. Ha ezeket a felület is megkülönbözteti, a felhasználó érthetőbb visszajelzést kap, a hibakeresés pedig célzottabbá válik.''',
'9.2': '''A betöltés eleinte egyetlen lassú folyamatnak látszott. A vizsgálat során viszont különvált az ismételt forrásfeldolgozás, az adatbázisba írás, a hiányzó háttérfolyamat és a futam adatait levágó lekérés. Ezekre eltérő javítást kellett készítenem. Egyetlen réteg gyorsítása nem szüntette volna meg a többi hiba hatását.

Felmerült a nagyobb telemetriamennyiség külön fájl- vagy objektumtárban történő kezelése is. Előbb azonban a meglévő PostgreSQL-alapú feldolgozás költségét vizsgáltam meg. A kiválasztás, az ismételt feldolgozás és az írás javítása a mért adatmennyiségnél használható eredményt adott. Külön tárolási megoldást akkor érdemes bevezetni, ha a további mérések vagy más követelmény ezt indokolja. [3]''',
'9.3': '''A számított eredményeknél rendszeresen visszatérő kérdés, hogy pontosan mit támasztanak alá az adatok. Két autó közeli pozíciója önmagában nem bizonyít szélárnyékot vagy érintkezést. A hirtelen lassulás nem minden esetben baleset. Egy összehasonlított kiállási terv pedig csak a megadott bemenetek mellett tekinthető a modellben legjobbnak.

Ezért a hiányzó adatot, a becslést és a feltételezést a válaszban is megőrzöm. Ugyanezt az elvet kell majd követniük az AI-paneleknek: a szöveges magyarázat sem állíthat többet annál, mint amit a számítás és a bemenet alátámaszt.''',
'10.1': '''Elkészítettem az edzések és futamok közös adattárolását, a háttérben végzett adat-előkészítést, a visszajátszást és a személyes elemzőfelületek szerkesztését. Az adatbetöltés fejlesztése során szétválasztottam az alapadatokat és a részletes méréseket, csökkentettem az ismételt feldolgozást, és átdolgoztam a nagy mennyiségű adat írását. A visszajátszásnál a teljes időtartomány megjelenítését és a közös lejátszási idő kezelését javítottam.

Kialakítottam az általános és a stratégiai számítások elkülönített rétegét is. Az eredményeket a felhasznált adatokkal és az értelmezési korlátaikkal együtt adom vissza. A rögzített helyi mérések a rendelkezésre álló forrásadatok mellett használható indulási időt mutatnak.

Az AI-panelek, az előfizetési szolgáltatás, valamint a tabella és a hírfolyam teljes működése még további fejlesztést igényel. A végleges összegzésben ezek ténylegesen elkészült állapotát is értékelnem kell.''',
}


def main():
    original = SOURCE.read_text(encoding='utf-8')
    chunks = re.split(r'(?m)(^#{2,3} .+\n)', original)
    output = ['# Forma-1 telemetria elemző alkalmazás készítése\n\nNovák József Pál\n\nSzakdolgozati munkaváltozat.\n\n## Összefoglaló\n\n[Kiegészítendő: a végleges eredmények ismeretében írandó magyar tartalmi összefoglaló.]\n\n## Abstract\n\n[Kiegészítendő: a végleges magyar összefoglaló angol fordítása.]\n\n']
    for index in range(1, len(chunks), 2):
        heading, body = chunks[index], chunks[index + 1]
        match = re.match(r'(#{2,3}) (\d+(?:\.\d+)*)\. (.+)', heading)
        if match:
            level, key, old_title = match.groups()
            heading = f'{level} {key}. {TITLES.get(key, old_title)}\n'
            if key in TEXT:
                body = '\n' + TEXT[key] + '\n\n'
        if heading.strip() in ('## Összefoglaló', '## Abstract'):
            continue
        if heading.strip() == '## Irodalomjegyzék':
            body = '''
[1] Novák József Pál: F1app. Saját tervezési és fejlesztési jegyzetek.

[2] PitWall Insights. Az alkalmazás forráskódja és a fejlesztési változatokhoz tartozó saját projektanyagok.

[3] PitWall Insights. Az alkalmazás felépítése, adatbetöltése és a visszajátszás működése. Saját műszaki leírások.

[4] PitWall Insights. A betöltés és a visszajátszás ellenőrzési jegyzőkönyvei, futási naplói és mérési adatai.

[5] PitWall Insights. Az általános elemzési szolgáltatás számítási katalógusa és ellenőrzése.

[6] PitWall Insights. A stratégiai számítások leírása, a forgatókönyvek és az előrejelzések ellenőrzése.

[7] PitWall Insights. Az elrendezésszerkesztő felépítése és ellenőrzési jegyzőkönyve.

[8] React: Passing Data Deeply with Context. Hivatalos dokumentáció. https://react.dev/learn/passing-data-deeply-with-context

[9] TanStack Query: Overview. Hivatalos dokumentáció. https://tanstack.com/query/latest/docs/framework/react/overview

[10] PostgreSQL: Populating a Database, Use COPY. Hivatalos dokumentáció. https://www.postgresql.org/docs/18/populate.html

[Kiegészítendő: további releváns szakirodalom, összehasonlított alkalmazások és a végleges bibliográfiai adatok.]

'''
        output.extend([heading, body])
    text = ''.join(output)
    text = text.replace('Az alábbi értékek különböző, a projektben megőrzött 2026. október 18-i futtatásokból származnak. A cache állapota és a vizsgált művelet eltérhet, ezért a sorok nem egyetlen összehasonlító kísérlet változatai. [4, 6]', 'Az alábbi táblázatban a javított változat ellenőrzéséhez rögzített eredményeket mutatom be. A sorok különböző helyzeteket írnak le: más munkát jelent az adatok első előkészítése és a már eltárolt mérések lekérése. A körülményeket ezért minden eredmény mellett feltüntetem. [4, 6]')
    text = text.replace('Üres adatbázis-telemetria, 20 pilóta, Olasz Nagydíj 2025', 'Még nem tárolt telemetria, 20 pilóta, Olasz Nagydíj 2025')
    text = text.replace('Meglévő FastF1-forrásfájlok mellett, a kezdeti replaylekérésekkel együtt', 'A forrásfájlok már letöltve, a visszajátszás kezdeti adatkéréseivel együtt')
    text = text.replace('Már tárolt adatokból indított böngészős replay, későbbi regressziós futtatás', 'Már tárolt adatokból indított böngészős visszajátszás')
    text = text.replace('A teljes mezőny előkészítése a lemezes forráscache mellett', 'A teljes mezőny adatainak előkészítése a már letöltött forrásfájlok mellett')
    text = text.replace('A korábbi tizenöt perces tapasztalattal való szigorú összehasonlításhoz azonos bemenetű és környezetű előtte-utána mérés szükséges.', 'A tizenöt perces korábbi tapasztalat és ez az eredmény eltérő körülményekből származik. Számszerű gyorsulást csak azonos bemenetű és környezetű előtte-utána próbából lehetne megadni.')
    text = text.replace('Általános elemzés cache-ből, külön nyugalmi futtatásban', 'Korábbi elemzési eredmény lekérése, külön nyugalmi futtatásban')
    text = text.replace('Ugyanaz a kiválasztás és érvényes eredménycache', 'Azonos kiválasztás, megőrzött és még érvényes eredmény')
    text = text.replace('Cache-találat', 'A korábbi eredmény felhasználása')
    assert not any(c in text for c in '\u2013\u2014\u2015')
    assert not re.search(r'április|májusi|júniusi|október|november|Git-előzmények|kiinduló rendszer', text, re.IGNORECASE)
    SOURCE.write_text(text, encoding='utf-8')
    print('Updated narrative, definitions and chapter titles. Development dates are kept only in the separate source audit.')


if __name__ == '__main__':
    main()
