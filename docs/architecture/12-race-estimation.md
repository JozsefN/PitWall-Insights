# Fizikai becslések és versenyelemző panelek

A `race_estimation_v2` közös időhatárt, finomított előzésbecslést és új eseménykategóriákat használ. A miniszektorok, bokszbecslések, rádióüzenetek és versenytempó új felületeit a [session review leírás](13-session-review.md) dokumentálja. Az alábbi mérési hivatkozások az első változat ellenőrzését őrzik.

Állapot: implementált, helyben numerikus, PostgreSQL-, API- és böngészős ellenőrzéssel. Modell: `race_estimation_v1`. A fizikai paraméterek futamonkénti kalibrációja és a detektorok címkézett adaton történő pontosságmérése további munka. A becslés determinisztikus, MI-t nem használ.

## A meglévő mutatók újraértékelése

A 137 általános és 67 stratégiai definíció megmarad. A köridő, sebesség, szektor, gumikor, átlag, medián és vezérlési arány továbbra is hasznos bemenet és megjeleníthető eredmény. Ezeket nem helyettesítjük feltételezett gumikopással. Az új, 75 definíciós réteg a már normalizált adatra épít fizikai forgatókönyveket, időben követhető eseményjelölteket és közös panelpillanatképet. A katalógusok fogalmai részben átfedik egymást; számuk nem az egymástól független szenzormérések száma.

| Réteg | Megtartott feladat | Értelmezési szabály |
| --- | --- | --- |
| Általános elemzés | Körök, szektorok, vezérlés, sebesség, időjárás, egyszerű statisztika | A mintavétel és az elérhetőség korlátozza a felbontást. A referenciaív távolsága nem pályahatár. |
| Stratégiai alapok | Tiszta körös tempó, kétpilótás időköz, kiállási veszteség, gumi- és üzemanyaghatás azonosíthatósága, tervkeresés | A korrigált komponenshez azonosítható illesztés kell. A szintetikus forgatókönyv nem versenybizonyíték. |
| Új becslési modell | Turbulens légáramlat, terhelés, fékezés, közeli autók, eseményjelöltek, szélfizika, paneladatok | A képlet, az alapfeltevés, a rendelkezésre állás és a bizonyíték erőssége külön szerepel. |

A korábbi körszomszédokon alapuló nettó kiállásveszteség-becslés és a rivális rossz kiállását kezelő ellenhipotetikus számítás a stratégiai szolgáltatásban marad. Az új Pit scenarios panel egyszerűbb, egyértelműen feltételezett forgatókönyvet mutat. Nem nevezi a 22 másodperces alapértéket mért pályaadatnak és nem állít optimális kiállási időpontot.

## Adatút és modulhatárok

1. Az OpenF1-adapter adatot tölt le, a normalizálás közös időorigóra és tárolási formára hozza.
2. A telemetria előkészítését a meglévő háttérmunka végzi. Az elemző kérés közvetlenül nem kér külső adatot.
3. A `RaceEstimationService` a meglévő `AnalysisInputProvider` révén időablakos, mintavételezett adatbázis-lekérdezést futtat. A natív időköz-, sorrend-, kiállás- és előzésjelentések a forrásrészletekből érkeznek.
4. A tiszta domainréteg végzi a fizikai és eseményszámításokat. A bemenő adatbázis-kapcsolat és HTTP-kliens nem kerül a domainbe.
5. A `RaceEstimationProvider` egyetlen megosztott lekérdezést tart fenn az adott összeállításhoz. A panelek ugyanazon határidőből, kiválasztott pilótákból és paraméterekből dolgoznak.
6. A válasz a meglévő elemzési cache-táblába kerül. Új adatbázis-migráció nem szükséges.

Fő fájlok: `backend/modules/feature_metrics/domain/race_estimation/{models,catalog,common,traffic,driver,events,engine}.py`; `application/race_estimation_service.py`; `delivery_api/api/race_estimation_routes.py`; `frontend/src/features/race-insights/`; `frontend/src/widgets/insights/`. A widgetjegyzék továbbra is a közös `shared/dashboard-widgets.json`.

