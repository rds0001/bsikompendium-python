"""Katalog, methodische Funktionen und getrennte ältere Bewertungsaggregation."""

from __future__ import annotations

import copy
import json
import math
from functools import lru_cache
from importlib.resources import files
from typing import Any

STUFEN = ("NORMAL", "HOCH", "SEHR_HOCH")
RISIKEN = ("GERING", "MITTEL", "HOCH", "SEHR_HOCH")
GRUNDWERTE = ("vertraulichkeit", "integritaet", "verfuegbarkeit")
FASSUNG = "BSI_KOMPENDIUM_2023_ERRATA_2026_03_26"


class Eingabefehler(ValueError):
    """Ungültige Eingabe; code ist in beiden Sprachen EINGABE_UNGUELTIG."""

    code = "EINGABE_UNGUELTIG"


def _fordere(bedingung: bool, text: str) -> None:
    if not bedingung:
        raise Eingabefehler(text)


def _text(wert: Any, name: str) -> None:
    _fordere(isinstance(wert, str) and bool(wert.strip()), name + ": Text erforderlich")


def _bool(wert: Any, name: str) -> None:
    _fordere(wert is None or type(wert) is bool, name + ": bool oder null erforderlich")


def _wahl(wert: Any, werte: Any, name: str, unbekannt: bool = False) -> None:
    _fordere(
        (unbekannt and wert is None) or (isinstance(wert, str) and wert in werte),
        name + ": unzulässiger Wert",
    )


def _liste(wert: Any, name: str, leer: bool = True) -> None:
    _fordere(
        isinstance(wert, list) and (leer or len(wert) > 0),
        name + ": Liste erforderlich",
    )


def _objekt(wert: Any, erlaubt: set[str], name: str) -> None:
    _fordere(isinstance(wert, dict), name + ": Objekt erforderlich")
    _fordere(
        all(isinstance(k, str) for k in wert) and not (set(wert) - erlaubt),
        name + ": unbekannte Felder",
    )


def _und(werte: list[bool | None]) -> bool | None:
    return False if False in werte else None if None in werte else True


def _oder(werte: list[bool | None]) -> bool | None:
    return True if True in werte else None if None in werte else False


def _ergebnis(
    regel: str,
    befund: Any,
    begruendung: str,
    fehlend: list[str] | None = None,
    anwendbar: bool | None = True,
    **zusatz: Any,
) -> dict:
    return {
        "regel_id": regel,
        "quellenfassung": FASSUNG,
        "status": "AUSGEWERTET",
        "anwendbarkeit": "UNBEKANNT"
        if anwendbar is None
        else "WAHR"
        if anwendbar
        else "FALSCH",
        "befund": befund,
        "begruendung": begruendung,
        "fehlende_angaben": sorted(set(fehlend or [])),
        **zusatz,
    }


def _befund(werte: dict[str, bool | None]) -> tuple[str, list[str], list[str]]:
    fehlend = sorted(k for k, v in werte.items() if v is None)
    maengel = sorted(k for k, v in werte.items() if v is False)
    if fehlend:
        return "UNBEKANNT", fehlend, maengel
    if not werte:
        return "NICHT_ANWENDBAR", [], []
    if not maengel:
        return "ERFUELLT", [], []
    return (
        ("NICHT_ERFUELLT" if len(maengel) == len(werte) else "TEILWEISE_ERFUELLT"),
        [],
        maengel,
    )


@lru_cache(maxsize=1)
def _katalog() -> dict:
    return json.loads(
        files("bsikompendium")
        .joinpath("resources/katalog.json")
        .read_text(encoding="utf-8")
    )


def anforderung(anforderung_id: str) -> dict:
    """Metadaten einer Anforderung, einschließlich entfallener Einträge."""
    _text(anforderung_id, "anforderung_id")
    _fordere(anforderung_id in _katalog()["anforderungen"], "Unbekannte Anforderung")
    return copy.deepcopy(_katalog()["anforderungen"][anforderung_id])


def baustein(baustein_id: str) -> dict:
    """Metadaten eines Bausteins mit Zielobjekttypen und Bearbeitungsreihenfolge."""
    _text(baustein_id, "baustein_id")
    _fordere(baustein_id in _katalog()["bausteine"], "Unbekannter Baustein")
    return copy.deepcopy(_katalog()["bausteine"][baustein_id])


