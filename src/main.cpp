#include "raylib.h"
#include "bullet_pool.h"
#include "boss.h"
#include "spatial_hash.h"
#include <cstdio>

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
static constexpr int   SCREEN_W      = 1280;
static constexpr int   SCREEN_H      = 720;
static constexpr int   TARGET_FPS    = 60;
static constexpr float PLAYER_SPEED  = 280.0f;
static constexpr float PLAYER_SIZE   = 18.0f;
static constexpr int   INVULN_FRAMES = 90;    // 1.5s at 60 FPS

// ---------------------------------------------------------------------------
// Player
// ---------------------------------------------------------------------------
struct Player {
    float x, y;
    int   invuln_frames;   // countdown while immune; 0 = vulnerable
    int   hit_count;       // total collisions received
};

// Center of the player sprite — used for collision and hitbox render
static inline float player_cx(const Player& p) { return p.x + PLAYER_SIZE * 0.5f; }
static inline float player_cy(const Player& p) { return p.y + PLAYER_SIZE * 0.5f; }

// ---------------------------------------------------------------------------
// Static globals — BSS, allocated once, zero heap during gameplay
// ---------------------------------------------------------------------------
static BulletPool  pool;
static Boss        boss;
static SpatialHash shash;

// ===========================================================================
// UPDATE PHASE — zero draw calls permitted here
// ===========================================================================

static void player_update(Player& p, float dt)
{
    if (IsKeyDown(KEY_W) || IsKeyDown(KEY_UP))    p.y -= PLAYER_SPEED * dt;
    if (IsKeyDown(KEY_S) || IsKeyDown(KEY_DOWN))  p.y += PLAYER_SPEED * dt;
    if (IsKeyDown(KEY_A) || IsKeyDown(KEY_LEFT))  p.x -= PLAYER_SPEED * dt;
    if (IsKeyDown(KEY_D) || IsKeyDown(KEY_RIGHT)) p.x += PLAYER_SPEED * dt;

    if (p.x < 0.0f)                   p.x = 0.0f;
    if (p.y < 0.0f)                   p.y = 0.0f;
    if (p.x + PLAYER_SIZE > SCREEN_W) p.x = SCREEN_W - PLAYER_SIZE;
    if (p.y + PLAYER_SIZE > SCREEN_H) p.y = SCREEN_H - PLAYER_SIZE;

    if (p.invuln_frames > 0) --p.invuln_frames;
}

// Full collision pipeline — clear → build → query
// Called once per frame, after boss.update() and pool.update()
static void collision_update(Player& p)
{
    shash.clear();
    shash.build(pool);

    if (p.invuln_frames == 0) {
        const bool hit = shash.query_player(player_cx(p), player_cy(p), pool);
        if (hit) {
            p.invuln_frames = INVULN_FRAMES;
            ++p.hit_count;
        }
    }
}

// ===========================================================================
// RENDER PHASE — zero state mutation permitted here
// ===========================================================================

static void render_boss(const Boss& b)
{
    const int bx = static_cast<int>(b.x - b.size * 0.5f);
    const int by = static_cast<int>(b.y - b.size * 0.5f);
    const int bs = static_cast<int>(b.size);

    DrawRectangle(bx, by, bs, bs, MAROON);
    DrawRectangleLines(bx, by, bs, bs, RED);
    DrawLine(static_cast<int>(b.x), by,       static_cast<int>(b.x), by + bs, RED);
    DrawLine(bx,      static_cast<int>(b.y),  bx + bs, static_cast<int>(b.y), RED);
}

static void render_bullets(const BulletPool& p)
{
    for (int i = 0; i < MAX_BULLETS; ++i) {
        if (!p.active[i]) continue;
        DrawRectangle(
            static_cast<int>(p.bx[i]) - 3,
            static_cast<int>(p.by[i]) - 3,
            6, 6, ORANGE
        );
    }
}

static void render_player(const Player& p)
{
    // Invulnerability blink: 5 frames visible, 5 frames hidden (10-frame period)
    const bool blink_on = (p.invuln_frames / 5) % 2 == 0;
    if (p.invuln_frames > 0 && !blink_on) return;  // hidden frame — skip body

    const Color body_col = (p.invuln_frames > 0) ? RED : SKYBLUE;
    DrawRectangle(
        static_cast<int>(p.x),
        static_cast<int>(p.y),
        static_cast<int>(PLAYER_SIZE),
        static_cast<int>(PLAYER_SIZE),
        body_col
    );

    // Hitbox dot — always drawn so the player knows their true collision point
    DrawRectangle(
        static_cast<int>(player_cx(p)) - 2,
        static_cast<int>(player_cy(p)) - 2,
        4, 4, WHITE
    );
}

