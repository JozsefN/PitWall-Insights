# Adatforrás-váltás és végleges OpenF1-architektúra

## Fejlesztési döntéstörténet

Az eredeti alkalmazás FastF1-adatokra épült. Az ingestion elválasztotta a külső
forrást a normalizálástól, a tárolástól és a felhasználói panelektől. Ekkor készült
el az alapvető importfolyamat, a kiválasztott telemetria materializációja, a
visszajátszás és a számítási réteg szerkezete.

A 2026. november 5-i hibavizsgálat az új telemetrialetöltések hitelesítési hibáját
mutatta ki. Az F1 archívumának hozzáférési változását a FastF1 újabb verziója
bejelentkezési lehetőségekkel kezelte. Maga a könyvtár nem vált fizetős szoftverré:
az új forrásletöltés igényelt megfelelő F1 TV-előfizetéshez kötött hozzáférést.

A következő, köztes terv két adatforrást használt volna. Az OpenF1 adta volna a
külső fiók nélküli történeti utat; saját F1-előfizetés esetén profilhoz kapcsolt
FastF1-hozzáférés is használható lett volna. Ehhez tartós kapcsolat, tokenlejárat,
hibakezelés, felhasználói elkülönítés és egy adathalmazhoz egy forrás szabály kellett.
Ez megoldotta volna a hozzáférés egy részét, de új termékfolyamatokat is behozott.

A használhatósági felülvizsgálatnál a hivatalos F1-weboldalon történő belépéshez
vizsgált FastF1 Companion tokenátadása böngészőkiegészítőt igényelt. A natív
bejelentkezési lehetőséghez nem kell kiegészítő, de a valós előfizetett fiókkal
ellenőrzött, megbízható teljes folyamat nem volt lezárva. A kiegészítő telepítése,
a külső előfizetés és az eltérő böngészők kezelése a jelenlegi célhoz túl nagy
felhasználói terhet jelentett. Emiatt a végleges döntés egyetlen OpenF1-adatút lett.

A szakdolgozat 4.8. alfejezete a teljes folyamatot, a köztes terv ábráját és a
végleges architektúrát együtt mutatja be. A köztes terv a döntés történetéhez
tartozik; a jelenlegi használati folyamat egyetlen adatforrásra épül.

## A jelenlegi rendszer

1. Az OpenF1Catalog az OpenF1 meetings és sessions végpontjaiból készít katalógust.
2. Az OpenF1Adapter megszerzi a kijelölt történeti munkamenet adatait.
3. A normalization közös időalapot, mértékegységeket és SessionSnapshotot készít.
4. A session_domain és a telemetry_materialization tárolja az adatokat és csak a
   szükséges pilóták hiányzó telemetriáját készíti elő.
5. A feature_metrics és decision_engine az adatbázisra építi a saját számításokat.
6. A panelek és a visszajátszás ezt a közös adatot olvassák.

A saját PitWall-regisztrációhoz nem tartozik külső F1-fiók vagy böngészőkiegészítő.
A profil megjelenített nevet, becenevet és opcionális telefonszámot kezel. Az
adatelérhetőségi fül egyetlen történeti forrás tényleges képességeit mutatja.
Az élő adatfolyam, a fizetés és a csapatok privát műszaki mérései nem kész funkciók.

## Mit pótol a saját feldolgozás?

A normalization az eltérő mezőket, időbélyegeket, típusokat és mértékegységeket
illeszti a közös modellhez. Az openf1_clean_lap_v1 a kör- és szektoradatokból,
órafolytonosságból, versenyirányítási üzenetekből, bokszeseményekből és törlésekből
ellenőrizhető tisztakör-minősítést számít. A feature_metrics állítja elő a
köridőtrendeket, páros különbségeket, saját időközöket és további stratégiai
alapértékeket. A döntési bemenetek csak a vizsgált időpontig ismert megfigyelést
használhatják.

Ez feldolgozási hiányokat pótol. Nem állít elő hiányzó nyers telemetriát vagy
nem közölt szenzoradatot. A becslés jelölt marad; hiányzó bizonyíték esetén a
minősítés vagy a számítás elérhetetlen. Ezzel a forrásváltás nem igényelt külön
panelrendszert, miközben a hiányok nem válnak kitalált méréssé.

## Tesztelési tartomány

A projekt kijelölt történeti tesztkészlete a 2023-2025-ös szezonokból származik.
Az OpenF1 lefedettsége 2023-ban kezdődik; 2025 a jelenlegi projektvizsgálat felső
határa, nem a szolgáltató teljes elérhetőségének felső határa. Nem állítjuk, hogy
minden szezon minden futama vagy pilótája teljes adatsort ad. Az élő hozzáférés
másik szolgáltatási mód, és a történeti visszajátszás nem igazolja annak működését.

## Források

- [FastF1 v3.9.0 és az archívum hitelesítési változása](https://github.com/theOehrly/Fast-F1/releases/tag/v3.9.0)
- [FastF1 natív és böngészős hitelesítés](https://github.com/theOehrly/Fast-F1/tree/v3.9.2/fastf1/internals/f1account)
- [OpenF1 dokumentáció](https://openf1.org/docs/)

## A végleges adatút ellenőrzése, 2026. november 19.

A teljes backendcsomag 101, a frontend 16 tesztje sikeres volt. A valódi OpenF1-próba
három pilótához 233 940 sort materializált 17,601 s alatt, meglévő forráscache-sel.
A külön, valódi böngészős folyamat 50,583 s alatt jutott lejátszható állapotba, és
az idővonal előrelépését is ellenőrizte. A hat böngészős folyamat nem küldött külső
fiókkapcsolási kérést. A jövőbeli munkamenet tiltásának esete tesztkatalógust használt;
a regisztráció, profil, import és replay valódi helyi szolgáltatást használt.

- [Adatút-mérés](../testing/openf1-current-validation.json)
- [Böngészős ellenőrzés](../testing/openf1-browser/results.json)
