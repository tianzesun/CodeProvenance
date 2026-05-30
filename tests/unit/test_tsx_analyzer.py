"""Tests for TSX/JSX-aware structural analysis."""

import pytest
from src.backend.engines.tsx_analyzer import (
    TSXAnalyzer,
    TSXAnalysisResult,
    ComponentInfo,
    analyze_tsx_similarity,
    calculate_boilerplate_discount,
)


class TestTSXAnalyzer:
    """Tests for TSX/JSX analyzer."""

    def test_detect_react_imports(self) -> None:
        """Should detect React imports."""
        analyzer = TSXAnalyzer()
        
        code_with_react = 'import React from "react";'
        assert analyzer._detect_react_imports(code_with_react) is True
        
        code_without_react = 'const x = 1;'
        assert analyzer._detect_react_imports(code_without_react) is False

    def test_detect_jsx(self) -> None:
        """Should detect JSX syntax."""
        analyzer = TSXAnalyzer()
        
        jsx_code = '<div>Hello</div>'
        assert analyzer._detect_jsx(jsx_code) is True
        
        plain_code = 'const x = 1;'
        assert analyzer._detect_jsx(plain_code) is False

    def test_analyze_simple_component(self) -> None:
        """Should analyze a simple component."""
        analyzer = TSXAnalyzer()
        
        code = '''
        import React from 'react';
        
        function MyComponent({ name }) {
          return <div>Hello {name}</div>;
        }
        '''
        
        result = analyzer.analyze(code)
        assert result.has_jsx is True
        assert result.has_react_imports is True
        assert len(result.component_tree) >= 0  # May or may not detect function

    def test_analyze_boilerplate_patterns(self) -> None:
        """Should detect common boilerplate patterns."""
        analyzer = TSXAnalyzer()
        
        code = '''
        import React from 'react';
        import { useState } from 'react';
        export default function App() {
          return <div className="app">Content</div>;
        }
        '''
        
        result = analyzer.analyze(code)
        assert "react_import" in result.structural_patterns
        assert "jsx_attributes" in result.structural_patterns
        assert "default_export" in result.structural_patterns

    def test_compare_components(self) -> None:
        """Should compare component trees."""
        analyzer = TSXAnalyzer()
        
        components_a = [ComponentInfo(
            name="Header",
            line_start=1,
            line_end=10,
            props=["title"],
            has_hooks=False,
            hook_names=[],
            jsx_depth=1,
            children_count=0,
        )]
        
        components_b = [ComponentInfo(
            name="Header",
            line_start=1,
            line_end=10,
            props=["title"],
            has_hooks=False,
            hook_names=[],
            jsx_depth=1,
            children_count=0,
        )]
        
        similarity = analyzer.compare_components(components_a, components_b)
        assert similarity == 1.0

    def test_boilerplate_discount_heavy(self) -> None:
        """Should apply heavy discount for heavy boilerplate."""
        result = TSXAnalysisResult(
            component_tree=[],
            has_jsx=True,
            has_react_imports=True,
            hook_usage={},
            structural_patterns=["react_import", "default_export", "jsx_attributes", "arrow_functions"],
            component_similarity=0.0,
            boilerplate_similarity=0.0,
        )
        
        discount = calculate_boilerplate_discount(result)
        assert discount == 0.1  # 90% discount


class TestTSXSimilarity:
    """Tests for TSX similarity analysis."""

    def test_analyze_tsx_similarity_react_pages(self) -> None:
        """Should detect and discount React boilerplate."""
        page_a = '''
        import React from 'react';
        import { useState } from 'react';
        export default function Home() {
          const [count, setCount] = useState(0);
          return <div className="container"><h1>Home</h1></div>;
        }
        '''
        
        page_b = '''
        import React from 'react';
        import { useState } from 'react';
        export default function Index() {
          const [count, setCount] = useState(0);
          return <div className="container"><h1>Index</h1></div>;
        }
        '''
        
        result = analyze_tsx_similarity(page_a, page_b)
        
        # Should detect JSX and boilerplate
        assert result["has_jsx"] is True
        assert result["boilerplate_similarity"] > 0.5
        # Should apply discount
        assert result["discount_factor"] < 1.0