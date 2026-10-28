"""Individually authored method steps, separate from catalogue requirements."""

import copy
import gzip
import json
from functools import lru_cache
from importlib.resources import files

from .fachlogik import _pruefe_vertrag
from .kern import _fordere


@lru_cache(maxsize=1)
def _methoden():
    return json.loads(
        gzip.decompress(
            files("bsikompendium").joinpath("resources/methodik.json.gz").read_bytes()
        )
    )


def methodenschritte() -> list[str]:
    """Return explicitly implemented method step IDs; not a completion claim."""
    return sorted(_methoden()["schritte"])


def _vertrag(schritt_id):
    _fordere(
        isinstance(schritt_id, str) and schritt_id in _methoden()["schritte"],
        "Unbekannter Methodenschritt.",
    )
    return _methoden()["schritte"][schritt_id]


def methodischer_eingabevertrag(schritt_id: str) -> dict:
    """Return facts, criteria and precise standard sections for a method step."""
    return copy.deepcopy(_vertrag(schritt_id))


def pruefe_methodenschritt(schritt_id: str, angaben: dict) -> dict:
    """Evaluate one method step; does not certify an entire risk assessment."""
    vertrag = _vertrag(schritt_id)
    result = _pruefe_vertrag(schritt_id, angaben, vertrag)
    result["quellenfassung"] = vertrag["quellenfassung"]
    result["quellenabschnitte"] = vertrag["quellenabschnitte"]
    if "geltungshinweis" in vertrag:
        result["geltungshinweis"] = vertrag["geltungshinweis"]
    return result


