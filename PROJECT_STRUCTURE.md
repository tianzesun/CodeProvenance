# IntegrityDesk Project Structure

```
IntegrityDesk/
├── src/
│   ├── application/
│   │   └── services/               # Business logic and orchestration
│   │       ├── batch_detection_service.py
│   │       ├── dashboard_service.py
│   │       └── detection_service.py
│   │
│   ├── api/
│   │   └── routes/                 # FastAPI REST endpoints
│   │
│   ├── engines/
│   │   └── similarity/             # 6 similarity detection engines
│   │       ├── ast_similarity.py
│   │       ├── winnowing_similarity.py
│   │       ├── codebert_similarity.py
│   │       ├── execution_similarity.py
│   │       ├── ngram_similarity.py
│   │       └── token_similarity.py
│   │
│   ├── features/                   # Feature extraction
│   ├── scoring/                    # Fusion scoring and ML logic
│   ├── infrastructure/             # Database, logging, report generation
│   │   ├── report_generator.py
│   │   └── database/
│   ├── evaluation/                 # Online metrics
│   ├── evaluation_lab/             # Offline optimization
│   ├── evaluation_dataset/         # Training data generation
│   └── web_gui.py                  # Web interface entry point
│
├── tests/
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── fixtures/                   # Test data
│
├── benchmark/                      # Benchmark runners (BigCloneBench, etc.)
├── datasets/                       # Datasets for training/evaluation
├── ml/                             # ML training (threshold optimizer)
├── tools/                          # External tool integrations
├── scripts/                        # Utility scripts
├── artifacts/                      # Generated output files
├── reports/                        # Generated reports
├── uploads/                        # Temporary upload directory
├── alembic/                        # Database migrations
├── docker/                         # Docker configuration
├── docs/                           # Documentation
├── .codex/                         # Codex/AI configuration
├── .kilo/                          # Kilo configuration
├── venv/                           # Python virtual environment
├── .ai-rules.md                    # AI coding rules
├── .cursorrules                    # Cursor IDE rules
├── .kilocoderc                     # Kilo Code rules
├── AGENTS.md                       # Kilo working agreements
├── README.md                       # Project documentation
├── requirements.txt                # Core dependencies
├── requirements-gpu.txt            # GPU dependencies
├── requirements-gui.txt            # GUI dependencies
├── docker-compose.yml              # Docker compose
├── Dockerfile                      # Docker image
├── alembic.ini                     # Alembic config
└── LICENSE                         # License file
```

## Key File Locations

### Core Detection
- Similarity engines: `src/engines/similarity/`
- Detection orchestration: `src/application/services/`
- Scoring logic: `src/scoring/`

### API & Web
- REST endpoints: `src/api/routes/`
- Web interface: `src/web_gui.py`

### Infrastructure
- Database: `src/infrastructure/database/`
- Report generation: `src/infrastructure/report_generator.py`
- Logging: `src/infrastructure/logging/`

### Testing
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Benchmarks: `benchmark/`
