# foto_check.py
from __future__ import annotations

import json
import base64
import mimetypes
from dataclasses import dataclass
from enum import Enum
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


# =========================================================
# Enums & Dataclasses
# =========================================================

class Decision(str, Enum):
    ALLOWED = "ALLOWED"
    LIMITED = "LIMITED"
    NOT_ALLOWED = "NOT_ALLOWED"


@dataclass
class PhotoContext:
    minors: bool
    identifiable: bool
    group_photo: bool
    prominent_subject: bool  # einzelne Personen hervorgehoben/zentral/groß?
    channel: str
    consent_status: str


@dataclass
class Result:
    decision: Decision
    message: str
    reasons: List[str]
    rule_id: Optional[str] = None
    legal_ref_keys: Optional[List[str]] = None


# =========================================================
# Konfiguration
# =========================================================

def load_config() -> Dict[str, Any]:
    path = Path(__file__).with_name("config.json")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# Input Helpers
# =========================================================

def yes_no(prompt: str) -> bool:
    while True:
        val = input(prompt + " (j/n): ").strip().lower()
        if val in ("j", "ja", "y", "yes"):
            return True
        if val in ("n", "nein", "no"):
            return False
        # Keine Fehlermeldung im „kryptischen“ Sinn – nur stille Wiederholung wäre auch möglich.
        # Ich gebe minimal Feedback, damit klar ist, warum erneut gefragt wird.
        print("Bitte 'j' oder 'n' eingeben.")


def ask_channel(prompt: str = "Kanal (website/social/print): ") -> str:
    """
    Fragt so lange nach, bis eine gültige Kanal-Eingabe vorliegt.
    Ungültige Eingaben werden effektiv ignoriert (keine Exception).
    """
    mapping = {
        "web": "website",
        "website": "website",
        "homepage": "website",
        "site": "website",
        "social": "social",
        "instagram": "social",
        "facebook": "social",
        "tiktok": "social",
        "print": "print",
        "flyer": "print",
        "plakat": "print",
        "broschüre": "print",
        "broschuere": "print",
    }
    while True:
        raw = input(prompt).strip().lower()
        if raw in mapping:
            return mapping[raw]
        # Eingabe wird ignoriert, wir fragen einfach erneut (kein Traceback)
        print("Ungültig. Bitte website, social oder print eingeben.")


def ask_consent(prompt: str = "Einwilligung (alle/teilweise/unbekannt): ") -> str:
    """
    Fragt so lange nach, bis eine gültige Einwilligungs-Eingabe vorliegt.
    Ungültige Eingaben werden effektiv ignoriert (keine Exception).
    """
    mapping = {
        "alle": "alle",
        "voll": "alle",
        "ja": "alle",
        "teilweise": "teilweise",
        "einige": "teilweise",
        "unbekannt": "unbekannt",
        "?": "unbekannt",
        "weiß nicht": "unbekannt",
        "weiss nicht": "unbekannt",
    }
    while True:
        raw = input(prompt).strip().lower()
        if raw in mapping:
            return mapping[raw]
        print("Ungültig. Bitte alle, teilweise oder unbekannt eingeben.")


# =========================================================
# Regel-Engine (Config-driven)
# =========================================================

def rule_matches(ctx: PhotoContext, when: Dict[str, Any]) -> bool:
    if "consent_status" in when and ctx.consent_status != when["consent_status"]:
        return False
    if "minors" in when and ctx.minors != when["minors"]:
        return False
    if "identifiable" in when and ctx.identifiable != when["identifiable"]:
        return False
    if "group_photo" in when and ctx.group_photo != when["group_photo"]:
        return False
    if "prominent_subject" in when and ctx.prominent_subject != when["prominent_subject"]:
        return False
    if "channel_in" in when and ctx.channel not in when["channel_in"]:
        return False
    return True


def apply_config_rules(
    ctx: PhotoContext, cfg: Dict[str, Any], base_reasons: List[str]
) -> Optional[Result]:

    for rule in cfg.get("rules_ordered", []):
        if rule_matches(ctx, rule.get("when", {})):
            return Result(
                decision=Decision[rule["decision"]],
                message=rule["message"],
                reasons=base_reasons + rule.get("extra_reasons", []),
                rule_id=rule.get("id"),
                legal_ref_keys=rule.get("legal_refs", []),
            )
    return None


