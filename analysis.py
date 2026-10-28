"""Reconcile historical TSA complaint counts before telling the service story."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import numpy as np
import pandas as pd
os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="portfolio-mpl-"))
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parent
BLUE, ORANGE, GRAY = "#176B87", "#C55A11", "#697586"


def setup():
    plt.rcParams.update({"figure.dpi": 120, "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "axes.titlepad": 16})
    (ROOT / "outputs").mkdir(exist_ok=True)


def source_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_and_audit():
    # I am keeping raw inputs outside the publication tree and verifying the frozen snapshot.
    folder = Path(os.environ.get("PROJECT_DATA_DIR", "data"))
    manifest = json.loads((ROOT / "sources.json").read_text())
    frames, inventory = {}, []
    for spec in manifest["files"]:
        path = folder / spec["file"]
        digest = source_hash(path)
        if digest != spec["sha256"]:
            raise ValueError(f"Snapshot mismatch: {path.name}; use the pinned source revision.")
        frame = pd.read_csv(path, dtype={"airport": "string", "iata": "string"}, low_memory=False)
        frames[spec["role"]] = frame
        inventory.append({"file": path.name, "rows": len(frame), "columns": len(frame.columns),
                          "duplicate_rows": int(frame.duplicated().sum()),
                          "missing_cells": int(frame.isna().sum().sum()), "sha256": digest})
    a, c, s, lookup = [frames[x] for x in ["airport", "category", "subcategory", "lookup"]]
    total = int(a["count"].sum())
    for frame in [a, c, s]:
        assert frame["count"].notna().all() and frame["count"].ge(0).all()
        assert frame["count"].mod(1).eq(0).all()
        assert pd.to_datetime(frame["year_month"], format="%Y-%m", errors="coerce").notna().all()
        assert pd.to_datetime(frame["pdf_report_date"], format="%Y-%m", errors="coerce").notna().all()
        assert int(frame["count"].sum()) == total
    # I am reconciling common-grain rollups, not multiplying three granular tables in a join.
    rolls = [f.assign(airport=f["airport"].fillna("[unassigned]"))
             .groupby(["airport", "year_month"])["count"].sum().rename(label)
             for f, label in zip([a, c, s], ["airport", "category", "subcategory"])]
    reconciled = pd.concat(rolls, axis=1)
    assert reconciled.notna().all().all()
    assert reconciled.eq(reconciled["airport"], axis=0).all().all()
    # I am retaining repeated subcategory line items because deduplication breaks reconciliation.
    lost = int(s["count"].sum() - s.drop_duplicates()["count"].sum())
    assert not lookup["iata"].dropna().duplicated().any()
    assert lookup["latitude"].between(-90, 90).all()
    assert lookup["longitude"].between(-180, 180).all()
    joined = a.merge(lookup.rename(columns={"airport": "airport_name"}),
                     left_on="airport", right_on="iata", how="left", validate="many_to_one")
    assert len(joined) == len(a) and int(joined["count"].sum()) == total
    unassigned = int(a.loc[a["airport"].isna(), "count"].sum())
    flagged = int(s.loc[s["clean_subcat_status"].isin(["imputed", "ambiguous"]), "count"].sum())
    months = pd.to_datetime(sorted(a["year_month"].unique()))
    assert len(months) == len(pd.date_range(months.min(), months.max(), freq="MS"))
    facts = {"complaints": total, "airport_months_reconciled": len(reconciled),
             "first_month": str(months.min().date()), "last_month": str(months.max().date()),
             "months": len(months), "unassigned_complaints": unassigned,
             "unassigned_pct": 100 * unassigned / total,
             "imputed_or_ambiguous_subcategory_complaints": flagged,
             "imputed_or_ambiguous_subcategory_pct": 100 * flagged / total,
             "subcategory_duplicate_rows_retained": int(s.duplicated().sum()),
             "complaints_lost_if_deduplicated": lost,
             "unmatched_airport_codes": int(a.loc[a["airport"].notna() & joined["iata"].isna(), "airport"].nunique()),
             "unmatched_airport_complaints": int(joined.loc[joined["airport"].notna() & joined["iata"].isna(), "count"].sum()),
             "inventory": inventory}
    return frames, facts


def save(fig, name):
    fig.savefig(ROOT / "outputs" / f"{name}.png", dpi=160, bbox_inches="tight")
    plt.show()


def timeline(frames, facts):
    a = frames["airport"]
    monthly = a.groupby("year_month")["count"].sum()
    annual = monthly.groupby(monthly.index.str[:4]).sum()
    facts["annual_complaints"] = {str(k): int(v) for k, v in annual.items()}
    facts["lowest_month"] = {"month": monthly.idxmin(), "complaints": int(monthly.min())}
    facts["highest_month"] = {"month": monthly.idxmax(), "complaints": int(monthly.max())}
    fig, ax = plt.subplots(figsize=(11, 4.6))
    dates = pd.to_datetime(monthly.index)
    ax.plot(dates, monthly, color=BLUE, lw=1.5, alpha=.65, label="Monthly total")
    ax.plot(dates, monthly.rolling(12, min_periods=12).mean(), color=ORANGE, lw=2.3, label="Trailing 12-month mean")
    ax.set(title="Recorded complaint volume changes; service quality is not identified",
           ylabel="Recorded complaints per month", xlabel="Complaint month")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}")); ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(mdates.YearLocator(2)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False)
    fig.text(.01, -.02, "January 2015–January 2024 snapshot; January 2024 is not a full year. Source: TSA / Data Liberation Project.", fontsize=9)
    save(fig, "01_monthly_complaints")
    monthly.rename("complaints").to_csv(ROOT / "outputs" / "monthly_complaints.csv")
    return pd.DataFrame({"year": annual.index, "complaints": annual.values,
                         "coverage": ["January only" if x == "2024" else "12 months" for x in annual.index]})


def composition(frames, facts):
    c = frames["category"]
    totals = c.groupby("clean_cat", dropna=False)["count"].sum().sort_values(ascending=False)
    facts["leading_category"] = {"category": str(totals.index[0]), "complaints": int(totals.iloc[0]),
                                 "pct": 100 * float(totals.iloc[0]) / facts["complaints"]}
    annual = c.assign(year=c["year_month"].str[:4]).query("year in ['2019','2023']").groupby(["year", "clean_cat"])["count"].sum().unstack(0, fill_value=0)
    top = totals.head(5).index
    plot = annual.reindex(top).fillna(0).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 5.2)); y = np.arange(len(plot))
    ax.barh(y-.18, plot["2019"], .36, color=GRAY, label="2019")
    ax.barh(y+.18, plot["2023"], .36, color=BLUE, label="2023")
    ax.set_yticks(y, [str(x).replace("Expedited Passenger Screening Program", "Expedited screening program") for x in plot.index])
    ax.set(title="Complaint growth is concentrated, not uniform across categories",
           xlabel="Recorded complaints in each complete calendar year")
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}")); ax.legend(frameon=False)
    fig.text(.01, -.02, "Five largest categories across the full snapshot. Counts, not passenger-adjusted rates.", fontsize=9)
    save(fig, "02_category_composition")
    totals.rename("complaints").to_csv(ROOT / "outputs" / "category_totals.csv")
    return plot


def reliability(frames, facts):
    s = frames["subcategory"]
    quality = s.groupby("clean_subcat_status", dropna=False)["count"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(10, 4.3))
    bars = ax.barh(quality.index.fillna("missing status"), quality, color=[ORANGE if x in ["imputed", "ambiguous"] else BLUE for x in quality.index])
    for bar, value in zip(bars, quality): ax.text(value + facts["complaints"]*.01, bar.get_y()+bar.get_height()/2, f"{value:,} ({value/facts['complaints']:.1%})", va="center")
    ax.set(title="Nearly half of complaint volume has reconstructed or ambiguous detail",
           xlabel="Recorded complaints, weighted by the count field", ylabel="Source label-quality status")
    ax.set_xlim(0, quality.max()*1.38); ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    fig.text(.01, -.02, "Quality flags are supplied by Data Liberation Project; no labels are newly imputed here.", fontsize=9)
    save(fig, "03_subcategory_reliability")
    return quality.rename("complaints").to_frame()


def airport_profiles(frames, facts):
    c = frames["category"].dropna(subset=["airport"])
    selected = c.groupby("airport")["count"].sum().nlargest(8).index
    cats = c.groupby("clean_cat")["count"].sum().nlargest(5).index
    matrix = c.groupby(["airport", "clean_cat"])["count"].sum().unstack(fill_value=0)
    shares = matrix.div(matrix.sum(axis=1), axis=0) * 100
    national = matrix.sum().div(matrix.values.sum()) * 100
    deviation = shares.loc[selected, cats].subtract(national.loc[cats], axis=1)
    fig, ax = plt.subplots(figsize=(11, 5.3)); vmax = max(1, abs(deviation.values).max())
    im = ax.imshow(deviation, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_yticks(range(len(selected)), selected)
    ax.set_xticks(range(len(cats)), [str(x).replace("Expedited Passenger Screening Program", "Expedited\nscreening").replace(" ", "\n", 1) for x in cats], fontsize=9)
    for i in range(len(selected)):
        for j in range(len(cats)): ax.text(j, i, f"{deviation.iloc[i,j]:+.1f}", ha="center", va="center", fontsize=9,
                                          color="white" if abs(deviation.iloc[i,j]) > vmax*.6 else "black")
    ax.set(title="Airport complaint mixes differ from the airport-assigned national mix", ylabel="Eight airports selected by complaint volume")
    fig.colorbar(im, ax=ax, label="Percentage-point difference in complaint share")
    fig.text(.01, -.02, "All snapshot months. Selection is volume-based, not a ranking of airport quality. Unassigned complaints excluded.", fontsize=9)
    save(fig, "04_airport_complaint_profiles")
    deviation.to_csv(ROOT / "outputs" / "airport_share_deviation_pp.csv")
    return deviation.round(1)


def attribution(frames, facts):
    a = frames["airport"]
    totals = a.groupby("year_month")["count"].sum()
    missing = a.loc[a["airport"].isna()].groupby("year_month")["count"].sum().reindex(totals.index, fill_value=0)
    pct = 100 * missing / totals
    years = sorted(set(pct.index.str[:4]) - {"2024"})
    groups = [pct.loc[pct.index.str.startswith(y)].values for y in years]
    facts["annual_median_unassigned_pct"] = {y: float(np.median(g)) for y, g in zip(years, groups)}
    fig, ax = plt.subplots(figsize=(10, 4.8)); ax.boxplot(groups, tick_labels=years, showfliers=True)
    for i, group in enumerate(groups, 1): ax.scatter(np.full(len(group), i), group, color=BLUE, s=12, alpha=.55)
    ax.set(title="Airport attribution improved, but a non-airport reason is still needed",
           ylabel="Monthly complaints without airport attribution (%)", xlabel="Complete calendar years; 12 monthly observations each")
    ax.set_ylim(0, 100)
    fig.text(.01, -.02, "Each point is a month, not a traveler. Missing airport may represent program-wide complaints; it is not automatically erroneous.", fontsize=9)
    save(fig, "05_airport_attribution")
    return pct.rename("unassigned_pct").to_frame()


def download_inputs(destination):
    """Acquire pinned upstream bytes into a folder outside the public package."""
    import base64
    import urllib.request
    folder = Path(destination).expanduser().resolve()
    if folder == ROOT or ROOT in folder.parents:
        raise ValueError("Keep raw inputs outside this public repository.")
    folder.mkdir(parents=True, exist_ok=True)
    for spec in json.loads((ROOT / "sources.json").read_text())["files"]:
        target = folder / spec["file"]
        if target.exists():
            if source_hash(target) != spec["sha256"]: raise ValueError(f"Existing snapshot mismatch: {target.name}")
            continue
        request = urllib.request.Request(spec["url"], headers={"User-Agent":"portfolio-reproducibility"})
        with urllib.request.urlopen(request, timeout=180) as response: payload = response.read()
        if spec.get("encoding") == "github-base64": payload = base64.b64decode(json.loads(payload)["content"])
        assert hashlib.sha256(payload).hexdigest() == spec["sha256"], f"Upstream mismatch: {target.name}"
        target.write_bytes(payload)
        print(f"Verified {target.name}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-data", metavar="EXTERNAL_FOLDER")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.download_data: download_inputs(args.download_data)
    if args.run:
        setup(); frames, facts = load_and_audit()
        for fn in [timeline, composition, reliability, airport_profiles, attribution]: fn(frames, facts)
        (ROOT / "outputs" / "metrics.json").write_text(json.dumps(facts, indent=2)+"\n")