def pruefe_risikoverlauf(
    vorher, nachher, matrix, akzeptierte_kategorien, weitere_akzeptanzkriterien, angaben
):
    """Couple matrix results, acceptance criteria and a BSI-200-3 treatment check.

    Planned effects remain separate from the risk actually incurred. The caller
    must supply the institution's applicable acceptance criteria explicitly.
    """
    from .fachlogik import _auswerten, _validiere
    from .kern import RISIKEN, _liste, _objekt, _text, _und, _wahl, bewerte_risiko

    for name, data in [("vorher", vorher), ("nachher", nachher)]:
        _objekt(
            data,
            {"haeufigkeit", "schaden", "bewertungsstand"}
            | ({"neubewertungsgrund"} if name == "nachher" else set()),
            name,
        )
        _wahl(
            data.get("bewertungsstand"),
            ("KONZEPT", "UMGESETZT"),
            name + ".bewertungsstand",
            True,
        )
    if nachher.get("neubewertungsgrund") is not None:
        _text(nachher["neubewertungsgrund"], "nachher.neubewertungsgrund")
    _liste(akzeptierte_kategorien, "akzeptierte_kategorien")
    for value in akzeptierte_kategorien:
        _wahl(value, RISIKEN, "akzeptierte_kategorien")
    _fordere(
        len(set(akzeptierte_kategorien)) == len(akzeptierte_kategorien),
        "Doppelte akzeptierte Kategorien.",
    )
    schema = {
        "weitere_akzeptanzkriterien": {
            "typ": "liste",
            "eindeutiges_feld": "id",
            "element": {"id": {"typ": "text"}, "erfuellt": {"typ": "bool"}},
        }
    }
    data = {"weitere_akzeptanzkriterien": weitere_akzeptanzkriterien}
    _validiere(data, schema)
    extra, extra_missing = _auswerten(
        {
            "op": "alle",
            "liste": "weitere_akzeptanzkriterien",
            "praedikat": {"op": "feld", "name": "erfuellt"},
        },
        data,
        schema,
    )
    before = bewerte_risiko(vorher.get("haeufigkeit"), vorher.get("schaden"), matrix)
    after = bewerte_risiko(nachher.get("haeufigkeit"), nachher.get("schaden"), matrix)
    initial = None if before["befund"] == "UNBEKANNT" else before["befund"]
    residual = None if after["befund"] == "UNBEKANNT" else after["befund"]
    derived = {
        "risikokategorie",
        "eingegangenes_risiko",
        "restrisiko_vorhanden",
        "akzeptanz_erreicht",
        "vorher_nachher",
        "bewertungsstand",
    }
    vertrag = _vertrag("BSI2003.RISIKOBEHANDLUNG")
    _objekt(angaben, set(vertrag["felder"]) - derived, "angaben")
    _validiere(angaben, vertrag["felder"])
    facts = copy.deepcopy(angaben)
    options = facts.get("optionen")
    phase = nachher.get("bewertungsstand")
    changed = (
        initial is not None
        and residual is not None
        and any(
            vorher.get(axis) != nachher.get(axis) for axis in ("haeufigkeit", "schaden")
        )
    )
    unbegruendete_neubewertung = (
        options == ["AKZEPTANZ"]
        and changed
        and nachher.get("neubewertungsgrund") is None
    )
    avoidance = None if options is None else "VERMEIDUNG" in options
    removal = (
        None
        if phase is None
        else facts.get(
            "vermeidung_wirksam_geplant"
            if phase == "KONZEPT"
            else "ursache_ausgeschlossen"
        )
    )
    absent = _und([avoidance, removal])
    _fordere(
        absent is not True or residual is None,
        "Ausgeschlossene Risikoursache und bekannte verbleibende Risikokategorie widersprechen sich.",
    )
    remains = (
        False
        if absent is True
        else True
        if absent is False or residual is not None
        else None
    )
    category_ok = (
        True
        if remains is False
        else None
        if residual is None
        else residual in akzeptierte_kategorien
    )
    actual = (
        initial
        if phase == "KONZEPT" and vorher.get("bewertungsstand") == "UMGESETZT"
        else residual
        if phase == "UMGESETZT"
        else None
    )
    ist_belegt = False if phase == "KONZEPT" else None
    if phase is None:
        actual = None
    if phase == "UMGESETZT":
        implemented = [] if options is not None else [None]
        for option, field in [
            ("REDUKTION", "reduktionsmassnahmen_umgesetzt"),
            ("TRANSFER", "transfer_wirksam"),
            ("VERMEIDUNG", "ursache_ausgeschlossen"),
        ]:
            if options is not None and option in options:
                implemented.append(facts.get(field))
        ist_belegt = _und(implemented)
        if ist_belegt is not True:
            actual = None
    if unbegruendete_neubewertung:
        if phase == "UMGESETZT":
            actual = None
            ist_belegt = None
    if (
        phase is None
        or phase == "UMGESETZT"
        and ist_belegt is not True
        or unbegruendete_neubewertung
    ):
        category_ok = None
    acceptance = _und([category_ok, extra])
    facts.update(
        risikokategorie=initial,
        eingegangenes_risiko=actual,
        restrisiko_vorhanden=remains,
        akzeptanz_erreicht=acceptance,
        bewertungsstand=phase,
        vorher_nachher=True
        if initial is not None
        and (residual is not None or remains is False)
        and (phase == "KONZEPT" or ist_belegt is True)
        else None,
    )
    result = pruefe_methodenschritt("BSI2003.RISIKOBEHANDLUNG", facts)
    result["regel_id"] = "BSI2003.RISIKOVERLAUF"
    result["begruendung"] = (
        "Gekoppelte Matrix- und Behandlungsprüfung; Maßnahmenannahmen und zusätzliche Akzeptanzkriterien bleiben explizit."
    )
    result["einstufung_vorher"] = before["befund"]
    result["einstufung_nachher"] = (
        "RISIKO_VERMIEDEN" if remains is False else after["befund"]
    )
    result["tatsaechlich_eingegangenes_risiko"] = actual
    result["matrix_id"] = before["matrix_id"]
    result["bewertungsstand"] = phase
    result["nachher_als_ist_belegt"] = ist_belegt
    result["neubewertungsgrund"] = nachher.get("neubewertungsgrund")
    result["kategorienkriterium_erfuellt"] = category_ok
    result["weitere_akzeptanzkriterien_erfuellt"] = extra
    result["akzeptanz_erreicht"] = acceptance
    result["abgeleitete_fakten"] = {name: facts[name] for name in sorted(derived)}
    stand_missing = []
    if unbegruendete_neubewertung:
        stand_missing.append("nachher.neubewertungsgrund")
    if phase is None:
        stand_missing.append("nachher.bewertungsstand")
    if phase == "KONZEPT" and vorher.get("bewertungsstand") is None:
        stand_missing.append("vorher.bewertungsstand")
    result["fehlende_angaben"] = sorted(
        set(
            result["fehlende_angaben"]
            + stand_missing
            + ["vorher." + p for p in before["fehlende_angaben"]]
            + (
                []
                if remains is False
                else ["nachher." + p for p in after["fehlende_angaben"]]
            )
            + extra_missing
        )
    )
    return result


