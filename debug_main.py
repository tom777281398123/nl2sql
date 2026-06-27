"""PyCharm 调试专用入口。

直接以普通脚本方式运行（Script path 指向本文件），
避免 module 模式下 pydevd 调试器不执行 uvicorn 的问题。
等价于 `python -m uvicorn backend.main:app`，但断点更稳。
"""
import uvicorn

from backend.main import app

if __name__ == "__main__":
    # reload 必须为 False：reload 会开子进程，断点会失效
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
