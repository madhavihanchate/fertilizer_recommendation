# Fertilizer Recommendation System

A rule-based Django web application that provides crop-specific fertilizer recommendations based on soil test reports. Uses three data files (RDF Rule Book, Crop Dataset, and Default Fertilizer Dataset) to derive all recommendations mathematically — no ML models.

## Features

- **Soil test report analysis** — 14 soil parameters analyzed against Rule Book thresholds
- **RDF adjustment** — 125%/100%/75% of standard N:P:K ratio based on soil status
- **Fertilizer conversion** — Adjusted NPK converted to Urea, DAP, and MOP quantities
- **Yield comparison** — Chart.js bar chart comparing normal farmer practice vs recommended fertilizer
- **Default recommendations** — For users without a soil test report, shows crop-wise default fertilizer values
- **State & crop filtering** — Dropdown filters crops by selected state

## Data Files

| File | Source | Purpose |
|------|--------|---------|
| `RDF_Rule_Book.docx` | File 1 | Soil parameter thresholds, management practices, recommended doses |
| `India_State_Wise_Crops_with_Soil_Parameters.xlsx` | File 2 | Crop-wise RDF ratios (N:P:K) per state |
| `India_Fertilizer_Recommendation_Threshold_Based.xlsx` | File 3 | Default Urea/DAP/MOP values per crop per state |

## Tech Stack

- **Backend:** Django (Python)
- **Frontend:** HTML + CSS + Chart.js
- **Data Parsing:** openpyxl, python-docx

## Setup

