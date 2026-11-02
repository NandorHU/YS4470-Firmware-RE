# YS-4470 – projektcél és folytatható állapot

A fő cél a későn reagáló diódamérés javítása: a kijelző és a hang is kövesse gyorsabban a mérőszondák kontaktusát. Az 1.0 tartalmazza a Beta3 gyorsítását, a highspeedv2 feliratot, a folyamatos dióda-hangot és a jobb alsó indulóképet.

## Elért eredmények

- A gyári firmware és két teljes flash-mentés kiinduló hash-e ellenőrzött; az eredetik megőrizve.
- Ghidra/ARM elemzés alapján feltárt válaszkezelés, dióda-érvényességi ág, hangindítás/ismétlésgátlás és bootloader képfeldolgozás.
- A Beta2 teljes válaszra váró határidő-javítása és a Beta3 felesleges, azonos szövegű kijelzőfrissítést kihagyó javítása működik. A felhasználó gyorsulást jelzett.
- Az 1.0 continuous fizikailag telepítve. A teljes visszaolvasás önálló ellenőrzése is pontos egyezést adott. A felhasználó: „az 1.0 jól működik”.
- A forráscsomag reprodukálható deltapatch-eket, telepítőt, visszaállítót, dokumentációt és tesztbizonyítékot tartalmaz. Saját teljes flash-mentés nincs a GitHubra szánt csomagban.

## Fontos címek

- 0x80003a0c: dióda-eredmény érvényességi ága; 0x80003a74: eredeti hangkapu hívása.
- 0x80006e4c: hangkapu; 0x805abf06: mérési ismétlésgátló latch.
- 0x805ac764: hangállapot/watchdog számláló; 0x8000553c: eredeti KeyTask számlálókezelés.
- 0x80060928: 1.0 watchdog-frissítő; 0x80060950: hangindítás utáni számlálóbeállítás.
- 0x80010718: a közös OPEN és érvénytelen ág scope-olt hangleállítása.
- 0x8000f568: Beta3 azonos-kijelzőszöveg ellenőrző wrapper.
- 0x80058750: Beta2 dióda-válaszhatáridő helper.
- 0x80051978: highspeedv2 angol felirat, 12 bájt lezáró nullával.
- boot0 fájloffset 0x45c és 0x464: indulókép pozíciója; flash boot0@0, logo@0x6000, main@0x50000.

## Korlátok és következő munka

A fizikai működés visszaigazolása nem teljes regresszió vagy pontossági minősítés. A kontaktus–hang késés számszerű összehasonlításához mérés szükséges; az emuláció nem helyettesíti az ADC/UART/panel tényleges időzítését. A watchdog névleges 13 KeyTask-ciklusos tartalék leállítása és a rövid billentyűhang elsőbbsége dokumentált szélső eseteket hagy. Az időzített hangú 1.0 alternatíva megmarad visszalépési lehetőségként.

A következő munka objektív késésmérés és hosszabb dióda-kontaktusteszt, majd más mérési módok ellenőrzése. Új firmware-írás vagy fizikai teszt külön felhasználói jóváhagyást igényel. A készülék jelenlegi működő 1.0-ját további kísérleti gyorsítással automatikusan nem módosítjuk.
