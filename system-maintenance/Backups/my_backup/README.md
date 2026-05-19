It sounds like you've hit a common frustration point with snapshot tools when the underlying filesystem or setup isn't perfectly aligned with their expectations. Building your own solution with `tar` and `rsync` gives you much more control and flexibility.

The core idea will be:
*   **Weekly Full System:** A compressed `tar` archive of your entire root filesystem (excluding non-essential temporary/cache files). This will be a complete snapshot.
*   **Daily Home Directory:** `rsync` with hardlinks to create incremental backups of your `/home` directory. This is incredibly space-efficient as unchanged files are hardlinked to the previous day's backup, consuming almost no extra space, but each backup *appears* to be a full copy. We'll also implement the 6GB exclusion.
*   **Scheduling:** `cron` will be used for automation.

---

### **Important Considerations Before You Start:**

1.  **Backup Destination:** Where will these backups be stored?
    *   **Strongly Recommended:** A *separate physical drive* (external USB HDD/SSD) or a network share. If your main drive fails, having backups on the same drive is useless.
    *   **Minimum:** A separate partition on the same drive.
    *   **For this guide:** We'll assume a path like `/mnt/backup_drive/my_arch_backups`. **Adjust `BACKUP_DIR` in the config accordingly.**
2.  **Root Privileges:** These scripts need to run as `root` to properly back up system files and preserve permissions/ownership.
3.  **Testing Restore:** A backup is only as good as its restore. **YOU MUST TEST THE RESTORE PROCESS AT LEAST ONCE** (preferably in a virtual machine or on a non-critical system) to ensure you understand it and that your backups are viable.
4.  **`fstab` and `grub`:** For a full system restore, merely extracting a `tar` archive isn't enough. You'll likely need to reinstall GRUB and regenerate `fstab`. This guide will provide instructions for that.

---

### **Step 1: Setup the Backup Directory**

First, create the directory where your backups will live.
```bash
sudo mkdir -p /mnt/backup_drive/my_arch_backups/system_weekly
sudo mkdir -p /mnt/backup_drive/my_arch_backups/home_daily
sudo chown -R root:root /mnt/backup_drive/my_arch_backups # Ensure root owns it
```
**Remember to change `/mnt/backup_drive/` to your actual backup location.**

---

### **Step 2: Create Configuration File (`/etc/my_backup/backup_config.sh`)**

This central configuration file will make your scripts cleaner and easier to manage.

```bash
sudo mkdir -p /etc/my_backup
sudo nano /etc/my_backup/backup_config.sh
```

Paste the following content:

```bash
#!/bin/bash

# --- General Backup Settings ---
BACKUP_DIR="/mnt/backup_drive/my_arch_backups" # <<< IMPORTANT: Change this to your actual backup destination
LOG_FILE="/var/log/my_backup.log"             # Log file for all backup operations
MAX_WEEKLY_BACKUPS=4                         # Number of weekly full system backups to keep
MAX_DAILY_HOME_BACKUPS=14                    # Number of daily home backups to keep

# --- Weekly Full System Backup Exclusions ---
# Paths that should NOT be included in the full system backup.
# These are common exclusions. Add more if needed, e.g., other mount points or large data directories.
SYSTEM_EXCLUDES=(
    "/dev/*"
    "/proc/*"
    "/sys/*"
    "/tmp/*"
    "/run/*"
    "/mnt/*"
    "/media/*"
    "/lost+found/*"
    "/var/cache/*"
    "/var/tmp/*"
    "/var/log/*"
    "${BACKUP_DIR}/*" # Crucial: Don't back up the backup directory itself!
    "/swapfile"       # If you use a swapfile
    "/var/lib/docker/*" # If you use Docker and don't want to back up images/containers
    # Add any other large data directories here that you don't need in a full system restore
    # e.g., "/opt/some_big_app_data/*"
)

# --- Daily Home Directory Backup Exclusions ---
# Paths within /home that should always be excluded (e.g., caches, large downloads)
HOME_COMMON_EXCLUDES=(
    ".cache/*"
    ".thunderbird/*/cache/*"
    ".mozilla/firefox/*/cache/*"
    ".local/share/Trash/*"
    "Downloads/*" # You might want to keep Downloads, adjust as needed
    "Videos/*"
    "Music/*"
    "Pictures/*" # Adjust these large media directories based on your needs
    # Add other common user-specific large or temporary directories here
)

# --- Helper function for logging ---
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

export BACKUP_DIR LOG_FILE MAX_WEEKLY_BACKUPS MAX_DAILY_HOME_BACKUPS
export SYSTEM_EXCLUDES HOME_COMMON_EXCLUDES
export -f log_message
```
**REMEMBER TO ADJUST `BACKUP_DIR` IN THIS FILE!**

