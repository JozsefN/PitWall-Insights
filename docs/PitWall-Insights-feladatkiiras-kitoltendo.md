# A feladatkiírás véglegesítése

A 2026. október 8-i változat a felhasználó által csatolt `feladatkiiras.docx` és a konzulensi megjegyzéseket tartalmazó kép alapján készült. Három rövid bekezdésből áll a bevezetés: általános háttér, az alkalmazás és a technológiák választásának indoklása, majd a szakdolgozat célja. Ezt hét, a mintának megfelelő felszólító módú feladatpont követi. A szöveg a PitWall Insights egészét írja le; az önálló laborban elkészült részek és az új fejlesztések megkülönböztetése a dolgozat előzményeket bemutató részébe tartozik.

A Word-változat a csatolt dokumentum logós fejlécét, intézményi láblécét, margóit és aláírási blokkját használja. A törzsszöveg 11 pontos Times New Roman, hogy az egész feladatlap olvashatóan egy oldalra férjen. A PDF közvetlenül ebből a Word-dokumentumból készült, így a két változat megjelenése egyezik.

A szerkesztendő fájl a [feladatkiírás-tervezet DOCX](PitWall-Insights-feladatkiiras-tervezet.docx), a hozzá tartozó [PDF](PitWall-Insights-feladatkiiras.pdf) Wordből exportált példány. A `szerkesztheto.docx` az aktuális Word-dokumentum másolata; a `tervezet.pdf` ugyanennek a PDF-nek a másik fájlneve. A generátor a Word-exportot használja mindegyik változathoz, külön PDF-elrendezés nem készül.

## Önálló laborból továbbvitt projekt

A 2026. október 6-án ellenőrzött nyilvános AUT- és VIK-forrásokban nem találtunk olyan kifejezett előírást, hogy az ilyen szakdolgozat feladatkiírása kizárólag az új félévben készülő funkciókat nevezheti meg. Ez nem külön intézményi engedély vagy automatikus kreditbeszámítás: a feladat tartalmát és a féléves munkát a konzulenssel kell egyeztetni.

A VIK Szakdolgozat-készítés tárgyának adatlapja önálló mérnöki munkát, a megoldás elemzését és értékelését, valamint a feladatkiírásban megnevezett valamennyi részfeladat bemutatását várja el. Az AUT útmutatója a féléves munka és elvárt eredmények konzulensi egyeztetését kéri. Ezekből a projekt egészének leírását, a korábbi alapok megjelölését és a szakdolgozati hozzájárulás egyértelmű bemutatását javasoljuk. Ez gyakorlati következtetés, nem egy szó szerint előírt feladatkiírás-formula.

A dolgozatban célszerű rövid „Előzmények és saját hozzájárulás” részt írni. Ebben rögzíthető a félév eleji állapot, az önálló laborban elkészült elemek, az új fejlesztések, az átdolgozások és az értékelés. A kiinduló állapotot a korábbi beszámoló és egy megfelelő Git-commit azonosíthatja. A korábbi beszámoló felhasznált szövegére vagy ábrájára is hivatkozni kell; a régi megvalósításokat nem célszerű új féléves eredményként bemutatni.

A teljes alkalmazás szerepelhet a tervezés, megvalósítás és értékelés leírásában, miközben a tárgyban elvárt új munka mennyiségét a konzulens külön értékeli. Nincs szükség a korábban elkészült saját modulok újbóli megírására pusztán a feladatkiírás megfogalmazása miatt. A végleges vállalások megfelelőségét a konzulensnek kell ellenőriznie.

## A portálon rögzített címek

Magyar: Forma-1 telemetria elemző alkalmazás készítése

Angol: Development of a Formula 1 Telemetry Analysis App

A címeket a felhasználó által bemásolt portáladatok szerint használjuk; az angol cím a másolható szövegfájlban szerepel. A nyilvános témaoldalt a webes eszköz nem tudta közvetlenül beolvasni.

## Beillesztett adatok és fogalmazás

- Név: Novák József Pál, a felhasználó javítása alapján.
- Neptun-kód: IT8VSG.
- Képzés: alapképzés, mérnökinformatikus szak; szakdolgozat.
- Tanszék: BME VIK, Automatizálási és Alkalmazott Informatikai Tanszék.
- Konzulens: Albert István, mérnöktanár. A beosztást az AUT telefonkönyvében ellenőriztük.
- Tanszékvezető: Dr. Charaf Hassan, egyetemi tanár. A korábban ellenőrzött AUT- és BME-oldalak alapján, a felhasználó megerősítésével.
- Dátum: 2026. október 8., az új tervezet elkészítésének napja. A konzulens a tényleges kiállításhoz igazíthatja.
- Külső konzulensről nem kaptunk adatot; a hozzá tartozó sort elhagytuk.

