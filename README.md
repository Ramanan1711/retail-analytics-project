Retail Analytics Project

This repository contains a reproducible ETL pipeline for the Retail Orders dataset. It downloads
the dataset from Kaggle (when configured), performs cleaning and simple feature derivation,
and can optionally load the cleaned data into a Microsoft SQL Server database.

**Repository layout**

- `retail_analysis.py` — main ETL script (download, extract, clean, optional SQL upload).
- `requirements.txt` — Python dependencies.
- `data/` — raw dataset files (`orders.csv`).
- `outputs/` — processed outputs (`processed_orders.csv`).
- `sql/` — helper SQL scripts: `create_database.sql`, `create_table.sql`.

**Quick start**

1. Create and activate a virtual environment, then install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure Kaggle credentials — either:

- Preferred (file): create `~/.kaggle/kaggle.json` with this exact shape:

```json
{"username":"YOUR_KAGGLE_USERNAME","key":"YOUR_KAGGLE_KEY"}
```

```bash
mkdir -p ~/.kaggle
cat > ~/.kaggle/kaggle.json <<'JSON'
{"username":"YOUR_KAGGLE_USERNAME","key":"YOUR_KAGGLE_KEY"}
JSON
chmod 600 ~/.kaggle/kaggle.json
```

- Or (session): export environment variables before running:

```bash
export KAGGLE_USERNAME=YOUR_KAGGLE_USERNAME
export KAGGLE_KEY=YOUR_KAGGLE_KEY
```

3. Run the ETL pipeline (download, extract, clean):

```bash
python retail_analysis.py
```

4. (Optional) Upload cleaned data to SQL Server:

Create the database/table with the SQL files in `sql/` (optional), then set the SQLAlchemy URI and run with `--upload-sql`:

```bash
# Example for a local Docker SQL Server; URL-encode special characters in the password
export SQLALCHEMY_DATABASE_URI='mssql+pyodbc://sa:YourPassword%40localhost:1433/RetailOrders?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes'
python retail_analysis.py --upload-sql
```

Notes:
- URL-encode special characters in passwords (e.g. `@` → `%40`).
- For named instances use an escaped backslash in zsh: `localhost\\INSTANCE`.

**What the script does (step-by-step)**

1. Downloads `orders.csv` using the Kaggle API (if configured). Kaggle may return a ZIP archive named `orders.csv` — the script detects and extracts it.
2. Moves/extracts the file to `data/orders.csv`.
3. Loads the CSV into pandas and normalizes column names to `snake_case`.
4. Derives columns where data exists:
	- `discount` = `list_price` * `discount_percent` * 0.01
	- `sale_price` = `list_price` - `discount`
	- `profit` = `sale_price` - `cost_price`
5. Converts `order_date` to datetime, drops intermediate price columns, and writes `outputs/processed_orders.csv`.
6. If `--upload-sql` is used and `SQLALCHEMY_DATABASE_URI` is set, the script ensures the `df_orders` table exists and appends the rows.

**Outputs**

- `data/orders.csv` — canonical raw copy the pipeline uses.
- `outputs/processed_orders.csv` — cleaned and enriched dataset for analysis or ingestion.

**SQL helper scripts**

- `sql/create_database.sql` — creates `RetailOrders` database.
- `sql/create_table.sql` — creates `dbo.df_orders` table if missing.

**Troubleshooting**

- If download fails: verify `~/.kaggle/kaggle.json` is valid and uses the exact keys `username` and `key` and that its permissions are `600`.
- If the script prints an empty or corrupted download, remove the temporary `orders.csv` in the project root and retry.
- If SQL upload fails: ensure the driver, `pyodbc`, and `ODBC Driver 17/18` are installed and the connection URI is correct.

**Why this is useful**

- Reproducible ETL for the retail orders dataset — ready for analysis, dashboards, or data science experiments.
- Demonstrates common production patterns: secure secret management, robust download/extraction, and SQL ingestion.

**Next steps (suggestions)**

- Add a `notebooks/` exploration notebook that reads `outputs/processed_orders.csv` and provides charts.
- Add a `--dry-run` flag and unit tests for the cleaning logic.
- Add CI to validate linting and tests on each change.

If you want, I can add a notebook, `--dry-run` mode, or CI configuration next — tell me which.
