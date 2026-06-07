# Gemini Context & Instructions: System Maintenance Backup Scripts

This directory contains utility shell scripts for system-level and user home-level backups.

---

## Project Overview

The project is a lightweight **Bash Shell Utility Suite** designed for local system backups using standard Linux utilities, primarily `rsync`.

### Key Technologies
*   **Language:** Bash (`/bin/bash`)
*   **Core Utilities:** `rsync` (for file copying, diff-tracking, and speed), `find`/`xargs` (for automated rotational cleanup), `mkdir`, `date`.

### Architecture & Scripts

1.  **`backup_full_weekly.sh`**
    *   **Purpose:** Performs a full system backup of the root directory (`/`), excluding dynamic directories and `/home/*`.
    *   **Destination:** `/mnt/full_system_backups/<YYYY-MM-DD>`
    *   **Retention Policy:** Keeps the last 4 weekly backups.
    *   **Permissions:** Requires administrative (`root` / `sudo`) privileges because it accesses system-restricted root files.

2.  **`backup_home_daily.sh`**
    *   **Purpose:** Performs a daily backup of the current user's home directory (`$HOME`), excluding transient caches, dependency registries (e.g., `.npm`, `.cargo`), and build targets.
    *   **Destination:** `/mnt/home_backups/<YYYY-MM-DD>`
    *   **Retention Policy:** Keeps the last 3 daily backups.
    *   **Permissions:** Run with the standard user's permissions.

---

## Building and Running

Since this is a collection of interpreted shell scripts, there is no build step.

### Running the Scripts

1.  **Make executable:**
    Before running, ensure both scripts have execute permissions:
    ```bash
    chmod +x backup_full_weekly.sh
    chmod +x backup_home_daily.sh
    ```

2.  **Run Weekly Full Backup (Requires sudo):**
    ```bash
    sudo ./backup_full_weekly.sh
    ```

3.  **Run Daily Home Backup:**
    ```bash
    ./backup_home_daily.sh
    ```

### Testing & Dry-Running

To test changes to the scripts without actually writing files or modifying existing backups:
*   Pass the `--dry-run` (or `-n`) option directly to `rsync` inside the scripts.
*   Example modification in the `rsync` command line for testing:
    ```bash
    eval "rsync -aP --dry-run --delete -x $EXCLUDE_ARGS '/' '$DESTINATION'"
    ```

---

## Development and Configuration Conventions

When extending or maintaining these scripts, please adhere to the following conventions:

### Configuration Top-Section
All configuration parameters must be located at the top of the scripts for readability and easy modification:
*   `BACKUP_DIR`: Path to the backup destination mount point or directory.
*   `MAX_BACKUPS`: Number of historical runs to retain.
*   `EXCLUDES`: An array of file/folder path glob patterns to ignore.

### Exclusion Array
*   In `backup_home_daily.sh`, the `EXCLUDES` array defines the list of directories/files under `$HOME` to skip (such as transient caches, virtual environments, build directories, and dotfiles).
*   Always ensure all double quotes within array elements are properly opened and closed to avoid shell syntax/EOF parsing errors.

### Rotation Mechanism
Retention of old backups is managed automatically via chronological directory names using the `YYYY-MM-DD` pattern. Rotation uses:
```bash
find "$BACKUP_DIR" -maxdepth 1 -type d -name "*-*-*" | sort -r | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -rf
```
When introducing new script types, ensure they follow this specific format to prevent accidental deletion of unrelated directories.

### Safety Checks
*   Always verify if the backup directory exists or can be created before starting `rsync` using `mkdir -p "$BACKUP_DIR" || { exit 1; }`.
*   Always preserve flags:
    *   `-a` (archive mode) to retain permissions, ownership, and timestamps.
    *   `-P` to support resuming and see copy progress.
    *   `--delete` to ensure backups stay mirrored and clean.
    *   `-x` (for system root backups) to prevent crossing filesystem boundaries into other mounted drives.
