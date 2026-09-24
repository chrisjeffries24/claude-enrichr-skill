# Capture subsystems — every layer of a site and how to pull it

This is the catalog behind the SKILL.md routing table. For each subsystem: which Enrichr tool produces it, where it lands in a `rebuild_brief` zip, what you actually get, and the traps specific to it. Read the entries you need; you rarely need all of them at once.

## Table of contents

1. [DOM & structure](#1-dom--structure)
2. [Applied CSS (the cascade, resolved)](#2-applied-css)
3. [Design tokens](#3-design-tokens)
4. [Fonts & typography](#4-fonts--typography)
5. [Animation — GSAP, ScrollTrigger, Framer, Lenis, CSS](#5-animation)
6. [Mouse followers & cursor effects](#6-mouse-followers--cursor-effects)
7. [Hover / focus / active interaction states](#7-interaction-states)
8. [WebGL, GLSL shaders & the 3D scene](#8-webgl-glsl--3d)
9. [SVG — inline paths, masks, filters, morphs](#9-svg)
10. [Assets — images, video, fonts, models](#10-assets)
11. [Framework internals & data payloads](#11-framework-internals)
12. [Responsive layout across breakpoints](#12-responsive)
13. [Motion frames & canvas-only motion](#13-motion-frames)
14. [Text baked into pixels (OCR)](#14-ocr)

---

## 1. DOM & structure

**Tool:** `reverse_engineer_dom` (standalone) or the `original/` folder in a `rebuild_brief` zip.
**In the zip:** `original/rendered.html` (post-JavaScript, the DOM as it settled) and `original/server.html` (raw SSR response before hydration). `index.html` is the rendered DOM with asset URLs rewritten to local paths.
**What you get:** condensed DOM tree, heading hierarchy, all text content, landmarks, tables, forms, and an internal/external link inventory. Seeps JS-rendered content a static fetch cannot see.
**Traps:** `reverse_engineer_dom` with the full tree can exceed the token limit and get saved to a file — pass `include_dom_tree: false` for a lighter structural read, or grep the saved file. For rebuilding, prefer `rendered.html` from the zip over the tool's JSON tree — it is the real markup, not a summary.

## 2. Applied CSS

**Tool:** `rebuild_brief` → `styles/used.css`.
**What you get:** *only* the CSS that actually applied to the rendered page — the cascade, media queries, and runtime theming already resolved. This is the single most useful file for a faithful rebuild because it strips the dead rules that ship in most stylesheets.
**Traps:** it is "used at capture time and viewport." Rules that only apply at other breakpoints or interaction states may be absent from the main pass — cross-reference `analysis/responsive.json` and `analysis/interaction-states.json` for those.

## 3. Design tokens

**Tool:** `extract_design_system` (standalone) or `analysis/design-tokens.json` in the zip.
**What you get:** CSS custom properties, a frequency-ranked color palette (top entries are the brand colors, the tail is incidental), the complete type scale (every rendered font-size/line-height/weight/letter-spacing combination, most-used first), spacing scale, radii, shadows, easing curves, durations, z-index layers, and breakpoints. Read from computed styles, so it is what actually rendered, not what a config claims.
**Reuse:** tokens are factual measurements — safe to reuse verbatim (SKILL.md §7).

## 4. Fonts & typography

**Tool:** `extract_design_system` (fonts section) + `extract_assets` for the files.
**In the zip:** `assets/fonts/`.
**What you get:** every `@font-face` family, weight, style, and the rendering stacks that actually painted text (with element counts).
**Traps — licensing:** fonts served via Adobe Fonts / Typekit (`use.typekit.net`) are often listed as "not exposed" and the binaries are **not** yours to self-host — that violates the vendor's license independently of the site's own copyright. Substitute an open-license equivalent (Google Fonts, etc.) and note the swap. Only self-host font files that are actually open-licensed.

## 5. Animation

**Tool:** `reverse_engineer_animations` (standalone) + `analysis/animations.json` and `analysis/scroll-motion.json` in the zip.
**What you get:**
- **Detected libraries** — GSAP (tweens, timelines, ScrollTriggers), Framer Motion, Lenis, AOS — via runtime instrumentation.
- **Authored `@keyframes`** — copied verbatim from the stylesheets.
- **Measured motion** (`scroll-motion.json`) — the page is physically scrolled in ~12 steps and computed styles are diffed, so you get real from→to values and the scroll window they animate over. **This holds regardless of which library produced the motion** — and when the animation library is minified into a bundle (the usual case on award-winning sites), the measured track is the *only* recoverable source.
**Key insight:** read `scroll-motion.json` *before* `animations.json`. If the library is bundled out of reach, `animations.json` may be nearly empty while `scroll-motion.json` still has the real numbers.
**Traps:** if `scroll-motion.json` reports no tracks on a page that visibly moves, the motion is inside a `<canvas>` — the DOM genuinely does not move, and `motion-frames/` (§13) is your only record. And per SKILL.md §5, a detected library or keyframe is not proof it drives the specific effect you care about — verify behaviorally.

## 6. Mouse followers & cursor effects

**Tool:** `interact_with_page` against the **live URL** — there is no static file for this.
**Why:** a cursor-follow effect (custom cursor, magnetic hover, trailing dot, WebGL wake-warp, lens/reveal that tracks the pointer) is a *runtime response to pointer movement*. It does not exist as a capturable artifact the way DOM or CSS does. A shader in the bundle with a `u_mouse` uniform is a hint, not proof — that uniform may drive something else entirely, or nothing on this route.
**How:** `interact_with_page` with `interactions: [{action:"hover", selector:"..."}]` and `capture_screenshots: true`, then extract the PNGs (`scripts/extract_screenshots.py`) and look. Move to several positions to see whether the background/DOM actually responds to the cursor, or whether only a specific element does.
**Lesson from the field:** on one site the "mouse follower" everyone assumed was a WebGL background warp was actually a pure-CSS pill→eye button morph on `:hover`. Only the interaction test revealed it.

## 7. Interaction states

**Tool:** `rebuild_brief` → `analysis/interaction-states.json`; or `interact_with_page` live.
**What you get:** the hover/focus/active styling a static snapshot cannot show — per element, the transition string and the from→to for each property that changes, plus cursors and pseudo-element changes.
**Use:** essential for buttons, links, and any control — the resting screenshot never shows these, so a rebuild without this file feels dead.

## 8. WebGL, GLSL & 3D

**Tool:** `reverse_engineer_webgl` (standalone) + `analysis/shaders/*.glsl`, `analysis/scene-graph`/`sceneExport`, `assets/3d/` in the zip.
**What you get:**
- **Shader source** captured from `compileShader()` — the exact GLSL the GPU ran, including material uniform lists.
- **Scene graph** — object/mesh/material/light/camera counts, geometry types, triangle/vertex counts, renderer settings.
- **glTF export** — the live scene read out of the running renderer and written as standard glTF 2.0 (`assets/3d/scene/scene.gltf` + `.bin`). **Load this directly** rather than rebuilding geometry by hand. Note: animation clips, skinning, morph targets, lights, and environment maps are *not* exported — static geometry, materials, and textures are.
- **Textures** read back off the GPU as PNG into `assets/3d/textures/` — includes textures that only ever existed as GPU-compressed blocks.
**Traps:** shader GLSL is often dense, heavily-commented **original** work — reuse the *effect*, not the source (SKILL.md §7). Do not pull all the raw GLSL into context if you only need uniform names or counts. And check `draw calls per frame` — a scene graph with shaders but 0 draw calls may not be rendering on this view.

## 9. SVG

**Tool:** present inline in `original/rendered.html` (and `index.html`).
**What you get:** inline `<svg>` markup — paths, `<mask>`, `<clipPath>`, `<filter>`, gradients, and any `data-*` hooks the animation JS targets. Morph effects usually work by tweening between two path `d` values or by animating a mask; both are visible in the markup.
**How to isolate:** grep the rendered HTML for `<svg`, lift the whole element, and check `interaction-states.json` / `scroll-motion.json` for what transforms its child paths. SVG geometry (path data) is functional and generally safe to reuse; a distinctive logo drawn in SVG is brand imagery — treat per SKILL.md §7.

## 10. Assets

**Tool:** `extract_assets` (standalone, with HTTP metadata) or the `assets/` tree in the zip.
**In the zip:** `assets/images/`, `assets/fonts/`, `assets/css/`, `assets/js/`, `assets/3d/`, `assets/other/` (JSON payloads, etc.), plus `manifest.json` mapping originals to local paths.
**What you get:** every image, font, video, SVG, script, stylesheet, and 3D model, deduped, merging network traffic with DOM declarations. `extract_assets` can fetch per-file metadata (sizes, dimensions) — slower but useful for budgeting.
**Traps:** streamed video and anything behind auth will not localize — expected. Very large hero images inflate the zip; that is fine, they are the real assets.

## 11. Framework internals

**Tool:** `extract_site_profile` → `analysis/runtime.json` and inline in the HTML.
**What you get:** `__NEXT_DATA__`, Nuxt `_payload.json`, Astro/Svelte/Nuxt state, the React component tree, response headers, security-header posture, CDN/platform fingerprints (Netlify, Cloudflare, Vercel…), robots.txt, sitemap, and structured data (JSON-LD, OpenGraph).
**Use:** the SSR payload often contains the page's *content model* — the actual data behind the rendered text, and sometimes the API errors that reveal the backend shape. Great for understanding a data-driven page; useless to reuse as code.
**Traps:** the payload can be huge — load specific keys, not the whole blob.

## 12. Responsive

**Tool:** `rebuild_brief` → `analysis/responsive.json` + `screenshots/*-responsive-*.png`.
**What you get:** which elements change layout at each breakpoint and what they change to, plus a screenshot per breakpoint (mobile/tablet/laptop/desktop) and a dark-mode capture. Named breakpoints also appear in the design tokens.
**Use:** without this, a rebuild only matches the one viewport you captured. Diff the responsive screenshots to see the real reflow.

## 13. Motion frames

**Tool:** `rebuild_brief` → `analysis/motion-frames/*.png` + `frames.json`.
**What you get:** one screenshot per scroll stop, in order — what the page looks like *in motion*. On a canvas-driven page where `scroll-motion.json` finds no DOM tracks, this is the only record of what actually animates.
**Use:** hand these to a vision model (read them as images) and OCR them (§14). Do not treat them as a video file — they are ordered stills.

## 14. OCR

**Tool:** `ocr_image` (one image) / `ocr_document` (PDF/multi-page).
**Why:** `reverse_engineer_dom` and `get_page_text` only see real DOM text. Anything drawn to `<canvas>`, baked into a texture, or composited into an image/video frame (hero text over a photo, captions burned into frames, a logo lockup) is invisible to them though a user reads it as text. OCR the relevant screenshots — including `motion-frames/` — so on-page copy is not silently dropped.
**Traps:** if OCR returns empty on a frame that plainly shows text, say so rather than dropping the content — the text may be low-contrast or mid-transition; try another frame.