def bausteine() -> list[str]:
    """Alle 111 Baustein-IDs in stabiler Reihenfolge."""
    return sorted(_katalog()["bausteine"])


def anforderungen(
    baustein_id: str | None = None,
    kategorie: str | None = None,
    entfallen: bool = False,
) -> list[str]:
    """Katalog filtern; entfallen=True schließt historische Einträge mit ein."""
    _fordere(type(entfallen) is bool, "entfallen: bool erforderlich")
    if baustein_id is not None:
        baustein(baustein_id)
    _wahl(kategorie, ("B", "S", "H"), "kategorie", True)
    return sorted(
        k
        for k, r in _katalog()["anforderungen"].items()
        if (baustein_id is None or r["baustein_id"] == baustein_id)
        and (kategorie is None or r["kategorie"] == kategorie)
        and (entfallen or not r["entfallen"])
    )


def anforderungen_fuer(
    baustein_ids: list[str],
    vorgehen: str,
    h_auswahl: list[str] | None = None,
    kernbereich: bool | None = None,
) -> list[str]:
    """B für Basis; B/S für Standard bzw. expliziten Kernbereich; H nur ausgewählt."""
    _liste(baustein_ids, "baustein_ids", False)
    for ident in baustein_ids:
        baustein(ident)
    _fordere(len(set(baustein_ids)) == len(baustein_ids), "Doppelte Bausteine")
    _wahl(vorgehen, ("BASIS", "STANDARD", "KERN"), "vorgehen")
    _bool(kernbereich, "kernbereich")
    if vorgehen == "KERN":
        _fordere(
            kernbereich is True,
            "Kern-Absicherung benötigt einen ausdrücklich festgelegten Kernbereich",
        )
    ausgewaehlt = [] if h_auswahl is None else h_auswahl
    _liste(ausgewaehlt, "h_auswahl")
    for ident in ausgewaehlt:
        r = anforderung(ident)
        _fordere(
            not r["entfallen"]
            and r["kategorie"] == "H"
            and r["baustein_id"] in baustein_ids,
            "H-Auswahl passt nicht zu den Bausteinen",
        )
    _fordere(len(set(ausgewaehlt)) == len(ausgewaehlt), "Doppelte H-Anforderungen")
    return sorted(
        {
            k
            for ident in baustein_ids
            for k in anforderungen(ident)
            if anforderung(k)["kategorie"]
            in (("B",) if vorgehen == "BASIS" else ("B", "S"))
        }
        | set(ausgewaehlt)
    )


def eingabevertrag(anforderung_id: str) -> dict:
    """Quellenbezogene Bewertungsblöcke; keine automatische Interpretation des Freitexts."""
    r = anforderung(anforderung_id)
    return {
        "anforderung_id": anforderung_id,
        "quellenfassung": FASSUNG,
        "pdf_seiten": r["pdf_seiten"],
        "kriterien": r["kriterien"],
        "felder_je_kriterium": [
            "relevant",
            "umgesetzt",
            "wirksam",
            "angemessen",
            "begruendung",
        ],
        "bewertungsumfang": "Qualifizierte Bewertung aller Teilanforderungen des bezeichneten Quellenabsatzes; keine Dokumentenprüfung.",
        "unbekannt": "null",
        "nichtrelevanz": "relevant=false verlangt eine Begründung.",
    }


def gefaehrdungen(anforderung_id: str) -> list[str]:
    """Direkte Gefährdungszuordnungen, mit Errata; keine Risikogewichte."""
    return anforderung(anforderung_id)["gefaehrdungen"]


