#pragma once
#include <cstring>
#include "bullet_pool.h"

// ---------------------------------------------------------------------------
// Grid dimensions — hardcoded for 1280x720 with CELL_SIZE=64
//   GRID_COLS = ceil(1280 / 64) = 20
//   GRID_ROWS = ceil( 720 / 64) = 12
//   GRID_CELLS = 240  (player's neighborhood = at most 9 of these)
// ---------------------------------------------------------------------------
static constexpr int  CELL_SIZE  = 64;
static constexpr int  GRID_COLS  = 20;
static constexpr int  GRID_ROWS  = 12;
static constexpr int  GRID_CELLS = GRID_COLS * GRID_ROWS; // 240

// Hitbox radii — true hitbox is intentionally smaller than the sprite
static constexpr float PLAYER_RADIUS   = 5.0f;
static constexpr float BULLET_RADIUS   = 3.0f;
static constexpr float HIT_SQ          = (PLAYER_RADIUS + BULLET_RADIUS) *
                                          (PLAYER_RADIUS + BULLET_RADIUS); // 64.0

// ---------------------------------------------------------------------------
// SpatialHash — Sort-based grid, ZERO dynamic allocation
//
// Why sort-based instead of per-cell vectors or intrusive linked lists?
//
//   After the 3-pass build(), all active bullet indices are scattered into
//   sorted[] such that cell c occupies the contiguous slice:
//       sorted[cell_start[c]  ..  cell_start[c] + cell_count[c] - 1]
//
//   A query reads that slice sequentially — the CPU prefetcher can issue
//   ahead-of-time loads, and the entire sorted[] (20 KB) fits in L2.
//   Linked-list traversal (next[i] → random jump) cannot achieve this.
//
// Memory footprint:
//   cell_count[240] =    960 B
//   cell_start[240] =    960 B
//   write_cur [240] =    960 B   ← mutable cursor during fill pass
//   sorted   [5000] = 20,000 B
//   ─────────────────────────
//   Total           ≈  22 KB    (fits entirely in L2)
//
// Per-frame cost:
//   clear()  → memset 960 B            O(CELLS)
//   build()  → 2×O(N) + O(CELLS)       ~10,240 ops for N=5000
//   query()  → O(cells_hit × K)        K ≈ bullets in ≤9 cells
// ---------------------------------------------------------------------------

struct SpatialHash {
    int cell_count[GRID_CELLS];   // bullet count per cell  (count pass output)
    int cell_start[GRID_CELLS];   // read-only prefix sums  (query uses this)
    int write_cur [GRID_CELLS];   // mutable write cursors  (fill pass only)
    int sorted    [MAX_BULLETS];  // bullet indices, contiguous slices per cell

    // Called at the start of the UPDATE phase each frame
    void clear() {
        memset(cell_count, 0, sizeof(cell_count));
    }

    // 3-pass O(N) build — no heap, no sorting comparison
    void build(const BulletPool& pool) {
        // ------------------------------------------------------------------
        // Pass 1 — COUNT: tally how many bullets land in each cell
        // Sequential reads on pool.active[], pool.bx[], pool.by[]
        // ------------------------------------------------------------------
        for (int i = 0; i < MAX_BULLETS; ++i) {
            if (!pool.active[i]) continue;
            ++cell_count[cell_of(pool.bx[i], pool.by[i])];
        }

        // ------------------------------------------------------------------
        // Pass 2 — PREFIX SUM: turn counts into start offsets
        // cell_start[c] = first index in sorted[] belonging to cell c
        // ------------------------------------------------------------------
        cell_start[0] = 0;
        for (int c = 1; c < GRID_CELLS; ++c)
            cell_start[c] = cell_start[c-1] + cell_count[c-1];

        // write_cur starts equal to cell_start; fill pass advances it
        memcpy(write_cur, cell_start, sizeof(cell_start));

        // ------------------------------------------------------------------
        // Pass 3 — FILL: scatter each bullet index into its cell slice
        // After this pass, sorted[cell_start[c]..+cell_count[c]-1] = cell c
        // ------------------------------------------------------------------
        for (int i = 0; i < MAX_BULLETS; ++i) {
            if (!pool.active[i]) continue;
            sorted[write_cur[cell_of(pool.bx[i], pool.by[i])]++] = i;
        }
    }

    // Query cells overlapping the player's hit circle.
    // Returns true on any collision; releases hit bullets to the pool (O(1)).
    // Skip entirely when player is invulnerable.
    bool query_player(float px, float py, BulletPool& pool) {
        // Expand player AABB by combined radius to get cell range
        const int x0 = cx(px - PLAYER_RADIUS - BULLET_RADIUS);
        const int x1 = cx(px + PLAYER_RADIUS + BULLET_RADIUS);
        const int y0 = cy(py - PLAYER_RADIUS - BULLET_RADIUS);
        const int y1 = cy(py + PLAYER_RADIUS + BULLET_RADIUS);

        bool hit = false;
        for (int gy = y0; gy <= y1; ++gy) {
            for (int gx = x0; gx <= x1; ++gx) {
                const int  c   = gy * GRID_COLS + gx;
                const int  end = cell_start[c] + cell_count[c];

                // Sequential read of sorted[k] — contiguous slice → L1/L2 hit
                for (int k = cell_start[c]; k < end; ++k) {
                    const int idx = sorted[k];

                    // Defensive guard: another hit this frame may have released it
                    if (!pool.active[idx]) continue;

                    const float dx = pool.bx[idx] - px;
                    const float dy = pool.by[idx] - py;
                    if (dx*dx + dy*dy <= HIT_SQ) {
                        pool.release(idx);   // O(1) — free-list push
                        hit = true;
                        // Keep checking: multiple bullets can hit on the same frame
                    }
                }
            }
        }
        return hit;
    }

private:
    // Clamp-and-hash helpers — CELL_SIZE=64=2^6, compiler emits SAR not IDIV
    int cx(float x) const {
        int c = static_cast<int>(x) / CELL_SIZE;
        return c < 0 ? 0 : (c >= GRID_COLS ? GRID_COLS - 1 : c);
    }
    int cy(float y) const {
        int c = static_cast<int>(y) / CELL_SIZE;
        return c < 0 ? 0 : (c >= GRID_ROWS ? GRID_ROWS - 1 : c);
    }
    int cell_of(float x, float y) const { return cy(y) * GRID_COLS + cx(x); }
};
