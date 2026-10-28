"""Direkte Zahlen- und Zeitkriterien aus dem Kompendium, keine freie Regel-DSL."""

from __future__ import annotations

import calendar
import math
import re
from datetime import date

from .kern import _bool, _ergebnis, _fordere, _objekt, _oder, _teilpruefung, _und

FELDER = {
    "APP.2.2.A1": ["funktionsebene_jahr"],
    "OPS.1.2.6.A11": ["genauigkeit_erheblich", "unabhaengige_ntp_server"],
    "DER.3.2.A5": ["teammitglieder"],
    "APP.3.6.A2": ["zusaetzliche_secondary_server"],
    "APP.4.4.A21": [
        "erhoehtes_fremdeinwirkungsrisiko",
        "schutzbedarf_sehr_hoch",
        "pod_laufzeit_stunden",
    ],
    "SYS.3.2.1.A29": ["passwortlaenge"],
    "IND.3.2.A6": ["sicherheitskomponenten_ot"],
    "NET.1.1.A4": ["firewall_stufen", "paketfilter_externe_dmz"],
    "NET.1.2.A28": ["managementclients_intern", "managementclients_extern"],
    "INF.1.A18": ["begehungen_im_jahr", "vorgabe_pro_jahr"],
    "INF.2.A9": [
        "loesch_oder_brandvermeidungsanlage",
        "brandfrueherkennung",
        "personal_geschult",
        "reaktionsplaene",
        "reaktionszeit_sekunden",
    ],
    "INF.2.A17": [
        "automatische_schutzreaktion",
        "stelle_staendig_besetzt",
        "kontrollzeit_sekunden",
    ],
    "INF.5.A13": ["feuer_minuten", "rauch_minuten"],
    "INF.5.A25": ["feuer_minuten", "rauch_minuten", "zuleitung_minuten"],
    "OPS.1.2.2.A19": ["letzte_pruefung", "bezugsdatum"],
    "INF.1.A36": ["letzte_pruefung", "bezugsdatum"],
    "INF.12.A10": [
        "aenderungsdatum",
        "abschlussdatum",
        "arbeitsdoku_aktualisiert",
        "stammdoku_aktualisiert",
        "letzte_pruefung",
        "bezugsdatum",
    ],
}
BOOLFELDER = {
    "genauigkeit_erheblich",
    "erhoehtes_fremdeinwirkungsrisiko",
    "schutzbedarf_sehr_hoch",
    "loesch_oder_brandvermeidungsanlage",
    "brandfrueherkennung",
    "personal_geschult",
    "reaktionsplaene",
    "automatische_schutzreaktion",
    "stelle_staendig_besetzt",
}
DATUMFELDER = {
    "letzte_pruefung",
    "bezugsdatum",
    "aenderungsdatum",
    "abschlussdatum",
    "arbeitsdoku_aktualisiert",
    "stammdoku_aktualisiert",
}
GANZZAHLEN = {
    "funktionsebene_jahr",
    "unabhaengige_ntp_server",
    "teammitglieder",
    "zusaetzliche_secondary_server",
    "passwortlaenge",
    "sicherheitskomponenten_ot",
    "firewall_stufen",
    "paketfilter_externe_dmz",
    "managementclients_intern",
    "managementclients_extern",
    "begehungen_im_jahr",
    "vorgabe_pro_jahr",
}


def _datum(v):
    if v is None:
        return None
    _fordere(
        isinstance(v, str)
        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v) is not None,
        "Datum muss YYYY-MM-DD sein",
    )
    try:
        return date.fromisoformat(v)
    except ValueError:
        _fordere(False, "Ungültiges Kalenderdatum")


def _jahresfrist(start, ende, jahre):
    if start is None or ende is None:
        return None
    _fordere(start <= ende, "Letzte Prüfung darf nicht nach Bezugsdatum liegen")
    jahr = start.year + jahre
    _fordere(jahr <= 9999, "Kalendergrenze überschritten")
    frist = date(
        jahr, start.month, min(start.day, calendar.monthrange(jahr, start.month)[1])
    )
    return ende <= frist


