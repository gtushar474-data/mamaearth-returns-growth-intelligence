"""Generate the two charts required by the Mamaearth capstone."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
OUTPUT_DIR = ROOT / "visualizations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

payment_path = ANALYSIS_DIR / "return_rate_by_payment.csv"
monthly_path = ANALYSIS_DIR / "monthly_revenue.csv"
if not payment_path.exists() or not monthly_path.exists():
    raise FileNotFoundError("Run 'python analysis/clean_and_eda.py' before generating charts.")

payment = pd.read_csv(payment_path).sort_values("return_rate_pct", ascending=False)
plt.figure(figsize=(9, 5))
plt.bar(payment["payment_method"].fillna("Unknown").astype(str), payment["return_rate_pct"])
plt.title("Mamaearth Return Rate by Payment Method")
plt.xlabel("Payment Method")
plt.ylabel("Return Rate (%)")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "return_rate_by_payment.png", dpi=300, bbox_inches="tight")
plt.close()

monthly = pd.read_csv(monthly_path).sort_values("order_month")
plt.figure(figsize=(11, 5))
plt.plot(monthly["order_month"], monthly["revenue_with_outliers"], marker="o", label="With flagged outliers")
plt.plot(monthly["order_month"], monthly["revenue_without_outliers"], marker="o", label="Excluding flagged outliers")
plt.title("Mamaearth Monthly Order Value: With vs Without Quantity Outliers")
plt.xlabel("Order Month")
plt.ylabel("Order Value (₹)")
plt.xticks(rotation=45, ha="right")
plt.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "monthly_revenue.png", dpi=300, bbox_inches="tight")
plt.close()
print("Saved:", OUTPUT_DIR / "return_rate_by_payment.png")
print("Saved:", OUTPUT_DIR / "monthly_revenue.png")
