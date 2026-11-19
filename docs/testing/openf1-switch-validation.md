# OpenF1 adatút ellenőrzése, 2026. november 19.

A jelenlegi alkalmazás OpenF1-t használ a katalógushoz és a történeti adatokhoz.
A regisztráció, a profil és a munkamenetválasztás nem kér külső fiókot vagy
böngészőkiegészítőt. A szakdolgozat 4.8. alfejezete külön tárgyalja a korábbi
forrásra épített kezdeti architektúrát, a köztes hibrid tervet és a végleges döntést.

- Backend: 101 sikeres teszt, nincs sikertelen teszt.
- Frontend: 16 sikeres teszt, sikeres típusellenőrzés és produkciós build.
- Böngésző: 6 sikeres folyamat, nincs JavaScript-kivétel és külső kapcsolódási kérés.
- Valódi OpenF1: új, elkülönített adatbázisséma, három pilóta, 233 940 materializált sor.
- Közvetlen adatút: 17,601 s; meglévő forráscache, párhuzamos funkcionális tesztfuttatás.
- Böngészős lejátszható állapot: 50,583 s; meglévő forráscache. A lejátszás előrehaladását is ellenőriztük.

A jövőbeli munkamenet tiltásának böngészős esete tesztkatalógust használt. A saját
regisztráció, profilmentés, alapimport, worker és visszajátszás valódi helyi
szolgáltatást és adatbázist használt. A tesztfiókokat eltávolítottuk; a történeti
munkamenet adatai az alkalmazás közös, újrafelhasználható cache-ében megmaradnak.

A 2023-2025-ös tartomány a projekt kiválasztott tesztelési köre. A most számszerűen
mért eset a 2025-ös Ausztrál Nagydíj három autója. Ez nem minden év minden futamának
lefedettségi bizonyítéka, teljes mezőnyös új letöltési SLA vagy kész optimális
stratégia igazolása. A stratégiai válasz külön jelzi a hiányzó modellezési bemenetet.

## Újrafuttatás

A projektgyökérből az API, adatbázis és worker indítása:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

A backend könyvtárában:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.verify_hybrid_replay --output ../docs/testing/openf1-current-validation.json
```

A frontend könyvtárában:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

A projektgyökérben, futó API/worker és preview mellett:

```powershell
python scripts/check_openf1_browser.py
```

Nyers eredmények: [adatút](openf1-current-validation.json),
[böngésző](openf1-browser/results.json), [összesítés](openf1-switch-validation.json).
