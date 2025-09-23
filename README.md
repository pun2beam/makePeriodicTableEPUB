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
   python scripts/fetch_wiki.py --lang en --page "List of chemical elements"
   ```
   Add `--log-level DEBUG` to see detailed progress information or `--log-file logs/wiki-fetch.log`
   to also persist the log to disk.
2. Normalize the downloaded table into `data/tables.json`:
   ```bash
   python scripts/normalize.py
   ```
3. Build the cover SVG and rasterize it:
   ```bash
   python scripts/build_cover_svg.py
   python scripts/rasterize_cover.py --width 1600 --height 2560 --out book/dist/cover_2560x1600.jpg
   ```
4. Generate TASL attribution (required before assembling the EPUB):
   ```bash
   python scripts/license_attribution.py
   ```
5. Assemble the EPUB package:
   ```bash
   python scripts/build_epub.py
   ```

The final files are written to `book/dist/`:

* `cover_2560x1600.jpg`
* `PeriodicTable.en.epub`

Raw responses, normalized data, and intermediate assets are stored in the `data/` and `assets/` directories.
