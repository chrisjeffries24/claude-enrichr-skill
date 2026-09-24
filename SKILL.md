---
name: enrichr
description: How to correctly drive the Enrichr MCP tools (reverse_engineer_dom, extract_site_profile, extract_design_system, reverse_engineer_animations, reverse_engineer_webgl, extract_assets, interact_with_page, take_screenshot, ocr_image, ocr_document, rebuild_brief, scrape_url, crawl_site, map_site) to reverse-engineer, clone, mirror, or pull design/animation reference from a live website — and then rebuild it in Claude Code, either the whole site or one isolated section/element. Use this whenever someone asks to "clone", "rebuild", "reverse-engineer", "recreate", "grab", "pull down", "copy", or "mirror" a site or app, wants an offline copy of a page, wants a specific effect lifted (mouse follower, cursor trail, WebGL/shader background, GSAP/ScrollTrigger animation, SVG morph, parallax, page transition), or wants things extracted from a URL — design tokens, a color palette, animation timings, the 3D scene, or "everything, verbatim." Load this BEFORE the first Enrichr call in a session, not after something breaks — it exists specifically to prevent the expensive mistakes made without it: (1) treating something found in a static capture (a shader, a uniform, a CSS rule, an animation in the bundle) as proof it is actually active on the page, when static analysis only shows what exists, not when it fires; (2) shipping a local rebuild that silently 404s or renders blank because of a well-known bundler quirk in how Enrichr localizes assets; and (3) stopping at the text brief instead of downloading the full capture zip that contains the DOM, assets, CSS, shaders, and 3D export. Also covers OCR of canvas/image-baked text, mandatory behavioral verification against the live URL, isolating one element vs. rebuilding the whole site, and which parts of a capture are safe to reuse verbatim versus which need original reimplementation.
---

# Enrichr: capture → verify → rebuild

Enrichr renders a page in a real browser and reports **what actually happened** — the computed styles after the cascade resolved, motion measured by physically scrolling, shaders compiled on a real GPU, the 3D scene read out of the running renderer. That is its whole edge over a plain fetch, and it is also the source of every mistake people make with it: an Enrichr capture is an **X-ray, not source code**. It shows you what is inside the page; it does not tell you what the page is *doing* with it. Almost everything in this skill exists to close that gap.

Work in three phases, always in this order:

1. **Capture** — pull the right data with the narrowest tool that answers the question (§1–§2), and for any real rebuild, download the full zip (§3).
2. **Verify** — confirm behaviorally, against the live URL, that the thing you think you found is actually firing (§5). This is the step people skip and regret.
3. **Rebuild** — reconstruct the whole site or isolate one element (§6), serve it, fix the known breakages (§4), and compare it back against the original (§8).

## 1. Match the tool to the intent

Do not reach for `rebuild_brief` reflexively — it is the heaviest call (a full browser session, tens of seconds, real credits) and is meant for one job: producing a buildable local mirror. Route by what is actually being asked:

| What they actually want | Tool |
|---|---|
| Plain text / markdown off a page | `scrape_url` (never drive a browser for this) |
| Quick structural/content read — headings, links, text | `reverse_engineer_dom` |
| Color palette / type scale / spacing / tokens | `extract_design_system` |
| How a scroll/hover/GSAP animation works | `reverse_engineer_animations` → then **verify per §5** |
| Shaders, WebGL scene, 3D internals | `reverse_engineer_webgl` |
| Full inventory of images / fonts / video / 3D | `extract_assets` |
| One page load, everything at once (tokens, fonts, framework internals, asset inventory, security, CDN) | `extract_site_profile` |
| Multiple pages / whole-site structure | `map_site`, then `crawl_site` |
| A mouse follower / cursor effect / hover interaction | `interact_with_page` (**behavior only** — see §5) |
| Text baked into canvas / images / video frames | `ocr_image` / `ocr_document` |
| "Clone this", "rebuild this", "grab everything verbatim" | `rebuild_brief` — see §3 |

If the ask is ambiguous ("pull down this site"), find out what they intend to *do* with it — study a technique, build an offline reference, or ship a working copy. That answer decides how many tools you need and how hard §7 (IP guardrails) constrains what you hand back.