def pruefe_checkentscheidung(anforderung_id: str, angaben: dict) -> dict:
    """Check a declared status against the actual catalogue category and threats.

    The result assesses whether the chosen check status is justified, not whether
    the underlying requirement is fulfilled. A justified NEIN can therefore pass
    this decision check while explicitly documenting a substantive deficit.
    """
    from .fachlogik import _validiere
    from .kern import _katalog, _objekt, _text

    _text(anforderung_id, "anforderung_id")
    requirement = _katalog()["anforderungen"].get(anforderung_id)
    _fordere(
        requirement is not None and not requirement["entfallen"],
        "Aktive Anforderung erforderlich.",
    )
    vertrag = _vertrag("BSI2002.CHECKENTSCHEIDUNG")
    derived = {"basis", "kreuzreferenzen_identifiziert"}
    _objekt(angaben, set(vertrag["felder"]) - derived, "angaben")
    _validiere(angaben, vertrag["felder"])
    facts = copy.deepcopy(angaben)
    expected = set(requirement["gefaehrdungen"])
    collection = facts.get("zugehoerige_gefaehrdungen")
    complete = None
    if collection is not None:
        objects = collection.get("objekte")
        if objects is not None:
            ids = [o.get("id") for o in objects]
            known = {i for i in ids if i is not None}
            _fordere(
                known <= expected,
                "Gefaehrdung gehoert nicht zur konkreten Anforderung.",
            )
            if collection.get("vollstaendig") is True and None not in ids:
                complete = known == expected
    facts.update(
        basis=requirement["kategorie"] == "B", kreuzreferenzen_identifiziert=complete
    )
    result = pruefe_methodenschritt("BSI2002.CHECKENTSCHEIDUNG", facts)
    result.update(
        regel_id="BSI2002.KATALOG_CHECKENTSCHEIDUNG",
        anforderung_id=anforderung_id,
        katalogfassung=_katalog()["quellenfassung"],
        gepruefter_status=facts.get("status"),
        zugehoerige_gefaehrdungen=sorted(expected),
        abgeleitete_fakten={name: facts[name] for name in sorted(derived)},
        begruendung="Pruefung der Begruendbarkeit des gewaehlten Check-Status; ERFUELLT bestaetigt die Statusentscheidung, nicht die Umsetzung der Anforderung.",
    )
    return result


