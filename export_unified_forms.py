"""일회용: Supabase 테이블 전체를 엑셀로 추출"""
import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY = os.getenv("SUPABASE_KEY", "")

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
}


def export_table(table_name: str) -> None:
    rows = []
    limit = 1000
    offset = 0

    print(f"\n[{table_name}] 데이터 수집 중...")
    while True:
        resp = requests.get(
            f"{URL}/rest/v1/{table_name}",
            headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + limit - 1}"},
            params={"select": "*"},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        print(f"  {offset + len(batch)}건 수집됨")
        if len(batch) < limit:
            break
        offset += limit

    print(f"총 {len(rows)}건 수집 완료")
    out_path = f"{table_name}_export.xlsx"
    pd.DataFrame(rows).to_excel(out_path, index=False, engine="openpyxl")
    print(f"저장 완료: {out_path}")


for table in ["legal_forms", "gov_contracts"]:
    export_table(table)
