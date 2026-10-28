"""Native Auswertung individuell hergeleiteter fachlicher Kriterienverträge."""

from __future__ import annotations

import copy
import calendar
import gzip
import math
import re
from datetime import datetime
import json
from functools import lru_cache
from importlib.resources import files

from .kern import _bool, _ergebnis, _fordere, _objekt, _und, _oder, anforderung
from .technik import _datum, _jahresfrist


@lru_cache(maxsize=1)
def _vertraege():
    return json.loads(
        gzip.decompress(
            files("bsikompendium").joinpath("resources/fachregeln.json.gz").read_bytes()
        )
    )


def fachlicher_eingabevertrag(anforderung_id: str) -> dict:
    """Individuelle Felder, Bewertungsmaßstäbe, Nachweise und Kriterien abfragen."""
    anforderung(anforderung_id)
    r = _vertraege()["anforderungen"].get(anforderung_id)
    if r is None:
        return {
            "anforderung_id": anforderung_id,
            "status": "REGEL_UNGEKLAERT",
            "felder": {},
            "kriterien": [],
        }
    return copy.deepcopy(r)


def _zeitpunkt(v, pfad):
    if v is None:
        return None
    _fordere(
        isinstance(v, str)
        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", v)
        is not None,
        pfad + ": UTC-Zeitpunkt YYYY-MM-DDTHH:MM:SSZ erforderlich",
    )
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fordere(False, pfad + ": ungültiger UTC-Zeitpunkt")


def _sekundentakt(v):
    return any(
        n in v for n in ("letzter_zeitpunkt", "bezugszeitpunkt", "intervall_sekunden")
    )


def _validiere(daten, schema, pfad="angaben"):
    _objekt(daten, set(schema), pfad)
    for name, vertrag in schema.items():
        v = daten.get(name)
        p = pfad + "." + name
        if v is None:
            continue
        typ = vertrag["typ"]
        if typ == "bool":
            _bool(v, p)
        elif typ == "datum":
            _datum(v)
        elif typ == "zeitpunkt":
            _zeitpunkt(v, p)
        elif typ == "zahl":
            _fordere(
                type(v) in (int, float) and math.isfinite(v),
                p + ": endliche Zahl erforderlich",
            )
        elif typ == "anzahl":
            _fordere(
                type(v) in (int, float) and math.isfinite(v) and v >= 0 and v == int(v),
                p + ": nichtnegative ganze Anzahl erforderlich",
            )
        elif typ == "kategorie":
            _fordere(
                isinstance(v, str) and v in vertrag["werte"],
                p + ": unzulässige Kategorie",
            )
        elif typ == "text":
            _fordere(isinstance(v, str) and bool(v.strip()), p + ": Text erforderlich")
        elif typ == "textliste":
            _fordere(
                isinstance(v, list)
                and all(isinstance(x, str) and bool(x.strip()) for x in v),
                p + ": Textliste erforderlich",
            )
            _fordere(len(set(v)) == len(v), p + ": doppelte Einträge")
            if "werte" in vertrag:
                _fordere(
                    set(v) <= set(vertrag["werte"]), p + ": unzulässiger Textlistenwert"
                )
        elif typ == "liste":
            _objekt(v, {"objekte", "vollstaendig"}, p)
            _bool(v.get("vollstaendig"), p + ".vollstaendig")
            items = v.get("objekte")
            if items is not None:
                _fordere(isinstance(items, list), p + ".objekte: Liste erforderlich")
                for i, item in enumerate(items):
                    _validiere(item, vertrag["element"], p + f".objekte[{i}]")
                if "eindeutiges_feld" in vertrag:
                    key = vertrag["eindeutiges_feld"]
                    ids = [item[key] for item in items if item.get(key) is not None]
                    _fordere(
                        len(ids) == len(set(ids)), p + ": doppelte Objektidentität"
                    )
        elif typ == "regelmaessigkeit":
            _fordere(isinstance(v, dict), p + ": Objekt erforderlich")
            sek = _sekundentakt(v)
            namen = (
                ("letzter_zeitpunkt", "bezugszeitpunkt", "intervall_sekunden")
                if sek
                else ("letztes_datum", "bezugsdatum", "intervall_tage")
            )
            _objekt(v, set(namen) | {"intervall_begruendet", "durchgefuehrt"}, p)
            _bool(v.get("intervall_begruendet"), p + ".intervall_begruendet")
            _bool(v.get("durchgefuehrt"), p + ".durchgefuehrt")
            n = v.get(namen[2])
            _fordere(
                n is None
                or type(n) in (int, float)
                and math.isfinite(n)
                and n > 0
                and n == int(n),
                p + ": positives ganzzahliges Intervall erforderlich",
            )
            start, ende = (
                _zeitpunkt(v.get(k), p + "." + k) if sek else _datum(v.get(k))
                for k in namen[:2]
            )
            _fordere(
                v.get("durchgefuehrt") is not False or start is None,
                p + ": ausgebliebene Durchführung hat keinen Durchführungstermin",
            )
            _fordere(
                start is None or ende is None or start <= ende,
                p + ": letzter Termin liegt nach Bezugsdatum",
            )
        else:
            raise RuntimeError("Unbekannter Vertragstyp: " + typ)
        if typ in ("zahl", "anzahl") and "werte" in vertrag:
            _fordere(
                v in vertrag["werte"],
                p + ": Zahl außerhalb des zulässigen Wertebereichs",
            )


