#!/bin/bash

# Configuration
BACKUP_DIR="/mnt/1/home_backups"
MAX_BACKUPS=3
EXCLUDES=(
    ".cache/"
    ".local/share/Trash/"
    "Downloads/"
    "pCloudDrive/"
    ".npm/"
    ".pcloud/"
    ".cargo/registry/"
    ".git/"
    ".bash_history"
    ".zsh_history"
    "Porn/"
    "tmp/"
    "temp/"
    "node_modules/"
    "target/"
    "build/"
    "venv/"
    ".venv/"
	"Applications"
	"webui-venv"
)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR" || { echo "Error: Could not create backup directory $BACKUP_DIR"; exit 1; }

# Get current date for backup folder name
CURRENT_DATE=$(date +%Y-%m-%d)
DESTINATION="$BACKUP_DIR/$CURRENT_DATE"

echo "Starting daily $HOME backup to $DESTINATION..."

# Build rsync exclude arguments
EXCLUDE_ARGS=""
for i in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS+="--exclude='$i' "
done

# Perform backup using rsync
# -a: archive mode (preserves permissions, ownership, timestamps, etc.)
# -P: --partial --progress (shows progress and allows resuming)
# --delete: deletes extraneous files from dest dirs (useful for keeping backup clean)
# --info=progress2: more granular progress info
# --exclude-from=FILE: if we had a large list, but for now individual --exclude is fine.
# Note: trailing slash on "$HOME/" is crucial for rsync to copy contents INTO DESTINATION, not HOME directory itself.
#       No trailing slash on "$DESTINATION" because we want a directory named $CURRENT_DATE inside $BACKUP_DIR.
eval "rsync -aP --delete $EXCLUDE_ARGS '$HOME/' '$DESTINATION'"

if [ $? -eq 0 ]; then
    echo "Backup completed successfully."
else
    echo "Backup failed!"
    exit 1
fi

# Rotation: Remove old backups
echo "Performing backup rotation. Keeping last $MAX_BACKUPS days."
find "$BACKUP_DIR" -maxdepth 1 -type d -name "*-*-*" | sort -r | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -rf

echo "Daily $HOME backup script finished."
