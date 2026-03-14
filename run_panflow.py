"""本地开发入口。

这个脚本的目标是让仓库在未安装成包的情况下也能直接运行 CLI。
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

# 启动时主动把源码目录塞进 sys.path，这样开发者不必先执行 `pip install -e .`。
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from panflow_service.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
