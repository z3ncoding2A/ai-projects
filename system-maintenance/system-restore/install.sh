#!/bin/bash
# Install script for sys-restore utility

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. (e.g. sudo ./install.sh)" 
   exit 1
fi

echo "Installing sys-restore..."

# Install main script
install -Dm755 sys-restore.sh /usr/local/bin/sys-restore

# Install configuration file (do not overwrite if it already exists to preserve user settings)
if [[ ! -f /etc/sys-restore.conf ]]; then
    install -Dm644 sys-restore.conf /etc/sys-restore.conf
    echo "Installed default configuration to /etc/sys-restore.conf"
else
    echo "Configuration file /etc/sys-restore.conf already exists. Skipping..."
fi

# Install systemd service
install -Dm644 sys-restore.service /etc/systemd/system/sys-restore.service

# Reload and enable
systemctl daemon-reload
systemctl enable sys-restore.service

echo "Installation complete!"
echo "The sys-restore service is enabled to run on boot."
echo "You can trigger a manual backup anytime by running: sudo sys-restore"
