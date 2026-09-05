"""
============================================================
 深田社区点位地图 Web App（独立小程序版）
 - 地图叠加 243 个设施点位（高德 GCJ-02）
 - 点开点位：上传现场照片、查看照片、旁边记录信息
 - 后端：SQLite 存点位记录/备注 + 本地 uploads 存照片
   （暂用本地文件存储，后续可无缝换成对象存储 OSS）
============================================================
"""
import os, json, time, sqlite3, mimetypes, csv, io
from flask import (Flask, render_template, request, jsonify,
                   send_from_directory, abort, Response)
from storage import create_photo_store

BASE = os.path.dirname(os.path.abspath(__file__))
# 数据库路径可用 FIELD_DB 环境变量覆盖（部署到服务器时指定）
DB_PATH = os.environ.get("FIELD_DB", os.path.join(BASE, "field.db"))
ALLOWED_EXT = {"png","jpg","jpeg","gif","webp","bmp"}
MAX_MB = 15

# 存储层：默认本地 uploads/，切换后端只改 PHOTO_STORAGE 环境变量
photo_store = create_photo_store(BASE)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

# ---- 加载点位数据 ----
def load_points():
    with open(os.path.join(BASE, "points.json"), encoding="utf-8") as f:
        raw = json.load(f)
    # 为每个点分配稳定的点号 id，并保留原 x/y（点位图坐标）以便可能的后端重映射
    for i, p in enumerate(raw):
        p["x_id"] = "P%03d" % i
    return raw
POINTS = load_points()

