"""Tests for file type classification."""

import pytest
from src.backend.engines.file_type_classifier import (
    FileType,
    FileTypeClassification,
    FileTypeClassifier,
    classify_file,
)


class TestFileTypeClassifier:
    """Tests for FileTypeClassifier class."""

    def test_classify_tailwind_config(self) -> None:
        """tailwind.config.js should be classified as CONFIG."""
        result = classify_file("tailwind.config.js")
        assert result.file_type == FileType.CONFIG
        assert result.confidence >= 0.9
        assert result.domain == "tailwind"

    def test_classify_postcss_config(self) -> None:
        """postcss.config.js should be classified as CONFIG."""
        result = classify_file("postcss.config.js")
        assert result.file_type == FileType.CONFIG
        assert result.confidence >= 0.9
        assert result.domain == "postcss"

    def test_classify_package_json(self) -> None:
        """package.json should be classified as CONFIG."""
        result = classify_file("package.json")
        assert result.file_type == FileType.CONFIG
        assert result.confidence >= 0.85

    def test_classify_typescript_config(self) -> None:
        """tsconfig.json should be classified as CONFIG."""
        result = classify_file("tsconfig.json")
        assert result.file_type == FileType.CONFIG

    def test_classify_webpack_config(self) -> None:
        """webpack.config.js should be classified as CONFIG."""
        result = classify_file("webpack.config.js")
        assert result.file_type == FileType.CONFIG
        assert result.domain == "webpack"

    def test_classify_python_code(self) -> None:
        """Python files should be classified as CODE."""
        result = classify_file("solution.py")
        assert result.file_type in (FileType.CODE, FileType.MIXED)

    def test_classify_javascript_code(self) -> None:
        """JavaScript files should be classified as CODE."""
        result = classify_file("app.js")
        assert result.file_type in (FileType.CODE, FileType.MIXED)

    def test_classify_shell_script(self) -> None:
        """Shell scripts should be classified as SCRIPT."""
        result = classify_file("deploy.sh")
        assert result.file_type == FileType.SCRIPT

    def test_classify_json_data_file(self) -> None:
        """JSON files should be classified as CONFIG."""
        result = classify_file("data.json")
        assert result.file_type == FileType.CONFIG

    def test_classify_yaml_data_file(self) -> None:
        """YAML files should be classified as CONFIG."""
        result = classify_file("config.yaml")
        assert result.file_type == FileType.CONFIG

    def test_classify_by_content_config(self) -> None:
        """Content analysis should detect config files."""
        config_content = '{"name": "my-project", "version": "1.0.0"}'
        result = classify_file("unknown.txt", config_content)
        assert result.file_type == FileType.CONFIG

    def test_classify_path_with_directories(self) -> None:
        """Should handle paths with directories."""
        result = classify_file("/path/to/tailwind.config.js")
        assert result.file_type == FileType.CONFIG
        assert result.domain == "tailwind"


class TestFileTypeWeights:
    """Tests for file type weighting rules."""

    def test_config_embedding_weight_zero(self) -> None:
        """CONFIG files should have embedding weight near zero."""
        from src.backend.engines.file_type_weights import CONFIG_WEIGHTS
        assert CONFIG_WEIGHTS.embedding == 0.0

    def test_code_balanced_weights(self) -> None:
        """CODE files should have balanced weights."""
        from src.backend.engines.file_type_weights import CODE_WEIGHTS
        assert CODE_WEIGHTS.embedding == 1.0
        assert CODE_WEIGHTS.ast == 1.0

    def test_apply_weights_config(self) -> None:
        """Apply weights should zero out embedding for CONFIG."""
        from src.backend.engines.file_type_weights import apply_weights
        
        raw_scores = {"embedding": 0.9, "ast": 0.8, "fingerprint": 0.7}
        weighted = apply_weights(raw_scores, FileType.CONFIG)
        
        assert weighted["embedding"] == 0.0
        assert weighted["ast"] == 0.8
        assert weighted["fingerprint"] == 0.21  # 0.7 * 0.3

    def test_should_veto_embedding_config(self) -> None:
        """Should veto embedding for CONFIG files."""
        from src.backend.engines.file_type_weights import should_veto_embedding
        
        assert should_veto_embedding(FileType.CONFIG) is True
        assert should_veto_embedding(FileType.CONFIG, "tailwind") is True
        assert should_veto_embedding(FileType.CODE) is False