A szöveg az egyetem által a hallgató számára kiadott feladatként fogalmaz, a legutóbb megadott minta szerint. Nem személyes fejlesztési napló: a pontok „Mutassa be”, „Készítse el”, „Alakítson ki”, „Integráljon” és „Tesztelje” igékkel írják le az elvárt munkát. A bevezető bekezdésekhez nem tartoznak külön alcímek.

Az aktuális szöveg ZeroGPT-, Smodin- és AIDetego-vizsgálata, valamint a korábbi fogalmazások eredményei a [külön ellenőrzési jegyzetben](generated/feladatkiiras-ai-ellenorzes.md) szerepelnek. A pontszámokhoz a vizsgált szöveg azonosítója és az ellenőrzés korlátai is tartoznak.

## A heti tervhez igazított tartalom

A hét pont a rendszertervet, az adatbetöltést és elemzést visszajátszással, az elrendezésszerkesztőt, az előfizetési hozzáférést tesztfizetéssel, az AI-paneleket, a működő kezdőoldalt/tabellát/hírfolyamot, valamint a tesztelést és dokumentációt tartalmazza. Az AI-panelek száma és konkrét típusai nincsenek rögzítve: a feldolgozott telemetriából, a kiválasztott elemzési feladat és panelbeállítások alapján segítik a grafikonok és számok értelmezését.

A legutóbbi kérés alapján a bevezetés és az első két feladatpont a végső alkalmazás célját írja le: a pilóták közötti különbségek, a küzdelmek és a gumihasználat adatainak értelmezését. Az elemzési feladat nem rögzít szűk metrikalistát vagy konkrét képleteket. Az egyszerű adatmegjelenítés mellett az alapadatokból számított összetett mutatók és összefüggések is a projekt részei. A külön rendszertervezési felszólítás kikerült az első pontból; az architektúra bemutatása a szakdolgozati dokumentáció része marad.

A csatolt Word tartalmához igazodva külön chatbot nem kötelező részfeladat. Az előfizetési szintek konkrét nevei, árai és számbeli keretei a tervezés során határozhatók meg. A fizetési folyamat tesztkörnyezetre vonatkozik, a bajnoki tabella frissítése pedig nem ígér verseny közbeni élő állást.

## A végső alkalmazás elemzési iránya

A feldolgozás az adatbetöltéstől a számított metrikákon át a kiemelt összefüggésekig vezet. A nézői áttekintésből az legyen követhető, hol alakul ki küzdelem, ki közeledik az előtte haladóhoz, és hogyan változik a versenytempó. Ugyanazokból az adatokból részletesebb pilóta-, kör- és etap-összehasonlítás is készülhet a műszaki érdeklődésű felhasználóknak. A dashboard összeállítása dönti el, milyen részletességű nézetet használnak.

A meglévő metrikamodul tempó-, egyenletességi és köridőváltozási számításokat tartalmaz. A regisztrálható számítások és az ezekre épülő szabályok jó alapot adnak az összetettebb elemzésekhez. A pilótapárok időkülönbségének és felzárkózásának vizsgálata, illetve a gumikeverék, a gumi kora és az etap alatti tempóváltozás összevetése ezt bővítheti. Ezek értelmezhető fejlesztési irányok; a feladatkiírás szándékosan nem nevez meg előzési valószínűséget vagy pontos fizikai gumikopási modellt.

Az AI-panelek feladata a már feldolgozott és kiszámított adatok magyarázata. Az elemzéshez tartozó pilóták, időszakok és értékek visszakereshetők maradnak. A metrikák számítását és ellenőrzését a feldolgozó réteg végzi, ezért a magyarázatok értékelésénél külön vizsgálható, hogy a szöveges következtetés összhangban van-e az alapjául szolgáló eredményekkel.

A terv feltételes elemei nem szerepelnek külön vállalásként: automatikus AI-körkommentár, természetes nyelvű munkamenet-keresés, verseny közbeni ideiglenes bajnoki állás, AI-hírösszefoglaló, felhasználói vizsgálat. A korábbi terv további bővítései (pitablak-becslés, külön fékezési elemzés, többszintű panelbeágyazás) sem kötelező részfeladatok.

## Megnézett példák