```bash
pip install django openpyxl python-docx
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

## Usage

1. Select **Yes** or **No** for soil test report
2. Choose **State** and **Crop**
3. **Yes**: enter 14 soil parameters → view analysis table, RDF adjustment, fertilizer cards, comparison charts
4. **No**: view default Urea/DAP/MOP recommendations with disclaimer

---

## Project Structure & File Explanations

### `fertilizer_recommender/` (Project Root)

#### `settings.py`
Standard Django project config. The only app registered is `recommender` (line 40). `BASE_DIR` is used by `data_loader.py` to locate the `data/` folder. No database tables needed — no models.

#### `urls.py`
Root URL config. Routes `/admin/` to Django admin and everything else (`''`) to `recommender.urls`.

---

### `recommender/` (Main App)

#### `engine.py` — Math Engine (Core Logic)
Contains all business logic. No Django dependency — pure Python.

- **`PARAM_CONFIG`** — List of 14 `(param_key, config_dict)` tuples defining soil parameters: pH, EC, Organic Carbon, N, P, K, Ca, Mg, S, Fe, Mn, Cu, Zn, B. Each has label, unit, and status bands with lambda functions that evaluate which band a value falls into.

- **`get_soil_status(key, value)`** — Iterates the bands for a given param and returns `(short_status, full_status, label)`. E.g., N=200 → `("Low", "Low (<280)", "Nitrogen (kg/ha)")`.

- **`get_npk_adjustment_factor(status)`** — Maps status to multiplier:
  - Low / Deficient → 1.25 (125% of RDF)
  - Medium / Marginal → 1.0 (100% of RDF)
  - High / Sufficient → 0.75 (75% of RDF)

- **`parse_rdf_ratio(ratio_str)`** — Splits a string like `"150:50:50"` into `(150.0, 50.0, 50.0)` for N, P, K.

- **`adjust_npk(n_rdf, p_rdf, k_rdf, n_status, p_status, k_status)`** — Multiplies each RDF component by its adjustment factor.

- **`convert_to_fertilizer(n_kg, p_kg, k_kg)`** — Converts adjusted NPK to fertilizer:
  - Urea = N / 0.46 (urea is 46% N)
  - DAP = (P × 2.29) / 0.46 (DAP is 46% P₂O₅, P needs conversion to P₂O₅)
  - MOP = (K × 1.20) / 0.60 (MOP is 60% K₂O, K needs conversion to K₂O)

- **`estimate_yield(n_adj, n_rdf, p_adj, p_rdf, k_adj, k_rdf)`** — Simple rule-based yield model: takes average of N/P/K compliance ratios (adjusted / RDF), multiplies by a base yield (3500 kg/ha). Normal practice is fixed at 75% of base.

- **`match_rule_for_param(param_key, status, rules)`** — Looks up management practice and dose from the rule book for a given param+status combination. Uses substring matching so "Low" matches "Low (<280)".

---

#### `data_loader.py` — File Reader
Reads all three data files dynamically at startup.

- **`load_rules()`** — Opens `RDF_Rule_Book.docx` using `python-docx`. Iterates 14 tables (one per param), reads each row as `{status, practice, dose}`.

- **`load_crop_dataset()`** — Opens `India_State_Wise_Crops_with_Soil_Parameters.xlsx`. Iterates state-named sheets from row 6 onward. Each record stores crop name, soil thresholds, and RDF ratio (N:P:K string).

- **`load_fertilizer_dataset()`** — Opens `India_Fertilizer_Recommendation_Threshold_Based.xlsx`. Iterates state sheets from row 8 onward. Reads actual Urea/DAP/MOP from file columns (col 9=DAP, col 11=Urea, col 12=MOP). Falls back to deriving from NPK ratio when actual value is 0:
  - Urea = N / 0.46
  - DAP = P₂O₅ / 0.46
  - MOP = K₂O / 0.60

- **`_parse_npk(ratio_str)`** — Helper to parse "100:40:150" → `(100, 40, 150)`.

- **`_float(v)`** — Safe float converter, returns 0.0 on failure.

---

#### `views.py` — Request Handlers
Contains 3 views and helper functions. Data files are loaded once at module level (not per-request).

- **`get_states()`** — Merges states from both crop_data and fert_data, returns sorted.
- **`get_crops_for_state(state)`** — Merges crop names from both datasets for a given state, deduplicating.
- **`_find_record(records, name)`** — Smart crop name matching: tries exact match → base name (strip parenthetical qualifier) → substantive substring (≥5 chars). Prevents false matches like "Orchid" matching "Palm Orchids".
- **`build_param_results_from_values(values_dict)`** — For each of the 14 params, evaluates soil value against rules, returns list of `{key, label, value, status, practice, dose}`.

**Views:**

- `home()` — Renders landing page with state dropdown, crop datalist (filtered by JS), and state_crops JSON blob.
- `soil_test_choice()` — **"No" branch**: looks up fert_data for default Urea/DAP/MOP → renders results without param table/charts. **"Yes" branch**: renders 14-field form.
- `results()` — **"Yes" branch**: collects 14 POST values → builds param results → looks up crop RDF → parses ratio → gets soil status → adjusts NPK → converts to fertilizer → estimates yield → looks up default fert for chart comparison → renders full output. **"No" branch**: looks up fert_data → renders only Urea/DAP/MOP + disclaimer.

---

#### `urls.py`
Three routes:
- `""` → `home`
- `"soil-test-choice/"` → `soil_test_choice`
- `"results/"` → `results`

---

### `templates/recommender/` — HTML Templates

#### `base.html`
Minimal skeleton. Loads Chart.js from CDN. Inline CSS (~40 lines) with cards, pills, fertilizer grid, notes, forms. No Bootstrap or Tailwind.

#### `home.html`
Radio buttons (Yes/No), state `<select>`, crop `<input>` with `<datalist>`. JavaScript filters crop list on state change using the JSON blob from context.

#### `soil_params.html`
14-field form in a 2-column grid. Fields are generated by iterating PARAM_CONFIG. Hidden fields carry state, crop, has_report.

#### `results.html`
Conditional rendering:
- If `param_results` exists → soil analysis table (with colored pills for Low/Medium/High) and RDF adjustment table.
- If `fert_chart_labels` exists → Chart.js grouped bar chart comparing current (default file) vs required (soil-based) for Urea/DAP/MOP.
- If `normal_yield` exists → Chart.js bar chart comparing normal practice vs recommended yield.
- For **"No"** case → only fertilizer cards + disclaimer note (no tables, no charts).

---

### `manage.py`
Standard Django CLI entry point. `python manage.py runserver` starts the dev server.

## Architecture Summary

Module-level loaded data (singleton), stateless views, pure math engine. No database, no ML — just rules from the Rule Book applied through `engine.py`. The three data files are the source of truth for thresholds, RDF ratios, and default fertilizer values respectively.