To prevent accidental modification of this file, you can make it immutable:
```bash
sudo chattr +i /etc/my_backup/backup_config.sh
```
If you need to edit it later, you'll first have to remove the immutable flag: `sudo chattr -i /etc/my_backup/backup_config.sh`.

---

### **Step 3: Create the Weekly Full System Backup Script (`/etc/my_backup/weekly_full_system_backup.sh`)**

This script will create a compressed `tar` archive of your entire system.

```bash
sudo nano /etc/my_backup/weekly_full_system_backup.sh
```

Paste the following content:

```bash
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
```

Make the script executable:
```bash
sudo chmod +x /etc/my_backup/weekly_full_system_backup.sh
```

---

### **Step 4: Create the Daily Home Directory Backup Script (`/etc/my_backup/daily_home_backup.sh`)**

This script uses `rsync` with hardlinks (`--link-dest`) for efficient incremental backups. It also includes logic to exclude files larger than 6GB.

```bash
sudo nano /etc/my_backup/daily_home_backup.sh
```

Paste the following content:

```bash
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
```

Make the script executable:
```bash
sudo chmod +x /etc/my_backup/daily_home_backup.sh
```

---

### **Step 5: Schedule with Cron**

We'll use `root`'s crontab for these tasks.

```bash
sudo crontab -e
```

Add the following lines at the end of the file:

```cron
# My Custom Backups
# Weekly Full System Backup (e.g., every Sunday at 3 AM)
0 3 * * 0 /etc/my_backup/weekly_full_system_backup.sh >> /var/log/my_backup.log 2>&1

# Daily Home Directory Backup (e.g., every day at 2 AM)
0 2 * * * /etc/my_backup/daily_home_backup.sh >> /var/log/my_backup.log 2>&1
```
*   `>> /var/log/my_backup.log 2>&1` appends all script output (stdout and stderr) to your log file, which is helpful for debugging.
*   **Adjust times (`0 3` for 3 AM, `0 2` for 2 AM) as you see fit.** Ensure they don't overlap with other demanding tasks.

Save and exit the crontab editor. Your backups will now run automatically.

---

### **Step 6: Monitoring and Testing**

*   **Check logs:** Regularly inspect `/var/log/my_backup.log` to ensure backups are running successfully and without errors.
*   **Manually run:** You can test the scripts manually:
    ```bash
    sudo /etc/my_backup/weekly_full_system_backup.sh
    sudo /etc/my_backup/daily_home_backup.sh
    ```
    Watch the output and check the backup directories.
*   **Space Usage:** Monitor the disk space used by your `BACKUP_DIR` to ensure it's not growing unexpectedly. The `rsync` with hardlinks for `/home` should be very efficient.

---

### **Restoring Your System (Crucial Steps!)**

This is the most critical part. A full system restore typically requires booting into a live Linux environment.

**A. Restoring Your Home Directory (Easy)**

If you only need to restore specific files or your entire `/home` directory:
1.  **Boot into your regular Arch system.**
2.  **Navigate to your desired backup:**
    `cd /mnt/backup_drive/my_arch_backups/home_daily/YYYY-MM-DD_HHMMSS` (replace with the date/time of the backup you want).
3.  **Copy files back:**
    *   To restore a specific file: `cp -a /path/to/backup/user/Documents/myfile.txt /home/user/Documents/`
    *   To restore your entire home directory (DANGER: this will overwrite current files):
        *   Log out of your user session, switch to a TTY (Ctrl+Alt+F2), and log in as root.
        *   `systemctl stop sddm` (or `gdm`, `lightdm`, etc., to stop your display manager)
        *   `rm -rf /home/yourusername/* /home/yourusername/.*` (BE CAREFUL with this command!)
        *   `cp -a /mnt/backup_drive/my_arch_backups/home_daily/YYYY-MM-DD_HHMMSS/yourusername/. /home/yourusername/`
        *   `chown -R yourusername:yourusername /home/yourusername`
        *   `systemctl start sddm`
        *   Reboot: `reboot`

