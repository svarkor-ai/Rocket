#!/usr/bin/env bash
# Night scan pipeline:
# 1. Split universe into batches
# 2. Scan each batch (sequential, to avoid rate limits)
# 3. Aggregate results → top 10 report
# 4. Send to Telegram via curl (env vars set in cron env)

set -euo pipefail
cd "$(dirname "$0")/.."

LOG="/tmp/night_scan.log"
echo "" > "$LOG"
log() { echo "$(date -u '+%H:%M:%S') $*" | tee -a "$LOG"; }

log "Night scan started"

# Step 1: Split universe
log "Step 1: Splitting universe..."
python scripts/split_universe.py --batch-size 2500 --output data/batches
NUM_BATCHES=$(python -c "import json; print(json.load(open('data/batches/metadata.json'))['num_batches'])")
log "  Split into $NUM_BATCHES batches"

# Step 2: Scan each batch sequentially
log "Step 2: Scanning batches..."
for i in $(seq 0 $((NUM_BATCHES - 1))); do
    BATCH="data/batches/batch_$(printf '%04d' $i).json"
    if [ -f "$BATCH" ]; then
        log "  Scanning batch $i..."
        python scripts/scan_batch.py --batch "$BATCH" --batch-id "$i" --delay 1.5
    fi
done
log "  All batches scanned"

# Step 3: Aggregate
log "Step 3: Aggregating results..."
python scripts/aggregate_results.py --top 10 --output results.json --report report.txt
log "  Report saved"

# Step 4: Send to Telegram via curl (env vars set in cron env)
log "Step 4: Sending to Telegram..."
if [ -n "${BOT_TOKEN:-}" ] && [ -n "${CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "parse_mode=Markdown" \
        -d "disable_web_page_preview=true" \
        -d "$(cat report.txt)" \
        -o /dev/null 2>/dev/null && log "  Sent to Telegram" || log "  Telegram send failed"
else
    log "  Skipping Telegram (env vars not set)"
fi

log "Night scan complete — see $LOG"
