import requests
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
import os
import logging
from dotenv import load_dotenv

# -----------------------------
# ENV
# -----------------------------
load_dotenv()

API_URL = os.getenv("API_URL")
POST_URL = os.getenv("POST_URL")
PHPSESSID = os.getenv("PHPSESSID")
VERIFY_SSL = os.getenv("VERIFY_SSL", "false").lower() == "true"

# -----------------------------
# LOG
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# -----------------------------
# SESSION
# -----------------------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": API_URL,
    "Content-Type": "application/x-www-form-urlencoded"
})
session.cookies.update({
    "PHPSESSID": PHPSESSID
})

# -----------------------------
# FLEET
# -----------------------------
fleet_groups = {
    "10": "ALLNOW",
    "4": "BTG",
    "7": "DHL",
    "6": "SCCC",
    "9": "TDM",
    "5": "TFG",
    "8": "คูเน่",
    "3": "ตู้ผ้าใบ",
    "2": "โม่เล็ก",
    "1": "โม่ใหญ่"
}

# -----------------------------
# DATE
# -----------------------------
now = datetime.now()
year = now.strftime("%Y")
month = now.strftime("%m")

# -----------------------------
# FETCH
# -----------------------------
def fetch_data():
    all_df = []

    for fleet_id, fleet_name in fleet_groups.items():
        logging.info(f"Downloading {fleet_name}")

        payload = {
            "fleet_group_id": fleet_id,
            "fleet_id": "",
            "year": year,
            "month": month,
            "plant_id": "",
            "vehicle_category": "",
            "submit": "พิมพ์",
            "report_type": "driver.availability"
        }

        r = session.post(API_URL, data=payload, verify=VERIFY_SSL, timeout=60)

        if r.status_code != 200:
            logging.error(f"Failed {fleet_name}")
            continue

        df = pd.read_excel(BytesIO(r.content), skiprows=1)

        df["fleet_group_id"] = fleet_id
        df["fleet_group_name"] = fleet_name
        df["year"] = year
        df["month"] = month

        all_df.append(df)

    return pd.concat(all_df, ignore_index=True)

# -----------------------------
# TRANSFORM
# -----------------------------
def transform(df):

    df["site_id"] = np.where(df["fleet_group_id"].isin(["1","2"]), 2, 3)
    df["truck_type"] = np.where(df["fleet_group_id"].isin(["1","2"]), "Mixer", "Trailer")

    df[["first_name", "last_name"]] = df["ชื่อนามสกุล"].str.split(" ", n=1, expand=True)

    df = df[df["รหัสพนักงาน"].notna()]
    df["month_year"] = df["month"] + "-" + df["year"]

    mapping = {"พจส": 1, "พจร": 2}
    df["สถานะ"] = df["สถานะ"].fillna("").astype(str).str.strip()
    df = df[df["สถานะ"].isin(mapping.keys())]
    df["driver_role_id"] = df["สถานะ"].map(mapping)

    df = df.rename(columns={
        'ลูกค้า': 'client_name',
        'รหัสแพล้นท': 'plant_code',
        'แพล้นท': 'plant_name',
        'เบอร์รถ': 'truck_number',
        'ทะเบียนรถ': 'number_plate',
        'รหัสพนักงาน': 'driver_id'
    })

    df = df[['client_name','plant_code','plant_name','truck_number',
             'number_plate','month_year','first_name','last_name',
             'site_id','driver_role_id','driver_id','truck_type']]

    # clean
    df['driver_id'] = df['driver_id'].astype(str).str.replace('.0', '', regex=False)
    df['driver_role_id'] = df['driver_role_id'].astype(int)
    df['site_id'] = df['site_id'].astype(int)

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.drop_duplicates(subset=['driver_id'])

    return df

# -----------------------------
# LOAD
# -----------------------------
def push(df):

    payload = df.to_dict(orient="records")

    logging.info(f"Pushing {len(payload)} records")

    r = requests.post(POST_URL, json=payload, timeout=60)

    logging.info(f"Status: {r.status_code}")
    logging.info(r.text)

# -----------------------------
# MAIN
# -----------------------------
def main():
    df = fetch_data()
    df = transform(df)
    push(df)

if __name__ == "__main__":
    main()