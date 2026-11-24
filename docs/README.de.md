# Relay-backed Light

Home-Assistant-Custom-Integration für eine Leuchte, deren Stromversorgung ein
separates Relais schaltet. Domain: `relay_backed_light`.

Veröffentlicht unter der registrierten Marke [peacode](https://peacode.com).
Rechteinhaber und Maintainer: [Norman Bauer](https://github.com/norman-bauer).
Repository: [peacodecom/relay-backed-light](https://github.com/peacodecom/relay-backed-light).
Lizenz: [MIT](../LICENSE). Weitere Angaben: [Rechte und Pflege](../AUTHORS.md).

[English README](../README.md) ·
[Release-Checkliste (Englisch)](releasing.md)

## Voraussetzungen

- Home Assistant **ab 2026.10.0**, Python **ab 3.14.2**.
- Genau ein vorhandenes Relais aus `switch` oder `light` und genau eine
  vorhandene Quellleuchte aus `light`.
- Die Quellintegration muss bereits eingerichtet sein.

Dieser Entwicklungsordner ist keine aktive HA-Konfiguration. Es gibt keine
automatische Installation oder Migration. Integrationscode und automatisierte
Tests liegen in diesem Repository. Version 0.1.0 ist eine erste
Entwicklungsfassung und noch nicht mit physischer Hardware abgenommen.
Release-Dateien stehen erst nach Veröffentlichung einer Version und
erfolgreichem Abschluss des Paketierungsworkflows bereit.

## Installation

Zuerst ein Backup anlegen.

### Marketplace: Home Assistant ab 2026.11

Ab HA 2026.11 ist HACS als **Marketplace** in Home Assistant eingebaut.
Die bisherige HACS-Custom-Integration darf dort nicht zusätzlich installiert werden.

1. Als Administrator **Einstellungen → Marketplace** öffnen und gegebenenfalls
  den Hinweis zu Community-Inhalten bestätigen.
2. Oben rechts **Add from link** (Hinzufügen über einen Link) wählen. Falls
  angefordert, das eigene GitHub-Konto verbinden.
3. Unter **GitHub link** die Adresse
  **https://github.com/peacodecom/relay-backed-light** eingeben und **Add** wählen.
4. Falls nach dem Typ gefragt wird, **Integration** auswählen und erneut
  **Add** bestätigen.
5. **Relay-backed Light** öffnen, **Install** wählen, Version prüfen und
  bestätigen. Falls ein Neustart angefordert wird, diesen vor der Einrichtung
  durchführen. Bezeichnungen können je nach Sprache abweichen.

Offizielle Anleitung: [Benutzerdefinierte Marketplace-Repositories](https://www.home-assistant.io/integrations/marketplace/#custom-repositories).

### HACS: Home Assistant 2026.10

Bei noch nicht eingerichtetem HACS zuerst dessen offizielle
[Einrichtungsanleitung](https://www.hacs.xyz/docs/use/) befolgen.

1. **HACS** öffnen und oben rechts das Drei-Punkte-Menü auswählen.
2. **Benutzerdefinierte Repositories / Custom repositories** öffnen.
3. **https://github.com/peacodecom/relay-backed-light** eintragen.
4. Kategorie **Integration** wählen und **Hinzufügen / Add** bestätigen.
5. **Relay-backed Light** suchen und öffnen. **Herunterladen / Download** bzw.
  **Installieren / Install** wählen und die Version bestätigen.
6. Home Assistant neu starten und anschließend die virtuelle Leuchte einrichten.

Offizielle Anleitung: [Benutzerdefinierte HACS-Repositories](https://www.hacs.xyz/docs/faq/custom_repositories/).

### Manuelle Installation

`relay_backed_light.zip` aus einem Release herunterladen. Im eigenen
HA-Konfigurationsverzeichnis `custom_components/relay_backed_light` anlegen und
das ZIP **dort** entpacken. Die Datei `manifest.json` muss direkt in diesem
Integrationsordner liegen, nicht in einem weiteren Unterordner. Das ZIP enthält
den **Inhalt** des Integrationsordners; nicht im Konfigurationshauptverzeichnis
entpacken. Anschließend HA neu starten.

Alternativ ausschließlich das Quellverzeichnis
`custom_components/relay_backed_light` nach `custom_components` der eigenen
HA-Konfiguration kopieren, nicht das gesamte Repository.

## Virtuelle Leuchte einrichten

Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → Relay-backed
Light** Relais, Quellleuchte und Namen auswählen. Relais und Quelle müssen
verschieden sein; keine Selbstreferenz oder Kette mit zyklischer Abhängigkeit
einrichten, auch nicht über Light-Gruppen. Jedes Relais und jede Quellleuchte
darf nur von einem Integrationseintrag verwendet werden.
**Keine YAML-Konfiguration der Integration unterstützt.**
Relais und Quelle lassen sich nachträglich nicht umstellen: Dafür den
Konfigurationseintrag entfernen und neu hinzufügen. Zeitparameter sind über die
Integrationsoptionen änderbar.

Nach einem Update über Marketplace/HACS Home Assistant neu starten, um den
neuen Integrationscode zu laden. Vor Updates Release-Hinweise lesen und sichern.

## Schaltverhalten

**Einschalten:** Relais einschalten, dessen Rückmeldung mit Zeitlimit abwarten,
bei zuvor abgeschalteter Versorgung die Boot-Verzögerung einhalten und mit
Zeitlimit auf einen verwendbaren Quellenzustand warten. Unterstützte Farb- und
Helligkeitsparameter sowie Effekte, Flash und Einschalt-Transition werden an
`light.turn_on` der Quelle weitergereicht. Nicht unterstützte Fähigkeiten werden
nicht ergänzt.

**Ausschalten:** Sofort das Ausschalten des Relais anfordern. Eine
Ausschalt-Transition wird ignoriert; es wird weder ein Fade noch ein geordnetes
Herunterfahren der Quelle abgewartet. Hardware- und Netzwerklatenz bleiben
möglich. Dies ist keine sicherheitsgerichtete Freischaltung.

Ein neuer Auftrag beendet den vorherigen Auftrag derselben Wrapper-Entität.
Extern ausgeschaltetes oder nicht verfügbares Relais bricht einen wartenden
Einschaltauftrag ab; dieser darf die Versorgung nicht erneut einschalten.
Bereits an das Gerät gesendete Befehle lassen sich nicht zurückholen.
Beim HA-Start und beim Wiederverbinden der Quelle wird das Relais **nicht
automatisch aktiviert**.

## Grenzen und Standardoptionen

Ein alter Quellenzustand `on` oder `off` in HA ist nach dem Zuschalten der
Versorgung **kein verlässlicher Erreichbarkeits- oder Bereitschaftsnachweis**.
Verzögerung und Wiederholungen sind lediglich Heuristiken. Der Ablauf kann
bereits beim Start an einem Timeout scheitern, bevor ein Quellenbefehl gesendet
wird. Auch mehrere Sendeversuche garantieren keinen Erfolg.

| Option | Standard | Bedeutung |
| --- | --- | --- |
| `boot_delay` | 2 s | Zusätzliche Wartezeit nach kaltem Einschalten |
| `relay_timeout` | 5 s | Zeitlimit für Relaiszustand ein |
| `light_timeout` | 20 s | Zeitlimit für verwendbaren Quellenzustand, kein Bereitschaftstest |
| `retry_count` | 3 | Insgesamt drei Quellen-Einschaltversuche nach Kaltstart |
| `retry_interval` | 2 s | Abstand zwischen Versuchen, nicht nach dem letzten |

Bei bereits eingeschalteter Versorgung erfolgt nur **ein** Quellenversuch.
Ausnahme: Eine noch nicht abgeschlossene Kaltstartsequenz behält bei einem
neuen Einschaltauftrag ihre Startwartezeit und Wiederholungen bei.
`retry_count` bezeichnet die Gesamtzahl und nicht zusätzliche Wiederholungen.
Die Zeitparameter sind keine garantierte Gesamtlaufzeit; Aufrufe der
Quellintegration und deren Transport benötigen gegebenenfalls weitere Zeit.

Es gibt keine Zigbee-spezifische Suche, kein Interview und keine garantierte
Bereitschaftserkennung. Das Hardware-Einschaltverhalten der Lampe wird nicht
verändert: Sie kann zunächst mit ihren eigenen gespeicherten Einstellungen
aufleuchten. Wiederholte Effekt- oder Flash-Befehle können diese neu starten.

Fähigkeiten werden aus Quellenattributen übernommen und im Arbeitsspeicher
behalten. Ist die Quelle beim HA-Start nicht verfügbar und liefert keine
Fähigkeitsattribute, bietet die virtuelle Leuchte zunächst nur Ein/Aus und
lernt weitere Funktionen mit der nächsten Quellenmeldung. Die Zuordnung
verwendet Entity-IDs: Nach Umbenennen der physischen Entitäten muss der
Integrationseintrag entfernt und neu angelegt werden.

## Entwicklung

Die Testabhängigkeit `pytest-homeassistant-custom-component==0.13.375` bringt
HA **2026.10.4** mit. Keine abweichende direkte HA-Abhängigkeit ergänzen.
Mindestversion **2026.10.0** und aktuelle unterstützte HA-Versionen sind zusätzlich
zu prüfen; der CI-Teststand allein belegt nicht deren gesamte Kompatibilität.
Die CI benötigt weder eine laufende HA-Instanz noch Zugriff auf `/config`.
