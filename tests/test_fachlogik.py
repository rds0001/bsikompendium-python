import json
import gzip
from pathlib import Path
import bsikompendium as b
import pytest

FAELLE = []
for pfad in sorted(Path(__file__).parent.glob("referenzen_*.json.gz")):
    FAELLE.extend(json.loads(gzip.decompress(pfad.read_bytes())))


@pytest.mark.parametrize("f", FAELLE, ids=lambda f: f["fall_id"])
def test_individuelle_fachreferenz(f):
    if "fehler" in f["erwartung"]:
        with pytest.raises(b.Eingabefehler) as exc:
            getattr(b, f["funktion"])(**f["eingaben"])
        assert exc.value.code == f["erwartung"]["fehler"]
        return
    erg = getattr(b, f["funktion"])(**f["eingaben"])
    for k, v in f["erwartung"].items():
        assert erg[k] == v, (f["fall_id"], k, erg[k], v)
    for k, v in f.get("kriterien_erwartung", {}).items():
        erwartung = {"befund": v} if isinstance(v, str) else v
        for feld, wert in erwartung.items():
            assert erg["teilbefunde"][k][feld] == wert, (
                f["fall_id"], k, feld, erg["teilbefunde"][k], wert
            )


def test_oeffentlicher_vertrag_veraendert_keine_internen_regeln():
    vertrag = b.fachlicher_eingabevertrag("ORP.3.A6")
    vertrag["kriterien"].clear()
    vertrag["felder"].clear()
    d = {
        "mitarbeitende": {
            "objekte": [{"geschult_aufgaben": True, "geschult_verantwortung": False}],
            "vollstaendig": True,
        }
    }
    erg = b.pruefe_fachregel("ORP.3.A6", d)
    assert erg["befund"] == "TEILWEISE_ERFUELLT"
    assert erg["bekannte_maengel"] == ["ORP.3.A6.K2"]
