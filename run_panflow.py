"""Zero-setup development entrypoint for the PanFlow CLI."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    # 直接从源码目录启动，避免本地开发必须先执行 pip install。
    sys.path.insert(0, str(SRC_DIR))

from panflow_service.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
