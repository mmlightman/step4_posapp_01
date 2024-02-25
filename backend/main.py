from fastapi import FastAPI, HTTPException, Body, Depends
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
from dotenv import load_dotenv
from typing import List

app = FastAPI()


# すべてのオリジンを許可する場合
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのメソッドを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

# .envファイルを読み込む
load_dotenv()

# 環境変数からデータベースファイルのパスを取得
DATABASE_FILE_PATH = os.getenv("DATABASE_FILE_PATH", default="sample02.db")

class ProductQuery(BaseModel):
    code: str


class Item(BaseModel):
    PRD_ID: int
    PRD_CODE: str
    PRD_NAME: str
    PRD_PRICE: int


class Purchase(BaseModel):
    EMP_CD: str = "9999999999"
    STORE_CD: str
    POS_NO: str
    items: List[Item]


def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/search_product/")
def search_product(
    product_query: ProductQuery = Body(...),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    code = product_query.code
    cursor = connection.cursor()
    sql = "SELECT PRD_ID, PRD_CODE, PRD_NAME, PRD_PRICE FROM m_product WHERE PRD_CODE = ?"
    cursor.execute(sql, (code,))
    result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "status": "success",
        "message": {
            "PRD_ID": result["PRD_ID"],
            "PRD_CODE": result["PRD_CODE"],
            "PRD_NAME": result["PRD_NAME"],
            "PRD_PRICE": result["PRD_PRICE"],
        },
    }


@app.post("/purchase/")
def purchase(
    data: Purchase,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    try:
        cursor = connection.cursor()
        sql_txn = """
        INSERT INTO t_txn (DATETIME, EMP_CD, STORE_CD, POS_NO, TOTAL_AMT, TTL_AMT_EX_TAX)
        VALUES (datetime('now'), ?, ?, ?, ?, ?);
        """
        total_amt = sum(item.PRD_PRICE for item in data.items)  # 合計金額
        ttl_amt_ex_tax = total_amt  # 税抜合計金額（仮に税込と同額として計算）
        cursor.execute(
            sql_txn,
            (data.EMP_CD, data.STORE_CD, data.POS_NO, total_amt, ttl_amt_ex_tax),
        )
        txn_id = cursor.lastrowid

        for index, item in enumerate(data.items, start=1):
            sql_dtl = """
            INSERT INTO t_txn_dtl (TXN_ID, TXN_DTL_ID, PRD_ID, PRD_CODE, PRD_NAME, PRD_PRICE, TAX_ID)
            VALUES (?, ?, ?, ?, ?, ?, '10');
            """
            cursor.execute(
                sql_dtl,
                (
                    txn_id,
                    index,
                    item.PRD_ID,
                    item.PRD_CODE,
                    item.PRD_NAME,
                    item.PRD_PRICE,
                ),
            )

        connection.commit()
        cursor.close()
        return {
            "status": "success",
            "message": {"合計金額": total_amt, "合計金額（税抜）": ttl_amt_ex_tax},
        }
    except Exception as e:
        connection.rollback()
        return {"status": "failed", "detail": f"An error occurred: {str(e)}"}
    finally:
        connection.close()