def _auswerten(e, daten, schema, pfad="angaben", eltern=()):
    op = e["op"]
    if op == "wert":
        return e["wert"], []
    if op == "feld":
        v = daten.get(e["name"])
        return v, [] if v is not None else [pfad + "." + e["name"]]
    if op == "oberfeld":
        d, _, p = eltern[-e["ebenen"]]
        v = d.get(e["name"])
        return v, [] if v is not None else [p + "." + e["name"]]
    if op == "zeitdifferenz":
        fehlend = sorted({pfad + "." + e[k] for k in ("von", "bis") if daten.get(e[k]) is None})
        if fehlend:
            return None, fehlend
        if schema[e["von"]]["typ"] == "datum":
            return (_datum(daten[e["bis"]]) - _datum(daten[e["von"]])).days, []
        start = _zeitpunkt(daten[e["von"]], pfad + "." + e["von"])
        ende = _zeitpunkt(daten[e["bis"]], pfad + "." + e["bis"])
        return int((ende - start).total_seconds()), []
    if op == "jahresdatum":
        tiefe = e.get("ebenen", 0)
        bezug, _, bezugspfad = eltern[-tiefe] if tiefe else (daten, schema, pfad)
        v = bezug.get(e["feld"])
        if v is None:
            return None, [bezugspfad + "." + e["feld"]]
        start = _datum(v)
        jahr = start.year + e["jahre"]
        _fordere(jahr <= 9999, "Kalendergrenze überschritten")
        return start.replace(
            year=jahr, day=min(start.day, calendar.monthrange(jahr, start.month)[1])
        ).isoformat(), []
    if op in ("und", "oder"):
        teile = [_auswerten(x, daten, schema, pfad, eltern) for x in e["args"]]
        v = (_und if op == "und" else _oder)([x[0] for x in teile])
        return v, sorted({p for _, ps in teile for p in ps}) if v is None else []
    if op == "nicht":
        v, f = _auswerten(e["arg"], daten, schema, pfad, eltern)
        return None if v is None else not v, f
    if op == "wenn":
        a, fa = _auswerten(e["bedingung"], daten, schema, pfad, eltern)
        b, fb = _auswerten(e["folge"], daten, schema, pfad, eltern)
        v = _oder([None if a is None else not a, b])
        return v, sorted(set(fa + fb)) if v is None else []
    if op == "vergleich":
        a, fa = _auswerten(e["links"], daten, schema, pfad, eltern)
        b, fb = _auswerten(e["rechts"], daten, schema, pfad, eltern)
        if a is None or b is None:
            return None, sorted(set(fa + fb))
        operator = e["operator"]
        if operator == "mengen==":
            return set(a) == set(b), []
        if operator == "<=":
            return a <= b, []
        if operator == "<":
            return a < b, []
        if operator == ">=":
            return a >= b, []
        if operator == "==":
            return a == b, []
        if operator == ">":
            return a > b, []
        if operator == "!=":
            return a != b, []
        raise RuntimeError("Unbekannter Vergleich: " + operator)
    if op == "enthaelt":
        v = daten.get(e["feld"])
        return (
            (None, [pfad + "." + e["feld"]])
            if v is None
            else (set(e["werte"]) <= set(v), [])
        )
    if op == "vorhanden":
        v = daten.get(e["feld"])
        return (None, [pfad + "." + e["feld"]]) if v is None else (bool(v), [])
    if op == "anzahl":
        v = daten.get(e["feld"])
        p = pfad + "." + e["feld"]
        if schema[e["feld"]]["typ"] == "liste":
            if v is None:
                return None, [p]
            if v.get("objekte") is None:
                return None, [p + ".objekte"]
            offen = [] if v.get("vollstaendig") is True else [p + ".vollstaendig"]
            key = schema[e["feld"]].get("eindeutiges_feld")
            if key is not None:
                offen.extend(
                    p + f".objekte[{i}].{key}"
                    for i, o in enumerate(v["objekte"])
                    if o.get(key) is None
                )
            attr = e.get("attribut")
            if attr is not None:
                offen.extend(
                    p + f".objekte[{i}].{attr}"
                    for i, o in enumerate(v["objekte"])
                    if o.get(attr) is None
                )
            if offen:
                return None, sorted(set(offen))
            return (
                len({o[attr] for o in v["objekte"]})
                if attr is not None
                else len(v["objekte"])
            ), []
        return (None, [pfad + "." + e["feld"]]) if v is None else (len(v), [])
    if op == "disjunkt":
        a, b = daten.get(e["links"]), daten.get(e["rechts"])
        fehlend = [
            pfad + "." + k for k in (e["links"], e["rechts"]) if daten.get(k) is None
        ]
        return (None, fehlend) if fehlend else (not bool(set(a) & set(b)), [])
    if op in ("alle", "irgendein", "mindestanteil"):
        name = e["liste"]
        tiefe = e.get("ebenen", 0)
        bezug, bezugsschema, bezugspfad = (
            eltern[-tiefe] if tiefe else (daten, schema, pfad)
        )
        mengenschema = bezugsschema[name]
        p = bezugspfad + "." + name
        menge = bezug.get(name)
        if menge is None:
            return None, [p]
        objekte = menge.get("objekte")
        if objekte is None:
            return None, [p + ".objekte"]
        teile = [
            _auswerten(
                e["praedikat"],
                o,
                mengenschema["element"],
                p + f".objekte[{i}]",
                eltern + ((daten, schema, pfad),),
            )
            for i, o in enumerate(objekte)
        ]
        # Ein Gegenbeispiel widerlegt ALL auch bei unvollständiger Grundmenge.
        voll = menge.get("vollstaendig")
        minimum = len(objekte) >= mengenschema.get("mindestelemente", 0)
        key = mengenschema.get("eindeutiges_feld")
        unbekannte_ids = [
            p + f".objekte[{i}].{key}"
            for i, o in enumerate(objekte)
            if key is not None and o.get(key) is None
        ]
        if op == "mindestanteil":
            if voll is not True or unbekannte_ids:
                v = None
            else:
                sicher = sum(x[0] is True for x in teile)
                moeglich = sicher + sum(x[0] is None for x in teile)
                erforderlich = len(objekte) * e["zaehler"]
                v = (
                    True
                    if sicher * e["nenner"] >= erforderlich
                    else False
                    if moeglich * e["nenner"] < erforderlich
                    else None
                )
        elif op == "irgendein":
            v = _oder([x[0] for x in teile] + [False if voll is True else None])
        else:
            v = _und(
                [x[0] for x in teile]
                + [
                    True if voll is True else None,
                    True if minimum else False if voll is True else None,
                    None if unbekannte_ids else True,
                ]
            )
        offen = sorted({p for _, ps in teile for p in ps})
        if op in ("alle", "mindestanteil"):
            offen = sorted(set(offen + unbekannte_ids))
        if voll is not True:
            offen.append(p + ".vollstaendig")
        return v, offen if v is None else []
    if op == "frist":
        p = pfad + "." + e["feld"]
        f = daten.get(e["feld"])
        if f is None:
            return None, [p]
        sek = _sekundentakt(f)
        namen = (
            ("letzter_zeitpunkt", "bezugszeitpunkt", "intervall_sekunden")
            if sek
            else ("letztes_datum", "bezugsdatum", "intervall_tage")
        )
        start, ende = (
            _zeitpunkt(f.get(k), p + "." + k) if sek else _datum(f.get(k))
            for k in namen[:2]
        )
        intervall = f.get(namen[2])
        abstand = (
            None
            if start is None or ende is None
            else (ende - start).total_seconds()
            if sek
            else (ende - start).days
        )
        vals = [
            f.get("intervall_begruendet"),
            f.get("durchgefuehrt") if "durchgefuehrt" in f else True,
        ]
        vals.append(
            None if abstand is None or intervall is None else abstand <= intervall
        )
        if e.get("max_tage") is not None:
            vals.append(
                None
                if abstand is None
                else abstand <= e["max_tage"] * (86400 if sek else 1)
            )
        if e.get("jahre") is not None:
            vals.append(
                _jahresfrist(
                    start.date() if sek and start is not None else start,
                    ende.date() if sek and ende is not None else ende,
                    e["jahre"],
                )
            )
        v = _und(vals)
        namen = (*namen, "intervall_begruendet") + (
            ("durchgefuehrt",) if "durchgefuehrt" in f else ()
        )
        fehlend = [p + "." + n for n in namen if f.get(n) is None]
        return v, fehlend if v is None else []
    raise RuntimeError("Unbekannte fachliche Operation: " + op)


