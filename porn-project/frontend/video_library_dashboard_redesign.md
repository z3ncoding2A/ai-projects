# Stitch & Claude Code Prompt Guide: Video Library Dashboard Redesign (10,000+ Items)

> **Generated using the Stitch Effective Prompting Guide & Claude Code Best Practices**  
> **Target Environment:** Claude Code (CLI) running Claude Opus | Frontend Architecture & UI/UX Redesign

---

## 🧭 Executive Overview & Design Intent

- **Application Type:** High-productivity desktop web application & media browser for a massive personal catalog (~10,000 items).
- **Core Utility:** Fast discovery, instant filtering, effortless categorization/tagging, zero-lag scrolling, and distraction-free viewing.
- **Design Vibe:** Modern, sleek, functional dark-mode workstation. Slate/obsidian neutrals, crisp typography, high-contrast badges, compact density options, and fluid micro-interactions. No generic neon gradients or bloated UI elements.

---

## 🚀 Part 1: The Master Initialization Prompt (Run First in Claude Code)

Use this prompt to kick off the project in Claude Code without overwhelming the model or breaking existing features.

```markdown
I am redesigning our video library dashboard (`z3ncoding_videos_grid.html` / `generate_grid.py`) to handle ~10,000 videos with workstation-level productivity and a sleek modern dark aesthetic.

Please act as a Principal Frontend Engineer and UI/UX Designer.

Before writing code:
1. Audit the existing codebase to understand how data (`videos.json`, `categories.json`, `blacklist.txt`) is loaded, filtered, and rendered.
2. Outline an architectural blueprint addressing:
   - **DOM Virtualization:** Windowed/virtual scrolling to keep DOM node count low and scroll FPS at a locked 60fps.
   - **Search & Filter Indexing:** In-memory or Web Worker indexing for instant (<16ms) multi-facet search across 10,000 entries.
   - **Component Hierarchy:** Persistent sidebar, sticky filter header, virtual grid container, quick-action drawer/modal.
3. Propose a phased, step-by-step implementation plan for approval.
```

---

## 🧱 Part 2: Step-by-Step Screen & Component Iteration Prompts

Following the *Stitch Prompting Philosophy* (focused, incremental changes screen-by-screen):

### 🔹 Step 1: Layout Shell & Responsive Frame
```markdown
Create the base layout structure for a full-viewport dark-themed media dashboard:
- Left Sidebar (Collapsible): Navigation for "All Videos", "Playlists", "Categories", "Recently Watched", "Blacklisted", and "Tags".
- Sticky Header Toolbar:
  - Global omni-search input with shortcut hint (`/`).
  - View density toggles (Comfortable Grid, Compact Grid, Dense Table).
  - Quick sort dropdown (Date Added, Duration, Rating, Views, Title, Random).
  - Stats counter ("Showing X of 10,000 videos").
- Main Content Area: High-performance scrollable canvas with a CSS Grid layout configured for virtualized item rendering.
- Color Palette: Deep slate background (`#0b0f17`), surface card background (`#151c28`), subtle borders (`#1f293d`), and vivid accent color (`#3b82f6` or `#06b6d4`).
```

---

### 🔹 Step 2: Media Card Component & Density Modes
```markdown
Design the video card component with three selectable density modes:

1. Standard Grid Card:
   - 16:9 Thumbnail preview with rounded 6px corners and lazy loading.
   - Overlays: Video duration badge (bottom-right), resolution badge (top-left), watched indicator checkmark.
   - Content: Two-line clamped title, category pill, relative date ("2 days ago"), and view count.
   - Hover State: Subtle scale/elevation lift, quick action icons overlay (Favorite, Add to Category, Blacklist, Copy Link).

2. Compact Grid Mode:
   - Smaller aspect ratio thumbnails with single-line truncated titles and concise metadata chips for maximum items per screen.

3. Dense Table / List Mode:
   - Full-width row format: Thumbnail snapshot (120px), title, duration, categories, date added, view count, and action buttons in discrete table columns.
```

---

### 🔹 Step 3: Faceted Filtering & Search Engine
```markdown
Implement a faceted filter drawer and multi-select pill system above the video grid:
- Category & Tag Pills: Horizontal scrollable chip bar with active counter states and multi-select support (AND/OR toggle).
- Range Sliders / Dropdowns:
  - Duration filter (e.g. Under 5m, 5–15m, 15–30m, 30m+).
  - Watch status toggle (All, Unwatched, Watched, Favorites).
- Performance requirement:
  - Offload filter matching and fuzzy title search to a client-side Web Worker or pre-compiled inverted index so filtering 10,000 videos takes <15ms without UI freeze.
```

---

### 🔹 Step 4: Power-User Controls & Quick Actions
```markdown
Add keyboard shortcuts and inline management capabilities:
- Keyboard Navigation:
  - `J` / `K` or `ArrowDown` / `ArrowUp` to navigate active selection between cards.
  - `Space` or `P` to trigger video preview overlay.
  - `Enter` to open video in target view / player.
  - `/` to jump focus directly to search bar.
  - `B` to toggle blacklist on selected video.
  - `C` to open quick category assignment menu.
- Metadata Modal: Floating inspector sheet allowing instant tag additions, category reassignments, and notes without reloading or resetting scroll position.
```

---

### 🔹 Step 5: Visual Polish & Micro-Interactions
```markdown
Refine the styling, animations, and micro-interactions:
- Typography: Clean modern sans-serif (Inter or Roboto) with proper tracking and tabular figures for durations and timestamps.
- Skeleton Loading: Smooth shimmer animation placeholders while virtualized cards and thumbnails mount into view.
- Micro-interactions: Smooth 150ms ease transitions on card hover, pill active states, and filter drawer toggle.
- Scrollbar: Custom slim, dark scrollbar that matches the dashboard theme.
```
