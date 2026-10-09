## Brand & Style

This design system embodies academic clarity, quiet intellect, and focused synthesis. Inspired by modern knowledge engines and rigorous editorial tools, it prioritizes unhindered cognition over decorative excess. The emotional response is one of calm mastery: an open, airy workspace where dense source materials, machine-assisted syntheses, and personal scholarship coalesce effortlessly.

The design movement combines **Modern Minimalist Utility** with **Contemporary Editorial Craft**:
- **Canvas Atmosphere:** Airy, luminous surfaces with subtle warm-slate and alabaster undertones that reduce ocular fatigue during multi-hour research sprints.
- **Editorial Legibility:** Crisp, utilitarian sans-serif UI frameworks juxtaposed against a bookish serif for synthesized outputs, reading panes, and deep reading surfaces.
- **Micro-Structured Layout:** Whisper-thin hairline borders define panels and modules without heavy shadows, preserving a lightweight, paper-like architectural grid.
- **Academic Hierarchy:** High-density, scannable elements (e.g., citation pills, metadata chips, source categories) using desaturated botanical, mineral, and ochre accents to provide effortless visual triage.

## Layout & Spacing

The layout is engineered around a purpose-built **3-Column Academic Cockpit** that enables synchronous retrieval, interrogation, and authoring:

### 3-Column Desktop Grid Model
- **Left Column (Sources & Index):** Fixed width between `280px` and `340px`. Dedicated to document ingestion, checkable source trees, audio overviews, and file meta.
- **Center Column (Synthesis & Studio Chat):** Fluid width (min `560px`, optimal reading width max `820px`). Hosts the conversational inquiry stream, generative summaries, and editorial answers.
- **Right Column (Notes & Working Surface):** Fixed or independently dockable width (`360px` to `420px`). Hosts user-curated notes, flashcards, outline trees, and pinned excerpts.

### Breakpoint Architecture & Reflow
- **Desktop (>= 1280px):** Simultaneous 3-column expanded mode. Columns scroll independently with decoupled overflow.
- **Tablet (768px - 1279px):** 2-column configuration. Left source pane collapses into an off-canvas slideover or icon drawer. Studio chat and notes share the viewport with a tabbed switcher.
- **Mobile (< 768px):** Single-column stacked mode. Bottom segmented bar toggles between **Sources**, **Studio**, and **Notes**. Margin drops to `1rem`.

### Spacing Rhythm
Spacing is derived from a strict 4px base unit. Internal component padding favors vertical containment and horizontal roominess (`space-sm` vertical by `space-md` horizontal for list rows) to maximize visible context.

## Elevation & Depth

Visual hierarchy relies on crisp surface layering and tactile borders rather than heavy drop shadows:

- **Tonal Planes:** 
  - Canvas base: Slate-tinted neutral (`#F8FAFC`).
  - Active panels and cards: Solid Alabaster (`#FFFFFF`).
  - Elevated modals & floating toolbars: Pure white with micro-blur fallbacks.
- **Micro-Borders (Ghost Linework):** Structural boundaries rely on crisp `1px` borders (`#E2E8F0` at 100% opacity, or `rgba(15, 23, 42, 0.08)`).
- **Subtle Ambient Shadows:** Reserved strictly for interactive popovers, context menus, and elevated focus cards:
  - *Resting Card:* No shadow; delineated solely by hairline borders.
  - *Hover State Card:* `0 2px 8px -2px rgba(15, 23, 42, 0.05), 0 1px 4px -1px rgba(15, 23, 42, 0.03)`.
  - *Floating Menus & Citations Tooltips:* `0 8px 24px -4px rgba(15, 23, 42, 0.08), 0 2px 6px -1px rgba(15, 23, 42, 0.04)`.

## Components

### 1. Citation Pill Badges
- **Visual Spec:** Fully rounded capsules (`9999px`). High-contrast, minimal footprint.
- **Default Appearance:** `height: 20px`, padding: `0 8px`, `fontFamily: Geist`, `fontSize: 11px`, `fontWeight: 600`.
- **States:**
  - *Standard Inline:* Slate ink (`#1E293B`) text on crisp warm gray (`#F1F5F9`) with a `1px` border (`#CBD5E1`).
  - *Hover / Target:* Transitions to Indigo (`#EEF2FF` background, `#4338CA` text, `#C7D2FE` border). Triggers a linked highlight in the Left Column source document.

### 2. Category Chips (Source Tags)
- **Visual Spec:** Muted, desaturated background with saturated text:
  - *Literature/PDF:* `#ECFDF5` background, `#047857` foreground.
  - *Audio/Transcript:* `#EEF2FF` background, `#4338CA` foreground.
  - *Notes/Draft:* `#FFFBEB` background, `#B45309` foreground.
- **Border:** `1px` matching parent accent at 20% opacity.

### 3. Studio Input & Query Bar
- **Visual Spec:** Floating pill-rounded command card anchored at the bottom of the central column.
- **Styling:** White surface, `1px` slate-200 border, elevated with ambient hover shadow. Features multi-line expanding input, voice recording icon, and an explicit source scope count chip (e.g., `"5 sources selected"`).

### 4. Cards (Notebook & Source Cards)
- **Visual Spec:** `rounded-xl` (`16px`), `1px` solid `#E2E8F0`, pure white background.
- **Interaction:** Hover transitions border to `#94A3B8` without scaling or jumping. Contains clear semantic header, metadata count, and selectable checkbox anchored in the top-right corner.

### 5. Buttons
- **Primary:** Deep slate (`#1E293B`) fill, pure white text, `rounded-lg` (`8px`), no shadow. Hover: `#0F172A`.
- **Secondary / Ghost:** Transparent fill, `1px` border (`#E2E8F0`), slate text. Hover: `#F8FAFC` background with `#CBD5E1` border.
- **Action Compact:** `28px` height for inline tools, citations, and panel toggles.

### 6. Form Controls (Checkboxes & Radios)
- **Checkboxes:** `rounded` (`4px`), `16px` dimension, slate border. Selected state filled with Indigo (`#4338CA`) displaying a sharp white micro-check.
- **Inputs:** `height: 40px`, `rounded-lg`, subtle background `#F8FAFC`, active focus border `#4338CA` with zero focus-ring spread.

### 7. Source Viewer Pane (Left Column)
- Item rows with leading icon indicating MIME type, title in `body-sm` (`Geist`), and trailing item checkbox. Active selected document highlighted with an indigo edge indicator (`3px` left solid bar).