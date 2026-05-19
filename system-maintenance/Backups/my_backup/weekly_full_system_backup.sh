#!/bin/bash
set -euo pipefail # Exit immediately if a command exits with a non-zero status, fail on unset variables, pipefail

# Load configuration
source /etc/my_backup/backup_config.sh

log_message "--- Starting Weekly Full System Backup ---"

DATE_FORMAT=$(date '+%Y-%m-%d_%H%M%S')
BACKUP_PATH="${BACKUP_DIR}/system_weekly/${DATE_FORMAT}.tar.xz"
TMP_EXCLUDE_FILE="/tmp/system_exclude_list.txt"

# Create temporary exclude file
printf "%s\n" "${SYSTEM_EXCLUDES[@]}" > "$TMP_EXCLUDE_FILE"

# Pre-check: Ensure destination directory exists
if [ ! -d "$(dirname "$BACKUP_PATH")" ]; then
    log_message "Error: Backup destination directory $(dirname "$BACKUP_PATH") does not exist."
    rm -f "$TMP_EXCLUDE_FILE"
    exit 1
fi

log_message "Creating full system backup to: ${BACKUP_PATH}"

# tar command:
# -c: Create an archive
# -v: Verbose output (can be removed if you don't want detailed log)
# -p: Preserve permissions
# -J: Use xz compression (better compression than gzip, but slower)
# -f: Archive file name
# --one-file-system: Stay on the current filesystem (don't cross mount points)
# --exclude-from: Read exclude patterns from a file
# /: The root directory to backup
if sudo tar -cvpJ \
    --one-file-system \
    --exclude-from="$TMP_EXCLUDE_FILE" \
    -f "$BACKUP_PATH" /; then
    log_message "Weekly full system backup completed successfully."
else
    log_message "Error: Weekly full system backup failed."
    rm -f "$TMP_EXCLUDE_FILE"
    exit 1
fi

# Cleanup old backups
log_message "Cleaning up old weekly backups (keeping ${MAX_WEEKLY_BACKUPS})."
find "${BACKUP_DIR}/system_weekly/" -maxdepth 1 -name "*.tar.xz" -type f \
    | sort -r \
    | tail -n +$((MAX_WEEKLY_BACKUPS + 1)) \
    | xargs -r rm -v >> "$LOG_FILE" 2>&1

log_message "--- Weekly Full System Backup Finished ---"

rm -f "$TMP_EXCLUDE_FILE"
