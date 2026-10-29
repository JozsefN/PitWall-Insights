# Forma-1 telemetria elemző alkalmazás készítése

## Feladatkiírás

## Hallgatói nyilatkozat

## Kivonat

## Abstract

## Tartalomjegyzék

## Rövidítések jegyzéke

## 1. Bevezetés

### 1.1. Motiváció és a megoldandó probléma

### 1.2. A dolgozat célkitűzései és felépítése

### 1.3. Az önálló labor előzményei és a saját hozzájárulás

## 2. Szakmai és technológiai háttér

### 2.1. A Forma–1 verseny- és telemetriaadatai

### 2.2. Meglévő telemetriaelemző megoldások összehasonlítása

### 2.3. Idősorok, mintavételezés és adatminőség

### 2.4. A webes elemzőrendszer technológiai alapjai

#### 2.4.1. React, TypeScript és TanStack Query

#### 2.4.2. FastAPI, API-kérések és háttérfeladatok

#### 2.4.3. PostgreSQL, SQLAlchemy és Alembic

### 2.5. Nyelvi modellek alkalmazása adatok szöveges értelmezésére

## 3. Követelmények és architekturális döntések

### 3.1. Felhasználói csoportok és használati esetek

### 3.2. Funkcionális és minőségi követelmények

### 3.3. A rendszer felépítése és a modulok felelőssége

### 3.4. Adatmodell, perzisztencia és API-szerződések

### 3.5. A fő feldolgozási és kommunikációs folyamatok

## 4. Adatfeldolgozás és összetett versenyelemzések

### 4.1. FastF1-integráció és az adatok egységesítése

### 4.2. Háttérben futó import és igény szerinti telemetriabetöltés

### 4.3. Időbélyegek összehangolása és a visszajátszás adatmodellje

### 4.4. Származtatott metrikák számítása

#### 4.4.1. Tempó, egyenletesség és köridőtrendek

#### 4.4.2. Pilóták közötti különbségek és felzárkózási helyzetek

#### 4.4.3. Etapok, gumihasználat és teljesítményváltozások

### 4.5. Jelentős versenyhelyzetek kiválasztása szabályokkal

### 4.6. Hiányos adatok, gyorsítótárazás és lekérdezési költségek

## 5. Interaktív elemzőfelület és felhasználói hozzáférés

### 5.1. Edzések és versenyek kiválasztása, adatbetöltési állapotok

### 5.2. Közös állapotkezelés és a visszajátszás vezérlése

### 5.3. Widgetrendszer és elrendezésszerkesztő

#### 5.3.1. Panelek kiválasztása, átrendezése és átméretezése

#### 5.3.2. Panelbeállítások és személyes elrendezések mentése

### 5.4. Felhasználói fiókok és előfizetési szintek

#### 5.4.1. Szerveroldali jogosultságok és használati korlátok

#### 5.4.2. Tesztfizetés, csomagváltás és lemondás

### 5.5. Kezdőoldal, bajnoki tabella és hírfolyam

## 6. AI-alapú elemzőpanelek

### 6.1. Az AI feladata és a feldolgozott adatokból képzett kontextus

### 6.2. Panelbeállítások, promptok és a modellhívás folyamata

### 6.3. A magyarázatok kapcsolata a hivatkozott adatokkal

### 6.4. Hibás, hiányos és nem alátámasztható válaszok kezelése

### 6.5. Modellválasztás és erőforráskorlátok

## 7. Tesztelés és értékelés

### 7.1. Tesztadatok, tesztesetek és futtatási környezet

### 7.2. A metrikák helyességének és az adatminőség kezelésének ellenőrzése

### 7.3. Felhasználói folyamatok és hozzáférési szabályok tesztelése

### 7.4. Adatbetöltés, lekérdezések és visszajátszás teljesítményvizsgálata

### 7.5. Az AI-magyarázatok pontossága, válaszideje és költsége

## 8. Fejlesztési tapasztalatok és korlátok

### 8.1. A prototípustól a bővíthető alkalmazásig

### 8.2. Adatforrásokból és aszinkron működésből adódó nehézségek

### 8.3. Átdolgozott megoldások és mérnöki kompromisszumok

### 8.4. A fejlesztési munkafolyamat és a levont tanulságok

### 8.5. Az elkészült rendszer korlátai

## 9. Összefoglalás és továbbfejlesztés

### 9.1. Elért eredmények és a feladatkiírás teljesítése

### 9.2. Továbbfejlesztési lehetőségek

## Irodalomjegyzék

## Függelékek

### A. Telepítési, konfigurációs és futtatási útmutató

### B. Kiegészítő adatmodellek és metrikadefiníciók

### C. Kiegészítő teszteredmények

### D. Nyilatkozat a generatív MI-eszközök használatáról
