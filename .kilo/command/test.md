---
description: Run pytest tests
agent: code
---
Run pytest tests for IntegrityDesk using project virtual environment.

source /home/tsun/Documents/CodeProvenance/venv/bin/activate && \
if [ -n "$ARGUMENTS" ]; then
  pytest $ARGUMENTS -v
else
  pytest tests/unit/ -v
fi
