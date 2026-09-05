# PythonAnywhere 的 WSGI 入口（挂载到 /var/www/<user>_pythonanywhere_com_wsgi.py）
# 部署时把下面你的用户名替换进去；field_app 目录路径改成你服务器上的实际路径。
import sys, os

# 1) 把 field_app 目录加入模块搜索路径（改成服务器上实际的绝对路径）
FIELD_APP_DIR = "/home/StarMo/field_app"
if FIELD_APP_DIR not in sys.path:
    sys.path.insert(0, FIELD_APP_DIR)

# 2) 可选：覆盖数据库路径与照片存储后端
os.environ.setdefault("FIELD_DB", os.path.join(FIELD_APP_DIR, "field.db"))

# 3) 引入 Flask app
from app import app as application