def pruefe_anforderung(
    anforderung_id: str,
    bewertungen: dict,
    anwendbar: bool | None = None,
    begruendung: str = "",
) -> dict:
    """Grundschutz-Check aus unabhängigen Maßnahmenbewertungen je Quellenblock."""
    r = anforderung(anforderung_id)
    _bool(anwendbar, "anwendbar")
    _fordere(isinstance(begruendung, str), "begruendung: Text erforderlich")
    ids = {x["kriterium_id"] for x in r["kriterien"]}
    _objekt(bewertungen, ids, "bewertungen")
    werte, fehlend = {}, []
    for ident, data in bewertungen.items():
        _objekt(
            data,
            {"relevant", "umgesetzt", "wirksam", "angemessen", "begruendung"},
            ident,
        )
        for key in ("relevant", "umgesetzt", "wirksam", "angemessen"):
            _bool(data.get(key), ident + "." + key)
        _fordere(
            isinstance(data.get("begruendung", ""), str),
            ident + ": Begründung muss Text sein",
        )
        if data.get("relevant") is False:
            _text(data.get("begruendung"), ident + ".begruendung")
    if r["entfallen"]:
        return _ergebnis(
            anforderung_id,
            "NICHT_ANWENDBAR",
            "Anforderung ist in der Quelle entfallen.",
            anwendbar=False,
        )
    if anwendbar is False:
        _text(begruendung, "begruendung")
        return _ergebnis(
            anforderung_id, "NICHT_ANWENDBAR", begruendung, anwendbar=False
        )
    if anwendbar is None:
        return _ergebnis(
            anforderung_id,
            "UNBEKANNT",
            "Anwendbarkeit nicht entschieden.",
            ["anwendbar"],
            None,
        )
    for ident in sorted(ids):
        data = bewertungen.get(ident, {})
        if data.get("relevant") is False:
            continue
        if data.get("relevant") is None:
            werte[ident] = None
            fehlend.append(ident + ".relevant")
            continue
        vals = [data.get(k) for k in ("umgesetzt", "wirksam", "angemessen")]
        werte[ident] = _und(vals)
        if werte[ident] is None:
            fehlend.extend(
                ident + "." + k
                for k in ("umgesetzt", "wirksam", "angemessen")
                if data.get(k) is None
            )
    if not ids:
        return _ergebnis(
            anforderung_id,
            "UNBEKANNT",
            "Kein automatischer Prüfumfang spezifiziert.",
            ["fachliche_pruefung"],
        )
    befund, _, maengel = _befund(werte)
    return _ergebnis(
        anforderung_id,
        befund,
        "Bewertung der relevanten Quellenblöcke nach BSI 200-2, 8.4.2.",
        fehlend,
        False if not werte else True,
        bekannte_maengel=maengel,
        teilbefunde={
            k: "UNBEKANNT" if v is None else "ERFUELLT" if v else "NICHT_ERFUELLT"
            for k, v in werte.items()
        },
    )


def pruefe_abweichung(
    anforderung_id: str,
    art: str,
    begruendung: str,
    gefaehrdungsbewertungen: dict,
    leitung_zustimmung: bool | None = None,
    alternativmassnahme: str = "",
    gleichwertig: bool | None = None,
    basis_ausnahme_begruendet: bool | None = None,
) -> dict:
    """Begründung einer Abweichung prüfen, ohne sie in Erfüllung umzudeuten."""
    r = anforderung(anforderung_id)
    _wahl(art, ("NICHT_RELEVANT", "ALTERNATIVMASSNAHME", "RISIKOAKZEPTANZ"), "art")
    _text(begruendung, "begruendung")
    for k, v in [
        ("leitung_zustimmung", leitung_zustimmung),
        ("gleichwertig", gleichwertig),
        ("basis_ausnahme_begruendet", basis_ausnahme_begruendet),
    ]:
        _bool(v, k)
    _fordere(
        isinstance(alternativmassnahme, str), "alternativmassnahme: Text erforderlich"
    )
    _objekt(gefaehrdungsbewertungen, set(r["gefaehrdungen"]), "gefaehrdungsbewertungen")
    for k, v in gefaehrdungsbewertungen.items():
        _bool(v, k)
    if r["entfallen"]:
        return _ergebnis(
            anforderung_id,
            "NICHT_ANWENDBAR",
            "Entfallene Anforderung.",
            anwendbar=False,
        )
    if art == "RISIKOAKZEPTANZ" and (
        r["kategorie"] == "B" or any(c["strikt"] for c in r["kriterien"])
    ):
        return _ergebnis(
            anforderung_id,
            "NICHT_ZULAESSIG",
            "Basis-/MUSS-Anforderungen nicht durch Risikoakzeptanz ersetzen.",
        )
    werte = {k: gefaehrdungsbewertungen.get(k) for k in r["gefaehrdungen"]}
    if art == "ALTERNATIVMASSNAHME":
        _text(alternativmassnahme, "alternativmassnahme")
        werte["gleichwertig"] = gleichwertig
        if r["kategorie"] == "B":
            werte["basis_ausnahme_begruendet"] = basis_ausnahme_begruendet
    if art == "RISIKOAKZEPTANZ":
        werte["leitung_zustimmung"] = leitung_zustimmung
    entscheidung = _und(list(werte.values()))
    return _ergebnis(
        anforderung_id,
        "UNBEKANNT"
        if entscheidung is None
        else "ZULAESSIG_BEGRUENDET"
        if entscheidung
        else "NICHT_ZULAESSIG",
        "Einzelfallnachweise; keine Aussage über Umsetzung der ursprünglichen Anforderung.",
        [k for k, v in werte.items() if v is None],
        abweichungsart=art,
    )


