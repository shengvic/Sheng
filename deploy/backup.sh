#!/bin/sh
# Nightly backup, run as a Coolify Scheduled Task in the `postgres` container:
#   sh /backups/backup.sh   (copy this file into the backups volume once; see the runbook)
# Writes a database dump and an archive of uploaded documents to the `backups` volume, keeping
# 14 days. Off-site copy
# and encryption happen on the host (rclone crypt), see docs/runbooks/deploy-coolify.md.
set -eu
stamp=$(date -u +%Y%m%dT%H%M%SZ)
pg_dump -U postgres -d travo -Fc -f "/backups/travo-$stamp.dump"
# Uploaded documents and exports (already envelope-encrypted with the master key).
tar -czf "/backups/appdata-$stamp.tar.gz" -C /appdata .
find /backups \( -name 'travo-*.dump' -o -name 'appdata-*.tar.gz' \) -mtime +14 -delete
echo "backup /backups/travo-$stamp.dump done"
