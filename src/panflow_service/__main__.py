"""包级命令入口，允许通过 `python -m panflow_service` 启动 CLI。"""

from panflow_service.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