def bestimme_schutzbedarf(
    werte: list[str | None],
    grundwert: str,
    anpassung: str | None = None,
    effekt: str | None = None,
    begruendung: str = "",
) -> dict:
    """Maximum je Grundwert; fachlich begründete Effekte ausdrücklich übergeben."""
    _liste(werte, "werte", False)
    _wahl(grundwert, GRUNDWERTE, "grundwert")
    for v in werte:
        _wahl(v, STUFEN, "schutzbedarf", True)
    _wahl(anpassung, STUFEN, "anpassung", True)
    _wahl(effekt, ("KUMULATION", "VERTEILUNG"), "effekt", True)
    _fordere(
        (anpassung is None) == (effekt is None),
        "Anpassung und Effekt gemeinsam angeben",
    )
    bekannt = [STUFEN.index(v) for v in werte if v is not None]
    maximum = max(bekannt, default=-1)
    if anpassung is not None:
        _text(begruendung, "begruendung")
        if effekt == "KUMULATION":
            _fordere(
                STUFEN.index(anpassung) >= maximum,
                "Kumulation darf bekannten Schutzbedarf nicht senken",
            )
        if effekt == "VERTEILUNG":
            _fordere(
                maximum >= 0 and STUFEN.index(anpassung) <= maximum,
                "Verteilung benötigt eine belegte Ausgangseinstufung und darf sie nicht erhöhen",
            )
    offen = None in werte and maximum < 2
    if offen:
        return _ergebnis(
            "SCHUTZBEDARF",
            "UNBEKANNT",
            "Ausgangseinstufungen unvollständig.",
            ["werte"],
            grundwert=grundwert,
        )
    return _ergebnis(
        "SCHUTZBEDARF",
        anpassung if anpassung is not None else STUFEN[maximum],
        "Maximumprinzip; Anpassung nur als begründete fachliche Vorgabe.",
        grundwert=grundwert,
        effekt=effekt,
    )


def pruefe_risikoanalysebedarf(
    schutzbedarf: dict,
    hinreichend_modelliert: bool | None,
    typisches_szenario: bool | None,
) -> dict:
    """Drei Anlässe der ergänzenden Risikoanalyse, BSI 200-3 Abschnitt 1.2."""
    _objekt(schutzbedarf, set(GRUNDWERTE), "schutzbedarf")
    for v in schutzbedarf.values():
        _wahl(v, STUFEN, "schutzbedarf", True)
    _bool(hinreichend_modelliert, "hinreichend_modelliert")
    _bool(typisches_szenario, "typisches_szenario")
    werte = {
        k: None if schutzbedarf.get(k) is None else schutzbedarf[k] != "NORMAL"
        for k in GRUNDWERTE
    }
    werte.update(
        hinreichend_modelliert=None
        if hinreichend_modelliert is None
        else not hinreichend_modelliert,
        typisches_szenario=None
        if typisches_szenario is None
        else not typisches_szenario,
    )
    bedarf = _oder(list(werte.values()))
    return _ergebnis(
        "RISIKOANALYSEBEDARF",
        "UNBEKANNT"
        if bedarf is None
        else "ERFORDERLICH"
        if bedarf
        else "KEIN_ZUSAETZLICHER_ANLASS",
        "BSI 200-3, 1.2; keine Sicherheits- oder Vollständigkeitsgarantie.",
        [k for k, v in werte.items() if v is None],
        ausloeser=sorted(k for k, v in werte.items() if v is True),
    )


def risikomatrix() -> dict:
    """BSI-Beispielmatrix, ausdrücklich kein universelles Organisationsmodell."""
    return copy.deepcopy(_katalog()["risikomatrix"])