// Debug overlay: visualise which cells the hash has just queried for the player
// Toggle with H key. Draws cyan outlines over the 1-4 neighbourhood cells.
static void render_hash_debug(const Player& p, bool show)
{
    if (!show) return;

    const float r  = PLAYER_RADIUS + BULLET_RADIUS;
    const int   x0 = (static_cast<int>(player_cx(p) - r) / CELL_SIZE);
    const int   x1 = (static_cast<int>(player_cx(p) + r) / CELL_SIZE);
    const int   y0 = (static_cast<int>(player_cy(p) - r) / CELL_SIZE);
    const int   y1 = (static_cast<int>(player_cy(p) + r) / CELL_SIZE);

    for (int gy = y0; gy <= y1; ++gy) {
        for (int gx = x0; gx <= x1; ++gx) {
            if (gx < 0 || gx >= GRID_COLS || gy < 0 || gy >= GRID_ROWS) continue;
            DrawRectangleLines(
                gx * CELL_SIZE, gy * CELL_SIZE, CELL_SIZE, CELL_SIZE,
                Color{0, 255, 200, 80}
            );
        }
    }
}

static void render_hud(int fps, int bullets, int hits, bool debug_on)
{
    char buf[64];

    const Color fps_col = (fps >= 55) ? GREEN : (fps >= 40) ? YELLOW : RED;
    snprintf(buf, sizeof(buf), "FPS: %d", fps);
    DrawText(buf, 10, 10, 20, fps_col);

    const Color blt_col = (bullets >= MAX_BULLETS) ? ORANGE : WHITE;
    snprintf(buf, sizeof(buf), "Bullets: %d / %d", bullets, MAX_BULLETS);
    DrawText(buf, 10, 36, 20, blt_col);

    snprintf(buf, sizeof(buf), "Hits: %d", hits);
    DrawText(buf, 10, 62, 20, (hits > 0) ? RED : WHITE);

    if (bullets >= MAX_BULLETS)
        DrawText("[ POOL SATURATED ]", 10, 88, 18, ORANGE);

    DrawText("[H] Toggle hash grid debug", SCREEN_W - 280, 10, 16, DARKGRAY);
    DrawText("WASD / Arrows — Move",       SCREEN_W - 280, 30, 16, DARKGRAY);

    if (debug_on) {
        snprintf(buf, sizeof(buf), "Grid: %d x %d = %d cells  |  cell = %dpx",
                 GRID_COLS, GRID_ROWS, GRID_CELLS, CELL_SIZE);
        DrawText(buf, 10, SCREEN_H - 28, 16, Color{0, 255, 200, 200});
    }
}

// ===========================================================================
// Entry point
// ===========================================================================

int main()
{
    InitWindow(SCREEN_W, SCREEN_H, "Bullet Hell — Phase 3: Spatial Hash Collision");
    SetTargetFPS(TARGET_FPS);

    pool.init();
    boss.init(SCREEN_W, SCREEN_H);

    Player player = {
        SCREEN_W * 0.5f - PLAYER_SIZE * 0.5f,
        SCREEN_H * 0.80f,
        0, 0
    };

    bool debug_hash = false;

    while (!WindowShouldClose())
    {
        // ---- INPUT (non-movement) ----------------------------------------
        if (IsKeyPressed(KEY_H)) debug_hash = !debug_hash;

        // ---- UPDATE --------------------------------------------------------
        const float dt = GetFrameTime();
        player_update(player, dt);
        boss.update(dt, pool);
        pool.update(dt, SCREEN_W, SCREEN_H);
        collision_update(player);   // clear → build → query

        // ---- RENDER --------------------------------------------------------
        BeginDrawing();
            ClearBackground({ 10, 10, 18, 255 });

            if (debug_hash) {
                // Draw full grid lines at low opacity for spatial context
                for (int c = 0; c <= GRID_COLS; ++c)
                    DrawLine(c * CELL_SIZE, 0, c * CELL_SIZE, SCREEN_H,
                             Color{255,255,255,15});
                for (int r = 0; r <= GRID_ROWS; ++r)
                    DrawLine(0, r * CELL_SIZE, SCREEN_W, r * CELL_SIZE,
                             Color{255,255,255,15});
            }

            render_boss(boss);
            render_bullets(pool);
            render_hash_debug(player, debug_hash);   // cyan query-cell outlines
            render_player(player);
            render_hud(GetFPS(), pool.active_count, player.hit_count, debug_hash);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
