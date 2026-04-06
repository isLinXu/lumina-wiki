"""
Lumina Wiki - Configuration Manager
读取并管理 lumina.toml 配置文件。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class RepositoryConfig:
    owner: str = "gatilin"
    name: str = "Lumina-Wiki"
    branch: str = "main"


@dataclass
class IngestConfig:
    label: str = "lumina"
    raw_dir: str = "raw"
    date_format: str = "%Y-%m-%d"
    process_images: bool = True
    close_after_ingest: bool = True


@dataclass
class CompilerConfig:
    wiki_dir: str = "wiki"
    concepts_dir: str = "concepts"
    papers_dir: str = "papers"
    notes_dir: str = "notes"
    auto_link: bool = True
    summary_max_tokens: int = 500
    entity_confidence: float = 0.7


@dataclass
class LLMConfig:
    provider: str = "github-copilot"
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4096
    # Provider-specific settings (loaded separately)
    openai_api_key_env: Optional[str] = None
    openai_base_url: Optional[str] = None
    azure_api_key_env: Optional[str] = None
    azure_endpoint_env: Optional[str] = None
    azure_deployment: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None


@dataclass
class LinkingConfig:
    min_concept_length: int = 3
    max_concept_length: int = 50
    case_sensitive: bool = False
    exclude_common_words: bool = True


@dataclass
class LintingConfig:
    conflict_threshold: float = 0.2
    suggest_issues: bool = True
    health_score_enabled: bool = True


@dataclass
class OutputConfig:
    front_matter: bool = True
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    author: str = "Lumina Compiler"


@dataclass
class LuminaConfig:
    repository: RepositoryConfig = field(default_factory=RepositoryConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)
    compiler: CompilerConfig = field(default_factory=CompilerConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    linking: LinkingConfig = field(default_factory=LinkingConfig)
    linting: LintingConfig = field(default_factory=LintingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    _config_path: Path = field(default=Path("lumina.toml"), repr=False)

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def raw_path(self) -> Path:
        return Path(self.ingest.raw_dir)

    @property
    def wiki_path(self) -> Path:
        return Path(self.compiler.wiki_dir)

    @property
    def concepts_path(self) -> Path:
        return self.wiki_path / self.compiler.concepts_dir

    @property
    def papers_path(self) -> Path:
        return self.wiki_path / self.compiler.papers_dir

    @property
    def notes_path(self) -> Path:
        return self.wiki_path / self.compiler.notes_dir


def load_config(config_path: Optional[Path | str] = None) -> LuminaConfig:
    """
    从 lumina.toml 加载配置。搜索顺序：
    1. 显式传入的路径
    2. 当前工作目录的 lumina.toml
    3. 此脚本所在目录的 lumina.toml
    4. 使用默认值（零配置启动）
    """
    if config_path is None:
        candidates = [
            Path.cwd() / "lumina.toml",
            Path(__file__).parent.parent / "lumina.toml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break
        else:
            config_path = Path.cwd() / "lumina.toml"

    config_path = Path(config_path)
    cfg = LuminaConfig(_config_path=config_path)

    if not config_path.exists():
        print(f"⚠️  配置文件不存在: {config_path}，使用默认值")
        return cfg

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Parse each section
    for section_key, section_data in data.items():
        if section_key == "repository":
            _update_dataclass(cfg.repository, section_data)
        elif section_key == "ingest":
            _update_dataclass(cfg.ingest, section_data)
        elif section_key == "compiler":
            _update_dataclass(cfg.compiler, section_data)
        elif section_key == "llm":
            _parse_llm_config(cfg.llm, section_data)
        elif section_key == "linking":
            _update_dataclass(cfg.linking, section_data)
        elif section_key == "linting":
            _update_dataclass(cfg.linting, section_data)
        elif section_key == "output":
            _update_dataclass(cfg.output, section_data)

    return cfg


def _update_dataclass(obj: Any, data: dict) -> None:
    """用字典数据更新 dataclass 实例。"""
    for key, value in data.items():
        if hasattr(obj, key):
            setattr(obj, key, value)


def _parse_llm_config(llm_cfg: LLMConfig, data: dict) -> None:
    """解析 LLM 配置（包含嵌套的 provider 设置）。"""
    for key, value in data.items():
        if hasattr(llm_cfg, key):
            setattr(llm_cfg, key, value)

    # Provider-specific nested config
    for provider in ["openai", "azure", "ollama"]:
        if provider in data:
            sub = data[provider]
            for k, v in sub.items():
                attr_name = f"{provider}_{k}"
                if hasattr(llm_cfg, attr_name):
                    setattr(llm_cfg, attr_name, v)


def get_token() -> str:
    """获取 GitHub Token，优先从环境变量读取。"""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    if not token:
        print(
            "❌ 未找到 GITHUB_TOKEN 或 GH_PAT 环境变量。\n"
            "   请设置: export GITHUB_TOKEN='your-token-here'"
        )
        sys.exit(1)
    return token
