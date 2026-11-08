# YS-4470 patchelő – saját gyári firmware-ből

Nem kell hozzá Beta3 vagy más készülék teljes mentése. Python3.10+ kell,
egyéb csomagot nem kell telepíteni. A patchelő nem kommunikál a készülékkel.

1. Töltsd le és bontsd ki a repository ZIP-jét: **Code → Download ZIP**.
2. A `patcher` mappában maradjon együtt a Python-program és a `patch-data.json`.
3. Húzd a saját gyári `f1c100s.bin` fájlodat vagy16 MiB-os teljes mentésedet
   a `PATCH-WINDOWS.cmd` fájlra.
4. Az új `*-ys4470-1.0-continuous.bin` és a hozzá tartozó ellenőrzési jelentés
   az eredeti fájl mellé kerül. Az eredeti fájl változatlan marad.

Támogatott: a SHA-256-tal azonosított gyári V3.6 és V3.8 alkalmazás.
Teljes mentésnél a belső alkalmazás hashét vizsgálja; a teljes fájl saját,
készülékenként eltérő hashe nem akadály. A bootloader, logó és a módosítási
tartományokon kívüli adatok megmaradnak. Ismeretlen firmware-t elutasít.

Ellenőrzés és visszaállítás a kicsomagolt projekt mappájából:

```text
python patcher/ys4470_patch.py inspect "sajat-mentes.bin"
python patcher/ys4470_patch.py apply "sajat-mentes.bin" --output "sajat-1.0.bin"
python patcher/ys4470_patch.py revert "sajat-1.0.bin" --output "visszaallitott-eredeti.bin"
```

A V3.8 eredménye a kiadott1.0 alkalmazásával bájtra egyezik. A V3.6 port
megőrzi a saját verziófüggő adatait; az offline teszteken átment, készüléken
még nem teszteltük. Ez nem a négyprofilos, kísérleti E2 build.

A program csak fájlt készít, nem telepít firmware-t. Az elkészült fájlokhoz
a régi, konkrét Beta3 mentést elváró telepítő nem használható. A gyári Mr.Yang
frissítővel történő telepítés nincs igazolva. Őrizd meg a saját teljes mentésedet,
és a bevált, ellenőrzött programozási/visszaállítási folyamatodat használd.

Elutasításnál az `inspect` szöveges kimenetét lehet hibajegyhez mellékelni;
személyes flash-mentést vagy kalibrációs dumpot ne tölts fel.
Részletes kompatibilitás, hashek és korlátok: [README.md](README.md).
