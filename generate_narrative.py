"""Generate a Situation–Complication–Resolution (SCR) business narrative.

Run from project root: python narrator/generate_narrative.py
Without a usable API key/network, the script uses a local template fallback.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "narrator" / "findings.json"
OUTPUT_PATH = ROOT / "narrator" / "sample_output.txt"
MODEL_NAME = "gemini-3.1-flash-lite"


def load_findings() -> dict[str, Any]:
    if not FINDINGS_PATH.exists():
        raise FileNotFoundError(
            f"{FINDINGS_PATH} not found. Run 'python analysis/clean_and_eda.py' first."
        )
    with FINDINGS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("findings.json must contain a JSON object.")
    return data


def offline_narrative(findings: dict[str, Any]) -> str:
    """Build an evidence-based SCR narrative with no API call."""
    peak_month = findings.get("peak_month_after_outlier_exclusion") or "not available"
    peak_value = findings.get("peak_month_revenue_after_outlier_exclusion")
    peak_text = f"₹{peak_value:,.2f}" if isinstance(peak_value, (int, float)) else "not available"
    cod_rate = findings.get("cod_return_rate_pct")
    non_cod_rate = findings.get("non_cod_return_rate_pct")
    cod_text = f"{cod_rate:.2f}%" if isinstance(cod_rate, (int, float)) else "not available"
    non_cod_text = f"{non_cod_rate:.2f}%" if isinstance(non_cod_rate, (int, float)) else "not available"
    return (
        "MAMAEARTH RETURNS & GROWTH INTELLIGENCE\n\n"
        "SITUATION\n"
        f"The source data contains {findings.get('raw_order_count')} order rows. "
        f"After natural-key duplicate removal, {findings.get('cleaned_order_count')} rows remain. "
        f"The calculated discounted order value before duplicate removal is ₹{findings.get('raw_discounted_order_value', 0):,.2f}, "
        f"and after cleaning it is ₹{findings.get('cleaned_discounted_order_value', 0):,.2f}.\n\n"
        "COMPLICATION\n"
        f"The analysis flagged {findings.get('quantity_outlier_count')} quantity outlier rows for review; they were not deleted. "
        f"The COD return rate is {cod_text}, compared with {non_cod_text} for non-COD orders. "
        "These rates describe an association and do not establish that payment method causes returns. "
        f"The retained order value is ₹{findings.get('retained_order_value', 0):,.2f}; this is an analytical measure, not verified accounting revenue.\n\n"
        "RESOLUTION\n"
        f"The highest monthly order value after excluding flagged quantity outliers is in {peak_month} ({peak_text}). "
        "Review flagged bulk orders, reconcile returned orders against refunds, and monitor return rates by payment method and city tier. "
        "Validate these findings with operational and finance records before making policy changes.\n\n"
        "VERIFIED FIGURES (source: generated findings.json)\n"
        f"{json.dumps(findings, indent=2, ensure_ascii=False)}\n"
    )


def _number_variants(value: Any) -> list[str]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, int):
        return [str(value), f"{value:,}"]
    if isinstance(value, float):
        if value.is_integer():
            n = int(value)
            return [str(n), f"{n:,}", f"{value:.2f}", f"{value:,.2f}"]
        return [str(value), f"{value:.2f}", f"{value:,.2f}"]
    if isinstance(value, str):
        return [value]
    return []


def numeric_accuracy_check(narrative: str, findings: dict[str, Any]) -> dict[str, Any]:
    """Verify five generated targets from findings.json appear in the narrative."""
    targets = findings.get("numeric_check_targets", [])
    checked = targets[:5]
    missing = []
    # Keep exact textual values for months; strip commas only for numeric variants.
    text = narrative
    text_without_commas = text.replace(",", "")
    for target in checked:
        value = target.get("value")
        variants = _number_variants(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            found = any(re.search(rf"(?<![\w.]){re.escape(v.replace(',', ''))}(?![\w.])", text_without_commas) for v in variants)
        else:
            found = any(v.casefold() in text.casefold() for v in variants)
        if not found:
            missing.append({"label": target.get("label"), "value": value})
    return {"checked_count": len(checked), "passed": len(checked) == 5 and not missing, "missing_figures": missing}


def generate_narrative(findings: dict[str, Any]) -> dict[str, Any]:
    """Return a dictionary, using Gemini when possible and offline fallback otherwise."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        narrative = offline_narrative(findings)
        return {"success": True, "mode": "offline", "narrative": narrative,
                "accuracy": numeric_accuracy_check(narrative, findings), "error": None}

    prompt = (
        "Create an executive business narrative using the Situation, Complication, Resolution (SCR) structure. "
        "Use only the JSON figures supplied below. Include all five values in numeric_check_targets exactly, "
        "with the associated month where applicable. Do not invent data. Discuss revenue, returns, outlier review, "
        "and actionable steps. State that retained order value is not verified accounting revenue and correlation is not causation. "
        "Return a polished report with headings Situation, Complication, Resolution.\n\n"
        "Verified findings JSON:\n" + json.dumps(findings, indent=2, ensure_ascii=False)
    )
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000),
        )
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a careful business analyst. Never fabricate or alter figures. "
                    "If data is missing, say so. Keep recommendations evidence-based."
                ),
                temperature=0,
                max_output_tokens=1200,
            ),
        )
        narrative = response.text
        if not narrative or not narrative.strip():
            raise ValueError("Gemini returned an empty response.")
        accuracy = numeric_accuracy_check(narrative, findings)
        return {"success": True, "mode": "gemini", "narrative": narrative,
                "accuracy": accuracy, "error": None}
    except Exception as exc:
        narrative = offline_narrative(findings)
        return {"success": True, "mode": "offline_fallback", "narrative": narrative,
                "accuracy": numeric_accuracy_check(narrative, findings),
                "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    findings = load_findings()
    result = generate_narrative(findings)
    OUTPUT_PATH.write_text(result["narrative"], encoding="utf-8")
    print("Narrative mode:", result["mode"])
    print(result["narrative"])
    print("\nNumeric accuracy check:", json.dumps(result["accuracy"], indent=2))
    print("\nSaved narrative to:", OUTPUT_PATH)
    if result["error"]:
        print("Gemini unavailable; offline fallback used. Error:", result["error"])
    if result["accuracy"] and not result["accuracy"]["passed"]:
        print("WARNING: Review the missing numeric figures before submission.")


if __name__ == "__main__":
    main()
