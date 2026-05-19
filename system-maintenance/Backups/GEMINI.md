# System Maintenance & Backups

This directory contains a suite of scripts and documentation for managing system-level and home directory backups on an Arch Linux system. It provides two main backup strategies: a weekly full system snapshot and a daily incremental home directory backup.

## Project Structure

- `scripts/`: Contains the primary, standalone backup scripts.
    - `backup_full_weekly.sh`: Performs a weekly full system backup using `rsync` with specific system exclusions.
    - `backup_home_daily.sh`: Performs a daily backup of the `$HOME` directory with user-defined exclusions and rotation.
- `my_backup/`: Contains an alternative, more modular backup implementation and detailed documentation.
    - `README.md`: A comprehensive guide on the backup strategy, configuration, scheduling (cron), and restoration procedures.
    - `backup_config.sh`: Central configuration file (intended to be placed in `/etc/my_backup/`).
    - `daily_home_backup.sh`: Advanced daily home backup using `rsync` with hard-linking (`--link-dest`) for space efficiency and 6GB+ file exclusion.
    - `weekly_full_system_backup.sh`: Full system backup using `tar` with compression.

## Backup Strategies

### 1. Weekly Full System Backup
- **Goal:** Create a restorable snapshot of the entire root filesystem.
- **Implementation:** 
    - `scripts/backup_full_weekly.sh` uses `rsync`.
    - `my_backup/weekly_full_system_backup.sh` uses `tar` with `xz` compression.
- **Key Exclusions:** `/dev`, `/proc`, `/sys`, `/tmp`, `/run`, `/mnt`, `/media`, `/var/cache`, and `/var/tmp`.

### 2. Daily Home Directory Backup
- **Goal:** Daily incremental backups of user data.
- **Implementation:** 
    - `scripts/backup_home_daily.sh` uses `rsync` with simple rotation.
    - `my_backup/daily_home_backup.sh` uses `rsync` with `--link-dest` for extremely space-efficient incrementals (hard-linking unchanged files).
- **Features:** Excludes large files (e.g., > 6GB), cache directories, and temporary files.

## Setup and Usage

### Configuration
Most scripts rely on hardcoded paths or a central config.
- **Standalone Scripts:** Edit `BACKUP_DIR` and `EXCLUDES` directly in `scripts/backup_home_daily.sh` and `scripts/backup_full_weekly.sh`.
- **Modular Scripts:** Edit `my_backup/backup_config.sh` (intended to be sourced from `/etc/my_backup/backup_config.sh`).

### Running Backups
Scripts must typically be run with `sudo` to ensure access to system files and correct permission preservation.

```bash
# Example manual execution
sudo ./scripts/backup_home_daily.sh
sudo ./scripts/backup_full_weekly.sh
```

### Automation (Cron)
Backups are intended to be scheduled via `root`'s crontab. Example:

```cron
# Weekly Full System (Sundays at 3 AM)
0 3 * * 0 /path/to/weekly_full_system_backup.sh >> /var/log/my_backup.log 2>&1

# Daily Home (Every day at 2 AM)
0 2 * * * /path/to/daily_home_backup.sh >> /var/log/my_backup.log 2>&1
```

## Restoration
Detailed restoration instructions, including restoring from a Live USB and fixing `fstab`/`grub`, can be found in `my_backup/README.md`.

## Development Conventions
- **Scripting:** Bash scripts with `set -euo pipefail` (in modular versions) for robustness.
- **Exclusions:** Systematic exclusion of ephemeral and mount-point data to prevent recursive or bloated backups.
- **Logging:** Basic logging to stdout/stderr, often redirected to `/var/log/my_backup.log`.
