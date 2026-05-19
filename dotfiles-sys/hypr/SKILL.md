---
name: hyprland-v0.55-rules
description: Fixes and updates Hyprland configurations for v0.55+, focusing on the Lua migration and stricter Hyprlang syntax.
---

# Hyprland v0.55+ Configuration & Rules

This skill helps migrate Hyprland configurations from the deprecated Hyprlang (`.conf`) format to the new Lua (`.lua`) format introduced in v0.55, and addresses stricter syntax rules.

## Triggers
- User is on Hyprland v0.55 or newer.
- User wants to migrate `hyprland.conf` to `hyprland.lua`.
- User reports "deprecated syntax" warnings or configuration errors.
- User needs to update window rules or dispatchers.

## Procedural Fixes

### 1. Lua Migration (Recommended)
Hyprland v0.55 defaults to `~/.config/hypr/hyprland.lua`. 
- **Structure**: Use the `hl` global and `hl.config({})` table.
- **Window Rules**: Use `hl.window_rule({ match = { ... }, ... })`.

**Example Conversion**:
- **Old (.conf)**: `windowrule = float 1, match:class ^(kitty)$`
- **New (.lua)**:
```lua
hl.window_rule({
    match = { class = "^(kitty)$" },
    float = true
})
```

### 2. Stricter Hyprlang (Legacy .conf)
If remaining on `.conf` (deprecated), several rules are now stricter:
- **Boolean Flags**: Must use `1`, `on`, `true`, or `0`, `off`, `false`.
    - `windowrule = float 1, match:class ...`
- **Unified Rules**: `windowrulev2` is deprecated. Use `windowrule` with `match:` prefixes.
    - `windowrule = float 1, match:class ^(kitty)$, match:title ^(kitty)$`

### 3. Dispatcher Updates
The long-deprecated `togglesplit` and `swapsplit` dispatchers are **removed**.
- **Old**: `bind = SUPER, P, togglesplit`
- **New**: `bind = SUPER, P, layoutmsg, togglesplit`

### 4. Relocated Options
- **Layout**: `dwindle:pseudotile` and other layout-specific settings are now under a unified `layout` section.
- **VFR**: `misc:vfr` has moved to `debug:vfr`.
- **Shadows**: `decoration:shadow:ignore_window` is removed (defaults to enabled).

### 5. Opacity Rules
Opacity rules require explicit values for active, inactive, and fullscreen in Hyprlang.
- **New**: `windowrule = opacity 0.8 0.8 1, match:class ^(my-app)$`

## Common Pitfalls
- **File Precedence**: If both `hyprland.lua` and `hyprland.conf` exist, `.lua` takes precedence.
- **Lua Syntax**: Ensure you are using correct Lua table syntax (commas between fields, curly braces).
- **Global `hl`**: Remember to `local hl = require("hyprland")` at the top of your Lua config.

## Verification
1. Run `hyprctl configerrors` to check for syntax errors.
2. For Lua, check `hyprctl messages` for any Lua execution errors.
3. Use LSP stubs in `/usr/share/hypr/stubs/` for editor feedback.