Az elemzés felhasználóhoz kötött cache-kulcsot kap: munkamenet, tulajdonos, modellverzió, katalógus, adatlenyomat és a teljes kérés. Élettartama 6 óra, munkamenetenként és felhasználónként legfeljebb 32 változat marad. A minták újraolvasását a cache-találat elkerüli. A folyamaton belüli és PostgreSQL-zár a korábbi elemző szolgáltatással közös. A számítás közben megváltozó adatlenyomat 409-es újrapróbálható hibát ad. A privát adathalmazokhoz az API meglévő tulajdonosi ellenőrzése szükséges.

## Időbeli szerződés

A POST-kérés kötelező `as_of_ms` értéke a megengedett legkésőbbi idő. A még be nem fejezett kör végső ideje, gumija és utólagos kimenetele nem látszhat korábban. A natív időközök, sorrendek és jelentett események alapértelmezett hozzáférési késleltetése 1000 ms. A kiállási idő legkorábban a jelentett kezdet plusz a látogatás ismert időtartama és a késleltetés után használható.

A felület lefelé kerekít 5 másodperces pillanatképre, és nem viszi tovább egy korábbi lekérdezési kulcs eredményét visszatekeréskor. A hírfolyam külön is kiszűri az aktuális lejátszási időnél későbbi üzeneteket. A teljes futamos lookback a tárolt idővonal végéhez kötődik; a kiválasztott kör nem változtatja meg észrevétlenül a becslési panel időablakát. A panel mindig mutatja a saját határidőpontját.

A friss időközre épülő taktikai panelek, köztük a Wake & traffic, csak nagydíj-visszajátszásban érhetők el. A lezárt körökre épülő tempó- és etap-összevetések az alkalmazható edzéstípusok utólagos elemzésében is használhatók. A panelenkénti mód- és edzéstípus-szabályokat a közös widgetkatalógus tárolja. A mentés és a session nézet egyaránt ellenőrzi ezeket.

Az eredmény eseményidő szerinti visszajátszás. A történeti forrás javításai miatt az eredeti hálózati érkezési sorrend nem rekonstruálható. A rögzített késleltetés sem bizonyítja, hogy az eredeti élő közvetítés pontosan ekkor tudta volna az adatot.

## Közeli autók és légáramlat

A fizikai közelséget nem az XYZ-ben legközelebbi pont jelenti: egy hajtűkanyar másik ágán álló autó más pályaszakaszon lehet. A modell friss natív időközt és ismert futamsorrendet használ. Az időköz 8 másodperc után elévül, a sorrend állapotváltozás-jelentésként a következő változásig megmarad. A körkülönbséget jelölő szöveget nem alakítjuk másodperccé. A körhátrány-jelentés önmagában nem azonosít egy fizikailag közeli lekörözendő autót.

Állandó, közel azonos sebességű követésben `d ≈ gap * v`. A 0,4 s időköz 80 km/h-nál 8,89 m, 250 km/h-nál 27,78 m. A becslés a saját autó sebességét használja, ezért erősen változó fékezési fázisban kisebb a fizikai jelentősége. Az átlagos időköz és a fejköztávolság-átlag az érvényes minták időtartamával súlyozott.

