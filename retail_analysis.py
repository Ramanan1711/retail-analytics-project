import os
import zipfile
import logging
import argparse
import tempfile

import pandas as pd

try:
    import kaggle
except Exception:
    kaggle = None

try:
    import sqlalchemy as sal
except Exception:
    sal = None


logging.basicConfig(level=logging.INFO, format='%(message)s')
ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT, 'data')
OUTPUTS_DIR = os.path.join(ROOT, 'outputs')


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)


def ensure_kaggle_configuration():
    if os.environ.get('KAGGLE_USERNAME') and os.environ.get('KAGGLE_KEY'):
        return

    config_path = os.path.expanduser('~/.kaggle/kaggle.json')
    if os.path.exists(config_path):
        return

    logging.warning(
        'Kaggle credentials not found. Create ~/.kaggle/kaggle.json ' \
        'with {"username":"YOUR_KAGGLE_USERNAME","key":"YOUR_KAGGLE_KEY"} ' \
        'or set KAGGLE_USERNAME and KAGGLE_KEY.'
    )


def download_dataset():
    if kaggle is None:
        logging.warning('kaggle package not installed; skipping download')
        return None

    ensure_kaggle_configuration()

    data_file = os.path.join(DATA_DIR, 'orders.csv')
    if os.path.exists(data_file) and os.path.getsize(data_file) > 0:
        logging.info('data/orders.csv already exists — skipping download')
        return data_file

    if os.path.exists(data_file) and os.path.getsize(data_file) == 0:
        logging.warning('Found empty data/orders.csv, removing and retrying download')
        os.remove(data_file)

    logging.info('Downloading dataset via Kaggle API...')
    try:
        kaggle.api.dataset_download_file(
            'ankitbansal06/retail-orders',
            file_name='orders.csv',
            path=ROOT
        )
    except Exception as exc:
        logging.error('Failed to download from Kaggle: %s', exc)
        return None

    root_csv = os.path.join(ROOT, 'orders.csv')
    root_zip = os.path.join(ROOT, 'orders.csv.zip')

    if os.path.exists(root_csv):
        if os.path.getsize(root_csv) == 0:
            logging.error('Downloaded orders.csv is empty; check Kaggle credentials and network')
            os.remove(root_csv)
            return None

        if zipfile.is_zipfile(root_csv):
            logging.info('Downloaded file is a ZIP archive at %s', root_csv)
            return root_csv

        logging.info('Found direct CSV download at %s', root_csv)
        dest = os.path.join(DATA_DIR, 'orders.csv')
        os.replace(root_csv, dest)
        logging.info('Moved %s to %s', root_csv, dest)
        return dest

    if os.path.exists(root_zip):
        if os.path.getsize(root_zip) == 0:
            logging.error('Downloaded orders.csv.zip is empty; check Kaggle credentials and network')
            os.remove(root_zip)
            return None

        logging.info('Downloaded %s', root_zip)
        return root_zip

    logging.error('Download completed but no orders.csv or orders.csv.zip found in %s', ROOT)
    return None


def extract_zip(zip_path: str):
    if not zip_path:
        logging.info('No zip to extract: %s', zip_path)
        return None

    if not os.path.exists(zip_path):
        logging.info('No zip to extract: %s', zip_path)
        return None

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        members = zip_ref.namelist()
        conflict = any(
            os.path.basename(member) == os.path.basename(zip_path)
            for member in members
        )

        if conflict:
            logging.info('Extracting archive to temporary directory to avoid overwrite')
            with tempfile.TemporaryDirectory() as tmp_dir:
                zip_ref.extractall(tmp_dir)
                extracted_paths = [os.path.join(tmp_dir, member) for member in members]
                if len(extracted_paths) == 1:
                    target = os.path.join(DATA_DIR, os.path.basename(members[0]))
                    os.replace(extracted_paths[0], target)
                    logging.info('Moved extracted file to %s', target)
                    return target
                logging.info('Extracted files: %s', extracted_paths)
                return extracted_paths[0] if extracted_paths else None
        else:
            zip_ref.extractall(DATA_DIR)
            logging.info('Extracted to %s', DATA_DIR)
            return os.path.join(DATA_DIR, members[0]) if members else None


