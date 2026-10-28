# TSA Complaint Data Quality and Service Improvement

How can service leaders act on complaints without confusing reporting gaps with airport performance? This project reconciles three nested datasets and turns data quality into an operational reporting recommendation.

## Verified findings

- **1,021,281 recorded complaints**, January 2015–January 2024; 109 continuous months. January 2024 is partial, not a full comparison year.
- All **41,721 airport-month totals** reconcile exactly across airport, category, and subcategory files.
- **437,786 complaints (42.9%)** have no airport attribution. Missing airport can legitimately mean a program-wide issue.
- **484,349 complaints (47.4%)** have imputed or ambiguous upstream subcategory labels.
- The Expedited Passenger Screening Program represents **569,943 complaints (55.8%)**; growth is not uniform across categories.
- Removing 1,405 repeated-looking subcategory rows would lose 978 complaints. They are retained because they reconcile with the higher-grain evidence.

These are submitted complaint counts, **not rates, safety scores, satisfaction measures, or causal effects**. Passenger/screening denominators are unavailable. Airport complaint mixes can suggest local review questions, not fair rankings of airport quality.

## Inspect the work

- [Executed visual-story notebook](tsa_complaint_quality.ipynb): raw audit, five explanatory figures, interpretations, limits, and call to action.
- [Analysis implementation](analysis.py): strict source hashes, nonnegative integer checks, date coverage, common-grain reconciliation, validated many-to-one lookup merge, count-weighted reliability, and chart generation.
- [Validation record](validation.json): fresh-kernel execution, source and code hashes, actual metrics. Seven code cells executed; zero saved errors.
- Five figures and aggregate summaries are embedded in the executed notebook. A rerun also generates local `outputs/` files; that folder is not part of the root-only public release. No raw datasets are included.

## Data and provenance

The [Data Liberation Project](https://github.com/data-liberation-project/tsa-complaint-counts) extracted and standardized TSA's historical PDF complaint reports. This release deliberately reproduces the original January 2024-ending snapshot, not newer upstream data. All three complaint CSVs byte-match revision [`e9f8b5e89b4774eb97b93165ee96b4bc986d4319`](https://github.com/data-liberation-project/tsa-complaint-counts/tree/e9f8b5e89b4774eb97b93165ee96b4bc986d4319/output/03-standardized).

The airport lookup is the [IP2Location IATA/ICAO list](https://github.com/ip2location/ip2location-iata-icao), pinned by its Git blob and SHA-256 hash in [sources.json](sources.json). This project includes IATA/ICAO List data available from that repository in its internal audit only; no lookup rows or coordinates are redistributed. The lookup is community-maintained, not ground truth. Five complaint airport codes (289 complaints) do not match. Geographic risk is not inferred from these matches.

Source documentation and licenses checked **October 28, 2026**. Both standardized data sources are CC BY-SA 4.0. Attribution and share-alike conditions apply to derived complaint aggregates and figures; see [LICENSE](LICENSE). Raw files are acquired from the source rather than republished.

## Reproduce from raw inputs

Use Python 3.12 (verified on 3.12.14) and an external data folder. The largest input is about 77 MB; this is a pandas-scale aggregate workflow, not individual complaint text.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analysis.py --download-data /absolute/path/outside-this-repo/tsa-data
export PROJECT_DATA_DIR=/absolute/path/outside-this-repo/tsa-data
MPLBACKEND=Agg python analysis.py --run
```

The downloader resolves the pinned source revision, decodes the pinned lookup Git blob, checks every SHA-256, refuses mismatching existing inputs, and will not place raw data inside this repository. Existing raw sources are never modified. No API credentials are required. Network access is needed only for acquisition.

For the notebook, select the environment above in Jupyter and **Restart Kernel and Run All** from the repository directory. Alternatively, install its kernel with `python -m ipykernel install --sys-prefix --name python3`, then run `jupyter execute tsa_complaint_quality.ipynb --inplace --kernel_name=python3`. The saved release was executed from a fresh kernel, reading all four original raw files and checking their hashes again afterward. The downloader was also independently tested against every pinned upstream URL; all four downloaded files matched the frozen hashes. See validation.json for actual results.

## Methods, interpretation, and action

Airport-month, airport-month-category, and airport-month-category-subcategory rows describe the **same** complaint totals. They are aggregated to a common grain before reconciliation, never joined many-to-many. Missing airport codes and zero counts remain in national totals; supplied cleaning flags remain visible. Complete-year comparisons exclude partial 2024. Monthly reliability shares weight the count field, not rows. Airport profiles are percentage-point differences from the assigned-airport national mix and explicitly disclose volume-based selection.

The actionable recommendation is to collect a validated airport **or an explicit non-airport reason**, retain source classification reliability, and add passenger/screening denominators before performance comparisons. Reporting channels, travel activity, and category definitions affect comparisons over time. This package is a Python visual report; it makes no claim of a validated Tableau workbook or live operational deployment.

## Scope of this release

Neutral professional names replace course-specific presentation. Original course materials are preserved elsewhere. The workflow fixes portability, pins historical data instead of silently changing the snapshot, reproduces the complete raw-data audit, and removes the old live map-boundary dependency: no external geographic boundary cache is required. The five final figures were visually checked for complete labels, truthful scales, and visible caveats.
