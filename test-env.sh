#!/bin/bash
set -e

echo "Testing environment loading:"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env.local"

if [ -f "$ENV_FILE" ]; then
    echo "Found .env.local"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ''|\#*)
                continue
                ;;
        esac
        echo "Read: $line"
        export "$line"
    done < "$ENV_FILE"
fi

echo ""
echo "Resulting env:"
echo "DATABASE_URL=$DATABASE_URL"
echo "DATABASE_URL length=${#DATABASE_URL}"
echo ""

source venv/bin/activate
python -c "import os; print('Python sees DATABASE_URL:', repr(os.environ.get('DATABASE_URL'))); from src.backend.config.database import DATABASE_URL; print('Config value:', repr(DATABASE_URL))"
