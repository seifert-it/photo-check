# Foto-Check (Seifert-IT)

Ein kleines Offline-Tool, das anhand weniger Fragen (Minderjährige, Erkennbarkeit, Gruppenfoto, Kanal, Einwilligung etc.)
eine Empfehlung ausgibt: **ALLOWED / LIMITED / NOT_ALLOWED** – inklusive Begründungen und optionalem HTML-Report.

> Hinweis: Das Tool ersetzt keine Rechtsberatung.

## Features
- Interaktiver CLI-Check (keine Bildanalyse, nur Entscheidungslogik)
- Regeln konfigurierbar über `config.json`
- Optionaler HTML-Report (inkl. Logo, wenn vorhanden)

## Voraussetzungen
- Python 3.10+ (empfohlen: 3.11 oder 3.12)
- Keine externen Python-Abhängigkeiten nötig (Standardbibliothek)

## Installation
```bash
git clone <DEIN-REPO-URL>
cd foto-check
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
.\.venv\Scripts\activate

