# System Restore Point Utility

This is a custom, `rsync`-based system restore utility designed specifically to replace Timeshift on Arch Linux systems, specifically addressing boot-related issues experienced with GRUB. 

It utilizes hardlinks to create exact copies of your files, meaning subsequent snapshots take very little space.

## Features
- Backs up the entire Root (`/`) filesystem (including `/home` unless excluded).
- Retains up to 3 Root snapshots (configurable).
- Automatically deletes the oldest snapshots when the limits are exceeded.
- Snapshots are fully browseable as standard directories.
- Runs automatically on system boot via a systemd `oneshot` service.
- Stores snapshots in `/mnt/snapshots`.

## Installation

Run the installation script as root to deploy the scripts, configuration, and systemd service:

```bash
sudo ./install.sh
```

## Configuration

The configuration file is installed at `/etc/sys-restore.conf`. You can edit this file to adjust the maximum number of snapshots or exclude specific directories.

## Manual Usage

To manually trigger a backup at any time, run:

```bash
sudo sys-restore
```

## How It Works

The script uses `rsync` with the `--link-dest` flag. When a backup is created, it compares the current files to the previous snapshot. Unchanged files are not duplicated; instead, a hardlink is created pointing to the existing file in the previous snapshot, saving significant disk space and time.