**B. Restoring Your Full System (Advanced - Requires Live USB)**

This is for when your system is unbootable or severely corrupted.

1.  **Prepare an Arch Linux Live USB.** Boot from it.
2.  **Identify your partitions:**
    `lsblk` or `fdisk -l`
    *   Example: `/dev/sda1` for `/boot`, `/dev/sda2` for `/` (root). Adjust as needed.
3.  **Mount your target partitions:**
    ```bash
    sudo mkdir /mnt/new_root
    sudo mount /dev/sda2 /mnt/new_root # Mount your root partition
    sudo mkdir /mnt/new_root/boot
    sudo mount /dev/sda1 /mnt/new_root/boot # Mount your boot partition (if separate)
    # If you have an EFI partition:
    # sudo mkdir /mnt/new_root/boot/efi
    # sudo mount /dev/sdXN /mnt/new_root/boot/efi # Replace sdXN with your EFI partition
    ```
4.  **Mount your backup drive:**
    ```bash
    sudo mkdir /mnt/backup
    sudo mount /dev/sdXN /mnt/backup # Replace sdXN with your backup drive partition
    ```
5.  **Navigate to the desired system backup:**
    `cd /mnt/backup/my_arch_backups/system_weekly/`
    Find the `YYYY-MM-DD_HHMMSS.tar.xz` file you want to restore.

6.  **Extract the backup:**
    ```bash
    sudo tar -xvpJ --numeric-owner -f YYYY-MM-DD_HHMMSS.tar.xz -C /mnt/new_root/
    ```
    *   `--numeric-owner`: Important to preserve UIDs/GIDs correctly, especially if they differ on the live system.
    *   `-C /mnt/new_root/`: Extract into the mounted root partition.

7.  **Post-Restore Fixes (CRITICAL!):**
    *   **Verify `fstab`:**
        After extraction, your `/mnt/new_root/etc/fstab` might still point to old UUIDs or device names. You *must* check and update it to reflect the correct UUIDs of your current partitions.
        `sudo genfstab -U /mnt/new_root >> /mnt/new_root/etc/fstab` (use -U for UUIDs)
        Then *carefully* edit `/mnt/new_root/etc/fstab` to remove duplicates and ensure it's correct.
        You can find UUIDs with `lsblk -f`.
    *   **Chroot into the restored system:**
        ```bash
        sudo arch-chroot /mnt/new_root
        ```
    *   **Reinstall GRUB (and update initramfs):**
        ```bash
        grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ArchLinux --recheck # For UEFI
        # OR for BIOS:
        # grub-install --target=i386-pc /dev/sda # Replace /dev/sda with your boot drive
        grub-mkconfig -o /boot/grub/grub.cfg
        mkinitcpio -P # Rebuild initramfs images
        ```
    *   **Update users/passwords/systemd (if needed):**
        If you restored a very old backup, you might want to consider running system upgrades within the chroot or updating user passwords if any issues arise.
        `pacman -Syu` (This might be a good idea, but proceed with caution if you want to restore to an exact point.)

8.  **Exit chroot and unmount:**
    ```bash
    exit
    sudo umount -R /mnt/new_root # Unmount all partitions under /mnt/new_root
    sudo umount /mnt/backup
    ```

9.  **Reboot:**
    `reboot`
    Remove the Live USB and cross your fingers!

---

### **Further Improvements (Optional):**

*   **Checksums:** Add checksum verification (e.g., `md5sum` or `sha256sum`) to your `tar` archives and log them, so you can verify integrity before attempting a restore.
*   **Notifications:** Integrate email notifications using `mailx` or other tools to get alerted on backup failures or successes.
*   **Pre-backup checks:** Add checks for free disk space on the backup destination before starting.
*   **Compression Level:** For `tar`, `-J` (xz) is strong but slow. `-z` (gzip) is faster but less compression. For large system backups, `xz` is usually preferred for space saving.
*   **Backup Encryption:** If backing up to an external or untrusted drive, consider encrypting the backup partition (e.g., LUKS) or encrypting the `tar` archives.
*   **Btrfs/ZFS:** If you ever switch to a Btrfs or ZFS root filesystem, native snapshots are vastly superior and faster than file-based backups like `tar`/`rsync` for system-level restore points.

This setup provides a robust and flexible solution tailored to your needs. Remember, **testing the restore process is paramount!** Good luck!
