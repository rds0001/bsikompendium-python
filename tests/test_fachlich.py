import copy
import json
from pathlib import Path

import pytest
import bsikompendium as b

FAELLE = json.loads(Path(__file__).with_name("referenzfaelle.json").read_text())


@pytest.mark.parametrize("fall", FAELLE, ids=lambda f: f["fall_id"])
def test_referenz(fall):
    args = copy.deepcopy(fall["eingaben"])
    vorher = copy.deepcopy(args)
    if "fehler" in fall["erwartung"]:
        with pytest.raises(b.Eingabefehler) as exc:
            getattr(b, fall["funktion"])(**args)
        assert exc.value.code == fall["erwartung"]["fehler"]
    else:
        ergebnis = getattr(b, fall["funktion"])(**args)
        assert ergebnis["befund"] == fall["erwartung"]["befund"]
        assert ergebnis["quellenfassung"] == "BSI_KOMPENDIUM_2023_ERRATA_2026_03_26"
    assert args == vorher


def test_katalog_und_vertraege():
    assert len(b.bausteine()) == 111
    assert len(b.anforderungen()) == 1835
    assert len(b.anforderungen(entfallen=True)) == 2125
    for ident in b.anforderungen():
        r = b.anforderung(ident)
        assert r["pdf_seiten"] and r["kriterien"]
        assert ident in b.anforderungen(r["baustein_id"], r["kategorie"])
        bew = {
            k["kriterium_id"]: dict(
                relevant=True, umgesetzt=True, wirksam=True, angemessen=True
            )
            for k in b.eingabevertrag(ident)["kriterien"]
        }
        assert b.pruefe_anforderung(ident, bew, True)["befund"] == "ERFUELLT"
        assert b.pruefe_anforderung(ident, {}, True)["befund"] == "UNBEKANNT"
    assert "G 0.4" in b.gefaehrdungen("INF.2.A13")
    assert "G 0.4" in b.gefaehrdungen("INF.2.A29")
    assert "G 0.0" not in b.gefaehrdungen("INF.2.A13")
    assert b.anforderung("OPS.2.3.A22")["pdf_seiten"]
    assert b.anforderung("APP.2.2.A2")["entfallen"]
    assert b.anforderung("SYS.1.2.3.A5")["korrekturen"]
    assert (
        "DARF NUR" not in b.anforderung("SYS.2.2.3.A6")["kriterien"][0]["modalverben"]
    )


def test_auswahl():
    assert (
        b.pruefe_technische_grenzen("OPS.1.2.6.A11", {})["anwendbarkeit"] == "UNBEKANNT"
    )
    assert (
        b.pruefe_technische_grenzen("APP.4.4.A21", {})["anwendbarkeit"] == "UNBEKANNT"
    )
    basis = b.anforderungen_fuer(["CON.10"], "BASIS")
    standard = b.anforderungen_fuer(["CON.10"], "STANDARD")
    assert set(basis) < set(standard)
    assert all(b.anforderung(x)["kategorie"] == "B" for x in basis)
    assert all(b.anforderung(x)["kategorie"] in ("B", "S") for x in standard)
    h = b.anforderungen("CON.10", "H")[0]
    assert h in b.anforderungen_fuer(["CON.10"], "STANDARD", [h])
    with pytest.raises(b.Eingabefehler):
        b.anforderungen_fuer(["CON.10"], "KERN")
    assert standard == b.anforderungen_fuer(["CON.10"], "KERN", kernbereich=True)


def test_keine_mutation_des_katalogs():
    b.anforderung("CON.10.A7")["kriterien"].clear()
    b.baustein("CON.10")["zielobjekttypen"].clear()
    b.risikomatrix()["werte"].clear()
    assert b.anforderung("CON.10.A7")["kriterien"]
    assert b.baustein("CON.10")["zielobjekttypen"]
    assert len(b.risikomatrix()["werte"]) == 4


@pytest.mark.parametrize("wert", [float("nan"), float("inf"), -float("inf")])
def test_nichtendliche_zahlen(wert):
    with pytest.raises(b.Eingabefehler):
        b.pruefe_datensicherung({"wiederherstellungsdauer": wert})
