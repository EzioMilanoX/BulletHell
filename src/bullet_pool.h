#pragma once
#include <cstring>

static constexpr int MAX_BULLETS = 5000;

// ---------------------------------------------------------------------------
// BulletPool — SoA layout with O(1) free-list
//
// Memory model: ONE static allocation at startup; zero heap activity during
// gameplay. The free-list is a stack of available indices. acquire() pops,
// release() pushes — both are a single array write + integer decrement/increment.
//
// SoA rationale: update() streams bx/by/bvx/bvy sequentially.
// Each 5000-element array fits in L2; the CPU prefetcher loads ahead without
// effort. An AoS layout (Bullet structs) would interleave unrelated fields and
// thrash cache lines during the tight update loop.
// ---------------------------------------------------------------------------

struct BulletPool {
    // --- Data streams (read sequentially in update/render) ---
    float bx  [MAX_BULLETS];
    float by  [MAX_BULLETS];
    float bvx [MAX_BULLETS];
    float bvy [MAX_BULLETS];
    bool  active[MAX_BULLETS];

    // --- Free-list stack ---
    int  free_stack[MAX_BULLETS];
    int  free_top;          // stack pointer; decrements on acquire, increments on release

    int  active_count;      // live HUD counter

    void init() {
        memset(active, 0, sizeof(active));
        active_count = 0;
        free_top     = MAX_BULLETS;
        for (int i = 0; i < MAX_BULLETS; ++i)
            free_stack[i] = i;
    }

    // O(1) — pop a free index; returns -1 if pool is saturated
    int acquire() {
        if (free_top == 0) return -1;
        const int idx = free_stack[--free_top];
        active[idx] = true;
        ++active_count;
        return idx;
    }

    // O(1) — push index back; caller must have set active[idx] data beforehand
    void release(int idx) {
        active[idx] = false;
        free_stack[free_top++] = idx;
        --active_count;
    }

    // Called once per frame in the UPDATE phase — never in RENDER
    void update(float dt, float sw, float sh) {
        constexpr float M = 12.0f;   // margin beyond screen edge before despawn
        for (int i = 0; i < MAX_BULLETS; ++i) {
            if (!active[i]) continue;

            // Integrate velocity — sequential writes to bx[] then by[]
            bx[i] += bvx[i] * dt;
            by[i] += bvy[i] * dt;

            // Out-of-bounds → O(1) return to pool
            if (bx[i] < -M || bx[i] > sw + M ||
                by[i] < -M || by[i] > sh + M)
                release(i);
        }
    }
};
