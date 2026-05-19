#!/bin/bash
set -euo pipefail

# Load configuration
source /etc/my_backup/backup_config.sh

log_message "--- Starting Daily Home Directory Backup ---"

DATE_FORMAT=$(date '+%Y-%m-%d_%H%M%S')
CURRENT_BACKUP_DIR="${BACKUP_DIR}/home_daily/${DATE_FORMAT}"
TMP_EXCLUDE_FILE="/tmp/home_exclude_list.txt"
LAST_BACKUP_DIR=$(find "${BACKUP_DIR}/home_daily/" -maxdepth 1 -name "*-*-*_*_*" -type d | sort -r | head -n 1)

# Create common exclude file
# Note: rsync exclude patterns are relative to the source directory being copied (i.e., /home/)
printf "%s\n" "${HOME_COMMON_EXCLUDES[@]}" > "$TMP_EXCLUDE_FILE"

# Find and add files larger than 6GB to the exclude list
log_message "Searching for files > 6GB in /home to exclude..."
# -size +6G means files strictly greater than 6GB. Use +6000M for roughly 6GB, or +6291456k
sudo find /home -type f -size +6G -print | sed "s|^/home/||" >> "$TMP_EXCLUDE_FILE"

# Pre-check: Ensure destination directory exists
if [ ! -d "$(dirname "$CURRENT_BACKUP_DIR")" ]; then
    log_message "Error: Backup destination directory $(dirname "$CURRENT_BACKUP_DIR") does not exist."
    rm -f "$TMP_EXCLUDE_FILE"
    exit 1
fi

log_message "Creating home directory backup to: ${CURRENT_BACKUP_DIR}"

# rsync command:
# -a: Archive mode (recursive, preserves symlinks, permissions, ownership, timestamps)
# -H: Hard-link unchanged files
# -v: Verbose output
# --delete: Delete extraneous files from dest dirs (if they don't exist in source)
# --link-dest: Hard-link to files in LAST_BACKUP_DIR if they are unchanged
# --exclude-from: Read exclude patterns from a file
# /home/: Source directory (trailing slash means copy contents of /home)
# ${CURRENT_BACKUP_DIR}: Destination directory
RSYNC_CMD="sudo rsync -aHv --delete --exclude-from=\"$TMP_EXCLUDE_FILE\""

if [ -n "$LAST_BACKUP_DIR" ]; then
    log_message "Linking to previous backup: ${LAST_BACKUP_DIR}"
    RSYNC_CMD+=" --link-dest=\"$LAST_BACKUP_DIR\""
else
    log_message "No previous backup found to link from. Performing full copy."
fi

# Execute rsync
eval "$RSYNC_CMD /home/ \"$CURRENT_BACKUP_DIR\""

if [ $? -eq 0 ]; then
    log_message "Daily home directory backup completed successfully."
else
    log_message "Error: Daily home directory backup failed."
    rm -f "$TMP_EXCLUDE_FILE"
    exit 1
fi

# Cleanup old backups
log_message "Cleaning up old daily home backups (keeping ${MAX_DAILY_HOME_BACKUPS})."
find "${BACKUP_DIR}/home_daily/" -maxdepth 1 -name "*-*-*_*_*" -type d \
    | sort -r \
    | tail -n +$((MAX_DAILY_HOME_BACKUPS + 1)) \
    | xargs -r rm -rv >> "$LOG_FILE" 2>&1

log_message "--- Daily Home Directory Backup Finished ---"

rm -f "$TMP_EXCLUDE_FILE"
