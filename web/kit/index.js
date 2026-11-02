// web/kit/index.js — client-side loader for the kit-of-parts.
//
// Mirrors graph/kit.py. Both import from web/kit/kit.json so the
// single source of truth is enforced across languages.
//
// Usage:
//   const KIT = await loadKit();
//   KIT.parts.papyrus_tablet        // the part spec
//   KIT.size_room_for(composition)  // {w, h}
//   KIT.is_text_bearing(role)       // bool
//   KIT.hall_styles[halLKey]        // {tl, tr, bl, br, h, v, inner}
//
// Loaded once at game.js boot; re-used by assembler, renderer, verifier.

export async function loadKit(url = '/web/kit/kit.json') {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`kit.json load failed: ${resp.status}`);
  const data = await resp.json();
  return enrich(data);
}

// Accept a pre-parsed kit object (tests / offline boot).
export function enrich(data) {
  const kit = {
    version: data.version,
    packing_density: data.packing_density,
    hall_styles: data.hall_styles,
    categories: data.categories,
    parts: data.parts,
    text_bearing_roles: new Set(data.text_bearing_roles),
    text_type_to_part: data.text_type_to_part,
    placement_order: data.placement_order,

    // Derived
    PART_FOOTPRINT: footprintMap(data.parts),

    // Helpers
    is_text_bearing(role) { return this.text_bearing_roles.has(role); },
    attach_of(role)       { return (this.parts[role] || {}).attach || 'floor'; },
    is_walkable(role)     { return (this.parts[role] || {}).walk === true; },
    parts_by_category(cat){ return Object.entries(this.parts).filter(([, p]) => p.cat === cat).map(([k]) => k); },
    resolve_role(keyOrTextType) {
      // Accept either a corpus text_type ('papyrus', 'Wand', …) or a
      // role name ('papyrus_tablet', 'wall_inscription', …).
      if (keyOrTextType in this.text_type_to_part) return this.text_type_to_part[keyOrTextType];
      if (keyOrTextType in this.parts) return keyOrTextType;
      return 'papyrus_tablet';  // safe default (same as Python)
    },
    compute_aspect(composition) {
      let wallW = 0, floorW = 0;
      for (const [key, n] of Object.entries(composition)) {
        const role = this.resolve_role(key);
        const p = this.parts[role]; if (!p) continue;
        const fp = this.PART_FOOTPRINT[role] * n;
        const att = p.attach;
        if (att === 'wall' || att === 'wall_sunken' || att === 'wall_band' || att === 'shell' || att === 'above_gateway') wallW += fp;
        else floorW += fp;
      }
      const total = wallW + floorW;
      if (total <= 0) return 1.2;
      const wallFrac = wallW / total;
      return 1.0 + 0.8 * wallFrac;
    },
    size_room_for(composition) {
      let footprint = 0;
      for (const [key, n] of Object.entries(composition)) {
        const role = this.resolve_role(key);
        footprint += (this.PART_FOOTPRINT[role] || 1) * n;
      }
      if (footprint <= 0) return { w: 12, h: 8 };
      const floorTiles = footprint / this.packing_density;
      const aspect = this.compute_aspect(composition);
      const w = clamp(Math.round(Math.sqrt(floorTiles * aspect)), 12, 64);
      const h = clamp(Math.round(Math.sqrt(floorTiles / aspect)), 8, 44);
      return { w, h };
    },
    density_for(composition, w, h) {
      let fp = 0;
      for (const [key, n] of Object.entries(composition)) {
        const role = this.resolve_role(key);
        fp += (this.PART_FOOTPRINT[role] || 1) * n;
      }
      return fp / Math.max(1, w * h);
    },
  };
  return kit;
}

function footprintMap(parts) {
  const out = {};
  for (const [role, p] of Object.entries(parts)) {
    out[role] = p.footprint ?? ((p.w || 1) * (p.h || 1));
  }
  return out;
}

function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }
