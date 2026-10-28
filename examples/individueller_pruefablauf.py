"""Ausgewählte native Modellierungs-, Risiko- und Fachprüfung gleicher JSON-Eingaben."""
import json
from pathlib import Path
import sys

import bsikompendium as b

pfad = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_suffix('.json')
d = json.loads(pfad.read_text(encoding='utf-8'))

# Verträge vor der Erhebung lesen: Felder, Maßstäbe und Quellenanker.
b.methodischer_eingabevertrag(d['modellierung']['schritt_id'])
b.fachlicher_eingabevertrag(d['fachpruefung']['anforderung_id'])
ergebnisse = {
    'zielobjekt_id': d['zielobjekt_id'],
    'modellierung': b.pruefe_methodenschritt(**d['modellierung']),
    'analysebedarf': b.pruefe_risikoanalysebedarf(**d['analysebedarf']),
    'risikoeinstufung': b.bewerte_risiko(**d['risikoeinstufung']),
    'fachpruefung': b.pruefe_fachregel(**d['fachpruefung']),
}
# Der eigene Ergebnisbefund wurde nicht als Eingabe geliefert.
assert ergebnisse['modellierung']['befund'] == 'ERFUELLT'
assert ergebnisse['analysebedarf']['befund'] == 'ERFORDERLICH'
assert ergebnisse['risikoeinstufung']['befund'] == 'HOCH'
assert ergebnisse['fachpruefung']['befund'] == 'TEILWEISE_ERFUELLT'
assert ergebnisse['fachpruefung']['bekannte_maengel'] == ['INF.11.A12.K1']
print(json.dumps(ergebnisse, ensure_ascii=False, indent=2))
