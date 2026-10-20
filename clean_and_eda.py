"""Mamaearth Returns & Growth Intelligence: cleaning, EDA and verified findings.

Run from any working directory with: python analysis/clean_and_eda.py
The script reads the source CSVs from ../data and regenerates analysis outputs,
visualization inputs, and narrator/findings.json. Source CSVs are never modified.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ANALYSIS_DIR = ROOT / "analysis"
NARRATOR_DIR = ROOT / "narrator"


def returned_flag(value) -> bool:
    return str(value).strip().lower() in {"1", "yes", "true", "returned"}


def money(value):
    return round(float(value), 2) if pd.notna(value) else None


def main() -> None:
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")

    print("========== 1. LOAD AND INSPECT ==========")
    print("Customers shape:", customers.shape)
    print("Products shape:", products.shape)
    print("Orders shape:", orders.shape)
    print("Raw missing values:\n", orders.isna().sum().to_string())
    raw_order_count = int(len(orders))

    # Preserve raw source for before-cleaning revenue calculation.
    raw_orders = orders.copy()
    raw_orders["payment_method"] = raw_orders["payment_method"].astype("string").str.strip().str.upper()
    raw_orders["discount_pct"] = pd.to_numeric(raw_orders["discount_pct"], errors="coerce").fillna(0)
    raw_orders["quantity"] = pd.to_numeric(raw_orders["quantity"], errors="coerce")
    products["price"] = pd.to_numeric(products["price"], errors="coerce")
    raw_merged = raw_orders.merge(products[["product_id", "price"]], on="product_id", how="left", validate="many_to_one")
    raw_merged["order_value"] = raw_merged["price"] * raw_merged["quantity"] * (1 - raw_merged["discount_pct"] / 100.0)
    raw_discounted_value = float(raw_merged["order_value"].sum())

    # Standardise casing before grouping.
    orders["payment_method"] = orders["payment_method"].astype("string").str.strip().str.upper()
    print("\n========== 2. STANDARDISE PAYMENT METHODS ==========")
    print(orders["payment_method"].value_counts(dropna=False).to_string())

    natural_key = ["customer_id", "product_id", "order_date", "quantity"]
    duplicate_mask = orders.duplicated(subset=natural_key, keep="first")
    duplicate_rows = orders.loc[duplicate_mask].copy()
    duplicate_count = int(duplicate_mask.sum())
    duplicate_ids = duplicate_rows["order_id"].astype(int).tolist()
    orders_clean = orders.drop_duplicates(subset=natural_key, keep="first").copy()
    print("\n========== 3. DUPLICATES ==========")
    print("Potential duplicate rows:", duplicate_count)
    print("Potential duplicate order IDs:", duplicate_ids)
    print("Orders before cleaning:", len(orders), "; after duplicate removal:", len(orders_clean))

    # Impute numeric values as specified by the project brief.
    for col in ["discount_pct", "rating", "quantity"]:
        orders_clean[col] = pd.to_numeric(orders_clean[col], errors="coerce")
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    rating_median = orders_clean["rating"].median()
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
    orders_clean["order_date"] = pd.to_datetime(orders_clean["order_date"], errors="coerce")
    orders_clean["is_returned"] = orders_clean["is_returned"].apply(returned_flag)

    df = orders_clean.merge(products, on="product_id", how="left", validate="many_to_one")
    df = df.merge(customers, on="customer_id", how="left", validate="many_to_one")
    df["order_value"] = df["price"] * df["quantity"] * (1 - df["discount_pct"] / 100.0)
    df["retained_value"] = np.where(~df["is_returned"], df["order_value"], 0.0)
    cleaned_discounted_value = float(df["order_value"].sum())
    retained_order_value = float(df["retained_value"].sum())

    print("\n========== 4. MISSING VALUES ==========")
    print("Missing discounts filled with 0. Median rating used:", rating_median)
    print("\n========== 5. REVENUE RECONCILIATION ==========")
    print(f"Raw discounted order value: ₹{raw_discounted_value:,.2f}")
    print(f"Cleaned discounted order value: ₹{cleaned_discounted_value:,.2f}")
    print(f"Retained order value excluding returns: ₹{retained_order_value:,.2f}")
    print("Note: retained order value is not verified accounting revenue.")

    q1, q3 = df["quantity"].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower_bound, upper_bound = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df["is_outlier"] = (df["quantity"] < lower_bound) | (df["quantity"] > upper_bound)
    outliers = df.loc[df["is_outlier"], ["order_id", "quantity", "order_value"]].copy()
    outliers.to_csv(ANALYSIS_DIR / "quantity_outliers.csv", index=False)
    print("\n========== 6. QUANTITY OUTLIERS (FLAG ONLY) ==========")
    print(f"Q1={q1}; Q3={q3}; IQR={iqr}; lower={lower_bound}; upper={upper_bound}")
    print("Outlier count:", len(outliers))
    print(outliers.to_string(index=False))

    # Return rate by payment method.
    payment_summary = (df.groupby("payment_method", dropna=False)
        .agg(total_orders=("order_id", "count"), returned_orders=("is_returned", "sum"))
        .reset_index())
    payment_summary["return_rate_pct"] = (100 * payment_summary["returned_orders"] / payment_summary["total_orders"]).round(2)
    payment_summary = payment_summary.sort_values("return_rate_pct", ascending=False)
    payment_summary.to_csv(ANALYSIS_DIR / "return_rate_by_payment.csv", index=False)
    cod_mask = df["payment_method"].eq("COD")
    cod_orders = int(cod_mask.sum())
    non_cod_orders = int((~cod_mask).sum())
    cod_return_rate = float(df.loc[cod_mask, "is_returned"].mean() * 100) if cod_orders else None
    non_cod_return_rate = float(df.loc[~cod_mask, "is_returned"].mean() * 100) if non_cod_orders else None
    if not cod_orders or not non_cod_orders:
        cod_verdict = "Insufficient data to compare COD and non-COD."
    elif cod_return_rate > non_cod_return_rate:
        cod_verdict = "SUPPORTED descriptively: COD return rate is higher."
    elif cod_return_rate < non_cod_return_rate:
        cod_verdict = "NOT SUPPORTED descriptively: COD return rate is lower."
    else:
        cod_verdict = "INCONCLUSIVE descriptively: return rates are equal."
    print("\n========== 7. RETURN RATE BY PAYMENT ==========")
    print(payment_summary.to_string(index=False))
    print("COD return rate:", None if cod_return_rate is None else round(cod_return_rate, 2))
    print("Non-COD return rate:", None if non_cod_return_rate is None else round(non_cod_return_rate, 2))
    print("COD hypothesis verdict:", cod_verdict)

    # Payment method x city tier.
    segment_summary = (df.groupby(["payment_method", "city_tier"], dropna=False)
        .agg(total_orders=("order_id", "count"), returned_orders=("is_returned", "sum"))
        .reset_index())
    segment_summary["return_rate_pct"] = (100 * segment_summary["returned_orders"] / segment_summary["total_orders"]).round(2)
    segment_summary = segment_summary.sort_values(["return_rate_pct", "total_orders"], ascending=[False, False])
    segment_summary.to_csv(ANALYSIS_DIR / "return_rate_by_payment_city_tier.csv", index=False)
    highest_segment = None
    if not segment_summary.empty:
        r = segment_summary.iloc[0]
        highest_segment = {"payment_method": str(r["payment_method"]), "city_tier": int(r["city_tier"]) if pd.notna(r["city_tier"]) else None,
                          "return_rate_pct": float(r["return_rate_pct"]), "total_orders": int(r["total_orders"])}
    print("\n========== 8. PAYMENT × CITY TIER ==========")
    print(segment_summary.to_string(index=False))

    # Correlation analysis.
    correlation_data = df[["quantity", "discount_pct", "rating", "is_returned", "order_value"]].copy()
    correlation_data["is_returned"] = correlation_data["is_returned"].astype(int)
    corr = correlation_data.corr(numeric_only=True)
    corr.to_csv(ANALYSIS_DIR / "correlation_matrix.csv")
    def strength_label(value):
        value = abs(value)
        if value < .10: return "Negligible"
        if value < .30: return "Weak"
        if value < .50: return "Moderate"
        return "Strong"
    correlation_labels = []
    for i, col_a in enumerate(corr.columns):
        for col_b in corr.columns[i + 1:]:
            val = corr.loc[col_a, col_b]
            if pd.notna(val):
                correlation_labels.append({"variable_1": col_a, "variable_2": col_b,
                                           "correlation": round(float(val), 3), "strength": strength_label(val)})
    print("\n========== 9. CORRELATION MATRIX ==========")
    print(corr.round(3).to_string())
    print("Correlation labels:", correlation_labels)

    # Monthly revenue with and without flagged quantity outliers.
    df["order_month"] = df["order_date"].dt.to_period("M").astype(str)
    monthly = (df.groupby("order_month")
        .agg(revenue_with_outliers=("order_value", "sum"),
             revenue_without_outliers=("order_value", lambda s: s.loc[~df.loc[s.index, "is_outlier"]].sum()),
             retained_value=("retained_value", "sum"), order_count=("order_id", "count"))
        .reset_index().sort_values("order_month"))
    for col in ["revenue_with_outliers", "revenue_without_outliers", "retained_value"]:
        monthly[col] = monthly[col].round(2)
    monthly.to_csv(ANALYSIS_DIR / "monthly_revenue.csv", index=False)
    peak_row = monthly.loc[monthly["revenue_without_outliers"].idxmax()] if not monthly.empty else None
    peak_month = str(peak_row["order_month"]) if peak_row is not None else None
    peak_month_revenue = money(peak_row["revenue_without_outliers"]) if peak_row is not None else None
    print("\n========== 10. MONTHLY REVENUE ==========")
    print(monthly.to_string(index=False))
    print("Peak month after excluding quantity outliers:", peak_month, "₹", peak_month_revenue)

    # Generate the five explicit numeric check targets from computed results.
    # These are selected from computed metrics, not manually typed figures.
    findings = {
        "project": "Mamaearth Returns & Growth Intelligence",
        "raw_order_count": raw_order_count,
        "cleaned_order_count": int(len(orders_clean)),
        "potential_duplicate_rows": duplicate_count,
        "potential_duplicate_order_ids": duplicate_ids,
        "raw_discounted_order_value": money(raw_discounted_value),
        "cleaned_discounted_order_value": money(cleaned_discounted_value),
        "retained_order_value": money(retained_order_value),
        "quantity_outlier_count": int(df["is_outlier"].sum()),
        "quantity_outlier_order_ids": df.loc[df["is_outlier"], "order_id"].astype(int).tolist(),
        "cod_return_rate_pct": money(cod_return_rate),
        "non_cod_return_rate_pct": money(non_cod_return_rate),
        "cod_hypothesis_verdict": cod_verdict,
        "peak_month_after_outlier_exclusion": peak_month,
        "peak_month_revenue_after_outlier_exclusion": peak_month_revenue,
        "highest_return_rate_payment_city_tier_segment": highest_segment,
        "return_rate_by_payment": payment_summary.to_dict(orient="records"),
        "monthly_revenue": monthly.to_dict(orient="records"),
        "correlation_labels": correlation_labels,
        "numeric_check_targets": [
            {"label": "raw_order_count", "value": raw_order_count},
            {"label": "cleaned_order_count", "value": int(len(orders_clean))},
            {"label": "potential_duplicate_rows", "value": duplicate_count},
            {"label": "quantity_outlier_count", "value": int(df["is_outlier"].sum())},
            {"label": "peak_month_after_outlier_exclusion", "value": peak_month},
        ],
        "definitions_and_limitations": [
            "Order value is quantity multiplied by unit price after discount.",
            "Retained order value excludes rows marked returned; it is not verified accounting revenue.",
            "Quantity outliers are flagged for review and are not deleted from the cleaned dataset.",
            "Observed associations do not establish causation.",
        ],
    }
    NARRATOR_DIR.mkdir(parents=True, exist_ok=True)
    (NARRATOR_DIR / "findings.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\nSaved verified findings:", NARRATOR_DIR / "findings.json")
    print("Saved monthly revenue:", ANALYSIS_DIR / "monthly_revenue.csv")
    print("Saved return-rate summaries and outlier/correlation outputs in analysis/.")


if __name__ == "__main__":
    main()
