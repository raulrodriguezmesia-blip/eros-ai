from enum import Enum
from typing import Any

from eros.config.settings import settings


class FeatureFlag(str, Enum):
    DEEP_AST_ANALYSIS = "deep_ast_analysis"
    AUTO_PATCH_GENERATION = "auto_patch_generation"
    STRICT_COMPLIANCE_MODE = "strict_compliance_mode"


class FeatureFlags:
    """Desacoplado: env vars ahora, Azure App Config después."""

    _overrides: dict[str, bool] = {}

    @classmethod
    def is_enabled(cls, flag: FeatureFlag) -> bool:
        if flag.value in cls._overrides:
            return cls._overrides[flag.value]
        return getattr(settings, flag.value, False)

    @classmethod
    def set_override(cls, flag: FeatureFlag, value: bool) -> None:
        cls._overrides[flag.value] = value

    @classmethod
    def clear_override(cls, flag: FeatureFlag) -> None:
        cls._overrides.pop(flag.value, None)

    @classmethod
    def all_flags(cls) -> dict[str, bool]:
        return {f.value: cls.is_enabled(f) for f in FeatureFlag}

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        return {
            "flags": cls.all_flags(),
            "source": "override" if cls._overrides else "env",
        }