# =========================================================
# Sensibilitäts-Bewertung
# =========================================================

def calculate_sensitivity(ctx: PhotoContext) -> tuple[str, str]:
    if ctx.consent_status in ("teilweise", "unbekannt"):
        return "HIGH", "🔶 Hohe Sensibilität – Einwilligung ist nicht vollständig geklärt."

    if ctx.prominent_subject and ctx.identifiable:
        if ctx.minors:
            return "HIGH", "🔶 Hohe Sensibilität – hervorgehobene minderjährige Person."
        return "MEDIUM", "🟡 Erhöhte Sensibilität – hervorgehobene Person (portraitähnlich)."

    if ctx.minors and ctx.channel == "social":
        return "HIGH", "🔶 Hohe Sensibilität – Minderjährige in sozialen Medien."

    if ctx.minors and not ctx.group_photo:
        return "HIGH", "🔶 Hohe Sensibilität – Einzelportrait Minderjähriger."

    if ctx.minors:
        return "MEDIUM", "🟡 Erhöhte Sensibilität – Minderjährige beteiligt."

    if ctx.channel == "social":
        return "MEDIUM", "🟡 Erhöhte Sensibilität – Veröffentlichung in sozialen Medien."

    if not ctx.group_photo:
        return "MEDIUM", "🟡 Erhöhte Sensibilität – Einzelportrait."

    return "LOW", "🟢 Niedrige Sensibilität."


# =========================================================
# Entscheidungslogik
# =========================================================

def evaluate(ctx: PhotoContext, cfg: Dict[str, Any]) -> Result:
    reasons: List[str] = []

    reasons.append("Personen sind erkennbar." if ctx.identifiable else "Personen sind nicht erkennbar.")
    reasons.append("Minderjährige beteiligt." if ctx.minors else "Keine Minderjährigen.")
    reasons.append("Gruppenfoto." if ctx.group_photo else "Einzelportrait oder kleine Gruppe.")
    reasons.append(
        "Eine oder wenige Personen sind deutlich hervorgehoben (portraitähnlich)."
        if ctx.prominent_subject
        else "Keine einzelne Person ist deutlich hervorgehoben."
    )
    reasons.append(f"Kanal: {ctx.channel}.")
    reasons.append(f"Einwilligung: {ctx.consent_status}.")

    hit = apply_config_rules(ctx, cfg, reasons)
    if hit:
        return hit

    return Result(
        decision=Decision.ALLOWED,
        message="🟢 ERLAUBT: Keine Regel greift restriktiv.",
        reasons=reasons,
    )


# =========================================================
# DSGVO-Link-Auflösung
# =========================================================

def resolve_legal_refs(cfg: Dict[str, Any], keys: Optional[List[str]]) -> List[Dict[str, str]]:
    if not keys:
        return []

    catalog = cfg.get("legal_ref_catalog", {})
    resolved = []
    for key in keys:
        if key in catalog:
            resolved.append(catalog[key])
    return resolved


# =========================================================
# Logo laden
# =========================================================

def load_logo_data_uri(cfg: Dict[str, Any]) -> Optional[str]:
    logo_path = cfg.get("logo_path")
    if not logo_path:
        return None

    path = Path(__file__).with_name(logo_path)
    if not path.exists():
        return None

    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "image/png"

    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


# =========================================================
# HTML Report
# =========================================================

