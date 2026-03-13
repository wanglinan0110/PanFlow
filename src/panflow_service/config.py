from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tomllib
from types import ModuleType

from panflow_service.runtime_paths import resolve_pandoc_binary, resolve_reference_doc, resolve_renderers_dir


DEFAULT_CONFIG_FILE = "panflow.toml"
DEFAULT_RENDERERS_DIR = Path("src/panflow_service/renderers")


@dataclass(frozen=True)
class PandocConfig:
    binary: str = "pandoc"
    reference_doc: Path | None = None


@dataclass(frozen=True)
class ProjectConfig:
    project_root: Path
    renderers: dict[str, Path]
    pandoc: PandocConfig


def scan_renderer_scripts(renderers_dir: Path) -> dict[str, Path]:
    if not renderers_dir.exists():
        return {}

    mapping: dict[str, Path] = {}
    for script_path in sorted(renderers_dir.glob("*.py")):
        if script_path.name == "__init__.py":
            continue
        # 允许一个脚本声明多个 renderer 键，便于兼容历史块类型命名。
        for key in _read_renderer_keys(script_path):
            mapping[key] = script_path
    return mapping


def discover_default_config(project_root: Path) -> ProjectConfig:
    # 没有显式 TOML 时，优先使用当前工程目录；打包后则回退到应用内置资源目录。
    renderers_dir = resolve_renderers_dir(project_root)
    return ProjectConfig(
        project_root=project_root.resolve(),
        renderers=scan_renderer_scripts(renderers_dir),
        pandoc=PandocConfig(
            binary=resolve_pandoc_binary(project_root),
            reference_doc=resolve_reference_doc(project_root),
        ),
    )


def load_project_config(config_path: Path) -> ProjectConfig:
    resolved_config = config_path.resolve()
    data = tomllib.loads(resolved_config.read_text(encoding="utf-8"))
    base_dir = resolved_config.parent

    pandoc_data = data.get("pandoc", {})
    renderers_data = data.get("renderers", {})

    reference_doc = pandoc_data.get("reference_doc")
    pandoc_config = PandocConfig(
        binary=pandoc_data.get("binary", "pandoc"),
        # TOML 内的相对路径统一相对配置文件所在目录解析，便于项目搬迁。
        reference_doc=_resolve_path(base_dir, reference_doc) if reference_doc else None,
    )

    renderers = {
        key: _resolve_path(base_dir, str(value))
        for key, value in renderers_data.items()
    }
    return ProjectConfig(
        project_root=base_dir.resolve(),
        renderers=renderers,
        pandoc=pandoc_config,
    )


def resolve_runtime_config(project_root: Path, config_path: Path | None = None) -> ProjectConfig:
    if config_path is not None:
        return load_project_config(config_path)

    default_path = project_root / DEFAULT_CONFIG_FILE
    if default_path.exists():
        return load_project_config(default_path)

    return discover_default_config(project_root)


def render_config_toml(
    renderers: dict[str, Path],
    *,
    base_dir: Path,
    pandoc_binary: str = "pandoc",
    reference_doc: Path | None = Path("templates/reference.docx"),
) -> str:
    # 导出的 TOML 尽量保留相对路径，方便跨机器拷贝整个工程。
    lines = [
        "[pandoc]",
        f'binary = "{pandoc_binary}"',
    ]
    if reference_doc is not None:
        lines.append(
            f'reference_doc = "{_to_display_path(base_dir, reference_doc)}"',
        )

    lines.extend(["", "[renderers]"])
    for key, path in sorted(renderers.items()):
        lines.append(f'{key} = "{_to_display_path(base_dir, path)}"')

    return "\n".join(lines) + "\n"


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def _to_display_path(base_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_renderer_keys(script_path: Path) -> list[str]:
    # 优先读取脚本显式声明的键，未声明时退回文件名。
    module = _load_module_from_path(script_path)
    raw_keys = getattr(module, "RENDER_KEYS", None)
    if raw_keys is None:
        raw_key = getattr(module, "RENDER_KEY", None)
        if isinstance(raw_key, str) and raw_key.strip():
            return [raw_key.strip()]
        return [script_path.stem]

    if not isinstance(raw_keys, (list, tuple)):
        return [script_path.stem]

    keys = [str(item).strip() for item in raw_keys if str(item).strip()]
    return keys or [script_path.stem]


def _load_module_from_path(script_path: Path) -> ModuleType:
    module_name = f"panflow_config_scan_{script_path.stem}_{abs(hash(script_path.resolve()))}"
    spec = spec_from_file_location(module_name, script_path.resolve())
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to inspect renderer metadata at '{script_path}'.")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
