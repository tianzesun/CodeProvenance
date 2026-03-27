# CodeProvenance Project Structure

```
CodeProvenance/
├── src/
│   ├── api/                 # REST API layer
│   │   ├── routes/         # API endpoints
│   │   ├── middleware/     # Request/response middleware
│   │   └── schemas/        # Request/response validation
│   ├── core/               # Core similarity detection logic
│   │   ├── parser/         # Code file parsing
│   │   ├── processor/      # Text processing & tokenization
│   │   ├── similarity/     # Similarity algorithms
│   │   └── analyzer/       # Analysis orchestration
│   ├── models/             # Data models & schemas
│   ├── utils/              # Utility functions
│   ├── config/              # Configuration management
│   └── main.py             # Application entry point
├── tests/                   # Unit and integration tests
│   ├── unit/
│   ├── integration/
│   └── fixtures/           # Test data
├── scripts/                 # Build and deployment scripts
├── docs/                    # Documentation
├── .ai-rules.md            # AI Development Rules (this file)
├── .env.example             # Environment variables template
├── pyproject.toml          # Python project configuration
└── README.md
```

## Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `src/api/` | REST API endpoints and request handling |
| `src/core/` | Core similarity detection algorithms |
| `src/models/` | Pydantic/dataclass models for data validation |
| `src/utils/` | Shared utility functions |
| `src/config/` | Configuration loading and management |
| `tests/` | All test files organized by type |
| `scripts/` | Build, deployment, and utility scripts |
| `docs/` | Project documentation |
