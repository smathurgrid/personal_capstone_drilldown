#!/usr/bin/env bash
# Gate G6 smoke — unified API regression (mock-friendly)
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
TMP="${TMPDIR:-/tmp}/drilldown-smoke.png"

echo "== DrillDown unified smoke (G6) =="
echo "BASE=$BASE"

echo "[1/7] Global health..."
curl -sf "$BASE/api/health" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok', d; print('  stage', d.get('stage'))"

echo "[2/7] Ecommerce health..."
curl -sf "$BASE/api/ecommerce/health" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok', d"

echo "[3/7] Vision health..."
VISION_CHECKS=$(curl -sf "$BASE/api/explainer/vision/health")
echo "$VISION_CHECKS" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok', d; c=d.get('checks',{}); print('  sam2_available:', c.get('sam2_available')); print('  default_grounding:', c.get('default_grounding_mode'))"

echo "[4/7] Generate health..."
curl -sf "$BASE/api/explainer/generate/health" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok', d"

echo "[5/7] Sid generate-from-text..."
curl -sf -X POST "$BASE/api/explainer/generate/generate-from-text" \
  -H "Content-Type: application/json" \
  -d '{"topic":"smoke test turbine"}' | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'image_b64' in d, d; print('  image_b64 length', len(d['image_b64']))"

echo "[6/7] Vision upload..."
python3 -c "from PIL import Image; Image.new('RGB',(64,64),(30,60,120)).save('$TMP')"

UPLOAD_JSON=$(curl -sf -X POST "$BASE/api/explainer/vision/upload" -F "file=@$TMP")
PAGE_ID=$(echo "$UPLOAD_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "  page_id=$PAGE_ID"

echo "[7/7] Vision drill stream (visionModel=none, red_ring)..."
curl -sf -N -X POST "$BASE/api/explainer/vision/stream-page" \
  -H "Content-Type: application/json" \
  -d "{\"parentId\":\"$PAGE_ID\",\"x\":0.5,\"y\":0.5,\"visionModel\":\"none\",\"groundingMode\":\"red_ring\"}" \
  | python3 -c "
import sys
text = sys.stdin.read()
assert 'event: complete' in text or 'event: error' in text, text[:500]
if 'event: error' in text and 'event: complete' not in text:
    raise SystemExit('stream-page returned error: ' + text[:300])
print('  stream events OK')
"

rm -f "$TMP"
echo ""
echo "All smoke checks passed."
