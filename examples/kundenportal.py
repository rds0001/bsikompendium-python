"""Legacy-Beispiel: Absatz-Selbstauskunft, keine individuelle Fachprüfung von 0.2.

Für individuelle Quellenverträge siehe individueller_pruefablauf.py.
"""

import json
from pathlib import Path
import sys
import bsikompendium as b

pfad = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).with_name("kundenportal.json")
)
d = json.loads(pfad.read_text(encoding="utf-8"))
ergebnisse = {
    "inventar": b.pruefe_informationsverbund(d["objekte"]),
    "modellierung": b.pruefe_modellierung(d["objekte"], d["zuordnungen"]),
    "risikoanalyse": b.pruefe_risikoanalysebedarf(
        d["schutzbedarf"], d["hinreichend_modelliert"], d["typisches_szenario"]
    ),
    "risiko": b.bewerte_risiko(d["haeufigkeit"], d["schaden"], d["matrix"]),
    "anforderung": b.pruefe_anforderung(d["anforderung_id"], d["bewertungen"], True),
}
assert ergebnisse["inventar"]["befund"] == "STRUKTURELL_KONSISTENT"
assert ergebnisse["modellierung"]["befund"] == "ZUORDNUNGEN_BESTAETIGT"
assert ergebnisse["risikoanalyse"]["befund"] == "ERFORDERLICH"
assert ergebnisse["risiko"]["befund"] == "HOCH"
assert ergebnisse["anforderung"]["befund"] == "TEILWEISE_ERFUELLT"
print(json.dumps(ergebnisse, ensure_ascii=False, indent=2))
