# AI Prompt Templates for IntegrityDesk

## Quick Start Prompts

### Basic Task
```
Read .ai-rules.md and .cursorrules before making any changes.
```

### New Feature
```
Read .ai-rules.md and .cursorrules before starting.
Implement a new feature in IntegrityDesk: [describe feature]
Follow all rules in .ai-rules.md
```

### Bug Fix
```
Read .ai-rules.md and .cursorrules before starting.
Fix bug in IntegrityDesk: [describe bug]
Follow all rules in .ai-rules.md including error handling and testing
```

### Code Review
```
Read .ai-rules.md and .cursorrules
Review my recent changes for this commit: [describe changes]
Check for: type hints, error handling, no hardcoded values, security issues, test coverage
```

---

## Full Prompt (Copy & Paste)

```
You are working on IntegrityDesk, a software similarity detection service.

IMPORTANT: Read these files before starting ANY task:
- .ai-rules.md (coding rules and standards)
- .cursorrules (IDE configuration)
- PROJECT_STRUCTURE.md (folder organization)

Follow all rules in .ai-rules.md including:
- Type hints for all functions
- Error handling with proper exceptions
- No hardcoded values (use config)
- Unit tests for new code
- Docstrings for all public functions
- Security: validate all input, prevent path traversal
- Performance: use async/await for I/O, cache expensive operations

Task: [YOUR TASK HERE]
```

---

## Short Prompt (For Quick Tasks)

```
Before starting: Read .ai-rules.md and follow all coding rules.

Task: [YOUR TASK]
```

---

## Kilo Code Specific Setup

To make Kilo Code follow these rules by default, you can add this to your workspace settings or create a custom instruction file. Ask me to help configure automatic rule enforcement.