A veszteségforgatókönyv: `loss(d) = min(35, 18 * exp(-(d-10)/6.65)) %`. A 10 m-nél 18%, 20 m-nél körülbelül 4% veszteség a 2022-es tervezési kutatásból választott támpont. Nem 2023-2025-ös autók illesztett modellje; a 35%-os plafon saját feltevés. A forrásban leírt megváltozott tervezési környezet miatt más korszakra nem vihető át automatikusan. [F1: a 2022-es autó tervezési céljai](https://www.formula1.com/en/latest/article/10-things-you-need-to-know-about-the-all-new-2022-f1-car.4OLg8DrXyzHzdoGrbqp6ye).

`R = R_200 * (v_air/200)^2 * rho/1.225`, alapértelmezésben `R_200=2.5`. A kvázistacionárius kanyarsebesség-érzékenység `100 * (1 - sqrt((1+R*(1-loss/100))/(1+R)))`. Ez a függőleges aerodinamikai terhelés és a tapadás egyszerű összefüggése. A gumi terhelésérzékenysége, beállítás, hasmagasság, oldalsó átfedés és aktív energiamenedzsment nincs azonosítva. Az egyenes szakaszokra használt vonóhatás a veszteségi prior 0,35-szöröse; ez különösen bizonytalan, nem mért légellenállás.

Az időköztrend legfeljebb 30 másodperc friss jelentéséből illesztett egyenes negatív meredeksége. Legalább három pont, friss utolsó jelentés és stabil célpont szükséges. A nagy időkorrekció vagy célpontcsere kizárja az extrapolációt. A pozitív zárkózási meredekségből a 10 s-os rés `max(0, gap-closing*10)`. Az elérési idő `gap/closing`, legfeljebb 120 s-ig; ez állandó trendű forgatókönyv, nem előzési valószínűség.

## Gumi és tempó

Az oldalgyorsulás becslése `a_y ≈ v * |delta heading| / dt`, rövid mediánszűréssel. A fordulási szög az egymást követő pozíciókból jön, a pozíció méteregysége külön feltevés. Az OpenF1 közelítő koordinátáiból nem állapítható meg hiteles oldalirányú elhelyezkedés vagy pályahatár. A hirtelen teleportálást és a nem folytonos szakaszokat elvetjük. [OpenF1-adatszerződés](https://openf1.org/docs/).

Folytonos, ismert zöld és nem boxszakaszon: `corner=min(1,a_y/4g)^2`; `traction=clamp(a_x/1.5g)*throttle/100`; `extra=min(1,loss_fraction*(a_y/g)^2)`. A pillanatnyi igény `D=clamp(0.65*corner+0.25*traction+2*extra)`. A hőterhelési állapot `T_next=T*exp(-dt/tau)+D*(1-exp(-dt/tau))`, `tau=60 s`. A panel `100*T` indexet mutat. Az ablak elején T=0 a feltevés; ismeretlen korábbi hőállapotot nem állítunk vissza. Geometriai lefedettség nélkül a kanyar- és összetett gumiterhelés elérhetetlen.

A terhelésindex nem °C, kopási százalék vagy hátralévő gumiélettartam. A valódi gumihőmodellhez szükséges csúszás, kerékfordulatszám, gumianyag és hőátadás nem áll rendelkezésre. A követés miatti csökkent leszorítóerő és a csúszás kapcsolata fizikailag indokolja a munkaterhelési forgatókönyvet, de az időközből nem bizonyítható a konkrét autó kopása. [Pirelli: követés és gumiterhelés](https://press.pirelli.com/the-grand-prix-of-europe-from-a-tyre-point-of-view/); [West és munkatársai: termikus gumi- és pályamodell](https://repository.up.ac.za/bitstream/2263/83745/1/West_Optimal_2022.pdf).

A tempó a legutóbbi, ismert zöld, pontos, nem generált, nem törölt és boxérintés nélküli körökből készül. A friss tempó legfeljebb öt azonos keverékű és stintű kör mediánja. A trend legalább négy, legfeljebb nyolc összehasonlítható kör páronkénti meredekségének mediánja. A pozitív trendből az 1 s-os romlásig hátralévő kör `1/trend`; ez nem a gumi élettartama. A negatív vagy nem azonosítható trend nem ad ilyen előrejelzést.

A forgalommal együtt megfigyelt tempókülönbséghez legalább két tisztább és két forgalmas kör, azonos keverék/stint és megfelelő időköz-lefedettség kell. A különbség asszociáció. A gyorsan javuló esős pálya, fogyó üzemanyag, ERS és taktikai visszavétel ettől még magyarázhatja. A teljesebb, azonosíthatóságot ellenőrző korrekciók a meglévő stratégiai modellben érhetők el.

## Fékezés és eseményjelöltek

`a_x=(v_i-v_(i-1))/dt`; a sebességet előbb m/s-ra váltjuk. A lassulás g-ben jelenik meg. A fékezési szakasz fajlagos mozgásienergia-csökkenése `max(0,(v_prev²-v²)/2)/1000 kJ/kg`. A tömeg hiányában nem használunk önkényesen választott autótömeget. A képlet a mozgási energia csökkenése a fékezés idején, amelybe légellenállás, hajtáslánc és emelkedő is beleszólhat; nem a féktárcsa mért hőterhelése.

| Jelölt | Feltétel | Szükséges kizárás és alternatíva |
| --- | --- | --- |
| Braking anomaly | Legalább 1 s és négy friss minta, fék bekapcsolva, sebesség legalább 100 km/h, kis gáz, legfeljebb 1 km/h mintakülönbség | Kerekítés, kis fékerő, lejtő, aszinkron adat. A kerékblokkolás nem figyelhető meg. |
| Traction disruption | Azonos fokozat, 70% feletti gáz, 12% feletti RPM-ugrás, 2 km/h alatti gyorsulás | Kuplung, váltási átmenet, zaj, minták eltolódása. 5 s ismétlésvédelem. |
| Stopped car | Legalább 4 s és négy friss minta, legfeljebb 5 km/h | Ismert zöld futás, megfigyelt körkezdet, nem ismert box. Még be nem jelentett boxtevékenység is lehetséges. |
| Possible incident | A tartós megállás előtt 5 s-on belül legalább 150 km/h, legalább 80 km/h sebességvesztés | Műszaki kiesés, kipörgés vagy ismeretlen mentési tevékenység. Nem bizonyított ütközés. |
| Traffic pressure | Legalább 5 s követés a beállított közeli résben | Nem igazolja a köridőromlás okát. |

Az OpenF1 fékadata bináris, körülbelül 3,7 Hz-es autótelemetria része. A blokkolás kinematikai azonosításához kerékfordulatszám és keréksugár szükséges: `slip=(v-R*omega)/v`. A puszta járműsebesség-plató ezért csak gyenge jelölt lehet. [OpenF1](https://openf1.org/docs/); [F1: lock-up fogalom](https://www.formula1.com/en/latest/article/f1-glossary-k-o.6g2hrWHA2pyxbXoe8FT9Db).

A hírfolyam a hivatalos versenyirányítási eseményeket `reported`, a befejezett körből számított rekordot `observed`, a detektor eredményét `candidate` jelzéssel különbözteti meg. A jelentett előzés is forrásjelentés: a boxkizárás és a mintavétel nem ad teljes körű bizonyítást egy pályán végrehajtott manőverről. SC-behívási valószínűséget nem találunk ki a sebességesésből.

## Időjárás és szél

A légsűrűség szárazlevegő-közelítése `rho=p/(287.05*(T+273.15))`, mbarból Pa-ba váltott nyomással. Az időjárás legfeljebb 120 s-os lehet. Földrajzi észak és szélirány-konvenció nélkül a szembeszél/oldalszél elérhetetlen; a légsebesség megengedett magnitúdótartománya `max(0,v-w)..v+w`.

Explicit kalibráció után a szembeszél `w*cos(theta_from-heading)` és az oldalszél `w*sin(theta_from-heading)`. A relatív légsebesség `sqrt((v+headwind)^2+crosswind^2)`, a dinamikus nyomás `q=0.5*rho*v_air²`. A leszorítóerő-terhelési forgatókönyv ezt a kalibrált légsebességet használja; egyébként középértékként a talajsebesség szerepel. A dinamikus nyomás szélsőértékei a szélirány ismeretlenségéből jönnek. Ezek nem tartalmaznak illesztett aerodinamikai együtthatót vagy számított köridőbüntetést.

## Bizonytalanság és százalékok

A százalékos lefedettség tényleges arány. Az index 0-100 közé skálázott, dokumentált heurisztika. A `support` a megfigyelési lefedettségből, mintaszámból és a módszerhez választott szorzóból áll; például az aerodinamikai becslés legfeljebb 0,4-es támogatást kap. Ez nem megtanult, kalibrált valószínűség.

A `sensitivity_range` elnevezésű intervallum választott forgatókönyv-tartomány. Több esetben szabály szerinti szorzó, például a fejköztávolság 0,7-1,3-szorosa vagy a feltételezett nettó boxveszteség 0,7-1,3-szorosa. Nem statisztikai konfidenciaintervallum. A szélből adódó nyomástartomány geometriai szélsőérték. Minden tartomány pontos szabálya a kódban és a katalógusban követhető; későbbi kalibráció módosítja a modellverziót.

## Panelek, szerepkörök és jogosultság

| Panel | Elsődleges használó | Tartalom |
| --- | --- | --- |
| Race notifications | Néző, elemző | Szűrhető versenyirányítás, rekordok, kiállások, előzések és jelöltek |
| Driver overview | Néző | Sebesség, friss tempó, gumikor, következő autó |
| Battle radar | Néző, stratégiai elemző | Sorrendi szomszédok és friss időközök |
| Wake & traffic | Mérnöki elemző | Követés, légáramlat- és kanyarsebesség-forgatókönyv |
| Tyre workload | Mérnöki elemző | Kanyar-, hajtási és követési munkaterhelés |
| Braking analysis | Mérnöki elemző | Fékezési epizódok, lassulás és fajlagos energia |
| Pace context | Stratégiai elemző | Saját tempóalap, szóródás és forgalmi asszociáció |
| Gap evolution | Stratégiai elemző | Rés, átlagos fejköz, trend és extrapoláció |
| Attack & defence | Néző, stratégiai elemző | Lehetőségindexek, DRS és vonóhatás |
| Pit scenarios | Stratégiai elemző | Feltevéses nettó veszteség és kiállás utáni rés |
| Incident watch | Néző, elemző | Jelöltek és jelentett figyelmeztetések |
| Track & weather | Mindegyik | Pályaállapot, friss időjárás és szélfizika |
| Stint performance | Stratégiai elemző | Gumikor, összehasonlítható körök, tempótrend |
| Driver comparison | Elemző | Két kiválasztott pilóta azonos időpontú összevetése |
| Model evidence | Mérnök, fejlesztő | Lefedettség, frissesség, alapfeltevések, korlátok |

Négy új, változatlan gyári azonosítójú sablon: Race spectator, Engineering desk, Strategy desk és Race review. Saját másolat és kedvenccsillag továbbra is a meglévő folyamatot használja. A gyári sablon nem törölhető vagy felülírható.

Az értesítéspanel mentett beállításai: `eventTypes`, `includeCandidates`, `minSeverity`, `driverScope`, `maxItems`, `lookbackMinutes`. Üres kategórialista semmit sem mutat. A kiválasztott pilóták szűrése mellett a globális versenyirányítás megmarad. A szám 3, 5, 10 vagy automatikus; az automatikus kapacitás a tényleges panelmagasságból számított `clamp(floor((height-170)/85),1,12)`. Az ablak 1, 3 vagy 5 perc. Az üzenet részletei lenyithatók. A globális eseménykészlet szerveroldalon korlátozott, a csonkolást a felület jelzi.

Minden jelenlegi panel ingyenes, `accessTier=0`. A `plannedAccessTier` 0/1/2 értéke a későbbi terméktervhez tartozó metaadat, nem fizetési jogosultság és nem aktív paywall. A valódi díjcsomaghoz később szerveroldali jogosultság és fizetési integráció szükséges; a böngészős szűrő önmagában nem alkalmas rá.

## API és fejlesztői runbook

`GET /api/feature-metrics/race-estimates/catalog` hitelesítve adja a definíciókat, képleteket, bemeneteket, felhasználást, eseménytípusokat és alapfeltevéseket.

`POST /api/feature-metrics/sessions/{session_id}/race-estimates` példa:

```json
{"as_of_ms":10000000,"entry_ids":["selected-entry-id"],"lookback_ms":300000,"sample_interval_ms":500,"prediction_horizon_s":10,"max_events":500,"assumptions":{"pit_loss_scenario_s":22}}
```

Legfeljebb 64 pilóta választható; a teljes mezőny korábban materializált telemetriája a kontextushoz olvasható. Az ablak 30 s és 30 perc közötti, a mintavétel 250-1000 ms. Hibák: 401 hitelesítés, 404 adathalmaz vagy tulajdonosi hozzáférés, 422 érvénytelen bemenet, 413 munkakorlát, 429 foglalt elemző, 409 közben megváltozott telemetria. Az eredmény metrikánként értéket, egységet, státuszt, módszert, támogatást, tartományt és magyarázatot ad.

Új számítás hozzáadásakor:

1. Írd le a döntést, amelyet az érték támogat, és a szükséges nyers mezőket. Ha a bemenet nem áll rendelkezésre, ne találj ki helyettesítő megfigyelést.
2. A `catalog.py` megfelelő csoportjába vegyél fel stabil azonosítót, címkét, egységet, módszert és képletet. A csoport kötelező bemeneteit és célját ellenőrizd. Válaszd külön a mért arányt, forgatókönyvet és heurisztikus indexet.
3. A tiszta domainfüggvény csak a látható pillanatképet és explicit paramétert használhatja. Minden as-of illesztés a múlt irányába történjen. Kezeld külön a változásjelentést és a folyamatos szenzormintát.
4. Adj fizikai tartományellenőrzést, mértékegység-váltást, hiányzóadat-ágat és indokot. Az ismeretlen értéket ne tedd nullává. Tartományhoz írd le, hogy érzékenységi feltevés, fizikai korlát vagy mintaszóródás adja.
5. Új eseményhez azonosítsd az első bizonyítható észlelési időt. Az esemény időbélyege ezt kövesse, a becsült kezdet külön mező. Stabil azonosítóval deduplikálj. Sorold fel az érdemi alternatív magyarázatokat.
6. Ellenőrizd kézzel számolható numerikus példával, a jövőbeli adatok hozzáadására változatlan múltbeli eredménnyel, hiányos/stale mintával, boxszal, SC-vel, körhátránnyal és normál manőverrel. A teszt ne csak a saját képletet másolja.
7. Algoritmus vagy paraméterszemantika módosításakor növeld a modellverziót. Futtasd az exportot, majd a `--check` változatot. Kalibrációhoz a paraméter, tanító időszak és a független ellenőrző futam eredete is szükséges.

Új elemzőpanel hozzáadásakor:

1. Kövesd a [widgetrunbookot](07-dashboard-builder-foundation.md). A közös JSON-jegyzékben legyen stabil ID, célcsoport, keresőkifejezés, méretkorlát, használható alapméret, előnézettípus és tényleges `accessTier`.
2. A méretet a megjelenített tartalomhoz válaszd. Az új panelek rugalmas alakúak, minimum 4 oszlop és 4 sor; a táblák belül görgethetők. Az olvashatóságot mobilon és a legkisebb méreten is vizsgáld.
3. Az új panel a `RaceEstimationProvider` eredményét használja; saját forrásletöltést, külön időorigót vagy panelenkénti elemzési kérést nem indíthat. Új komponensregisztráció a `insight.registry.tsx` fájlba, tartalmi specifikáció a `panel-specs.ts` fájlba kerül.
4. A cím és beállítás példányhoz tartozik. Új opcióhoz szerveroldali típustartomány-ellenőrzés, szerkesztőkontroll és mentés-visszaolvasás teszt szükséges. A gyári sablon változatlan és csak másolható.
5. Az előnézet hálózat nélküli szemléltető rajz. A valódi panel csak a tényleges API-eredményt mutatja, a hiányt külön jelzi. A jelölt, index és feltevés ne váljon bizonyított versenyeseménnyé a felületi címben.
6. Teszteld a címkéket a tényleges katalógusmezővel (`metric_id`), a kétpilótás összevetést, a visszatekerést, a közös kérés deduplikálását és az eltérő panelméreteket.

Ellenőrzési parancsok a megfelelő munkakönyvtárból: backendben `.venv/Scripts/python.exe -m unittest discover -s tests`; backendben `.venv/Scripts/python.exe -m scripts.export_race_estimation_catalog --check`; frontendben `npm test` és `npm run build`; a repó gyökerében `python scripts/check_race_insights_browser.py`. A böngészős teszt helyi API-t és a 4173-as production preview-t, valamint előkészített OpenF1 9693-as futamot használ. Tesztfiókját és az ahhoz kötött elrendezéseket eltávolítja.

A konkrét mérések: [böngészős jegyzőkönyv](../testing/race-estimates-browser/results.json), [számítási katalógus](race-estimation-catalog.md). Egy sikeres futam és szintetikus peremtesztek a működést ellenőrzik; fizikailag kalibrált pontosságot nem igazolnak.
