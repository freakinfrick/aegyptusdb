/* ═══════════════════════════════════════════════════════════════════════════
 * web/kit/loader.js — classic-script kit loader (exposes window.Kit).
 * ─────────────────────────────────────────────────────────────────────────
 * Mirrors graph/kit.py and web/kit/index.js. Loads kit.json once at boot
 * and hydrates window.Kit with the part table + sizing helpers.
 *
 * We ship a classic-script form (not ES module) so game.js can remain
 * a single <script src> entry in index.html and not require type=module.
 *
 * Usage:
 *   await Kit.load();
 *   const {w, h} = Kit.size_room_for({ papyrus: 12, Wand: 6 });
 *   const role   = Kit.resolve_role('papyrus');
 *   const p      = Kit.parts[role];
 *   Kit.is_text_bearing(role);
 *   Kit.verify_density(composition, w, h);   // returns {ok, density}
 * ═════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  if (window.Kit && window.Kit.__loaded) return;

  function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }

  function footprintMap(parts) {
    const out = {};
    for (const [role, p] of Object.entries(parts)) {
      out[role] = p.footprint ?? ((p.w || 1) * (p.h || 1));
    }
    return out;
  }

  const Kit = {
    __loaded: false,
    version: null,
    packing_density: 0.28,
    hall_styles: {},
    categories: [],
    parts: {},
    text_bearing_roles: new Set(),
    text_type_to_part: {},
    placement_order: [],
    PART_FOOTPRINT: {},

    // Sizing clamps (mirror graph/kit.py ROOM_MIN_W / MAX_W)
    ROOM_MIN_W: 12, ROOM_MAX_W: 64,
    ROOM_MIN_H: 8,  ROOM_MAX_H: 44,
    DENSITY_MIN: 0.22, DENSITY_MAX: 0.45,

    async load(url) {
      url = url || `${window.location.origin}/web/kit/kit.json`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`kit.json load failed: ${resp.status}`);
      const data = await resp.json();
      Kit.version             = data.version;
      Kit.packing_density     = data.packing_density;
      Kit.hall_styles         = data.hall_styles || {};
      Kit.categories          = data.categories || [];
      Kit.parts               = data.parts || {};
      Kit.text_bearing_roles  = new Set(data.text_bearing_roles || []);
      Kit.text_type_to_part   = data.text_type_to_part || {};
      Kit.placement_order     = data.placement_order || [];
      Kit.PART_FOOTPRINT      = footprintMap(Kit.parts);
      Kit.__loaded = true;
      return Kit;
    },

    is_text_bearing(role) { return this.text_bearing_roles.has(role); },
    attach_of(role)       { return (this.parts[role] || {}).attach || 'floor'; },
    is_walkable(role)     { return (this.parts[role] || {}).walk === true; },
    parts_by_category(cat){
      return Object.entries(this.parts).filter(([, p]) => p.cat === cat).map(([k]) => k);
    },
    resolve_role(keyOrTextType) {
      if (keyOrTextType in this.text_type_to_part) return this.text_type_to_part[keyOrTextType];
      if (keyOrTextType in this.parts) return keyOrTextType;
      return 'papyrus_tablet';
    },

    compute_aspect(composition) {
      let wallW = 0, floorW = 0;
      for (const [key, n] of Object.entries(composition)) {
        const role = this.resolve_role(key);
        const p = this.parts[role]; if (!p) continue;
        const fp = this.PART_FOOTPRINT[role] * n;
        const att = p.attach;
        if (att === 'wall' || att === 'wall_sunken' || att === 'wall_band' ||
            att === 'shell' || att === 'above_gateway') {
          wallW += fp;
        } else {
          floorW += fp;
        }
      }
      const total = wallW + floorW;
      if (total <= 0) return 1.2;
      const wallFrac = wallW / total;
      return 1.0 + 0.8 * wallFrac;
    },

    size_room_for(composition) {
      let footprint = 0;
      for (const [key, n] of Object.entries(composition || {})) {
        const role = this.resolve_role(key);
        footprint += (this.PART_FOOTPRINT[role] || 1) * n;
      }
      if (footprint <= 0) return { w: this.ROOM_MIN_W, h: this.ROOM_MIN_H };
      const floorTiles = footprint / this.packing_density;
      const aspect = this.compute_aspect(composition);
      const w = clamp(Math.round(Math.sqrt(floorTiles * aspect)),
                      this.ROOM_MIN_W, this.ROOM_MAX_W);
      const h = clamp(Math.round(Math.sqrt(floorTiles / aspect)),
                      this.ROOM_MIN_H, this.ROOM_MAX_H);
      return { w, h };
    },

    density_for(composition, w, h) {
      let fp = 0;
      for (const [key, n] of Object.entries(composition || {})) {
        const role = this.resolve_role(key);
        fp += (this.PART_FOOTPRINT[role] || 1) * n;
      }
      return fp / Math.max(1, w * h);
    },

    verify_density(composition, w, h) {
      const d = this.density_for(composition, w, h);
      const ok = d >= this.DENSITY_MIN && d <= this.DENSITY_MAX;
      return { ok, density: d, min: this.DENSITY_MIN, max: this.DENSITY_MAX };
    },

    verify_composition(composition, assignedIds) {
      const seen = new Set(); let dup = 0;
      for (const id of assignedIds) { if (seen.has(id)) dup++; seen.add(id); }
      if (dup > 0) return { ok: false, reason: `duplicate canonical_ids (${dup})` };
      let textPartTotal = 0;
      for (const [key, n] of Object.entries(composition || {})) {
        const role = this.resolve_role(key);
        if (this.text_bearing_roles.has(role)) textPartTotal += n;
      }
      if (textPartTotal !== assignedIds.length) {
        return { ok: false, reason: `composition expects ${textPartTotal} text-bearing parts; got ${assignedIds.length} ids` };
      }
      return { ok: true };
    },
  };

  window.Kit = Kit;
})();
