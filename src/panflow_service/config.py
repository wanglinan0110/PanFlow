"""项目配置加载。"""

from dataclasses import dataclass
from pathlib import Path
import tomllib

from panflow_service.runtime_paths import executable_root, resolve_pandoc_binary, resolve_reference_doc


DEFAULT_CONFIG_FILE = "panflow.toml"


@dataclass(frozen=True)
class PandocConfig:
    # 这里只保留运行时真正需要的 pandoc 选项。
    binary: str = "pandoc"
    reference_doc: Path | None = None


@dataclass(frozen=True)
class ProjectConfig:
    # ProjectConfig 是 CLI、转换流程和打包流程共享的统一配置对象。
    project_root: Path
    pandoc: PandocConfig


def discover_default_config(project_root: Path) -> ProjectConfig:
    # 没有显式 TOML 时，优先使用当前工程目录；打包后则回退到应用内置资源目录。
    return ProjectConfig(
        project_root=project_root.resolve(),
        pandoc=PandocConfig(
            binary=resolve_pandoc_binary(project_root),
            reference_doc=resolve_reference_doc(project_root),
        ),
    )


def load_project_config(config_path: Path) -> ProjectConfig:
    # 显式配置文件模式：以配置文件所在目录作为相对路径基准。
    resolved_config = config_path.resolve()
    data = tomllib.loads(resolved_config.read_text(encoding="utf-8"))
    base_dir = resolved_config.parent

    pandoc_data = data.get("pandoc", {})

    reference_doc = pandoc_data.get("reference_doc")
    pandoc_config = PandocConfig(
        binary=pandoc_data.get("binary", "pandoc"),
        # TOML 内的相对路径统一相对配置文件所在目录解析，便于项目搬迁。
        reference_doc=_resolve_path(base_dir, reference_doc) if reference_doc else None,
    )

    return ProjectConfig(
        project_root=base_dir.resolve(),
        pandoc=pandoc_config,
    )


def resolve_runtime_config(project_root: Path, config_path: Path | None = None) -> ProjectConfig:
    # 运行时优先级：显式配置 > 默认 panflow.toml > 自动发现。
    if config_path is not None:
        return load_project_config(config_path)

    candidates = [project_root / DEFAULT_CONFIG_FILE]
    exe_root = executable_root()
    if exe_root is not None:
        candidates.append(exe_root / DEFAULT_CONFIG_FILE)
    for default_path in candidates:
        if default_path.exists():
            return load_project_config(default_path)

    return discover_default_config(project_root)


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    # 相对路径一律解释为“相对配置文件所在目录”。
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()
