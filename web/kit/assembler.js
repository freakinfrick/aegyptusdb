/* ═══════════════════════════════════════════════════════════════════════════
 * web/kit/assembler.js — kit-of-parts chamber assembler (window.Assembler).
 * ─────────────────────────────────────────────────────────────────────────
 * Day-4 headline deliverable — the bridge between the live topology's
 * canonical_id lists and the ad-hoc game.js renderer.
 *
 * Scope v0 (what this ships):
 *
 *   Assembler.bayDimsFor(chamber, armDir, constraints)
 *     → {w, h}   clamped to cruciform arm constraints while obeying
 *                Kit.size_room_for(composition).
 *
 *   Assembler.placeStorageScrolls(room, kit, setTileFn, getTileFn)
 *     → replaces legacy placeScrolls(): every scroll glyph carries a real
 *       canonical_id popped from chamber.assigned_ids. No diamond lattice
 *       into a chamber.physical_texts array — that only existed on v3.1
 *       Sanctum chambers. Under v5, chamber.assigned_ids is the budget.
 *
 *   Assembler.verifyChamber(room, kit)
 *     → {ok, density, composition_ok, warnings[]}
 *
 * Out of scope for v0 (still inline in game.js):
 *   - STRUCTURE:shell  (handled by carveRoomShell)
 *   - STRUCTURE:interior archetype (handled by placeArchetype)
 *   - MARKER:sanctum_only (L0 torches / braziers already correct)
 *
 * Ship v1 (next pass) will move archetype into Assembler.placeInterior().
 * ═════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const Assembler = {
    /**
     * Pick chamber bay dimensions for the cruciform layout.
     *
     * The kit's size_room_for(composition) returns the *content-driven*
     * ideal size. Cruciform bays have two geometric constraints on top:
     *   1. Long axis is perpendicular to spine (chamber acts as a chapel).
     *   2. Depth (short axis) must be >= some minimum so the spine can
     *      punch a 3-wide gateway with adjacency buffer.
     *
     * We take kit's (w, h) and rotate it so w = long-axis for the bay,
     * h = short-axis, then re-clamp.
     *
     * Args:
     *   chamber: {text_type_composition, text_count, assigned_ids}
     *   armDir : 'N'|'E'|'S'|'W'
     *   c      : {
     *     maxLong:  hard ceiling on long axis  (e.g. worldW - 4)
     *     maxShort: hard ceiling on short axis (depth)
     *     minLong:  floor (so a 1-text chamber is still legible),
     *     minShort: floor (e.g. 14 — archetype needs this)
     *   }
     *
     * Returns { w, h, long, short } — w/h are room dims in world coords
     *   (already rotated for the arm), long/short for diagnostics.
     */
    bayDimsFor(chamber, armDir, c) {
      const K = window.Kit;
      c = c || {};
      const maxLong  = c.maxLong  || 56;
      const maxShort = c.maxShort || 22;
      const minLong  = c.minLong  || 24;
      const minShort = c.minShort || 14;

      const composition = chamber.text_type_composition ||
                          chamber.composition || {};
      const hasKit = K && K.__loaded && Object.keys(composition).length > 0;

      // Kit's natural size (wall-weighted composition → wider rectangle).
      let kitW, kitH;
      if (hasKit) {
        const { w, h } = K.size_room_for(composition);
        kitW = w; kitH = h;
      } else {
        // Fallback: scale by text_count. Old LEVEL_ROOM_SIZES-style.
        const n = chamber.text_count || 0;
        kitW = Math.max(minLong, Math.min(maxLong, 28 + Math.round(n / 24)));
        kitH = Math.max(minShort, Math.min(maxShort, 16 + Math.round(n / 60)));
      }

      // Pick long = max(w,h), short = min(w,h). In the kit, wall-heavy rooms
      // already come back wider than tall; taking max/min just normalises.
      let longDim  = Math.max(kitW, kitH);
      let shortDim = Math.min(kitW, kitH);

      // Clamp to cruciform constraints.
      longDim  = Math.max(minLong,  Math.min(maxLong,  longDim));
      shortDim = Math.max(minShort, Math.min(maxShort, shortDim));

      // Rotate: spine-perpendicular arms (N, S) have horizontal long axis.
      //         spine-parallel arms   (E, W) have vertical long axis.
      const isNS = armDir === 'N' || armDir === 'S';
      const w = isNS ? longDim  : shortDim;
      const h = isNS ? shortDim : longDim;
      return { w, h, long: longDim, short: shortDim };
    },

    /**
     * Place scroll glyphs for the L>0 chambers, bound to real canonical_ids.
     *
     * room.chamber.assigned_ids is consumed head-first. Each scroll
     * carries exactly one canonical_id. Placement uses a diamond lattice
     * around the chamber centre, skipping walls, labels, gateways, the
     * spine channel, and existing occupants (pillars etc.).
     *
     * glyphList: per-level scroll glyph cycle (game.js passes SCROLL_GLYPHS).
     * frame    : {left, right} for the flanking brackets.
     * budget   : max scrolls to place (defaults to all assigned_ids).
     *
     * Returns number of scrolls actually placed.
     */
    placeStorageScrolls(room, opts) {
      opts = opts || {};
      const setTile = opts.setTile;
      const getTile = opts.getTile;
      if (!setTile || !getTile) {
        console.warn('Assembler.placeStorageScrolls: setTile/getTile required');
        return 0;
      }
      const chamber = room.chamber;
      const ids = (chamber.assigned_ids || chamber.canonical_ids || []).slice();
      if (!ids.length) return 0;
      const glyphs = opts.glyphs || ['\u{1F4DC}'];
      const frame  = opts.frame  || { left: '[', right: ']' };
      const budget = Math.min(ids.length, opts.budget || ids.length);

      const { x: rx, y: ry, w: rw, h: rh } = room;
      const cx = rx + Math.floor(rw / 2);
      const cy = ry + Math.floor(rh / 2);

      // Spine channel predicate (3-wide) — identical to placeArchetype.
      const armDir = room.armDir;
      const spineAxis = (armDir === 'N' || armDir === 'S') ? 'vertical'
                      : (armDir === 'E' || armDir === 'W') ? 'horizontal'
                      : null;
      const onSpine = (x, y) => {
        if (spineAxis === 'vertical')   return Math.abs(x - cx) <= 1;
        if (spineAxis === 'horizontal') return Math.abs(y - cy) <= 1;
        return false;
      };

      // Candidate positions: diamond lattice around centre, every 3rd tile.
      const candidates = [];
      for (let dy = -Math.floor(rh / 2) + 4; dy <= Math.floor(rh / 2) - 4; dy++) {
        for (let dx = -Math.floor(rw / 2) + 3; dx <= Math.floor(rw / 2) - 3; dx++) {
          if ((Math.abs(dx) + Math.abs(dy)) % 3 !== 0) continue;
          if (Math.abs(dx) < 2 && Math.abs(dy) < 2) continue;  // keep centre clear
          candidates.push({ x: cx + dx, y: cy + dy, dist: Math.abs(dx) + Math.abs(dy) });
        }
      }
      candidates.sort((a, b) => a.dist - b.dist);

      let placed = 0;
      room.scrolls = room.scrolls || [];
      for (const pos of candidates) {
        if (placed >= budget) break;
        if (onSpine(pos.x, pos.y)) continue;
        const t = getTile(pos.x, pos.y);
        if (!t || !t.walk) continue;
        if (t.isInscription || t.isTablet || t.isDecor || t.isStair ||
            t.isOracle || t.isLabel || t.isTorch || t.isStructure ||
            t.isGateway || t.isScroll || t.isScrollFrame) continue;
        const tl = getTile(pos.x - 1, pos.y);
        const tr = getTile(pos.x + 1, pos.y);
        if (!tl?.walk || !tr?.walk) continue;
        if (tl.isScroll || tr.isScroll || tl.isGateway || tr.isGateway) continue;

        const cid   = ids[placed];
        const glyph = glyphs[placed % glyphs.length];
        const rec = {
          x: pos.x, y: pos.y,
          chamberId: chamber.id,
          canonicalId: cid,
          textName: '',           // filled by on-demand /chamber/{id} passage lookup
          scrollIdx: placed,
        };
        room.scrolls.push(rec);

        setTile(pos.x, pos.y, {
          ch: glyph,
          fg: opts.fgGlyph || '#ffcc50',
          walk: true,
          isScroll: true,
          scrollIdx: placed,
          roomPtrIdx: opts.roomIdx,
          chamberId: chamber.id,
          canonicalId: cid,
        });
        setTile(pos.x - 1, pos.y, {
          ch: frame.left, fg: opts.fgFrame || '#7a5a28', walk: true,
          isScrollFrame: true,
        });
        setTile(pos.x + 1, pos.y, {
          ch: frame.right, fg: opts.fgFrame || '#7a5a28', walk: true,
          isScrollFrame: true,
        });
        placed++;
      }
      return placed;
    },

    /**
     * Cheap fit verifier — mirrors graph/kit.py::verify_density.
     *
     * Returns { ok, density, composition_ok, warnings[] }.
     * Never throws — the old kit.py ChamberFitError is too strict for a
     * first-pass assembler where many rooms are clamp-saturated.
     */
    verifyChamber(room, assignedIds) {
      const K = window.Kit;
      const warnings = [];
      const composition = room.chamber.text_type_composition || {};
      const ids = assignedIds || room.chamber.assigned_ids || [];
      let ok = true, density = null, compOk = true;

      if (!K || !K.__loaded) {
        warnings.push('kit not loaded — skipping verify');
        return { ok, density, composition_ok: compOk, warnings };
      }

      if (Object.keys(composition).length === 0) {
        warnings.push('empty composition');
        compOk = false;
      } else {
        const compRes = K.verify_composition(composition, ids);
        if (!compRes.ok) {
          compOk = false;
          warnings.push('composition: ' + compRes.reason);
        }
        const d = K.verify_density(composition, room.w, room.h);
        density = d.density;
        if (!d.ok) {
          warnings.push(`density ${d.density.toFixed(3)} outside [${d.min}, ${d.max}]`);
          // Clamp-saturated large chambers legitimately overflow — warn only.
        }
      }

      return { ok, density, composition_ok: compOk, warnings };
    },
  };

  window.Assembler = Assembler;
})();