def pruefe_checkabdeckung(vorgehen, modellierung, checks):
    """Compare concrete block/object modelling with mandatory check records.

    This validates completeness of recorded statuses, not substantive fulfilment.
    Basis coverage requires B; Standard/Kern require B and S. The explicit Kern
    restriction in BSI 200-2 section 7.7 remains visible for B/ENTBEHRLICH.
    """
    from .fachlogik import _validiere
    from .kern import _katalog, _wahl, _ergebnis

    _wahl(vorgehen, ("BASIS", "STANDARD", "KERN"), "vorgehen")
    catalog = _katalog()
    active = {i: r for i, r in catalog["anforderungen"].items() if not r["entfallen"]}
    schema = {
        "modellierung": {
            "typ": "liste",
            "element": {
                "baustein_id": {
                    "typ": "kategorie",
                    "werte": list(catalog["bausteine"]),
                },
                "zielobjekt_id": {"typ": "text"},
            },
        },
        "checks": {
            "typ": "liste",
            "element": {
                "anforderung_id": {"typ": "kategorie", "werte": list(active)},
                "zielobjekt_id": {"typ": "text"},
                "status": {
                    "typ": "kategorie",
                    "werte": ["JA", "TEILWEISE", "NEIN", "ENTBEHRLICH"],
                },
            },
        },
    }
    data = dict(modellierung=modellierung, checks=checks)
    _validiere(data, schema)
    missing = []
    indexed = {}
    for name, id_field in [
        ("modellierung", "baustein_id"),
        ("checks", "anforderung_id"),
    ]:
        collection = data[name]
        rows = None if collection is None else collection.get("objekte")
        index = {}
        if collection is None:
            missing.append(name)
        elif rows is None:
            missing.append(name + ".objekte")
        else:
            for i, row in enumerate(rows):
                absent = [f for f in [id_field, "zielobjekt_id"] if row.get(f) is None]
                missing.extend(f"{name}.objekte[{i}].{f}" for f in absent)
                if not absent:
                    key = row[id_field] + "\x1f" + row["zielobjekt_id"]
                    _fordere(
                        key not in index,
                        "Doppelte Anforderungs-/Baustein-Zielobjekt-Zuordnung.",
                    )
                    index[key] = row
        indexed[name] = index
    expected = {}
    for row in indexed["modellierung"].values():
        for ident, req in active.items():
            if req["baustein_id"] == row["baustein_id"] and req["kategorie"] in (
                "B",
            ) + (() if vorgehen == "BASIS" else ("S",)):
                expected[ident + "\x1f" + row["zielobjekt_id"]] = dict(
                    anforderung_id=ident, zielobjekt_id=row["zielobjekt_id"]
                )
    received = indexed["checks"]
    absent_keys = sorted(set(expected) - set(received))
    open_keys = sorted(
        key
        for key in set(expected) & set(received)
        if received[key].get("status") is None
    )
    forbidden = sorted(
        key
        for key in set(expected) & set(received)
        if vorgehen == "KERN"
        and active[received[key]["anforderung_id"]]["kategorie"] == "B"
        and received[key].get("status") == "ENTBEHRLICH"
    )
    for i, row in enumerate((checks or {}).get("objekte") or []):
        if (
            row.get("anforderung_id") is not None
            and row.get("zielobjekt_id") is not None
        ):
            key = row["anforderung_id"] + "\x1f" + row["zielobjekt_id"]
            if key in open_keys:
                missing.append(f"checks.objekte[{i}].status")
    if modellierung is not None and modellierung.get("vollstaendig") is not True:
        missing.append("modellierung.vollstaendig")
    if absent_keys and checks is not None and checks.get("vollstaendig") is not True:
        missing.append("checks.vollstaendig")
    # Known missing required records remain visible even when the broader scope
    # is unknown. A complete declared set turns absence into a known deficit.
    checks_complete = checks is not None and checks.get("vollstaendig") is True
    known_absent = absent_keys if checks_complete else []
    if missing:
        finding = "UNBEKANNT"
    elif not expected:
        finding = "NICHT_ANWENDBAR"
    elif known_absent or forbidden:
        finding = "NICHT_ERFUELLT"
    else:
        finding = "ERFUELLT"
    return _ergebnis(
        "BSI2002.CHECKABDECKUNG",
        finding,
        "Pruefung der Vollstaendigkeit dokumentierter Check-Status; keine Aussage zur Erfuellung der Anforderungen. Kern-Sonderregel fuer Basis-Anforderungen gemaess Abschnitt 7.7.",
        missing,
        vorgehen=vorgehen,
        quellenabschnitte=["6.3", "7.7", "8.4.2"],
        erforderliche_checks=[expected[key] for key in sorted(expected)],
        fehlende_checks=[expected[key] for key in known_absent],
        ungeklaerte_checks=[
            expected[key] for key in absent_keys if not checks_complete
        ],
        offene_status=[expected[key] for key in open_keys],
        kern_unzulaessig_entbehrlich=[expected[key] for key in forbidden],
        zusaetzliche_checks=[
            dict(
                anforderung_id=received[key]["anforderung_id"],
                zielobjekt_id=received[key]["zielobjekt_id"],
            )
            for key in sorted(set(received) - set(expected))
        ],
    )