def render_report(ctx: PhotoContext, result: Result, cfg: Dict[str, Any]) -> str:
    sens_level, sens_msg = calculate_sensitivity(ctx)
    legal_refs = resolve_legal_refs(cfg, result.legal_ref_keys)

    logo_uri = load_logo_data_uri(cfg)
    logo_html = ""
    if logo_uri:
        logo_html = f'<img src="{logo_uri}" alt="Logo" style="height:40px;vertical-align:middle;">'

    reasons_html = "\n".join(f"<li>{escape(r)}</li>" for r in result.reasons)

    legal_html = ""
    if legal_refs:
        items = []
        for ref in legal_refs:
            label = escape(ref.get("label", ""))
            url = escape(ref.get("url", ""))
            items.append(f'<li><a href="{url}" target="_blank" rel="noopener">{label}</a></li>')
        legal_html = "<ul>" + "\n".join(items) + "</ul>"

    rule_info = ""
    if result.rule_id:
        rule_info = f"<p><b>Regel-ID:</b> {escape(result.rule_id)}</p>"

    ctx_table = f"""
    <table>
      <tr><th>Minderjährige</th><td>{'Ja' if ctx.minors else 'Nein'}</td></tr>
      <tr><th>Erkennbar</th><td>{'Ja' if ctx.identifiable else 'Nein'}</td></tr>
      <tr><th>Gruppenfoto</th><td>{'Ja' if ctx.group_photo else 'Nein'}</td></tr>
      <tr><th>Hervorgehoben</th><td>{'Ja' if ctx.prominent_subject else 'Nein'}</td></tr>
      <tr><th>Kanal</th><td>{escape(ctx.channel)}</td></tr>
      <tr><th>Einwilligung</th><td>{escape(ctx.consent_status)}</td></tr>
      <tr><th>Sensibilität</th><td>{escape(sens_level)} – {escape(sens_msg)}</td></tr>
    </table>
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Foto-Check Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; }}
  h1 {{ margin-top: 0; }}
  .header {{ display:flex; align-items:center; gap:16px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; width: 200px; }}
  .box {{ border: 1px solid #ddd; padding: 12px; border-radius: 8px; }}
  .decision {{ font-size: 18px; font-weight: bold; }}
  .muted {{ color:#666; font-size: 12px; }}
</style>
</head>
<body>
  <div class="header">
    {logo_html}
    <div>
      <h1>Foto-Check Report</h1>
      <div class="muted">Erstellt: {escape(now)}</div>
    </div>
  </div>

  <div class="box">
    <div class="decision">{escape(result.message)}</div>
    {rule_info}
    {ctx_table}
  </div>

  <h2>Begründungen</h2>
  <ul>
    {reasons_html}
  </ul>

  <h2>Rechtsgrundlagen / Hinweise</h2>
  {legal_html if legal_html else "<p class='muted'>Keine Links hinterlegt.</p>"}

  <hr>
  <p class="muted">
    Hinweis: Dieses Tool ersetzt keine Rechtsberatung. Im Zweifel Datenschutzbeauftragte/r oder Rechtsberatung einbeziehen.
  </p>
</body>
</html>
"""


def write_report(html: str) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"report_{timestamp}.html"
    path = Path(__file__).with_name(filename)
    path.write_text(html, encoding="utf-8")
    return path


# =========================================================
# Main
# =========================================================

def main():
    cfg = load_config()

    print("Foto-Check\n")

    minors = yes_no("Sind Minderjährige auf dem Foto?")
    identifiable = yes_no("Sind Personen erkennbar?")
    group_photo = yes_no("Ist es ein Gruppenfoto?")
    prominent_subject = yes_no("Sind einzelne Personen deutlich hervorgehoben (zentral/groß/portraitähnlich)?")

    # NEU: robust, keine Exceptions mehr
    channel = ask_channel("Kanal (website/social/print): ")
    consent_status = ask_consent("Einwilligung (alle/teilweise/unbekannt): ")

    ctx = PhotoContext(
        minors=minors,
        identifiable=identifiable,
        group_photo=group_photo,
        prominent_subject=prominent_subject,
        channel=channel,
        consent_status=consent_status,
    )

    result = evaluate(ctx, cfg)
    sens_level, sens_msg = calculate_sensitivity(ctx)

    print("\nErgebnis:")
    print(result.message)
    print(f"Sensibilität: {sens_level} – {sens_msg}")

    print("\nBegründung:")
    for r in result.reasons:
        print(" - " + r)

    if result.legal_ref_keys:
        print("\nRechtsgrundlagen/Hinweise:")
        for ref in resolve_legal_refs(cfg, result.legal_ref_keys):
            print(f" - {ref.get('label')}: {ref.get('url')}")

    if yes_no("\nHTML-Report erzeugen?"):
        html = render_report(ctx, result, cfg)
        out = write_report(html)
        print(f"Report gespeichert: {out}")


if __name__ == "__main__":
    main()
