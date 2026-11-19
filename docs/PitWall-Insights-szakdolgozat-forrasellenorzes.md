# A szakdolgozati munkaváltozat forrásellenőrzése

Felülvizsgálat dátuma: 2026. november 19. A vizsgált ág a main.

## A fő állítások ellenőrzése

| Dolgozati téma | Ellenőrzött alap | Érvényességi határ |
| --- | --- | --- |
| Történeti forrás és előzmények | Az aktív forrásgyár, az OpenF1 dokumentációja és a FastF1 v3.9.0 kiadásleírása | Az OpenF1 2023-tól ad történeti adatot. A kiválasztott próbák jellemzően 2023–2025-ből valók, néhány 2026-os esettel. |
| Előkészítés és visszajátszás | Munkamenet-normalizálás, materializációs szolgáltatás, közös replay-óra, állapotok és böngészőteszt | A teljes mezőny hideg vagy gyorsítótárazott előkészítése a végleges adatúton külön mérési kérdés. |
| Sorrend és viszonyítás | A timing tower szolgáltatás, a replay modell és a valódi böngészőpróbák | A körvonalból becsült rés csillagot kap. Az időmérőn a visszajátszás addigi munkamenetszintű legjobb köreit mutatja. |
| Stratégia és gumik | A ReplayStrategyService, a rajt előtti szabályok, szektoros időmérések, riváliságak és az időjárási összevetés | A tervek feltételesek, az időjárási előrejelzés megadott forgatókönyv. A történeti adatok eredeti beérkezési sorrendje nem rekonstruált. |
| Fizikai becslések | A race_estimation számítások, forrásmegfigyelések és mértékegységek | A bináris fékjel sebességgel együtt is csak eseményjelöltet adhat. |
| Jövőbeli funkciók | Útvonalak, profil, paneljogosultsági címkék, állapotvégpontok | A felhasználó által megadott előfizetési, MI- és tartalomfejlesztési ütemterv készültséget célzó terv. |

## Mérési nyom

- A korábbi és megismételt hárompilótás közvetlen OpenF1-mérést az openf1-current-validation és az openf1-architecture-data-validation jelentés rögzíti. A két böngészős idő két külön futásból, az openf1-switch-validation és az openf1-browser jelentésből származik.
- A rögzített bahreini és silverstone-i időelőnyt, a melbourne-i esőgumi-javaslatot és a felületi példát a weather-crossover-timing és a weather-crossover-workflow támasztja alá. A közölt bokszidő és a becsült belépés külön időpont.
- Az incidens és bokszidő pontossági számai az intervention-backtest, a pit-sector-backtest és a Miami rés-visszateszt külön mintáin alapulnak. Az átvitt modellek összehasonlításánál a célfutam mért zöld bokszköltsége közös bemenet.
- A böngészőből származó képek a replay-strategy, a timing-tower és a qualifying-lap-map tesztmappákból valók. A főszövegbeli részletek kivágást kaptak az olvashatóság érdekében.
- Az összesített 212 backend- és 65 frontendteszt előző, helyi regressziós futásból származik. A szerkesztés most a mérési jegyzőkönyvek és az exportok egyezését ellenőrzi. A pontossági és időméréseket ez az átdolgozás nem ismételte meg.

Az ellenőrzési összesítő tartalmazza a függelék előtti oldalszámot, az ábrák számát, a címsorok Word- és PDF-méretét, valamint a forrás és a kimenetek tartalmi egyezését.