def _matrix(matrix: str | dict) -> dict:
    if isinstance(matrix, str):
        _wahl(matrix, ("BSI_200_3_BEISPIEL_2017",), "matrix")
        return risikomatrix()
    _objekt(matrix, {"id", "haeufigkeiten", "schaeden", "werte"}, "matrix")
    _text(matrix.get("id"), "matrix.id")
    for key in ("haeufigkeiten", "schaeden"):
        vals = matrix.get(key)
        _liste(vals, key, False)
        for v in vals:
            _text(v, key)
        _fordere(len(set(vals)) == len(vals), "Doppelte Achsenwerte")
    _liste(matrix.get("werte"), "werte", False)
    _fordere(
        len(matrix["werte"]) == len(matrix["schaeden"]), "Matrix: falsche Zeilenzahl"
    )
    for row in matrix["werte"]:
        _liste(row, "Matrixzeile")
        _fordere(
            len(row) == len(matrix["haeufigkeiten"]), "Matrix: falsche Spaltenzahl"
        )
        for v in row:
            _wahl(v, RISIKEN, "Risikokategorie")
    return matrix


def bewerte_risiko(
    haeufigkeit: str | None, schaden: str | None, matrix: str | dict
) -> dict:
    """Explizite Matrix nachschlagen, nicht ordinale Werte multiplizieren."""
    m = _matrix(matrix)
    _wahl(haeufigkeit, m["haeufigkeiten"], "haeufigkeit", True)
    _wahl(schaden, m["schaeden"], "schaden", True)
    fehlend = [
        k for k, v in [("haeufigkeit", haeufigkeit), ("schaden", schaden)] if v is None
    ]
    wert = (
        "UNBEKANNT"
        if fehlend
        else m["werte"][m["schaeden"].index(schaden)][
            m["haeufigkeiten"].index(haeufigkeit)
        ]
    )
    return _ergebnis(
        "RISIKOEINSTUFUNG",
        wert,
        "Einstufung nach ausdrücklich ausgewählter Matrix.",
        fehlend,
        matrix_id=m["id"],
    )


def pruefe_risikobehandlung(
    option: str,
    restrisiko: str | None,
    akzeptierte_kategorien: list[str],
    angaben: dict,
) -> dict:
    """Optionenspezifische Behandlung, Restbewertung und Leitungszustimmung prüfen."""
    _wahl(option, ("VERMEIDUNG", "REDUKTION", "TRANSFER", "AKZEPTANZ"), "option")
    _wahl(restrisiko, RISIKEN, "restrisiko", True)
    _liste(akzeptierte_kategorien, "akzeptierte_kategorien")
    for v in akzeptierte_kategorien:
        _wahl(v, RISIKEN, "akzeptierte_kategorien")
    _fordere(
        len(set(akzeptierte_kategorien)) == len(akzeptierte_kategorien),
        "Doppelte Risikokategorien",
    )
    felder = {
        "begruendung",
        "leitung_zustimmung",
        "konsolidiert",
        "umgesetzt",
        "wirkung_geprueft",
        "vertrag_geprueft",
        "ursache_entfallen",
        "basis_muss_offen",
    }
    _objekt(angaben, felder, "angaben")
    for k in felder - {"begruendung"}:
        _bool(angaben.get(k), k)
    _text(angaben.get("begruendung"), "begruendung")
    werte = {k: angaben.get(k) for k in ("leitung_zustimmung", "konsolidiert")}
    werte["basis_muss_offen"] = (
        None
        if angaben.get("basis_muss_offen") is None
        else not angaben["basis_muss_offen"]
    )
    if option == "VERMEIDUNG":
        werte["ursache_entfallen"] = angaben.get("ursache_entfallen")
    else:
        werte["restrisiko"] = (
            None if restrisiko is None else restrisiko in akzeptierte_kategorien
        )
    if option in ("REDUKTION", "TRANSFER"):
        for k in ("umgesetzt", "wirkung_geprueft"):
            werte[k] = angaben.get(k)
    if option == "TRANSFER":
        werte["vertrag_geprueft"] = angaben.get("vertrag_geprueft")
    entscheidung = _und(list(werte.values()))
    return _ergebnis(
        "RISIKOBEHANDLUNG",
        "UNBEKANNT"
        if entscheidung is None
        else "NACHVOLLZIEHBAR_ABGESCHLOSSEN"
        if entscheidung
        else "BEHANDLUNG_OFFEN",
        "Dokumentierte Bewertung, keine Garantie der realen Wirksamkeit.",
        [k for k, v in werte.items() if v is None],
        option=option,
    )


