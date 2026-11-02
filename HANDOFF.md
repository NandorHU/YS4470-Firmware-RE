# Folytatás és GitHub-átadás – YS-4470 1.0

Célrepó: https://github.com/NandorHU/YS4470-Firmware-RE

A projekt célját, jelenlegi állapotát, fontos címeit és következő lépéseit a README.md és PROJECT-STATUS.md rögzíti. A felhasználó engedélyezte a forráscsomag feltöltését ebbe a repóba.

Az 1.0 continuous fizikailag telepítve. A teljes 16 MiB visszaolvasás a célképpel bájtra egyezik; a felhasználó visszajelezte: „az 1.0 jól működik”. Az evidence/physical-install-1.0.json tartalmazza az ellenőrzés eredményét. A régebbi offline tesztek és manifestek keletkezéskori státuszukat őrzik; a jelenlegi állapotot ez a fizikai bizonyíték és a PROJECT-STATUS.md adja meg.

A felhasználó a mérési sebességet fontosabbnak tartja a folyamatos hangnál. Az 1.0 várakozást és extra mérési parancsot nem vezet be, a Beta3 lényegi időzítési és kijelzőgyorsító kódját megtartja; fizikai késésmérés még szükséges. Külön timed visszalépési változat megmarad.

Csak a GitHub-forráscsomag tartalma kerüljön a tárolóba. A teljes flash-mentések, out/inputs/tools könyvtárak, USB-naplók és a LOCAL-INSTALLERS.zip maradjanak helyben. A hordozható build.py saját, hash-ellenőrzött Beta3-mentést igényel. A projekt nem a gyártói teljes firmware-forrás.

Az 1.0 működő állapot; új kísérleti firmware vagy fizikai teszt külön felhasználói engedélyt igényel. Következő kutatási irány az objektív késésmérés és a teljes mérési módregresszió. Nem igazolt nagyobb pontosság, új méréstartomány vagy maximális hardversebesség.
