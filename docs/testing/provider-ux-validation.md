# Adatelérhetőség és F1-kapcsolat: ellenőrzés, 2026. november 14.

A javítás az alkalmazás felületét, az import hibaszerződését és a profilhoz
mentett F1-hozzáférést érinti. A meglévő hibrid adapterhatár megmaradt.

| Ellenőrzés | Eredmény |
| --- | --- |
| Teljes backend tesztcsomag | 109 sikeres teszt, 42,731 s |
| Frontend tesztcsomag | 16 sikeres teszt |
| Típusellenőrzés és produkciós build | Sikeres; a meglévő nagy JS-csomag figyelmeztetése megmaradt |
| Profil és munkamenetválasztó böngészős ellenőrzése | 11 sikeres folyamat, nincs böngészős kivétel |
| Migráció | `j6a371f8e490` alkalmazva; `alembic check`: nincs hiányzó módosítás |
| Szakdolgozat export és ellenőrzés | 42 PDF-oldal, 8 beágyazott kép, egyező forrás/Word/PDF tartalom |

A backendtesztek valódi loopback HTTP-kéréssel vizsgálják a Companion fogadóját:
eredet- és Host-ellenőrzés, CORS-előkérés, hibás vagy túlméretes törzs, lejárat,
megszakítás, felhasználói elkülönítés, egyszeri jóváhagyás, titokmentes válasz.
Az előfizetési token szolgáltatói ellenőrzése ezekben tesztválasz. A kapcsolat
lejárat után is megmarad; a böngészős mód felhasználói újrabelépést kér,
a mentett jelszavas mód megújítást végez. Archívumtiltás nem törli a kapcsolatot.

A Playwright-folyamatok valódi regisztrációt és adatbázisba mentett profilt,
valódi böngészős kérelmet és helyi fogadóindítást/megszakítást használtak.
A sikeres F1-azonosítást és a forráshibákat tudatosan helyettesítették.
A tesztfiókokat eltávolították. Részletek:
[böngészős eredmények](profile-browser/results.json).

A külön Chromium-kiegészítő próba a böngésző által ténylegesen küldött
`chrome-extension://` eredettel és localhost Host-fejléccel is sikeres átadást
végzett. Az ismeretlen kiegészítő először 403-at kapott, majd kizárólag a
tesztkiegészítő eredetének tesztbeli engedélyezése után sikerült az átadás.
Az upstream ellenőrző itt is tesztválasz, és valódi F1-sütit nem olvasott.
[Protokolleredmény](profile-browser/companion-protocol.json).

Az F1 hitelesítő felületének nyilvános konfigurációja és első, hitelesítő adatot
nem tartalmazó űrlapkérése a helyi hálózatról sikerült (HTTP 200, a FastF1 által
várt mezőkkel). Ez kizárólag a belépés megkezdését ellenőrzi. Nem bizonyítja,
hogy az érintett felhasználó előfizetése érvényes, vagy az archívum elérhető lesz.
Az előfizetés-ellenőrzéshez használt 2026-os archívumindex hitelesítés nélkül
401-et adott, tehát a kapcsolódás ellenőrzése nem egy nyilvános indexre épül.
Valódi, előfizetett F1-fiókkal történő végponttól végpontig ellenőrzés még szükséges.

Újrafuttatás:

```powershell
# backend könyvtárban
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic check
# frontend könyvtárban
npm.cmd test
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4173 --strictPort
# projektgyökérben, futó 8000-es API és 4173-as preview mellett
python scripts/check_profile_browser.py
# Valódi Chromium-kiegészítő HTTP/CORS protokollpróba; upstream helyettesítve
python scripts/check_f1_companion_protocol.py
```