def pruefe_informationsverbund(objekte: list[dict]) -> dict:
    """IDs, Typen und lokale Beziehungen prüfen; keine automatische Asset-Erkennung."""
    _liste(objekte, "objekte", False)
    ids = []
    typen = (
        "Informationsverbund",
        "Prozess",
        "Information",
        "Anwendung",
        "IT-System",
        "Netz",
        "Gebäude/Raum",
        "Kommunikationsverbindung",
    )
    for o in objekte:
        _objekt(o, {"id", "typ", "abhaengigkeiten"}, "objekt")
        _text(o.get("id"), "id")
        _wahl(o.get("typ"), typen, "typ")
        ids.append(o["id"])
        _liste(o.get("abhaengigkeiten", []), "abhaengigkeiten")
        for a in o.get("abhaengigkeiten", []):
            _text(a, "abhaengigkeit")
        _fordere(
            len(set(o.get("abhaengigkeiten", []))) == len(o.get("abhaengigkeiten", [])),
            "Doppelte Beziehung",
        )
    _fordere(len(set(ids)) == len(ids), "Doppelte Objekt-ID")
    fehlende = sorted(
        {a for o in objekte for a in o.get("abhaengigkeiten", []) if a not in ids}
    )
    return _ergebnis(
        "INFORMATIONSVERBUND",
        "BEZIEHUNG_FEHLT" if fehlende else "STRUKTURELL_KONSISTENT",
        "Prüft nur übergebene Objekte; reale Inventarvollständigkeit ist nicht automatisch feststellbar.",
        fehlende,
    )


def pruefe_modellierung(
    objekte: list[dict],
    zuordnungen: list[dict],
    institution: str | None = None,
    unterliegt_vsa: bool | None = None,
) -> dict:
    """Zielobjekttypen, fachliche Zuordnung und korrigierte VSA-Abgrenzung prüfen."""
    basis = pruefe_informationsverbund(objekte)
    _liste(zuordnungen, "zuordnungen")
    _wahl(
        institution,
        (
            "BUNDESBEHOERDE",
            "BUNDESUNMITTELBARE_EINRICHTUNG",
            "LANDESBEHOERDE",
            "UNTERNEHMEN",
            "SONSTIGE",
        ),
        "institution",
        True,
    )
    _bool(unterliegt_vsa, "unterliegt_vsa")
    index = {o["id"]: o for o in objekte}
    teile, paare, belegt = {}, set(), set()
    for z in zuordnungen:
        _objekt(z, {"objekt_id", "baustein_id", "fachlich_passend"}, "zuordnung")
        _text(z.get("objekt_id"), "objekt_id")
        _fordere(z["objekt_id"] in index, "Zielobjekt fehlt")
        b = baustein(z.get("baustein_id"))
        _bool(z.get("fachlich_passend"), "fachlich_passend")
        key = z["objekt_id"] + ":" + z["baustein_id"]
        _fordere(key not in paare, "Doppelte Bausteinzuordnung")
        paare.add(key)
        typ = index[z["objekt_id"]]["typ"]
        passend = any(
            typ == v
            or (typ == "Informationsverbund" and v.startswith("Informationsverbund/"))
            for v in b["zielobjekttypen"]
        )
        werte = [passend, z.get("fachlich_passend")]
        if z["baustein_id"] == "CON.11.1":
            werte.extend(
                [
                    None
                    if institution is None
                    else institution
                    in ("BUNDESBEHOERDE", "BUNDESUNMITTELBARE_EINRICHTUNG"),
                    unterliegt_vsa,
                ]
            )
        teile[key] = _und(werte)
        if teile[key] is True:
            belegt.add(z["objekt_id"])
    offen = sorted(set(index) - belegt)
    befund = (
        "UNBEKANNT"
        if any(v is None for v in teile.values())
        else (
            "MODELLIERUNGSLUECKEN"
            if offen
            or False in teile.values()
            or basis["befund"] != "STRUKTURELL_KONSISTENT"
            else "ZUORDNUNGEN_BESTAETIGT"
        )
    )
    return _ergebnis(
        "MODELLIERUNG",
        befund,
        "Typkompatibilität und explizite Fachbewertung; kein automatischer Vollständigkeitsbeweis.",
        sorted(k for k, v in teile.items() if v is None),
        unbestaetigte_objekte=offen,
        unpassende_zuordnungen=sorted(k for k, v in teile.items() if v is False),
    )


