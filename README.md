# YS-4470 firmware 1.0 – highspeedv2

Első 1.0 build a fizikai készüléken már kipróbált Beta3 alapján. **Az 1.0 continuous változat a készülékre felírva, a teljes 16 MiB visszaolvasás bájtra egyezik a célképpel. A felhasználó visszajelzése: „az 1.0 jól működik”.** A verziószám a build azonosítója, nem pontossági vagy stabilitási tanúsítás.

## A projekt célja

A Mr. Yang YS-4470 készülék meglévő firmware-ének visszafejtése és célzott javítása, elsősorban a diódamérés kijelzési és hangjelzési késésének csökkentése. További cél a követhető, eredetibájt- és hash-védelemmel ellátott offline build, ellenőrzött Windows FEL-telepítés és visszaállíthatóság. A projekt megtartja az eredeti mérőhardvert és a gyári mérési parancsokat; új méréstartomány vagy nagyobb pontosság megvalósítása nincs bizonyítva.

## Jelenlegi állapot – 2026. november 2.

A célhardver F1C100s rendszervezérlő és Winbond 16 MiB SPI-flash. A firmware visszafejtése Ghidra, ARM-disassembly és függvényszintű Unicorn-emuláció alapján történt. A mérési válaszkezelés, a kijelzőfrissítés, a hangkapu és a bootkép útvonalának elegendő részét feltártuk a célzott módosításokhoz. Ez bináris patchprojekt; a gyártó teljes forráskódja nem áll rendelkezésre.

A Beta2/Beta3 változatokat a felhasználó gyorsabbnak és jól frissülőnek találta. Az 1.0 continuous hat változó 64 KiB szektorának felírása után az egész 16 MiB flash visszaolvasása pontosan egyezett a tervezett képpel. Az eredeti Beta3-ról friss teljes mentés készült. A felhasználó az 1.0 működését visszaigazolta.

Ami még hátravan: a kontaktustól a kijelzésig/hangig tartó idő objektív mérése, a folyamatos hang és watchdog szélső eseteinek hosszabb fizikai tesztje, minden mérési mód regressziója, valamint metrológiai és további hardvervizsgálatok. A további gyorsítás lehetősége és a hardver maximális sebessége még nem bizonyított.

## Tartalom

- Megmarad a Beta3 gyorsított dióda-lekérdezése, teljes válaszra váró javított határideje és az ismétlődő kijelzőszöveg felesleges újrarajzolásának elhagyása.
- A kapcsoló angol felirata pontosan `highspeedv2`. Az eredeti 12 bájtos helyen, lezáró nullával együtt elfér. Más nyelvek feliratai nem változtak.
- `continuous`: 1321 Hz-es folyamatos dióda-hang az eredeti érvényes mérési ágban; nyitott/érvénytelen bemenet leállítja. Nem ad várakozást vagy extra mérési parancsot a mérési ciklushoz.
- `timed`: visszalépési változat a Beta3 bevált, névleg 420 tickes egyszeri hangjával. Ugyanaz az új felirat és indulókép.

A hang PWM-szintézis, a korábban adott MP3 hangmagasságának közelítése. Nem tényleges MP3-lejátszás. A folyamatos változat a legújabb kérésnek megfelelően felülírja a korábbi egyszeri időtartam-kérést.

## Használat és korlátok

Diódamód + bekapcsolt `highspeedv2`. Újraindítás után ellenőrizd a kapcsolót; új automatikus beállításmentés nincs. A fizikai Beta3-nál a felhasználó gyorsabb reakciót és megfelelő frissítést igazolt. Az 1.0 működését a felhasználó igazolta. A reakcióidő számszerű összehasonlítása, minden további mérési mód regressziója és a mérési pontosság vizsgálata még hátravan.

A folyamatos hang minden érvényes eredménynél frissíti a véges hang-watchdogot. Az eredeti KeyTask 13 ciklus után leállítja, ha nem jön új érvényes eredmény; névleg kb. 650 ms, a tényleges ütemezéstől függően. Módváltáskor sincs korlátlanul fennmaradó hang, de a leállás nem bizonyítottan azonnali. Más, rövid billentyűhang elsőbbségét a számláló <=3 eset védelme őrzi. Ritka ütemezési résben ezért egy érvénytelen eredmény után a watchdogig maradhat hang. Ezeket fizikai tesztnek kell ellenőriznie.

