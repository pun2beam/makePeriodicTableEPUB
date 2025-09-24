# Periodic Table EPUB Generator

This project automates the creation of a Kindle-friendly periodic table EPUB by following the steps outlined in `spec.md`.

## Requirements

* Python 3.12+
* Dependencies listed in `requirements.txt`

Install them with:

```bash
pip install -r requirements.txt
```

## Generation Pipeline

1. Fetch Wikipedia data (defaults to the English "List of chemical elements" page):
   ```bash
   python scripts/fetch_wiki.py --lang en --page "List of chemical elements" --output-file list-of-chemical-elements-en-rest.json
   ```
   Add `--log-level DEBUG` to see detailed progress information or `--log-file logs/wiki-fetch.log`
   to also persist the log to disk.
2. Normalize the downloaded table into `data/tables.json`:
   ```bash
   python scripts/normalize.py
   ```
3. Fetch per-element summaries using the normalized table and write them to a language-specific file:
   ```bash
   python scripts/fetch_wiki.py --lang en --page "List of chemical elements" --elements-from data/tables.json --elements-json data/elements.en.json
   ```
   This step downloads REST summaries for every element listed in `data/tables.json` and aggregates them into
   `data/elements.en.json` (raw responses are saved under `data/raw/elements/`).
4. Build the cover SVG and rasterize it:
   ```bash
   python scripts/build_cover_svg.py
   python scripts/rasterize_cover.py --width 1600 --height 2560 --out book/dist/cover_2560x1600.jpg
   ```
5. Generate TASL attribution (required before assembling the EPUB):
   ```bash
   python scripts/license_attribution.py
   ```
6. Assemble the EPUB package (pass the per-element summaries so the detailed pages are included):
   ```bash
   python scripts/build_epub.py --element-data data/elements.en.json
   ```

The final files are written to `book/dist/`:

* `cover_2560x1600.jpg`
* `PeriodicTable.en.epub`

Raw responses, normalized data, and intermediate assets are stored in the `data/` and `assets/` directories.