def _fakten(angaben: dict, felder: set[str]) -> dict:
    _objekt(angaben, felder, "angaben")
    for k in felder:
        _bool(angaben.get(k), k)
    return {k: angaben.get(k) for k in sorted(felder)}


def _teilpruefung(regel: str, werte: dict) -> dict:
    befund, fehlend, maengel = _befund(werte)
    return _ergebnis(
        regel,
        befund,
        "Direkte Teilkriterienprüfung im dokumentierten Umfang.",
        fehlend,
        bekannte_maengel=maengel,
    )


def pruefe_http_datenschutz(angaben: dict) -> dict:
    """CON.10.A7 einschließlich korrigierter Body-Regel, ohne feste HTTP-Methode."""
    felder = {
        "vertrauliche_daten_im_body",
        "client_cache_verhindert",
        "formulardaten_maskiert",
        "unerwartetes_browser_speichern_verhindert",
        "zugangsdaten_salted_hash",
        "quelltextabruf_geschuetzt",
    }
    return _teilpruefung("CON.10.A7", _fakten(angaben, felder))


def pruefe_datensicherung(angaben: dict) -> dict:
    """CON.3.A5/A15; Zeitgrenze stammt ausdrücklich aus dem eigenen Sicherungsplan."""
    boolfelder = {
        "plan_eingehalten",
        "mitarbeitende_informiert",
        "aufgaben_bekannt",
        "tests_regelmaessig",
        "wiederherstellung_erfolgreich",
    }
    _objekt(
        angaben, boolfelder | {"wiederherstellungsdauer", "maximale_dauer"}, "angaben"
    )
    for k in boolfelder:
        _bool(angaben.get(k), k)
    for k in ("wiederherstellungsdauer", "maximale_dauer"):
        v = angaben.get(k)
        _fordere(
            v is None or (type(v) in (int, float) and math.isfinite(v) and v >= 0),
            k + ": endliche nichtnegative Zahl",
        )
    dauer, maximum = (
        angaben.get("wiederherstellungsdauer"),
        angaben.get("maximale_dauer"),
    )
    werte = {k: angaben.get(k) for k in boolfelder}
    werte["zeitgrenze_eingehalten"] = (
        None if dauer is None or maximum is None else dauer <= maximum
    )
    return _teilpruefung("CON.3.A5+CON.3.A15", werte)


def pruefe_passwortgebrauch(angaben: dict) -> dict:
    """ORP.4.A8: Tatsachen prüfen, keine echten Passwörter entgegennehmen."""
    felder = {
        "verbindlich_geregelt",
        "zusatzverfahren_geprueft",
        "mehrfach_verwendet",
        "leicht_erratbar",
        "geheim_gehalten",
        "unbeobachtet_eingegeben",
        "auf_funktionstasten_gespeichert",
        "schriftlich_fixiert",
        "notfallhinterlegung",
        "sicher_aufbewahrt",
        "passwortmanager_geprueft",
        "drittanbieter_sync_vorhanden",
        "drittanbieter_sync_deaktiviert",
        "kompromittierung_oder_verdacht",
        "passwort_gewechselt",
    }
    f = _fakten(angaben, felder)

    def nicht(v):
        return None if v is None else not v

    def wenn(a, b):
        return _oder([nicht(a), b])

    werte = {
        k: f[k]
        for k in (
            "verbindlich_geregelt",
            "zusatzverfahren_geprueft",
            "geheim_gehalten",
            "unbeobachtet_eingegeben",
            "passwortmanager_geprueft",
        )
    }
    for k in (
        "mehrfach_verwendet",
        "leicht_erratbar",
        "auf_funktionstasten_gespeichert",
    ):
        werte[k] = nicht(f[k])
    werte["schriftliche_hinterlegung"] = wenn(
        f["schriftlich_fixiert"],
        _und([f["notfallhinterlegung"], f["sicher_aufbewahrt"]]),
    )
    werte["drittanbieter_sync"] = wenn(
        f["drittanbieter_sync_vorhanden"], f["drittanbieter_sync_deaktiviert"]
    )
    werte["wechsel_bei_kompromittierung"] = wenn(
        f["kompromittierung_oder_verdacht"], f["passwort_gewechselt"]
    )
    return _teilpruefung("ORP.4.A8", werte)
