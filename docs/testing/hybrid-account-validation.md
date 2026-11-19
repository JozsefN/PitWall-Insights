# Hibrid adatút és profil - ellenőrzési jegyzőkönyv

Ellenőrizve: 2026. 11. 14. Helyi Windows-környezet, Python 3.12, PostgreSQL 16,
FastF1 3.9.2, React/Vite produkciós build.

## Eredmények

| Ellenőrzés | Eredmény |
| --- | --- |
| Teljes backend: `python -m unittest discover -s tests -v` | 97 sikeres teszt, 32,551 s. |
| Profil, tartós kapcsolat, titkosítás és hibahelyzetek | 8 célzott teszt. |
| Hibrid forrásválasztás, időillesztés, adatkonverzió és minőség | 13 célzott teszt. |
| Önálló OpenF1-tisztakör-szabályzat | 8 célzott teszt. |
| Privát munkamenetek hozzáférése és háttérfeladat-kérései | 2 célzott teszt. |
| Korábbi backend- és migrációs regressziók | A teljes csomag részeként sikeresek. |
| Frontend: `npm.cmd run build` | TypeScript és produkciós build sikeres. Meglévő méretfigyelmeztetés: a fő csomag meghaladja az 500 kB-ot. |
| Frontend: `npm.cmd test` | 14 sikeres teszt. |
| Chromium: `python scripts/check_profile_browser.py` | 7 sikeres folyamat, nincs böngészős futási hiba. |
| Alembic és függőségek | `alembic check`: nincs hiányzó művelet; `pip check`: nincs törött függőség. |
| Titkok a hibaválaszban | A validációs hiba nem ismétli vissza a beküldött jelszót. |

Az új tesztek nem módosítják a nyilvános munkasort: elkülönített PostgreSQL-sémákat
hoznak létre és törölnek. A böngészőpróba saját, megkülönböztethető tesztfiókjait
a végén eltávolítja.

## Valós OpenF1-mérés

A 2025-ös Ausztrál Nagydíj pilótái közül az 1-es, 16-os és 4-es autó szerepelt.
Az alapadat-betöltés után valódi materializációs munka készült, a worker szolgáltatását
ugyanabban az elkülönített tesztsémában futtattuk. A végén a készenléti kérés,
visszajátszási időtartomány és stratégiai számítás is lefutott.

| Mérési feltétel | Eredmény |
| --- | --- |
| Első, üres adatbázis-telemetriával és új OpenF1-adapter-gyorsítótárral | 52,487 s; a szezonkatalógus korábban rendelkezésre állt. |
| Végső adapter, üres adatbázis-telemetriával és már meglévő szolgáltatói gyorsítótárral | 16,820 s. |
| Materializált telemetria és pozíció | 233 940 sor. |
| Önálló szabályzattal tisztának minősített körök | 470, a munkamenet teljes betöltött mezőnyében. |
| Végső kiegészítő adatok | 82 bokszjelentés, 18 965 időköz, 335 versenypozíció-változás, 172 előzési jelentés. |
| Rajtrács | Az adott forráslekérés üres eredményt adott; nem helyettesítettük kitalált adattal. |
| Stratégiai végpont | 256 mutatóérték, ebből 74 elérhető; kalibrált modellek nélkül `missing_model_inputs`. |
| Ismételt készenléti kérés | Kész állapot, új munkára nem volt szükség. |

Ez egy futam három kiválasztott autójának esettanulmánya. Nem teljes mezőnyös,
nem több futamra kiterjedő teljesítménygarancia, és a két gyorsítótár-állapotot
nem szabad azonos feltételként összehasonlítani. A régi, más szolgáltatói úthoz
tartozó 93,687 s-os mérés nem lett újraértelmezve vagy felülírva.

## F1-kapcsolat: mi bizonyított és mi nem?

A hitelesítési kliens válaszait helyettesítő integrációs tesztek ellenőrzik az
adatbázisbeli titkosítást, felhasználói elkülönítést, új szolgáltatáspéldány utáni
kapcsolatmegmaradást, lejárt token megújítását, ideiglenes szolgáltatói kiesést,
hibás hitelesítést, leválasztást és felhasználótörlési kaszkádot. A böngészőpróba
valódi PitWall-regisztrációt és profilt, de szimulált F1-válaszokat használ.

Nem állt rendelkezésre valós, előfizetett F1-fiók. Így a szolgáltató által esetleg
kért interaktív ellenőrzés, a valós F1-token megújítása és a hitelesített teljes
futamletöltés sikeressége és ideje még külön ellenőrizendő. A technikai implementáció
nem igazolja a nyilvános vagy üzleti adatszolgáltatás engedélyét.

Az élő felület és a folyamatos élő állapotfeldolgozás továbbra is tervezett.
A saját előfizetési és fizetési kártya váz; nincs aktív pénztár vagy díjterhelés.

## Bizonyítékok és reprodukció

- [Gépi összesítés](hybrid-account-validation.json)
- [Első valós OpenF1-próba](hybrid-openf1-validation.json)
- [Végső adapter valós próbája](hybrid-openf1-validation-final.json)
- [Böngészős folyamatok](profile-browser/results.json)
- [Architektúra, API-k, kulcskezelés és korlátok](../architecture/11-hybrid-data-and-accounts.md)

Új valós adatpróba a `backend` könyvtárból:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_hybrid_replay --year 2025 --round 1 --drivers 1,4,16 --output ../docs/testing/hybrid-openf1-repeat.json
```

Az ismétlés időeredményéhez fel kell jegyezni az aktuális szolgáltatói gyorsítótár
állapotát és a párhuzamos terhelést. Valós F1-titkot a tesztjegyzőkönyvbe vagy
parancssori argumentumba nem szabad írni.
