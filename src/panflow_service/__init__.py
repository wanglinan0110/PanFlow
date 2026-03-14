"""PanFlow service package."""

# 显式导入共享表格 helper，确保动态加载的 examples/*.py 在打包后仍能正常导入。
from panflow_service.renderers import testcase_table as _testcase_table  # noqa: F401
