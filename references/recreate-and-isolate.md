# Rebuild the whole site, or isolate one element

Both workflows start from the same downloaded capture (SKILL.md §3) and share the same serving/debugging setup. The difference is scope: reconstruct the entire page faithfully, or lift one section/effect/element and stand it up on its own.

## Serving the capture locally

You need the capture running in a browser to verify anything. On any machine with Python:

```bash
# from the capture directory's parent
python scripts/serve_capture.py site_capture 8811
```

`serve_capture.py` runs the dynamic-import fix (SKILL.md §4) first, then serves the folder over HTTP. Open `http://localhost:8811`.

In Claude Code with the Browser pane, add a `.claude/launch.json` so `preview_start` can drive it:

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "capture", "runtimeExecutable": "python",
      "runtimeArgs": ["-m", "http.server", "8811", "--directory", "site_capture"],
      "port": 8811 }
  ]
}
```

**Debugging order when something is wrong** (follow it top to bottom — each step rules out a class of problem):

1. **Console 404s** → the SPA dynamic-import breakage. Run `fix_dynamic_imports.py` (SKILL.md §4).
2. **Console `THREE.WebGLProgram: Shader Error`** → a GLSL reserved-word or compile bug; the canvas will be blank with no JS exception. Fix the shader before touching anything else.
3. **Blank content, no 404s, `[nuxt]`/`[next]` app-init errors** → the client bundle is calling a live API that is not there offline. This is a real limit of static-capturing an SPA; rebuild the affected view yourself rather than expecting the captured bundle to run headless.
4. **A `three`/library import fails** → add an importmap (below).
5. **Hover/cursor looks wrong in a screenshot but the CSS looks right** → check `getComputedStyle` / `:hover` in the console; the screenshot tool can reset the synthetic cursor before capturing (SKILL.md §5).

For loading `three` (and similar) in a hand-built rebuild without a bundler, an importmap plus a CDN module build is the least-friction path:

```html
<script type="importmap">
{ "imports": { "three": "https://unpkg.com/three@0.160.0/build/three.module.js" } }
</script>
<script type="module" src="js/app.js"></script>
```

---

## Whole-site rebuild

1. **Read `REBUILD.md`** in the capture — it gives the capture-specific rebuild order and lists what was and was not captured. Follow its order; it exists because dependencies run that way (fonts must load before layout settles, tokens underpin everything).
2. **Tokens first.** Port `analysis/design-tokens.json` into `:root` custom properties — colors, type scale, spacing, radii, breakpoints. Everything downstream references these.
3. **Structure.** Take the skeleton from `original/rendered.html`. Keep the class-name conventions; they make the used CSS drop in cleanly.
4. **Typography & assets.** Wire fonts (substituting any licensed webfonts per SKILL.md §7), then drop in `assets/` images/video/SVG.
5. **CSS.** `styles/used.css` is the resolved cascade — start from it, then layer `analysis/responsive.json` and `analysis/interaction-states.json` for breakpoints and hover/focus states.
6. **Motion.** Reproduce `scroll-motion.json` tracks and `@keyframes` from `animations.json`. Reimplement library-driven motion (GSAP/ScrollTrigger/Lenis) as your own code hitting the measured from→to values and timings — you have the numbers, you do not need their minified bundle.
7. **3D.** Load `assets/3d/scene/scene.gltf` directly rather than rebuilding geometry; reimplement shader *effects* (not verbatim GLSL) for anything custom.
8. **Behavior.** Add cursor/hover/scroll interactions — each **verified against the live site first** (SKILL.md §5).
9. **Multi-page.** For a real multi-page site, `map_site`/`crawl_site` to enumerate routes, then `rebuild_brief` per page and repeat. For an SPA, reproduce the routing rather than capturing each route as a separate static page.
10. **Compare** against the original, same viewport and interactions (SKILL.md §8). Name the gaps.

## Isolate one element / section / effect

Usually what "I just want the cursor effect / the hero / that one animation" means. Do not rebuild the whole page.

1. **Locate it** in `original/rendered.html` — grep for its text, an aria-label, or a distinctive class. Copy that subtree's markup (including any inline `<svg>`, `<canvas>`, and `data-*` hooks the JS targets).
2. **Slice its CSS.** From `styles/used.css`, pull the rules matching that element and its children. Include the custom properties it references (grep the token names out of `:root`). Keep the box model and positioning context it lived in — an element ripped out of its flex/grid parent often collapses; recreate a minimal version of that parent.
3. **Its assets only.** Copy just the images/fonts/SVG/textures that element uses from `assets/`.
4. **Its motion track.** Find the element's single entry in `scroll-motion.json` (and `interaction-states.json` for hover/focus). Reproduce just that track. If it is WebGL/canvas, pull only its material's shader/uniforms — and reimplement the effect (SKILL.md §7).
5. **Verify it live.** Especially for anything cursor- or scroll-driven, confirm the isolated behavior against the original element on the live URL (SKILL.md §5) before trusting your reconstruction.
6. **Minimal host page.** Stand it up on a bare HTML page with just the tokens, the sliced CSS, the assets, and the one script. This is your deliverable — an element someone can drop into their own project, not a whole cloned site.

### Isolating specific effect types

- **Mouse follower / custom cursor** → there is no static file; capture behavior live (`interact_with_page`), then reimplement with a damped pointer-lerp loop. Verify what actually responds to the cursor (whole background vs. one element) before building.
- **GSAP / ScrollTrigger reveal** → take the from→to and scroll window from `scroll-motion.json`; rebuild with your own GSAP (or CSS scroll-timeline) hitting those exact values. Do not try to run their bundled GSAP.
- **WebGL / shader background** → load any `assets/3d/` geometry directly; reimplement the shader effect from its behavior and uniform list, not the captured GLSL verbatim.
- **SVG morph** → lift the two path `d` values (or the mask) from the inline SVG; tween between them yourself.
- **Parallax / depth** → if a depth map is in `assets/`, it is a real reusable asset; the displacement math is simple to write fresh.
