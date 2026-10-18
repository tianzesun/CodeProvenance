#!/usr/bin/env bash
# Check whether the AI detector's Binoculars layer can load on this host.
# Run on the GPU server: bash scripts/check-binoculars.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== 1. Environment ==="
grep -E "^BINOCULARS_ENABLED" src/backend/.env.local 2>/dev/null || echo "BINOCULARS_ENABLED not set (defaults to 1 = enabled)"
grep -E "^HF_HOME" src/backend/.env.local 2>/dev/null || echo "HF_HOME not set (defaults to ~/.cache/huggingface)"

echo ""
echo "=== 2. HF cache (models must be present offline) ==="
HF_DIR="${HF_HOME:-$HOME/.cache/huggingface}"
echo "HF cache dir: $HF_DIR"
for model in models--Qwen--Qwen2.5-0.5B models--Qwen--Qwen2.5-0.5B-Instruct; do
    path="$HF_DIR/hub/$model"
    if [ -d "$path" ]; then
        size=$(du -sh "$path" 2>/dev/null | cut -f1)
        echo "  FOUND: $model ($size)"
    else
        echo "  MISSING: $model"
    fi
done

echo ""
echo "=== 3. CUDA + memory ==="
source venv/bin/activate 2>/dev/null || true
python3 - <<'PYEOF'
try:
    import torch
    print(f"  torch: {torch.__version__}")
    print(f"  cuda_available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  device: {torch.cuda.get_device_name(0)}")
        free, total = torch.cuda.mem_get_info()
        print(f"  vram: {free / 1e9:.1f} GB free / {total / 1e9:.1f} GB total")
except ImportError:
    print("  torch: not installed")
PYEOF

echo ""
echo "=== 4. Memory headroom ==="
free -h | awk '/^Mem:/ {printf "  %s total, %s available\n", $2, $7}'

echo ""
echo "=== 5. Binoculars load test ==="
python3 - <<'PYEOF'
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # fail fast if models missing
from src.backend.engines.ai.binoculars_detector import BinocularsDetector
d = BinocularsDetector()
ok = d.is_available()
print(f"  Binoculars loads: {ok}")
if ok:
    r = d.analyze("def add(a, b):\n    return a + b\n" * 20)
    print(f"  test score: {r['ai_probability']}  calibrated: {r.get('calibrated')}")
else:
    print("  -> models missing or load failed; see warning above")
PYEOF
