from eros.config.feature_flags import FeatureFlag, FeatureFlags


def test_flag_default_false():
    """Feature flags default to False."""
    assert FeatureFlags.is_enabled(FeatureFlag.DEEP_AST_ANALYSIS) is False
    assert FeatureFlags.is_enabled(FeatureFlag.AUTO_PATCH_GENERATION) is False
    assert FeatureFlags.is_enabled(FeatureFlag.STRICT_COMPLIANCE_MODE) is False


def test_flag_toggle():
    """Toggle flag and verify."""
    FeatureFlags.set_override(FeatureFlag.DEEP_AST_ANALYSIS, True)
    assert FeatureFlags.is_enabled(FeatureFlag.DEEP_AST_ANALYSIS) is True
    FeatureFlags.clear_override(FeatureFlag.DEEP_AST_ANALYSIS)
    assert FeatureFlags.is_enabled(FeatureFlag.DEEP_AST_ANALYSIS) is False


def test_flag_all_flags():
    """all_flags returns dict with all flags."""
    flags = FeatureFlags.all_flags()
    assert "deep_ast_analysis" in flags
    assert "auto_patch_generation" in flags
    assert "strict_compliance_mode" in flags


def test_flag_snapshot():
    """snapshot returns flags and source."""
    snap = FeatureFlags.snapshot()
    assert "flags" in snap
    assert "source" in snap