def load_and_clean(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, na_values=['Not Available', 'unknown'])

    logging.info('Initial preview:')
    logging.info('\n%s', df.head().to_string())

    logging.info('Shape: %s', df.shape)
    logging.info('Columns: %s', list(df.columns))

    df.columns = df.columns.str.lower().str.replace(' ', '_')

    # Create discount, sale_price, profit if possible
    if {'list_price', 'discount_percent'}.issubset(df.columns):
        df['discount'] = df['list_price'] * df['discount_percent'] * 0.01
        df['sale_price'] = df['list_price'] - df['discount']
    else:
        logging.info('list_price or discount_percent missing; skipping discount/sale_price calc')

    if {'sale_price', 'cost_price'}.issubset(df.columns):
        df['profit'] = df['sale_price'] - df['cost_price']
    else:
        logging.info('sale_price or cost_price missing; skipping profit calc')

    if 'order_date' in df.columns:
        df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')

    drop_cols = [c for c in ['list_price', 'cost_price', 'discount_percent'] if c in df.columns]
    if drop_cols:
        df.drop(columns=drop_cols, inplace=True)

    processed_path = os.path.join(OUTPUTS_DIR, 'processed_orders.csv')
    df.to_csv(processed_path, index=False)
    logging.info('Saved processed data to %s', processed_path)

    logging.info('Missing values per column:\n%s', df.isnull().sum().to_string())
    return df


def ensure_sql_table(conn):
    create_table_sql = """
IF NOT EXISTS (
    SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.df_orders') AND type in (N'U')
)
BEGIN
    CREATE TABLE dbo.df_orders
    (
        order_id INT PRIMARY KEY,
        order_date DATE,
        ship_mode VARCHAR(30),
        segment VARCHAR(30),
        country VARCHAR(50),
        city VARCHAR(50),
        state VARCHAR(50),
        postal_code VARCHAR(20),
        region VARCHAR(20),
        category VARCHAR(30),
        sub_category VARCHAR(30),
        product_id VARCHAR(50),
        quantity INT,
        discount FLOAT,
        sale_price FLOAT,
        profit FLOAT
    );
END;
"""
    conn.execute(sal.text(create_table_sql))


def upload_to_sql(df: pd.DataFrame, uri: str):
    if sal is None:
        logging.warning('sqlalchemy not installed; cannot upload to SQL')
        return

    logging.info('Uploading %d rows to SQL using %s', len(df), uri)
    engine = sal.create_engine(uri)
    with engine.begin() as conn:
        ensure_sql_table(conn)
        df.to_sql('df_orders', con=conn, if_exists='append', index=False)

    logging.info('SQL upload complete: %d rows appended to df_orders', len(df))


def main(upload_sql: bool = False):
    ensure_dirs()
    downloaded_path = download_dataset()

    if downloaded_path and zipfile.is_zipfile(downloaded_path):
        csv_path = extract_zip(downloaded_path)
    else:
        csv_path = downloaded_path or os.path.join(DATA_DIR, 'orders.csv')

    if not csv_path or not os.path.exists(csv_path):
        logging.error('orders.csv not found — please download manually or place it in data/')
        return

    df = load_and_clean(csv_path)

    if upload_sql:
        uri = os.environ.get('SQLALCHEMY_DATABASE_URI')
        if not uri:
            logging.error('SQLALCHEMY_DATABASE_URI not set; cannot upload')
            return
        upload_to_sql(df, uri)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--upload-sql', action='store_true', help='Upload processed data to SQL')
    args = parser.parse_args()

    main(upload_sql=args.upload_sql)