# ---- SQLite ----
def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_records (
            point_id TEXT PRIMARY KEY,
            note TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            point_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            note TEXT DEFAULT '',
            uploaded_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_photos_point ON photos(point_id)")
    # 被用户拖动调整后的点位坐标（覆盖 points.json 原始值）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS point_positions (
            point_id TEXT PRIMARY KEY,
            lon REAL NOT NULL,
            lat REAL NOT NULL,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # 用户新增的自定义点位（类型可以是预设8类，也可以是自定义名称）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_points (
            point_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            lon REAL NOT NULL,
            lat REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # 被用户删除的默认（识别）点位：记录 id，用于“恢复所有已删除（仅默认）”
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deleted_points (
            point_id TEXT PRIMARY KEY,
            deleted_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit(); conn.close()

def get_note(point_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM site_records WHERE point_id=?", (point_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"point_id": point_id, "note": "", "updated_at": None}

def save_note(point_id, note):
    conn = get_db()
    conn.execute("""INSERT INTO site_records (point_id, note, updated_at)
                    VALUES (?,?,datetime('now','localtime'))
                    ON CONFLICT(point_id) DO UPDATE SET
                      note=excluded.note, updated_at=excluded.updated_at""",
                 (point_id, note))
    conn.commit(); conn.close()

def list_photos(point_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM photos WHERE point_id=? ORDER BY id DESC",
                        (point_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_photo(point_id, filename, note=""):
    conn = get_db()
    cur = conn.execute("INSERT INTO photos (point_id, filename, note) VALUES (?,?,?)",
                       (point_id, filename, note))
    rid = cur.lastrowid
    conn.commit(); conn.close()
    return rid

def delete_all_photos(point_id):
    conn = get_db()
    rows = conn.execute("SELECT filename FROM photos WHERE point_id=?", (point_id,)).fetchall()
    conn.execute("DELETE FROM photos WHERE point_id=?", (point_id,))
    conn.commit(); conn.close()
    return [r["filename"] for r in rows]

# ---- 点位坐标覆盖（拖动调整后的值）----
def get_position_overrides():
    conn = get_db()
    rows = conn.execute("SELECT point_id, lon, lat FROM point_positions").fetchall()
    conn.close()
    return {r["point_id"]: {"lon": r["lon"], "lat": r["lat"]} for r in rows}

def save_point_position(point_id, lon, lat):
    conn = get_db()
    conn.execute("""INSERT INTO point_positions (point_id, lon, lat, updated_at)
                    VALUES (?,?,?,datetime('now','localtime'))
                    ON CONFLICT(point_id) DO UPDATE SET
                      lon=excluded.lon, lat=excluded.lat, updated_at=excluded.updated_at""",
                 (point_id, lon, lat))
    conn.commit(); conn.close()

def delete_point_position(point_id):
    """删除覆盖值，使该点位回到原始识别坐标"""
    conn = get_db()
    conn.execute("DELETE FROM point_positions WHERE point_id=?", (point_id,))
    conn.commit(); conn.close()

def get_point_original(point_id):
    """返回点位的原始识别坐标（静态点来自 points.json；自选点来自 custom_points）"""
    for p in POINTS:
        if p["x_id"] == point_id:
            return {"lon": p["lon_gcj"], "lat": p["lat_gcj"]}
    c = get_custom_point(point_id)
    if c:
        return {"lon": c["lon"], "lat": c["lat"]}
    return None

# ---- 自定义点位（用户新增）----
def get_custom_points():
    conn = get_db()
    rows = conn.execute("SELECT * FROM custom_points ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_custom_point(point_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM custom_points WHERE point_id=?", (point_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def next_custom_id():
    """生成新的自选点编号，如 C001, C002 …"""
    conn = get_db()
    rows = conn.execute("SELECT point_id FROM custom_points").fetchall()
    conn.close()
    used = {r["point_id"] for r in rows}
    n = 1
    while ("C%03d" % n) in used:
        n += 1
    return "C%03d" % n

def add_custom_point(category, lon, lat):
    pid = next_custom_id()
    conn = get_db()
    conn.execute("INSERT INTO custom_points (point_id, category, lon, lat) VALUES (?,?,?,?)",
                 (pid, category, lon, lat))
    conn.commit(); conn.close()
    return pid

def update_custom_point_position(point_id, lon, lat):
    conn = get_db()
    conn.execute("UPDATE custom_points SET lon=?, lat=? WHERE point_id=?", (lon, lat, point_id))
    conn.commit(); conn.close()

# ---- 删除 / 恢复 ----
def is_default_point(point_id):
    """判断是否是默认识别点位（来自 points.json）"""
    return any(p["x_id"] == point_id for p in POINTS)

def has_custom_point(point_id):
    return get_custom_point(point_id) is not None

def delete_point(point_id):
    """删除一个点位。
       默认点：软删除（记录 id，可从“恢复所有已删除”找回）。
       自选点：硬删除（彻底移除，无法找回）。"""
    conn = get_db()
    if is_default_point(point_id):
        conn.execute("INSERT OR IGNORE INTO deleted_points (point_id) VALUES (?)", (point_id,))
        conn.commit(); conn.close()
        return "default"
    elif has_custom_point(point_id):
        # 一并删除它的位置覆盖、记录、照片记录
        files = delete_all_photos(point_id)
        conn.execute("DELETE FROM custom_points WHERE point_id=?", (point_id,))
        conn.execute("DELETE FROM point_positions WHERE point_id=?", (point_id,))
        conn.execute("DELETE FROM site_records WHERE point_id=?", (point_id,))
        conn.commit(); conn.close()
        for fn in files:
            photo_store.delete(fn)
        return "custom"
    return None

def restore_all_deleted():
    """恢复所有被删除的默认点位（自选点不可恢复）。返回恢复数量。"""
    conn = get_db()
    rows = conn.execute("SELECT point_id FROM deleted_points").fetchall()
    cur = conn.execute("DELETE FROM deleted_points")
    conn.commit(); conn.close()
    return len(rows)

def get_deleted_ids():
    conn = get_db()
    rows = conn.execute("SELECT point_id FROM deleted_points").fetchall()
    conn.close()
    return {r["point_id"] for r in rows}

# ---- helpers ----
def ok(data):
    return jsonify({"success": True, **data})

def err(msg, code=400):
    return jsonify({"success": False, "error": msg}), code

def save_upload(f):
    if not f or f.filename == "":
        return None, "未选择文件"
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    try:
        # 通过存储层写入；key 即返回
        safe = photo_store.save(f.stream, ext)
    except ValueError as e:
        return None, str(e)
    return safe, None

def photo_url(key):
    """照片的公开访问 URL（存储层决定本地 /uploads 还是远端 URL）"""
    return photo_store.get_url(key)

# ================================================================
# 页面与 API
# ================================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/points")
def api_points():
    """返回全部点位（未删除的静态图点 + 用户自选点），坐标：静态点优先覆盖值，自选点取自身坐标"""
    overrides = get_position_overrides()
    deleted = get_deleted_ids()
    pts = []
    for p in POINTS:
        pid = p["x_id"]
        if pid in deleted:      # 已删除的默认点不再返回
            continue
        photos = list_photos(pid)
        rec = get_note(pid)
        ov = overrides.get(pid)
        lon = ov["lon"] if ov else p["lon_gcj"]
        lat = ov["lat"] if ov else p["lat_gcj"]
        pts.append({"id": pid, "category": p["category"], "lon": lon, "lat": lat,
                    "photo_count": len(photos), "has_note": bool(rec.get("note","").strip()),
                    "source": "detected"})
    for c in get_custom_points():
        pid = c["point_id"]
        photos = list_photos(pid)
        rec = get_note(pid)
        pts.append({"id": pid, "category": c["category"], "lon": c["lon"], "lat": c["lat"],
                    "photo_count": len(photos), "has_note": bool(rec.get("note","").strip()),
                    "source": "custom"})
    return ok({"points": pts, "total": len(pts)})

@app.route("/api/points", methods=["POST"])
def api_add_point():
    """新增自选点位：类型可选预设或自定义名称，坐标为当前落点"""
    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "").strip()
    try:
        lon = float(data.get("lon")); lat = float(data.get("lat"))
    except (TypeError, ValueError):
        return err("坐标缺失或格式错误")
    if not category:
        return err("请填写设施类型")
    if len(category) > 30:
        return err("类型名称过长")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return err("坐标超出合理范围")
    pid = add_custom_point(category, lon, lat)
    return ok({"id": pid, "category": category, "lon": lon, "lat": lat})

@app.route("/api/points/<point_id>", methods=["DELETE"])
def api_delete_point(point_id):
    """删除一个点位。默认点软删除（可恢复）；自选点硬删除。"""
    if point_id in get_deleted_ids():
        return err("该点位已删除", 404)
    kind = delete_point(point_id)
    if kind is None:
        return err("点位不存在", 404)
    return ok({"id": point_id, "kind": kind,
               "restorable": (kind == "default")})   # 只有默认点可恢复

@app.route("/api/points/restore", methods=["POST"])
def api_restore_points():
    """恢复所有被删除的默认点位（自选点不可恢复）。"""
    n = restore_all_deleted()
    return ok({"restored": n, "note": "仅默认点位可恢复"})

@app.route("/api/export")
def api_export():
    """导出全部点位的备注 + 照片记录（CSV，UTF-8 BOM）。"""
    overrides = get_position_overrides()
    deleted = get_deleted_ids()
    rows = []
    # 默认点（未删除）
    for p in POINTS:
        pid = p["x_id"]
        if pid in deleted:
            continue
        ov = overrides.get(pid)
        lon = ov["lon"] if ov else p["lon_gcj"]
        lat = ov["lat"] if ov else p["lat_gcj"]
        rec = get_note(pid)
        photos = [ph for ph in list_photos(pid)]
        rows.append([pid, p["category"], lon, lat, rec.get("note",""), len(photos),
                     "; ".join(photo_url(ph['filename']) for ph in photos)])
    # 自选点
    for c in get_custom_points():
        pid = c["point_id"]
        rec = get_note(pid)
        photos = list_photos(pid)
        rows.append([pid, c["category"], c["lon"], c["lat"], rec.get("note",""), len(photos),
                     "; ".join(photo_url(ph['filename']) for ph in photos)])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["点号","类别","GCJ02经度","GCJ02纬度","备注","照片数","照片路径"])
    for r in rows:
        w.writerow(r)
    data = "\ufeff" + buf.getvalue()   # BOM -> Excel 中文不乱码
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=field_records.csv"})

@app.route("/api/points/<point_id>/position", methods=["POST"])
def api_save_position(point_id):
    """保存拖动调整后的坐标。静态点写覆盖表；自选点直接改自身坐标。"""
    data = request.get_json(silent=True) or {}
    try:
        lon = float(data.get("lon")); lat = float(data.get("lat"))
    except (TypeError, ValueError):
        return err("坐标缺失或格式错误")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return err("坐标超出合理范围")
    if get_custom_point(point_id):
        update_custom_point_position(point_id, lon, lat)
    else:
        save_point_position(point_id, lon, lat)
    return ok({"lon": lon, "lat": lat})

@app.route("/api/points/<point_id>/position", methods=["DELETE"])
def api_reset_position(point_id):
    """恢复到该点位的原始坐标（静态点=识别值；自选点=其自身存储坐标）。只影响这一个点。"""
    orig = get_point_original(point_id)
    if orig is None:
        return err("点位不存在", 404)
    delete_point_position(point_id)   # 自选点无覆盖行，删除无害
    return ok({"lon": orig["lon"], "lat": orig["lat"]})

@app.route("/api/points/<point_id>")
def api_point_detail(point_id):
    if point_id in get_deleted_ids() and not get_custom_point(point_id):
        return err("点位已删除", 404)
    rec = get_note(point_id)
    photos = list_photos(point_id)
    ov = get_position_overrides().get(point_id)
    orig = get_point_original(point_id)
    custom = get_custom_point(point_id)
    # 当前坐标：自选点=自身坐标；静态点=覆盖值或识别值
    cur_lon = cur_lat = None
    if custom:
        cur_lon, cur_lat = custom["lon"], custom["lat"]
    elif ov:
        cur_lon, cur_lat = ov["lon"], ov["lat"]
    photos_out = [{
        "id": ph["id"], "note": ph["note"],
        "url": photo_url(ph['filename']),
        "uploaded_at": ph["uploaded_at"],
    } for ph in photos]
    return ok({"note": rec.get("note",""), "photos": photos_out,
               "lon": cur_lon, "lat": cur_lat,
               "orig_lon": orig["lon"] if orig else None,
               "orig_lat": orig["lat"] if orig else None,
               "modified": (ov is not None) or (custom is not None),
               "source": "custom" if custom else "detected",
               "updated_at": rec.get("updated_at")})

@app.route("/api/points/<point_id>/note", methods=["POST"])
def api_save_note(point_id):
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    save_note(point_id, note)
    return ok({"note": note, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")})

@app.route("/api/points/<point_id>/photos", methods=["POST"])
def api_upload(point_id):
    if "file" not in request.files:
        return err("没有收到文件")
    f = request.files["file"]
    note = request.form.get("note", "")
    fname, e = save_upload(f)
    if e:
        return err(e)
    rid = add_photo(point_id, fname, note)
    return ok({"id": rid, "url": photo_url(fname),
               "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S")})

@app.route("/api/points/<point_id>/photos/<int:photo_id>", methods=["DELETE"])
def api_delete_photo(point_id, photo_id):
    conn = get_db()
    row = conn.execute("SELECT filename FROM photos WHERE id=? AND point_id=?",
                       (photo_id, point_id)).fetchone()
    conn.execute("DELETE FROM photos WHERE id=? AND point_id=?", (photo_id, point_id))
    conn.commit(); conn.close()
    if row:
        photo_store.delete(row["filename"])
        return ok({"deleted": photo_id})
    return err("照片不存在", 404)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # 本地后端从 uploads/ 目录提供文件；切到 OSS 后此路由不再被前端使用
    if photo_store.local_dir() is None:
        return abort(404)
    return send_from_directory(photo_store.local_dir(), filename)

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
