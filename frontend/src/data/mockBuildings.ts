import type { Building } from '../types/digitalTwin'

// City blocks arranged around the J1–J2–J3–J4–J5 road network
// North block: above the J1-J2-J3 corridor (z > 9)
// East block: right of J3-J4 (x > 10)
// South block: below J4-J5 corridor (z < -9)
// West block: left of J5-J1 (x < -14)
// Central cluster: around J4 (the busy central exchange)

export const buildings: Building[] = [
  // ── NORTH BLOCK (above J1–J2–J3 road, z 10–16) ──────────────────────────
  { id: 'B_N01', x: -15, z: 13,  width: 3.2, depth: 3.2, height: 11, variant: 'tower' },
  { id: 'B_N02', x: -10, z: 12,  width: 4.5, depth: 3.0, height: 5,  variant: 'midrise' },
  { id: 'B_N03', x: -5,  z: 13,  width: 3.0, depth: 3.0, height: 8,  variant: 'tower' },
  { id: 'B_N04', x: -1,  z: 12,  width: 4.0, depth: 3.5, height: 4,  variant: 'commercial' },
  { id: 'B_N05', x:  4,  z: 13,  width: 3.2, depth: 3.2, height: 9,  variant: 'tower' },
  { id: 'B_N06', x:  9,  z: 12,  width: 4.5, depth: 3.0, height: 5,  variant: 'midrise' },
  { id: 'B_N07', x: -13, z: 16,  width: 3.5, depth: 3.0, height: 4,  variant: 'commercial' },
  { id: 'B_N08', x: -7,  z: 15,  width: 3.0, depth: 3.0, height: 6,  variant: 'midrise' },
  { id: 'B_N09', x:  1,  z: 16,  width: 3.5, depth: 3.5, height: 13, variant: 'tower' },
  { id: 'B_N10', x:  7,  z: 15,  width: 4.0, depth: 3.0, height: 3,  variant: 'commercial' },

  // ── EAST BLOCK (right of J3, x 12–18) ────────────────────────────────────
  { id: 'B_E01', x: 13,  z: 7,   width: 3.5, depth: 3.5, height: 10, variant: 'tower' },
  { id: 'B_E02', x: 13,  z: 2,   width: 3.5, depth: 4.0, height: 5,  variant: 'midrise' },
  { id: 'B_E03', x: 13,  z: -3,  width: 3.0, depth: 3.0, height: 3,  variant: 'commercial' },
  { id: 'B_E04', x: 17,  z: 5,   width: 3.0, depth: 3.5, height: 7,  variant: 'tower' },
  { id: 'B_E05', x: 17,  z: -1,  width: 4.0, depth: 3.0, height: 4,  variant: 'corner' },

  // ── SOUTH BLOCK (below J4–J5, z -10 to -17) ──────────────────────────────
  { id: 'B_S01', x:  4,  z: -11, width: 3.5, depth: 3.0, height: 8,  variant: 'tower' },
  { id: 'B_S02', x: -2,  z: -11, width: 4.0, depth: 3.5, height: 4,  variant: 'midrise' },
  { id: 'B_S03', x: -8,  z: -11, width: 4.5, depth: 3.0, height: 3,  variant: 'commercial' },
  { id: 'B_S04', x: -14, z: -11, width: 3.0, depth: 3.0, height: 6,  variant: 'midrise' },
  { id: 'B_S05', x:  1,  z: -15, width: 3.0, depth: 3.0, height: 12, variant: 'tower' },
  { id: 'B_S06', x: -7,  z: -15, width: 4.0, depth: 3.5, height: 5,  variant: 'corner' },

  // ── WEST BLOCK (left of J1/J5, x -17 to -20) ─────────────────────────────
  { id: 'B_W01', x: -18, z: 5,   width: 3.0, depth: 3.5, height: 7,  variant: 'tower' },
  { id: 'B_W02', x: -18, z: -2,  width: 4.0, depth: 3.0, height: 4,  variant: 'midrise' },
  { id: 'B_W03', x: -18, z: -9,  width: 3.5, depth: 3.5, height: 3,  variant: 'commercial' },

  // ── CENTRAL CLUSTER (near J4 central exchange) ────────────────────────────
  { id: 'B_C01', x:  9,  z: -6,  width: 3.0, depth: 3.0, height: 6,  variant: 'midrise' },
  { id: 'B_C02', x: -4,  z: -5,  width: 3.5, depth: 3.0, height: 4,  variant: 'commercial' },
  { id: 'B_C03', x:  6,  z: -10, width: 3.0, depth: 3.5, height: 8,  variant: 'tower' },
]
