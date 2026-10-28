# bsikompendium 0.2.0

Native Offline-Prüfungen für BSI IT-Grundschutz: **1.835 aktive Anforderungen**,
**111 individuelle Bausteinmodellierungen** und **83 Methodenschritte** nach
BSI 200-1/200-2/200-3 sind implementiert und auf Bereichsebene unabhängig gegen
Quellen geprüft. Die Paketprüfergebnisse werden im versionierten Abnahmebericht des Projekts
geführt. Eine Veröffentlichung ist nicht erfolgt.
Python ab 3.10; keine Laufzeitabhängigkeiten.

## Lokal installieren und prüfen

Aus diesem Paketverzeichnis:

```sh
python3 -m pip install .
```

```python
import bsikompendium as b

vertrag = b.fachlicher_eingabevertrag("ORP.3.A6")
befund = b.pruefe_fachregel("ORP.3.A6", {
    "mitarbeitende": {
        "vollstaendig": True,
        "objekte": [{"geschult_aufgaben": True, "geschult_verantwortung": False}],
    }
})
assert befund["befund"] == "TEILWEISE_ERFUELLT"
assert befund["bekannte_maengel"] == ["ORP.3.A6.K2"]
```

Die Tatsachen beziehen sich auf Schulungsinhalt, Aufgaben und Verantwortung der
konkreten Mitarbeitenden. Die Library berechnet den Befund aus den Einzelpflichten;
ein pauschales Nutzer-Endurteil wird nicht verlangt. Felddefinitionen nennen
Nachweisgegenstand und gegebenenfalls fachlichen Bewertungsmaßstab.

## Modellierung, Methodik und Risiko

`methodenschritte()` liefert 194 IDs: 111 `BSIMODELL.*`-Modelle und 83 Schritte
der Standards `BSI2001.*`, `BSI2002.*`, `BSI2003.*`.
`methodischer_eingabevertrag(id)` beschreibt ihre Eingaben;
`pruefe_methodenschritt(id, angaben)` prüft sie nativ.
`bewerte_risiko()` schlägt Häufigkeit und Schaden in der ausdrücklich gewählten
Matrix nach. Die mitgelieferte BSI-Beispielmatrix ist keine allgemeine Vorgabe
für jede Institution. `pruefe_risikoverlauf()` verbindet diese Berechnung mit
tatsächlicher bzw. erst geplanter Risikobehandlung.

[Das Beispiel `individueller_pruefablauf`](examples/individueller_pruefablauf.py)
verbindet Fahrzeugmodellierung, Analysebedarf, Matrixeinstufung und die
Diebstahlschutzpflicht `INF.11.A12`:

```sh
python3 examples/individueller_pruefablauf.py examples/individueller_pruefablauf.json
```

Die identische JSON-Datei kann dem gleichnamigen R-Beispiel übergeben werden.
Erwartet werden eine erfüllte Modellierung, erforderliche zusätzliche
Risikoanalyse, Risikokategorie `HOCH` und eine teilweise erfüllte Fachpflicht
mit Mangel `INF.11.A12.K1`. Das ist eine ausgewählte Prüfung, kein Gesamturteil
über die Sicherheit des Fahrzeugs.

## Daten und Grenzen

Objekte sind `dict`, Arrays `list`. `None` oder fehlende Angaben bedeuten
unbekannt; `False` ist ein bekannter falscher Sachverhalt. Objektmengen enthalten
`objekte` und eine ausdrückliche Angabe `vollstaendig`. Entscheidungsrelevante unbekannte Eingaben können
keine positive Gesamtbewertung erzeugen; feststehende Mängel bleiben sichtbar.
Ungültige Daten lösen `Eingabefehler` mit `code="EINGABE_UNGUELTIG"` aus.

- [Fachlogik und vollständige Datenformen](docs/FACHLOGIK.md)
- [Öffentliche API](docs/API.md)

`eingabevertrag()` und `pruefe_anforderung()` sind **Legacy-Funktionen** für
Absatz-Selbstauskünfte. Das alte Beispiel `kundenportal` verwendet diesen Ablauf;
es gehört nicht zur individuellen Anforderungsabdeckung von 0.2.
Spezialisierte Teilprüfungen ersetzen ebenfalls keine vollständige Fachregel.

Quellenstand: Kompendium 2023 mit Errata vom 26.03.2026; BSI-Standards
200-1/200-2/200-3 jeweils Version 1.0 und dokumentierte ergänzende Verweise.
Die Library läuft ohne Netzbetrieb oder Telemetrie, liest keine Nachweisdateien
und schreibt keine Nutzerdaten. Die Beispielprogramme lesen ausdrücklich ihre
JSON-Eingabe. Ein positiver Befund beruht auf den erhobenen Tatsachen und ist
keine BSI-Zertifizierung.

Lizenz: Apache-2.0. Copyright RiskDataScience GmbH.
Maintainer: Dr. Dimitrios Geromichalos, riskdatascience@web.de.
