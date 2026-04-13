---
description: Start development server
agent: code
---
Start the FastAPI development server using project virtual environment.

source /home/tsun/Documents/CodeProvenance/venv/bin/activate && \
uvicorn src.web_gui:app --host 0.0.0.0 --port 8000 --reload
