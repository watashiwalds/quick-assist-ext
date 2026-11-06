#!/bin/sh
# Sao lưu PostgreSQL hằng ngày (H04): pg_dump dạng custom, nén, giữ BACKUP_KEEP_DAYS ngày.
# Khôi phục: docs/deploy/runbook.md §6.
set -eu
ts=$(date -u +%Y%m%dT%H%M%SZ)
out="/backups/quickassist_${ts}.dump"
pg_dump --format=custom --no-owner --file="${out}.partial"
mv "${out}.partial" "${out}"
find /backups -name 'quickassist_*.dump' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
echo "{\"event\":\"backup_done\",\"file\":\"${out}\",\"bytes\":$(wc -c < "${out}")}"
