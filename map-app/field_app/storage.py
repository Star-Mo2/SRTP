"""
============================================================
 存储层抽象：照片的"存 / 取 / 删 / 访问URL"
 目标：app.py 只调用 photo_store 的统一接口，
       具体用哪种存储（本地磁盘 / 对象存储 OSS）由配置决定，
       业务代码无需改动即可切换后端。

 后端：photo_store 是单一入口。
   - LocalPhotoStore：存到本地 uploads/，通过 /uploads/<key> 访问（默认）
   - OssPhotoStore   ：预留接口，接入腾讯云 COS / 阿里云 OSS 时实现即可
============================================================
"""
import os, uuid

# ---- 允许的图片扩展名 ----
ALLOWED_EXT = {"png","jpg","jpeg","gif","webp","bmp"}

def _ext_of(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


class BasePhotoStore(object):
    """照片存储统一接口。子类必须实现 save/get_url/delete。"""
    backend = "base"

    def save(self, file_stream, ext, makedirs=True):
        """把文件流写入存储，返回存储 key（在库中持久化）。抛 ValueError 表示不支持。"""
        raise NotImplementedError

    def get_url(self, key):
        """由存储 key 生成公开访问 URL（供前端 <img> 使用）。"""
        raise NotImplementedError

    def delete(self, key):
        """删除指定 key 的文件。"""
        raise NotImplementedError

    def local_dir(self):
        """本地后端返回存储目录；不是本地后端返回 None。"""
        return None


class LocalPhotoStore(BasePhotoStore):
    """存到本地 uploads/ 文件夹，通过 /uploads/<key> 访问（默认）。"""
    backend = "local"

    def __init__(self, base_dir):
        self.dir = os.path.join(base_dir, "uploads")

    def save(self, file_stream, ext, makedirs=True):
        ext = ext.lower()
        if ext not in ALLOWED_EXT:
            raise ValueError("不支持的图片格式: %s" % (ext or "无扩展名"))
        if makedirs:
            os.makedirs(self.dir, exist_ok=True)
        key = "img_%s.%s" % (uuid.uuid4().hex[:12], ext)
        with open(os.path.join(self.dir, key), "wb") as fh:
            fh.write(file_stream.read())
        return key

    def get_url(self, key):
        return "/uploads/" + key

    def delete(self, key):
        path = os.path.join(self.dir, key)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def local_dir(self):
        return self.dir


# ---- 工厂：按配置选择后端 ----
def create_photo_store(base_dir, backend=None):
    """backend 优先取参数，其次取环境变量 PHOTO_STORAGE，默认 'local'。"""
    backend = backend or os.environ.get("PHOTO_STORAGE", "local") or "local"
    if backend == "local":
        return LocalPhotoStore(base_dir)
    # 其它后端（oss 等）暂未接入，先回退到本地，避免配置错了就崩
    return LocalPhotoStore(base_dir)


# 供上层直接使用的默认实例（由 app.py 在 import 时用真实 BASE 创建）。
photo_store = None