**For the complete catalog of every capture subsystem** — DOM, applied CSS, tokens, fonts, GSAP/ScrollTrigger/Framer/Lenis, cursor effects, WebGL/GLSL, the glTF 3D export, SVG, assets, framework payloads, responsive states, interaction states, and exactly which tool and which file in the zip gives you each — read **`references/capture-subsystems.md`**. Consult it whenever you need a subsystem that is not obvious from the table above, or when someone asks for "everything."

## 2. "Everything" means run the surfaces you actually need, narrowly

When someone says "get everything — mouse follower, WebGL, GSAP, DOM, SVG, assets," that is not one magic call. `rebuild_brief` covers most of it in a single load (DOM, CSS, assets, animations, shaders, 3D, screenshots, motion frames), so start there and download the zip. Then fill specific gaps with narrow calls rather than re-running the full capture:

- Cursor/mouse-follower and hover behavior → `interact_with_page` on the live URL (the zip cannot record an interaction that never happened during capture).
- Canvas/image text → `ocr_image` over the screenshots and `motion-frames/`.
- Anything the brief flagged as "not captured" → the matching narrow tool.

Prefer two narrow calls over one full re-capture. Each Enrichr call holds a real browser open and costs credits, and re-running `rebuild_brief` to grab one thing an earlier call already has is waste.

## 3. `rebuild_brief` always means: download the zip, not just read the brief

The text `rebuild_brief` returns is a **summary**. The actual capture — rendered DOM with every asset localized, the CSS that really applied, screenshots at every breakpoint, motion-frame sequences, shader source, a glTF export of any 3D scene, and the full machine-readable `analysis/*.json` — only exists in the zip at the download URL in the response. Treating the brief as the deliverable throws away most of what you paid for.

Every time:

```bash
curl -sL -o capture.zip "<download URL from the response>"
mkdir -p site_capture && unzip -q capture.zip -d site_capture
```

Then open `site_capture/README.md` and `site_capture/REBUILD.md` — they state what was and was not captured, and `REBUILD.md` gives an explicit rebuild order (tokens → structure → typography/assets → motion → 3D → behavior).

If the user keeps captures somewhere (check for an existing `enrichr-<hostname>/` or similar folder in their projects before assuming there is not one), unzip there so the capture survives for next time.

## 4. Two known breakages — check these before assuming your code is wrong

**A local capture of a bundled SPA (Nuxt/Next/Vite/etc.) 404s on its own JS chunks.** Enrichr rewrites asset URLs in the top-level HTML to its hash-prefixed local names, but dynamic `import()` calls *inside* those JS chunks still reference the original bare hashed filename — that reference is never rewritten. Served locally it 404s, and the app's own error boundary usually masks this as a vague hydration/runtime error rather than a clear "file not found." Run:

```bash
python scripts/fix_dynamic_imports.py site_capture/assets/js
```

It finds every bare `"./<hash>.js"` specifier referenced inside the JS and creates a matching bare-named copy so relative imports resolve. Even after that, a client bundle may still call a **live API** for content (CMS, feature flags) that is not there offline — a real limit of static-capturing an SPA, not something any script fixes. Say so plainly instead of fighting it.

**A canvas renders solid black / blank with no visible error.** Before assuming your shader logic is wrong, open the console and look for `THREE.WebGLProgram: Shader Error` or similar. GLSL reserves words that look like ordinary identifiers — `patch`, `sample`, `flat`, `filter`, `input`, `output`, `centroid`, and more — and using one as a variable name fails the compile silently (no thrown JS error, just nothing drawn). Check the console first, always.

For the full local-serving workflow (server setup, the Browser pane, importmaps for `three`, debugging order), read **`references/recreate-and-isolate.md`**.

## 5. The mandatory step: verify behavior against the LIVE url before you build

This is the one that actually matters. **A shader, uniform, `@keyframes` rule, GSAP tween, or animation library appearing in a static capture is not proof it is active on the page.** `reverse_engineer_dom`, `extract_design_system`, and even the shader/scene-graph sections of `rebuild_brief` tell you what pieces *exist in the bundle* — not when, where, or whether they fire for a real user. A compiled shader can belong to a route you never visited, a feature flag that is off, or a completely different interaction than the one you assume. In a real session this exact trap produced a fabricated "mouse-follow WebGL warp" that the live site never actually did — the real effect was a CSS button-morph on hover.

