# Objective: Fix invalid Hyprland monitor syntax

### 🔎 DIAGNOSTIC / SANITY CHECK
```bash
# Verify current Hyprland monitor configuration
hyprctl monitors -j | jq
```

### ⚠️ DANGER: SYSTEM MODIFICATION
```bash
# BACKUP HYPRLAND CONFIGURATION
cp ~/.config/hypr/hyprland.conf ~/.config/hypr/hyprland.conf.bak_$(date +%s)
```

### 🛠️ EXECUTION
```bash
# Dynamically identify the main monitor and fix the invalid mirror configuration
MAIN_MONITOR=$(hyprctl monitors -j | jq -r '.[0].name')
sed -i "s/monitor = ,preferred,auto,auto,mirror,HDMI-A-1/monitor = HDMI-A-1,preferred,auto,1,mirror,${MAIN_MONITOR}/g" ~/.config/hypr/hyprland.conf
# Verify configuration
hyprctl reload
```

### 📝 ROOT CAUSE / RATIONALE
*   The 'mirror' option in Hyprland's `monitor` configuration requires a specific positional argument syntax, which the previous configuration failed to satisfy.
*   The fix updates the syntax to follow the mandatory `monitor = <name>, <resolution>, <position>, <scale>, mirror, <source>` structure and dynamically identifies the source monitor.
