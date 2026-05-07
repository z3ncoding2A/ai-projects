#!/bin/bash

# Configuration
BACKUP_DIR="/mnt/1/full_system_backups"
MAX_BACKUPS=4 # 4 weekly restore points
EXCLUDES=(
    "/dev/*"
    "/proc/*"
    "/sys/*"
    "/tmp/*"
    "/run/*"
    "/mnt/*" # Exclude the mount point itself to prevent recursive backups
    "/sys/fs/cgroup/*"
    "/var/tmp/*"
    "/var/cache/*" # Can be very large, generally safe to exclude for system rollback
    "/var/log/*"   # Can be very large, generally safe to exclude for system rollback
    "/lost+found"
	"/home/*"
    "/home/z3ncoding123/.gemini/projects/system-maintenance/Backups/*" # Exclude backup scripts and data
    "/home/z3ncoding123/.gemini/tmp/*" # Exclude gemini's temporary directory
)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR" || { echo "Error: Could not create backup directory $BACKUP_DIR"; exit 1; }

# Get current date for backup folder name
CURRENT_DATE=$(date +%Y-%m-%d)
DESTINATION="$BACKUP_DIR/$CURRENT_DATE"

echo "Starting weekly full system backup to $DESTINATION..."

# Build rsync exclude arguments
EXCLUDE_ARGS=""
for i in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS+="--exclude='$i' "
done

# Perform backup using rsync
# -a: archive mode (preserves permissions, ownership, timestamps, etc.)
# -x: don't cross filesystem boundaries (important for full system backup)
# -P: --partial --progress (shows progress and allows resuming)
# --delete: deletes extraneous files from dest dirs (useful for keeping backup clean)
# --info=progress2: more granular progress info
# Note: no trailing slash on "/" source to backup the root directory itself.
eval "rsync -aP --delete -x $EXCLUDE_ARGS '/' '$DESTINATION'"

if [ $? -eq 0 ]; then
    echo "Full system backup completed successfully."
else
    echo "Full system backup failed!"
    exit 1
fi

# Rotation: Remove old backups
echo "Performing backup rotation. Keeping last $MAX_BACKUPS weeks."
find "$BACKUP_DIR" -maxdepth 1 -type d -name "*-*-*" | sort -r | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -rf

echo "Weekly full system backup script finished."