## Reprodukálható build Windows alatt

Python 3.12, standard könyvtár elegendő a hordozható patch-buildhez. A bemenet a saját, ellenőrzött **teljes 16 MiB Beta3 flash-mentés**, SHA-256:

`2ce9c1693a9726a2fe042620debd7705e77cfec58d98e8729bb6ec1ade4a9d0f`

```powershell
python build.py --backup C:/sajat-mentes/current-beta3.bin --fel C:/eszkozok/sunxi-fel.exe
```

Az `out/continuous` és `out/timed` önálló helyi telepítőcsomag. A `--fel` elhagyható offline buildhez, de a natív telepítéshez szükséges. A binárisok, saját teljes mentések és eszközprogramok nem kerülnek a GitHub-forráscsomagba. Az összes bemeneti hash, eredeti patch-bájt és kimeneti hash ellenőrzött. A `patches/*.json` alkalmazható deltapatch, nem teljes firmware-forráskód; a gyártói forráskód nem áll rendelkezésre.

## Telepítés – csak a konkrét build külön jóváhagyása után

Ez a build **bootloadert is módosít** a jobb alsó pozíció miatt. Az írás megszakadása FEL-helyreállítást igényelhet. Nem indulhat felügyelet nélküli vagy automatikus flash.

1. Készülék FEL módban, stabil táp és USB. Egyetlen F1C100s/Winbond 16 MiB eszköz lehet csatlakoztatva.
2. A kiválasztott könyvtár `Install-V1-APPROVAL-REQUIRED.cmd` indítója a konkrét felhasználói jóváhagyás után futtatható.
3. Friss teljes mentés, pontos ismert állapot- és hash-ellenőrzés, csak az eltérő 64 KiB blokkok írása, majd teljes 16 MiB visszaolvasás és bájtegyezés.
4. Magyar fázisnevek és tényleges blokkalapú százalékok. 100% csak teljes siker után; automatikus újraindítás nincs.
5. Visszaállítás: az adott könyvtár `Restore-Beta3-APPROVAL-REQUIRED.cmd` indítója helyreállítja a teljes korábbi működő Beta3-t, a gyári bootképpel együtt. Ehhez is külön jóváhagyás kell.

Ismeretlen flash-állapotnál az írás nem indul. A telepítő csak az eredeti ismert Beta3 és a saját célváltozata között vált; a másik 1.0 változatról előbb annak saját visszaállítójával kell Beta3-ra visszalépni. Hiba esetén maradjon FEL módban, minden napló és mentés megőrzendő.

## Tesztek

A hordozható build és a telepítő virtuális tesztje, USB-hozzáférés nélkül:

```powershell
python tests/test_build.py --backup C:/sajat-mentes/current-beta3.bin
python tests/simulate_installer.py out/continuous
python tests/simulate_installer.py out/timed
```

A szimuláció ideiglenes másolatban helyettesíti az eszközfelsorolást és minden natív FEL-hívást; az eredeti telepítő nem változik.

`evidence/`: valódi ARM-kód függvényszintű emulációja a rajzolásra és a hangra, valamint virtuális flashen tesztelt telepítő. A hardvervégpontok helyettesítettek. Ez nem teljes hidegindítási, analóg mérési vagy fizikai sebességteszt.

`src/` kutatási szkriptjei az eredeti munkakönyvtárhoz tartozó archívumok. A hordozható build belépési pontja kizárólag a gyökérben található `build.py`. Az archív tesztekhez Unicorn és a helyi gyári képek szükségesek.

## GitHub-átadás

Lásd `HANDOFF.md`. Ne töltsd fel az `out`, `inputs`, `tools` könyvtárakat, a teljes flash-mentéseket vagy az USB-naplókat. A fizikai felírás és a felhasználó által igazolt működés bizonyítékát az `evidence/physical-install-1.0.json` rögzíti; ez nem teljes pontossági vagy időzítési minősítés. Külső firmware-/eszközkódra ez a csomag nem ad új licencet; az eredeti jogosultságok változatlanok.
