#!/bin/bash
# sys-restore: Rsync-based system restore utility

CONFIG_FILE="/etc/sys-restore.conf"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

source "$CONFIG_FILE"

# Function to perform backup
perform_backup() {
    local source_dir=$1
    local dest_parent=$2
    local max_snapshots=$3
    local prefix=$4

    # Ensure snapshot directory exists
    if ! mkdir -p "$dest_parent"; then
        echo "Error: Failed to create snapshot directory $dest_parent"
        return 1
    fi

    # Get current date for the snapshot name
    local timestamp=$(date +%Y-%m-%d_%H-%M-%S)
    local dest_dir="${dest_parent}/${prefix}_${timestamp}"
    
    # Find the most recent snapshot for --link-dest
    local latest_snapshot=$(ls -1d ${dest_parent}/${prefix}_* 2>/dev/null | sort | tail -n 1)

    local rsync_opts=(
        -aAX
        --delete
        --numeric-ids
    )

    for excl in "${EXCLUSIONS[@]}"; do
        rsync_opts+=(--exclude="$excl")
    done

    # If a previous snapshot exists, use it to hardlink unchanged files
    if [[ -n "$latest_snapshot" && -d "$latest_snapshot" ]]; then
        rsync_opts+=(--link-dest="$latest_snapshot")
    fi

    echo "Creating snapshot: $dest_dir"
    
    # Run rsync
    rsync "${rsync_opts[@]}" "$source_dir/" "$dest_dir/"
    
    local rsync_exit=$?
    if [[ $rsync_exit -ne 0 && $rsync_exit -ne 24 ]]; then
        # 24 is a common non-fatal rsync error (vanished files during sync)
        echo "Warning: rsync completed with exit code $rsync_exit"
    fi

    # Update mtime of the newly created directory so it reflects the creation time correctly
    touch "$dest_dir"

    # Prune old snapshots
    local snapshots=($(ls -1d ${dest_parent}/${prefix}_* 2>/dev/null | sort))
    local count=${#snapshots[@]}

    if (( count > max_snapshots )); then
        local num_to_delete=$(( count - max_snapshots ))
        for (( i=0; i<num_to_delete; i++ )); do
            echo "Deleting old snapshot: ${snapshots[$i]}"
            rm -rf "${snapshots[$i]}"
        done
    fi
}

echo "Starting system restore backup process..."

# Ensure /mnt is mounted if SNAPSHOT_DIR is configured under /mnt, preventing root partition exhaustion
if [[ "$SNAPSHOT_DIR" == "/mnt"* ]]; then
    if ! findmnt -M "/mnt" >/dev/null 2>&1; then
        echo "Error: /mnt is not mounted! Aborting to prevent root filesystem exhaustion."
        exit 1
    fi
fi

if [[ "$BACKUP_ROOT" == "yes" ]]; then
    echo "Processing root (/) backup..."
    perform_backup "/" "$SNAPSHOT_DIR/root" "$MAX_ROOT_SNAPSHOTS" "root"
fi

echo "Backup process completed."
