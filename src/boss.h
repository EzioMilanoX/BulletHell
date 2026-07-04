#pragma once
#include <cmath>
#include "bullet_pool.h"

// ---------------------------------------------------------------------------
// Spiral parameters — tuned so the pool reaches ~5000 bullets in steady state:
//
//   Spawn rate  = ARMS / FIRE_RATE = 8 / 0.006 ≈ 1333 bullets/s
//   Lifetime    = avg_screen_distance / B_SPEED ≈ 500px / 150px·s⁻¹ ≈ 3.3s
//   Steady-state ≈ 1333 * 3.7 ≈ 4900  (pool cap clamps it at 5000)
// ---------------------------------------------------------------------------
static constexpr float TWO_PI    = 6.28318530718f;
static constexpr int   ARMS      = 8;
static constexpr float B_SPEED   = 150.0f;   // px/s
static constexpr float FIRE_RATE = 0.006f;   // seconds between ring bursts (~167 Hz)
static constexpr float SPIRAL_DT = 0.05f;    // radians the spiral advances per burst

struct Boss {
    float x, y, size;
    float fire_acc;   // time accumulator — avoids frame-rate-dependent firing
    float angle;      // current leading edge of the spiral

    void init(float sw, float sh) {
        x        = sw * 0.5f;
        y        = sh * 0.5f;
        size     = 48.0f;
        fire_acc = 0.0f;
        angle    = 0.0f;
    }

    // UPDATE phase only — advances accumulator and fires rings
    void update(float dt, BulletPool& pool) {
        fire_acc += dt;
        // Sub-frame loop: fires multiple rings if dt > FIRE_RATE (e.g. on lag spike)
        while (fire_acc >= FIRE_RATE) {
            fire_acc -= FIRE_RATE;
            spawn_ring(pool);
            angle += SPIRAL_DT;
            if (angle >= TWO_PI) angle -= TWO_PI;
        }
    }

private:
    // Spawns one full ring of ARMS bullets equally distributed in angle.
    // Each successive call rotates the ring by SPIRAL_DT → spiral pattern.
    void spawn_ring(BulletPool& pool) {
        const float sep = TWO_PI / ARMS;
        for (int a = 0; a < ARMS; ++a) {
            const int idx = pool.acquire();
            if (idx < 0) return;    // pool at capacity — drop gracefully

            const float theta  = angle + a * sep;
            pool.bx[idx]  = x;
            pool.by[idx]  = y;
            pool.bvx[idx] = cosf(theta) * B_SPEED;
            pool.bvy[idx] = sinf(theta) * B_SPEED;
        }
    }
};