- BME MIT: „Telemetria rendszer, mozgó objektumok valós idejű ellenőrzésére”, 2015-ös önálló labor témakiírás. Rövid célleírás után konkrét adatgyűjtési, megjelenítési és visszajátszási feladatokat sorol fel. Ez korábbi témakiírás, nem jóváhagyott AUT-szakdolgozati feladatlap: https://regiweb.mit.bme.hu/eng/node/9799
- AUT: Albert István „Alaprajz tervező webes alkalmazás készítése” témája. Egyszerű funkciófelsorolást alkalmaz; a témahirdetés opcionális elemeit nem vettük át. Ez a jelenlegi félév témája, nem korábbi beadott dolgozat: https://www.aut.bme.hu/Task/26-27-osz/Alaprajz-tervezo-webes-alkalmazas
- AUT: „Fullstack webalkalmazás készítése Spring és React technológiákkal”, jelenlegi féléves témakiírás. A konkrét funkciókra és a rendszer részeire koncentrál: https://www.aut.bme.hu/Task/26-27-osz/Fullstack-webalkalmazas

A példák szerkezeti támpontok. A PitWall Insights feladatszövege a saját projekt és a heti terv alapján készült. Nyilvánosan hozzáférhető, jóváhagyott, névre szóló korábbi AUT-feladatlapot a keresés során nem sikerült ellenőrizni.

## Ellenőrzött formai és eljárási információk

A mellékelt `Diplomaterv_Portal_leiras_v15.pdf` 17. oldala a témalétrehozásnál magyar és angol címet, Neptun-kódot, képzést és tárgyat kér. A 19–21. oldal szerint a feladatkiírás PDF-ben kerül feltöltésre a konzulens által, majd tanszékvezetői jóváhagyás szükséges. Az útmutatóban a méretkorlát 15 MB; a tényleges feltöltési felület aktuális korlátja az irányadó.

Az útmutató nem ad konkrét szószámot vagy karakterkorlátot a feladatkiírás szövegére. Az AUT-sablon hallgatói adatokat, címet, bevezetést, feladatpontokat, konzulensi adatokat, dátumot és tanszékvezetői blokkot tartalmaz. A tervezet ezt a szerkezetet követi. A hét feladatpont tartalmi döntés, nem intézményi előírás.

A feladatkiírás nem azonos a dolgozat későbbi magyar és angol összefoglalójával vagy a szakdolgozati adatlappal. Ezek külön portálfeladatok.

A megadott táblázat feltöltési határideje 2026. október 9. 00:00, felelőse a konzulens. A táblázat maga tájékoztató jellegűnek nevezi az időpontokat; a tényleges határidőt a konzulenssel/tanszékkel kell egyeztetni. A december 6-i fejlesztési céldátum nem kerül hivatalos beadási határidőként a feladatkiírásba.

## Források

- A felhasználó által megadott portálútmutató: `C:/Users/jozse/Downloads/Diplomaterv_Portal_leiras_v15.pdf`, 17., 19–21. oldal.
- AUT segédletek: https://www.aut.bme.hu/Pages/Gyik/Diploma
- Magyar feladatkiírás-sablon: https://www.aut.bme.hu/Upload/Course/VIAUMT00/publikus_anyagok/FeladatkiirasSablonAUT.docx
- AUT GYIK: https://www.aut.bme.hu/Pages/Gyik/Diploma/Gyik
- AUT tanszékvezetés: https://www.aut.bme.hu/Staff
- AUT telefonkönyv, konzulensi és tanszékvezetői beosztások: https://www.aut.bme.hu/staff/Phonebook
- Téma nyilvános oldala (a tartalom a felhasználó másolatából): https://diplomaterv.vik.bme.hu/hu/Theses/Forma1-telemetria-elemzo-alkalmazas-keszitese
- VIK Szakdolgozat-készítés tantárgyi adatlap (7., 8. és 10. pont): https://portal.vik.bme.hu/kepzes/targyak/VIAUAT00/
- AUT önálló labor, szakdolgozat és diplomaterv tudnivalók (féléves munka és konzulensi egyeztetés): https://www.aut.bme.hu/Upload/Pages/Gyik/Onlab/OnalloLaborTudnivalok.pdf

Az aktuális Word-dokumentum PDF-exportja elkészült. Ha a konzulensi egyeztetés után változik a DOCX, abból új PDF-et kell exportálni. A tervezet önmagában nem minősül jóváhagyott vagy feltöltött feladatkiírásnak.
