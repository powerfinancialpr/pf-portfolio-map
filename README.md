# pf-portfolio-map

Standalone Python script that builds an interactive Folium map of solar installations across Puerto Rico. Run it, point it at a portfolio CSV and a PR municipality shapefile, and it produces `map.html` with four toggleable layers:

- **Municipality Border Mode** — choropleth of PR municipios colored by average credit score, with popups showing average cost, average system size, average credit score, and installation count. Uses a spatial join on lat/lon (not the raw `installation_city` text) to correctly assign each install to its municipio regardless of typos or accent variants.
- **Coordinate Cluster Mode** — clustered markers at each installation's coordinates (`FastMarkerCluster`).
- **Bubble Mode** — one bubble per ZIP code, sized by average system size in that ZIP. Malformed ZIPs (e.g. `"00062-3"`, `"0063"`) are cleaned to 5 digits before grouping.
- **Installation Timelapse Mode** — `TimestampedGeoJson` animation of installations over time.

## Requirements

- **Python 3.12+** (tested on 3.14.6).
- **Tk** bindings for Python — needed for the file-picker dialogs. On macOS with Homebrew Python this is a separate package: `brew install python-tk@<version>` (e.g. `python-tk@3.14`).
- Python packages listed in `requirement.txt`: `folium`, `geopandas`, `pandas`, `jinja2`, `branca`.
- **Portfolio CSV** with these columns:
  - `latitude`, `longitude` (numeric)
  - `installation_date` (parseable by `pandas.to_datetime`)
  - `amount`, `system_size`, `credit_score` (numeric)
  - `installation_zip_code`, `installation_city`
- **PR municipality shapefile** — a US Census TIGER/Line county shapefile works (the script filters `STATEFP == '72'`, which is Puerto Rico). The `.shp` must be alongside its sidecar files (`.shx`, `.dbf`, `.prj`, `.cpg`). [Download](https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip) the full ZIP from the Census TIGER/Line site — not just the loose `.shp` — and extract it before use.

## Setup

```bash
cd pf-portfolio-map
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirement.txt
```

On macOS, if `import tkinter` fails, install Tk for your Homebrew Python:

```bash
brew install python-tk@3.14   # match your Python minor version
```

## Running

```bash
source .venv/bin/activate
python Portfolio_MAP.py
```

Two file dialogs will appear in order:

1. **Select Installation File** — pick the portfolio CSV.
2. **Select Puerto Rico Municipality File** — pick the `.shp`.

The script writes `map.html` to the current working directory and opens it in your default browser.

## Output

- `map.html` — self-contained interactive map. Gitignored.
- Console output includes any installations whose coordinates fell outside every municipio polygon (likely bad lat/lon) and any municipios with no installations.
