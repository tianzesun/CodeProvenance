# IntegrityDesk Project Structure

```
IntegrityDesk/
├── src/
│   ├── api/                 # REST API layer
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   ├── engines/             # ⭐ Core algorithm layer (decoupled)
│   │   ├── base_engine.py
│   │   ├── fingerprint/     # Token-based fingerprinting
│   │   ├── ast/             # AST structural analysis
│   │   ├── semantic/        # Semantic/embedding similarity
│   │   └── fusion/          # Ensemble engine
│   ├── pipeline/            # ⭐ Pipeline orchestrator
│   │   ├── detect.py        # Detection workflow
│   │   ├── benchmark.py     # Benchmark workflow
│   │   └── train.py         # Training workflow
│   ├── analysis/            # ⭐ Error analysis
│   │   └── error_analysis.py
│   ├── workers/             # Background workers
│   └── utils/               # Utilities
├── benchmark/               # ⭐ Benchmark system
│   ├── datasets/            # Benchmark datasets
│   ├── runners/             # Dataset runners
│   ├── evaluators/          # Metric evaluators
│   └── reports/             # Benchmark reports
├── ml/                      # ⭐ ML system
│   ├── datasets/            # Training datasets
│   ├── training/            # Model training
│   ├── models/              # Trained model storage
│   └── checkpoints/         # Training checkpoints
├── tools/                   # ⭐ Competitor tools
│   ├── jplag/
│   ├── moss/
│   ├── nicad/
│   └── pmd/
├── data/                    # Data files
├── reports/                 # Generated reports
├── scripts/                 # Build scripts
├── tests/                   # Tests
├── docker/                  # Docker config
└── docs/                    # Documentation
```
