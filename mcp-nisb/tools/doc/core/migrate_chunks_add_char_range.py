#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3

BASE = "/opt/nisb-data/users"

def alter(db_path: str):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    # chunks 表加列（若已存在会报错，捕获即可）
    for sql in [
        "ALTER TABLE chunks ADD COLUMN char_start INTEGER",
        "ALTER TABLE chunks ADD COLUMN char_end INTEGER",
    ]:
        try:
            cur.execute(sql)
        except Exception:
            pass

    con.commit()
    con.close()

def main():
    for root, dirs, files in os.walk(BASE):
        if "doc_db.sqlite" in files:
            db = os.path.join(root, "doc_db.sqlite")
            print("[migrate]", db)
            alter(db)

if __name__ == "__main__":
    main()

