# Tools Directory

Third-party tool depot for benchmarking.

## Structure

```
tools/
├── external/               # First-class benchmarked external tools
│   ├── moss/
│   ├── JPlag/
│   ├── NiCad-6.2/
│   ├── dolos/
│   ├── pmd/
│   ├── Sherlock/
│   └── vendetect-0.0.3/
├── libs/                   # Helper libraries used in baseline implementations
│   ├── textdistance/
│   ├── fuzzywuzzy/
│   ├── py_stringmatching/
│   └── sim_metrics/
├── configs/                # Per-tool configuration templates
│   ├── moss/
│   ├── jplag/
│   ├── nicad/
│   ├── dolos/
│   └── pmd/
├── sandbox/                # Temporary per-run execution workspaces
├── outputs/                # Tool execution outputs
│   ├── raw/                # Unmodified raw tool outputs
│   └── normalized/         # Parsed normalized benchmark-ready results
└── README.md
```

## Rules

1.  **`tools/external/`**: Contains only third-party runnable distributions. No modifications.
2.  **`tools/libs/`**: Helper libraries only used for internal baseline implementations.
3.  **`tools/configs/`**: Static per-tool configuration templates for reproducible runs.
4.  **`tools/sandbox/`**: Temporary working directory for tool execution. Git ignored.
5.  **`tools/outputs/`**: Execution artifacts. Raw outputs preserved for audit trails.

All adapter implementation code remains in:
```
src/backend/benchmark/adapters/
```

Benchmark protocol, validation logic, and metrics remain in their respective architecture layers. This directory contains only third-party assets and runtime artifacts.