def pruefe_fachregel(anforderung_id: str, angaben: dict) -> dict:
    """Konkrete Tatsachen anhand individueller BSI-Kriterien auswerten; offene Regeln bleiben offen."""
    original = anforderung(anforderung_id)
    if original["entfallen"]:
        return _ergebnis(
            anforderung_id,
            "NICHT_ANWENDBAR",
            "Anforderung ist entfallen.",
            anwendbar=False,
        )
    # Internal evaluation only reads contracts. Public access still returns a deep copy.
    vertrag = _vertraege()["anforderungen"].get(anforderung_id)
    if vertrag is None:
        erg = _ergebnis(
            anforderung_id,
            None,
            "Individuelle Fachlogik noch nicht vollständig erarbeitet.",
            anwendbar=None,
        )
        erg["status"] = "REGEL_UNGEKLAERT"
        return erg
    return _pruefe_vertrag(anforderung_id, angaben, vertrag)


def _pruefe_vertrag(anforderung_id, angaben, vertrag):
    """Shared native evaluator; callers supply source-specific validated contracts."""
    _validiere(angaben, vertrag["felder"])
    app, fehlend = _auswerten(vertrag["anwendbarkeit"], angaben, vertrag["felder"])
    if app is not True:
        return _ergebnis(
            anforderung_id,
            "UNBEKANNT" if app is None else "NICHT_ANWENDBAR",
            "Anwendungsvoraussetzungen des Fachvertrags.",
            fehlend,
            app,
            bekannte_maengel=[],
            teilbefunde={},
        )
    teile = {}
    maengel = []
    offen = []
    for k in vertrag["kriterien"]:
        ka, kf = _auswerten(k["anwendbarkeit"], angaben, vertrag["felder"])
        v, f = _auswerten(k["ausdruck"], angaben, vertrag["felder"])
        if ka is False:
            teile[k["kriterium_id"]] = {
                "befund": "NICHT_ANWENDBAR",
                "anwendbarkeit": "FALSCH",
                "modalitaet": k["modalitaet"],
                "fehlende_angaben": [],
            }
            continue
        if ka is None:
            v, f = None, sorted(set(kf + f))
        teile[k["kriterium_id"]] = {
            "befund": "UNBEKANNT"
            if v is None
            else "ERFUELLT"
            if v
            else "NICHT_ERFUELLT",
            "anwendbarkeit": "UNBEKANNT" if ka is None else "WAHR",
            "modalitaet": k["modalitaet"],
            "fehlende_angaben": f,
        }
        if v is False:
            maengel.append(k["kriterium_id"])
        if v is None:
            offen.extend(f)
    befunde = [t["befund"] for t in teile.values() if t["befund"] != "NICHT_ANWENDBAR"]
    befund = (
        "NICHT_ANWENDBAR"
        if not befunde
        else "UNBEKANNT"
        if "UNBEKANNT" in befunde
        else "ERFUELLT"
        if not maengel
        else "NICHT_ERFUELLT"
        if len(maengel) == len(befunde)
        else "TEILWEISE_ERFUELLT"
    )
    return _ergebnis(
        anforderung_id,
        befund,
        "Individuelle Kriterienprüfung; Abweichungen und Risiko separat bewerten.",
        offen,
        anwendbar=bool(befunde),
        bekannte_maengel=maengel,
        teilbefunde=teile,
        fachvertrag_status=vertrag["status"],
    )