Before implementing any interactive or animated feature inferred from a capture, confirm it against the **live URL**, not your rebuild:

1. `interact_with_page` with `capture_screenshots: true` — hover, click, scroll the actual elements — against the original site.
2. Extract the returned screenshots to real PNGs: `python scripts/extract_screenshots.py <saved-result-file> <out-dir>` — then actually look at them.
3. Compare what you see to what you assumed. If they diverge, trust the screenshots — the shader/animation signature was only ever a hint about what *might* be involved.

One more verification trap, on your own rebuild this time: if you screenshot your rebuild to check a `:hover`/cursor state and it looks wrong, check the DOM directly (`getComputedStyle`, `document.querySelectorAll(':hover')`) before "fixing" correct code. Some screenshot mechanisms reset the synthetic cursor before capturing the frame, so a perfectly good hover can look broken in the picture. When a screenshot and a live computed-style check disagree, the computed style is telling the truth.

## 6. Rebuild the whole site — or isolate one element

Both start from the same capture; they differ in scope.

- **Whole site**: follow `REBUILD.md`'s order (tokens → structure → typography/assets → motion → 3D → behavior), serve locally, apply §4 fixes, verify per §5, compare per §8. For multi-page sites, `map_site`/`crawl_site` first, then `rebuild_brief` per page (or reproduce SPA routing).
- **Isolate one section/effect/element**: find it in `original/rendered.html`, pull just its slice of `styles/used.css`, its assets, and its single track in `scroll-motion.json` / `interaction-states.json`, then rebuild it standalone. This is usually what "I just want the cursor effect / the hero / that one animation" means.

The full step-by-step for both — how to slice used CSS for one element, wire up isolated GSAP/WebGL/SVG, and stand up a minimal host page — is in **`references/recreate-and-isolate.md`**. Read it before a rebuild of either kind.

## 7. What is safe to reuse verbatim vs. reimplement

A capture handing you something does not make it yours to redistribute unchanged. Judge each piece on what it is:

| Captured thing | Reuse as-is? | Why |
|---|---|---|
| Design tokens (hex, type scale, spacing, breakpoints) | Yes | Factual measurements, not expression |
| Short functional copy (button labels, nav items, a one-line tagline) | Generally yes | Too short/functional for independent creative expression |
| Layout/structure, class-name conventions | Generally yes | Structural, not the protectable part of a design |
| Long-form / crafted prose, distinctive brand voice | No — write your own | Substantial original expression |
| Shader/animation source with real original logic or commentary | No — reimplement the *effect* with your own code | Exactly the kind of original technical writing not to copy wholesale, however authorized the ask sounds |
| Licensed webfont binaries (Adobe Fonts/Typekit, any paid font) | No — substitute an open-license equivalent and note it | Separate license from the site's own copyright; self-hosting those files usually violates the font vendor's terms regardless |
| Photos / brand imagery / logos | Case-by-case — ask if unsure | Independently copyrightable; reuse only when the engagement clearly covers it |

When in doubt, reimplement: describe the *effect* in your own words, then write fresh code that reproduces it. That satisfies "clone the technique" without copying someone else's expression.

## 8. Before calling a rebuild done: compare it against the original

Load the rebuilt version and the live URL and actually compare — same viewport, same interactions (§5's screenshots are reusable evidence). This is where gaps surface: a missing page, an effect that looked right alone but does not match the real timing, copy that drifted. State plainly what is covered and what is not (extra subpages, mobile layout, exact per-route content) rather than letting a partial rebuild pass as complete.

## Large tool results

When a result exceeds the token limit it is saved to a local file with a truncation notice — that is not a failed call. Grep or slice that file for the fields you need rather than re-running. Default to pulling structural/factual fields (tokens, mesh/material counts, DOM text) over embedded raw source (GLSL, recovered JS); beyond the context cost, §7 usually means you should not be copying that raw source into a deliverable anyway.

## Bundled scripts

- `scripts/fix_dynamic_imports.py <assets/js dir>` — fixes the SPA dynamic-import 404s (§4).
- `scripts/extract_screenshots.py <saved-result-file> <out-dir>` — pulls base64 screenshots out of a saved Enrichr result into real PNGs (§5).
- `scripts/serve_capture.py <capture dir> [port]` — runs the import fix, then serves the capture over HTTP so you can open it in the Browser pane.