def pruefe_technische_grenzen(anforderung_id: str, angaben: dict) -> dict:
    """Belegte Zahlen-/Zeitteilkriterien; keine vollständige technische Anforderungsabnahme."""
    _fordere(
        isinstance(anforderung_id, str) and anforderung_id in FELDER,
        "Keine direkte Grenzprüfung für diese ID",
    )
    _objekt(angaben, set(FELDER[anforderung_id]), "angaben")
    f = {}
    for k in FELDER[anforderung_id]:
        v = angaben.get(k)
        if k in BOOLFELDER:
            _bool(v, k)
        elif k in DATUMFELDER:
            v = _datum(v)
        else:
            _fordere(
                v is None
                or (
                    type(v) in (int, float)
                    and math.isfinite(v)
                    and v >= 0
                    and (k not in GANZZAHLEN or v == int(v))
                ),
                k + ": nichtnegative Zahl erforderlich",
            )
        f[k] = v

    def mind(k, n):
        return None if f[k] is None else f[k] >= n

    def hoech(k, n):
        return None if f[k] is None else f[k] <= n

    a = anforderung_id
    w = {}
    if a == "APP.2.2.A1":
        w = {"funktionsebene_mindestens_2016": mind("funktionsebene_jahr", 2016)}
    elif a == "OPS.1.2.6.A11":
        if f["genauigkeit_erheblich"] is False:
            return _ergebnis(
                a,
                "NICHT_ANWENDBAR",
                "Bedingung dieses Teilkriteriums trifft nicht zu.",
                anwendbar=False,
                pruefumfang="Nur die bezeichneten Zahlen-/Zeitkriterien; übrige Anforderung separat prüfen.",
            )
        w = {
            "vier_unabhaengige_ntp_server": None
            if f["genauigkeit_erheblich"] is None
            else mind("unabhaengige_ntp_server", 4)
        }
    elif a == "DER.3.2.A5":
        w = {"mindestens_zwei_personen": mind("teammitglieder", 2)}
    elif a == "APP.3.6.A2":
        w = {"zusaetzlicher_secondary": mind("zusaetzliche_secondary_server", 1)}
    elif a == "APP.4.4.A21":
        gilt = _und(
            [f["erhoehtes_fremdeinwirkungsrisiko"], f["schutzbedarf_sehr_hoch"]]
        )
        if gilt is False:
            return _ergebnis(
                a,
                "NICHT_ANWENDBAR",
                "Bedingung dieses Teilkriteriums trifft nicht zu.",
                anwendbar=False,
                pruefumfang="Nur die bezeichneten Zahlen-/Zeitkriterien; übrige Anforderung separat prüfen.",
            )
        w = {
            "pod_hoechstens_24_stunden": None
            if gilt is None
            else hoech("pod_laufzeit_stunden", 24)
        }
    elif a == "SYS.3.2.1.A29":
        w = {
            "passwort_eins_bis_64_stellen": _und(
                [mind("passwortlaenge", 1), hoech("passwortlaenge", 64)]
            )
        }
    elif a == "IND.3.2.A6":
        w = {"sicherheitskomponente_ot": mind("sicherheitskomponenten_ot", 1)}
    elif a == "NET.1.1.A4":
        w = {
            "zweistufige_firewall": mind("firewall_stufen", 2),
            "filter_externe_dmz": mind("paketfilter_externe_dmz", 1),
        }
    elif a == "NET.1.2.A28":
        w = {
            "client_intern": mind("managementclients_intern", 1),
            "client_extern": mind("managementclients_extern", 1),
        }
    elif a == "INF.1.A18":
        _fordere(
            f["vorgabe_pro_jahr"] is None or f["vorgabe_pro_jahr"] in (1, 2),
            "Vorgabe explizit als ein oder zwei Begehungen festlegen",
        )
        w = {
            "begehungszahl": None
            if f["vorgabe_pro_jahr"] is None or f["begehungen_im_jahr"] is None
            else f["begehungen_im_jahr"] >= f["vorgabe_pro_jahr"]
        }
    elif a == "INF.2.A9":
        w = {
            "brandbekaempfung": _oder(
                [
                    f["loesch_oder_brandvermeidungsanlage"],
                    _und(
                        [
                            f["brandfrueherkennung"],
                            f["personal_geschult"],
                            f["reaktionsplaene"],
                            hoech("reaktionszeit_sekunden", 180),
                        ]
                    ),
                ]
            )
        }
    elif a == "INF.2.A17":
        w = {
            "schutzreaktion": _oder(
                [
                    f["automatische_schutzreaktion"],
                    _und(
                        [
                            f["stelle_staendig_besetzt"],
                            hoech("kontrollzeit_sekunden", 180),
                        ]
                    ),
                ]
            )
        }
    elif a in ("INF.5.A13", "INF.5.A25"):
        grenze = 30 if a == "INF.5.A13" else 90
        w = {k: mind(k, grenze) for k in FELDER[a]}
    elif a in ("OPS.1.2.2.A19", "INF.1.A36"):
        w = {
            "pruefintervall": _jahresfrist(
                f["letzte_pruefung"], f["bezugsdatum"], 1 if a.startswith("OPS") else 3
            )
        }
    elif a == "INF.12.A10":
        w = {
            "dokumentationstreue": _jahresfrist(
                f["letzte_pruefung"], f["bezugsdatum"], 4
            )
        }
        for key, tage in [
            ("arbeitsdoku_aktualisiert", 0),
            ("stammdoku_aktualisiert", 28),
        ]:
            start, ende = (
                f["aenderungsdatum"] if tage == 0 else f["abschlussdatum"],
                f[key],
            )
            w[key] = (
                None
                if start is None or ende is None
                else 0 <= (ende - start).days <= tage
            )
    erg = _teilpruefung(a, w)
    if (a == "OPS.1.2.6.A11" and f["genauigkeit_erheblich"] is None) or (
        a == "APP.4.4.A21" and gilt is None
    ):
        erg["anwendbarkeit"] = "UNBEKANNT"
    erg["pruefumfang"] = (
        "Nur die bezeichneten Zahlen-/Zeitkriterien; übrige Anforderung separat prüfen."
    )
    return erg
