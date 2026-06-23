"""
============================================================
 SQLite 数据库 v3.0（三层BN 11字段）
============================================================
"""
import sqlite3, json, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluations.db")

def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            facility_name TEXT NOT NULL DEFAULT '',
            facility_type TEXT NOT NULL,
            material TEXT, install_age TEXT, water_log TEXT, sun_shade TEXT,
            use_freq TEXT, user_group TEXT, use_intensity TEXT,
            inspect_freq TEXT, repair_time TEXT,
            dependency TEXT, outage_impact TEXT,
            exposure TEXT, usage TEXT, maintenance TEXT, social_impact TEXT,
            user_groups TEXT NOT NULL,
            risk_level TEXT NOT NULL, risk_score REAL NOT NULL,
            prob_low REAL, prob_med REAL, prob_high REAL,
            social_weight REAL, weight_tier TEXT,
            priority_score REAL, priority_level TEXT,
            llm_interpretation TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON evaluations(created_at DESC)")
    # 迁移：v3.0→v3.1，accessibility → outage_impact
    cols = [row[1] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()]
    if "accessibility" in cols and "outage_impact" not in cols:
        conn.execute("ALTER TABLE evaluations RENAME COLUMN accessibility TO outage_impact")
    conn.commit(); conn.close()

def save_evaluation(data):
    conn = get_db()
    string_fields = ["facility_name","facility_type",
        "material","install_age","water_log","sun_shade",
        "use_freq","user_group","use_intensity",
        "inspect_freq","repair_time","dependency","outage_impact",
        "exposure","usage","maintenance","social_impact",
        "risk_level","weight_tier","priority_level"]
    float_fields = ["risk_score","prob_low","prob_med","prob_high","social_weight","priority_score"]
    all_fields = string_fields + ["user_groups"] + float_fields
    values = [data.get(f,"") for f in string_fields]
    values.append(json.dumps(data.get("user_groups",[]), ensure_ascii=False))
    values.extend([data.get(f,0) for f in float_fields])
    placeholders = ",".join(["?"]*len(all_fields))
    conn.execute(f"INSERT INTO evaluations ({','.join(all_fields)}) VALUES ({placeholders})", values)
    cur = conn.execute("SELECT last_insert_rowid()"); rid = cur.fetchone()[0]
    conn.commit(); conn.close(); return rid

def get_all_evaluations(page=1, per_page=20, risk_filter=None, priority_filter=None):
    conn = get_db()
    where=[]; params=[]
    if risk_filter: where.append("risk_level=?"); params.append(risk_filter)
    if priority_filter: where.append("priority_level=?"); params.append(priority_filter)
    wc = ("WHERE "+" AND ".join(where)) if where else ""
    count = conn.execute(f"SELECT COUNT(*) FROM evaluations {wc}",params).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM evaluations {wc} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        params+[per_page,(page-1)*per_page]).fetchall()
    results = [dict(r) for r in rows]
    for d in results: d["user_groups"] = json.loads(d.get("user_groups","[]"))
    conn.close()
    return {"records":results,"total":count,"page":page,"per_page":per_page}

def get_evaluation(rid):
    conn = get_db()
    row = conn.execute("SELECT * FROM evaluations WHERE id=?",(rid,)).fetchone()
    conn.close()
    if row: d=dict(row); d["user_groups"]=json.loads(d.get("user_groups","[]")); return d
    return None

def delete_evaluation(rid):
    conn=get_db(); conn.execute("DELETE FROM evaluations WHERE id=?",(rid,)); conn.commit(); conn.close()

def clear_all():
    conn=get_db(); conn.execute("DELETE FROM evaluations"); conn.commit(); conn.close()

def update_interpretation(rid,text):
    conn=get_db(); conn.execute("UPDATE evaluations SET llm_interpretation=? WHERE id=?",(text,rid)); conn.commit(); conn.close()

def get_statistics():
    conn=get_db()
    total=conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
    by_risk=dict(conn.execute("SELECT risk_level,COUNT(*) FROM evaluations GROUP BY risk_level").fetchall())
    by_priority=dict(conn.execute("SELECT priority_level,COUNT(*) FROM evaluations GROUP BY priority_level").fetchall())
    conn.close()
    return {"total":total,"by_risk":by_risk,"by_priority":by_priority}

init_db()
