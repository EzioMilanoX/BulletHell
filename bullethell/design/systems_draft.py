# ============================================================================
# OuroborosEngine — Sistemas do Bullet Hell
# ----------------------------------------------------------------------------
# Toda a lógica vive aqui. Componentes (components.py) são dados puros;
# storages SoA (resources.py) carregam o hot path vetorizado.
#
# Premissa de API (MIGRATION.md §4): além de world.create() /
# world.add_component(id, c) / world.get_component(id, C), assumo o join
# do sparse-set como world.view(A, B, ...) -> iterável de (eid, a, b, ...).
#
# `res` é o bundle de resources: res.clock, res.input, res.ebullets,
# res.particles, res.damage, res.mutators, res.db_* (loaders), res.pools.
#
# Agenda (ordem por frame): ver MIGRATION.md §3.
# ============================================================================
import math
import numpy as np

from .components import *          # dataclasses puras + flyweights
from . import resources as R

TWO_PI = math.tau
SCREEN_W, SCREEN_H = 640, 780      # herdados do legado


# ===========================================================================
# 1. Núcleo
# ===========================================================================

class MovementSystem:
    """Integra Transform += Velocity * dt para TODAS as entidades móveis.
    [Regra inegociável 2: física padrão, escalada por delta_time.]
    Entidades com OrbitAround não têm Velocity — quem as move é o
    OrbitSystem, então elas nem aparecem neste join."""

    def update(self, world, res):
        dt = res.clock.dt_world
        for eid, t, v in world.view(Transform, Velocity, Enabled):
            t.x += v.vx * dt
            t.y += v.vy * dt
        # Jogador usa dt_player (FOCUS desacelera o mundo, não ele) —
        # o PlayerControlSystem escreve direto no Transform do player.


class LifetimeSystem:
    def update(self, world, res):
        dt = res.clock.dt_world
        for eid, life in world.view(Lifetime, Enabled):
            life.t -= dt
            if life.t <= 0.0:
                so = world.get_component(eid, SpawnOnExpire)
                if so is not None:                      # PLASMA+ → poça
                    res.pools.spawn_player_bullet(world, so.archetype,
                                                  at_entity=eid, vx=0.0, vy=0.0)
                res.pools.despawn(world, eid)           # remove Enabled


class DamageSystem:
    """Drena o DamageRing → aplica em Health, roteando BossPart → root.
    Fica no FIM do frame: uma única passada de aplicação de dano."""

    def update(self, world, res):
        ring = res.damage
        for i in range(ring.n):
            eid, amount = int(ring.target[i]), float(ring.amount[i])
            part = world.get_component(eid, BossPart)
            if part is not None:
                eid = part.root
            hp = world.get_component(eid, Health)
            if hp is not None:
                hp.hp -= amount
                fl = world.get_component(eid, HitFlash)
                if fl is not None:
                    fl.t = 0.08
        ring.clear()


# ===========================================================================
# 2. Boss — fases, movimento, emissão data-driven
# ===========================================================================

class BossPhaseSystem:
    """Quando hp/max cruza o threshold da próxima fase (bosses.json),
    troca o conjunto de Emitters: desativa os filhos atuais e ativa os
    da nova fase (entidades-emitter pré-criadas no setup do boss)."""

    def update(self, world, res):
        for eid, ph, hp in world.view(BossPhases, Health, Enabled):
            bdef = res.db_bosses[ph.boss_id]
            frac = hp.hp / hp.max_hp
            nxt = ph.index + 1
            if nxt < len(bdef.phases) and frac <= bdef.phases[ph.index].hp_above:
                ph.index = nxt
                res.pools.swap_emitters(world, boss=eid,
                                        phase=bdef.phases[nxt])


class WaypointSystem:
    """Movimento por waypoints com easing smoothstep (rota em bosses.json)."""

    def update(self, world, res):
        dt = res.clock.dt_world
        for eid, wm, t in world.view(WaypointMover, Transform, Enabled):
            route = res.db_bosses_routes[wm.route_id]
            if not route:
                continue
            x0, y0, _ = route[wm.seg % len(route)]
            x1, y1, dur = route[(wm.seg + 1) % len(route)]
            wm.seg_t += dt
            u = min(wm.seg_t / dur, 1.0)
            s = u * u * (3.0 - 2.0 * u)              # smoothstep
            t.x = x0 + (x1 - x0) * s
            t.y = y0 + (y1 - y0) * s
            if u >= 1.0:
                wm.seg += 1
                wm.seg_t = 0.0


class EmitterSystem:
    """O coração data-driven: executa PatternDefs (patterns.json) gravando
    LOTES vetorizados no EnemyBulletStorage. Um método por tipo de emissão;
    adicionar um `emit` novo = 1 método + entradas no JSON, nenhuma classe."""

    def update(self, world, res):
        dt = res.clock.dt_world
        px, py = res.player_pos                       # cache do frame
        for eid, em, t in world.view(Emitter, Transform, Enabled):
            if em.warmup_t > 0.0:                     # fake prep: telegrafa
                em.warmup_t -= dt
                continue
            pat = res.db_patterns[em.pattern_id]
            em.t += dt
            while em.t >= pat.period:
                em.t -= pat.period
                ox, oy = t.x + em.offset_x, t.y + em.offset_y
                getattr(self, "_emit_" + pat.emit)(res, pat, em, ox, oy, px, py)

    # -- tipos de emissão ---------------------------------------------------

    def _emit_arc(self, res, pat, em, ox, oy, px, py):
        """Leque: `count` balas em `arc` rad, centrado na mira."""
        aim = (math.atan2(py - oy, px - ox) if pat.aim == "player"
               else math.pi / 2)                       # "down"/"fixed"
        n = pat.count
        th = (np.linspace(aim - pat.arc / 2, aim + pat.arc / 2, n)
              if n > 1 else np.full(1, aim))
        self._write(res, pat, ox, oy,
                    np.cos(th) * pat.speed, np.sin(th) * pat.speed)

    def _emit_ring(self, res, pat, em, ox, oy, px, py):
        """Anel com vão de fuga rotativo (classic/ring do legado)."""
        th = np.arange(pat.count) * (TWO_PI / pat.count)
        if pat.gap > 0.0:
            to_p = math.atan2(py - oy, px - ox)
            gap_c = to_p + math.pi / 2 + em.shot_count * pat.gap_step
            d = np.abs(((th - gap_c + math.pi) % TWO_PI) - math.pi)
            th = th[d > pat.gap / 2]
        em.shot_count += 1
        self._write(res, pat, ox, oy,
                    np.cos(th) * pat.speed, np.sin(th) * pat.speed)

    def _emit_spiral(self, res, pat, em, ox, oy, px, py):
        """Braços girando spin_speed rad/s; 1 bala/braço por disparo."""
        em.phase_angle += pat.spin_speed * pat.period
        th = em.phase_angle + np.arange(pat.arms) * (TWO_PI / pat.arms)
        self._write(res, pat, ox, oy,
                    np.cos(th) * pat.speed, np.sin(th) * pat.speed)

    def _emit_rain(self, res, pat, em, ox, oy, px, py):
        """Colunas do topo com fração `gap` de vãos (wall/rain)."""
        cols = np.arange(pat.count)
        keep = res.rng.random(pat.count) > pat.gap
        xs = (cols[keep] + 0.5) * (SCREEN_W / pat.count)
        n = xs.size
        self._write(res, pat, xs, np.zeros(n, np.float32),
                    np.zeros(n, np.float32), np.full(n, pat.speed, np.float32))

    def _emit_stream(self, res, pat, em, ox, oy, px, py):
        """Stream 1-a-1 rastreando player_x com suavização (wall/pillar)."""
        if pat.track == "player_x":
            em.phase_angle += (px - em.phase_angle) * 0.12   # lerp do X
            ox = em.phase_angle
        self._write(res, pat, ox, oy, 0.0, pat.speed)

    def _emit_pair(self, res, pat, em, ox, oy, px, py):
        """Duas balas ligadas (tether): grava e amarra os índices."""
        aim = math.atan2(py - oy, px - ox)
        th = np.array([aim - pat.arc / 2, aim + pat.arc / 2])
        idx = self._write(res, pat, ox, oy,
                          np.cos(th) * pat.speed, np.sin(th) * pat.speed)
        if idx is not None and len(idx) == 2:
            res.ebullets.tether[idx[0]] = idx[1]
            res.ebullets.tether[idx[1]] = idx[0]

    def _emit_laser(self, res, pat, em, ox, oy, px, py):
        """Lasers são entidades (≤16), não balas de storage."""
        for _ in range(pat.count):
            res.pools.spawn_laser(res.rng)

    # -- gravação em lote no storage -----------------------------------------

    def _write(self, res, pat, x, y, vx, vy):
        """Aloca N slots da free-list e grava colunas + arquétipo de uma vez.
        Alocação zero: só indexação NumPy em arrays pré-existentes."""
        st, arch = res.ebullets, res.db_archetypes[pat.bullet]
        n = np.size(vx)
        if len(st._free) < n:
            return None
        idx = np.array([st._free.pop() for _ in range(n)], np.int32)
        st.x[idx] = x;  st.y[idx] = y
        st.vx[idx] = vx; st.vy[idx] = vy
        st.active[idx] = True
        st.contact[idx] = arch.contact
        st.color[idx] = arch.color
        st.radius[idx] = arch.radius
        st.grazed[idx] = False
        st.beh[idx] = arch.beh
        st.beh_t[idx] = arch.beh_params[0] if arch.beh_params else 0.0
        st.stage[idx] = 0
        st.homing_t[idx] = arch.homing_t
        st.spin[idx] = arch.spin
        st.phase_p[idx] = arch.phase_period
        st.gravity[idx] = arch.gravity
        st.bounces[idx] = arch.bounces
        st.fragment[idx] = arch.fragment
        if arch.beh == R.BEH_STOPGO:                  # snapshot do jogador
            st.tgt_x[idx], st.tgt_y[idx] = res.player_pos
        return idx


# ===========================================================================
# 3. Kernel das balas inimigas (NumPy — hot path, ver MIGRATION.md §1)
# ===========================================================================

class EnemyBulletKernelSystem:
    """Uma passada vetorizada por comportamento. Nenhum loop Python sobre
    balas individuais, exceto os comportamentos raros (stop&go/boomerang:
    dezenas de balas por vez — o legado já fazia igual)."""

    def update(self, world, res):
        st, dt = res.ebullets, res.clock.dt_world
        a = st.active
        px, py = res.player_pos

        # HOMING (roxa): curva para o jogador enquanto homing_t > 0
        h = a & (st.homing_t > 0.0)
        if h.any():
            st.homing_t[h] -= dt
            dx = px - st.x[h];  dy = py - st.y[h]
            d = np.sqrt(dx * dx + dy * dy) + 1e-6
            st.vx[h] += (dx / d) * 260.0 * dt
            st.vy[h] += (dy / d) * 260.0 * dt

        # SPIN: rotaciona vetor velocidade
        s = a & (st.spin != 0.0)
        if s.any():
            ang = st.spin[s] * dt
            c, sn = np.cos(ang), np.sin(ang)
            vx, vy = st.vx[s].copy(), st.vy[s]
            st.vx[s] = vx * c - vy * sn
            st.vy[s] = vx * sn + vy * c

        # PHASE: acumula timer (o PlayerHitSystem lê a janela sólida)
        p = a & (st.phase_p > 0.0)
        st.phase_t[p] += dt

        # GRAVITY: puxa o jogador (efeito de campo — escreve no resource)
        g = a & (st.gravity > 0.0)
        if g.any():
            dx = px - st.x[g];  dy = py - st.y[g]
            d = np.sqrt(dx * dx + dy * dy) + 1e-6
            res.player_pull[0] -= float(np.sum(dx / d * st.gravity[g])) * dt
            res.player_pull[1] -= float(np.sum(dy / d * st.gravity[g])) * dt

        # STOP&GO / BOOMERANG / SLEEPER: máquina de estados (poucas balas)
        beh = a & (st.beh != R.BEH_NONE)
        for i in np.where(beh)[0]:
            st.beh_t[i] -= dt
            if st.beh_t[i] > 0.0:
                continue
            arch_dispatch(st, i, res)                # transições (abaixo)

        # MOVIMENTO (todas) — regra 2: velocity * delta_time
        st.x[a] += st.vx[a] * dt
        st.y[a] += st.vy[a] * dt

        # RICOCHETE nas bordas
        b = a & (st.bounces > 0)
        if b.any():
            out = b & ((st.x < 0) | (st.x > SCREEN_W))
            st.vx[out] = -st.vx[out]
            st.bounces[out] -= 1

        # CULL fora da tela (+ fragmentação ABISSAL antes de liberar)
        out = a & ((st.x < -24) | (st.x > SCREEN_W + 24) |
                   (st.y < -24) | (st.y > SCREEN_H + 24))
        frag = out & st.fragment
        for i in np.where(frag)[0]:
            spawn_fragment_pair(st, i)               # ±30°, herda módulo/cor
        for i in np.where(out)[0]:
            st.active[i] = False
            st.tether[i] = -1
            st._free.append(int(i))


def arch_dispatch(st, i, res):
    """Transições de estado (stop&go: para → espera → relança no snapshot;
    boomerang: inverte ×fator; sleeper: acorda mirando o jogador).
    Parâmetros por arquétipo em bullet_archetypes.json."""
    arch = res.db_archetypes_by_row(st, i)
    if st.beh[i] == R.BEH_STOPGO:
        if st.stage[i] == 0:                          # voando → parada
            st.vx[i] = st.vy[i] = 0.0
            st.stage[i] = 1
            st.beh_t[i] = arch.beh_params[1]          # pause_t (1.80)
        else:                                         # parada → relança
            dx = st.tgt_x[i] - st.x[i];  dy = st.tgt_y[i] - st.y[i]
            d = math.hypot(dx, dy) or 1.0
            spd = arch.beh_params[2]                  # 260 px/s
            st.vx[i] = dx / d * spd;  st.vy[i] = dy / d * spd
            st.beh[i] = R.BEH_NONE
    elif st.beh[i] == R.BEH_BOOMERANG:
        f = arch.beh_params[1]                        # ×1.8
        st.vx[i] *= -f;  st.vy[i] *= -f
        st.beh[i] = R.BEH_NONE
    elif st.beh[i] == R.BEH_SLEEPER:
        px, py = res.player_pos
        dx = px - st.x[i];  dy = py - st.y[i]
        d = math.hypot(dx, dy) or 1.0
        spd = arch.beh_params[1]                      # 145 px/s
        st.vx[i] = dx / d * spd;  st.vy[i] = dy / d * spd
        st.beh[i] = R.BEH_NONE


def spawn_fragment_pair(st, i):
    """2 fragmentos em ±30° da direção de retorno, herdando |v| e cor."""
    if len(st._free) < 2:
        return
    spd = math.hypot(st.vx[i], st.vy[i])
    back = math.atan2(-st.vy[i], -st.vx[i])
    for dth in (-0.524, 0.524):
        j = st._free.pop()
        st.x[j] = st.x[i];  st.y[j] = st.y[i]
        st.vx[j] = math.cos(back + dth) * spd
        st.vy[j] = math.sin(back + dth) * spd
        st.active[j] = True
        st.color[j] = st.color[i]
        st.contact[j] = R.CONTACT_ALWAYS
        st.fragment[j] = False
        st.bounces[j] = 0


# ===========================================================================
# 4. Colisão
# ===========================================================================

class PlayerHitSystem:
    """Jogador × storage: check vetorizado completo (5000 distâncias em
    NumPy custam ~µs — mais rápido que manter um spatial hash em Python).
    Aplica ContactRule, janela sólida do PHASE, tether ponto-segmento e
    graze (anel entre HIT e GRAZE, 1×/bala, reduz skill_cd)."""

    HIT_R, GRAZE_R = 10.0, 26.0

    def update(self, world, res):
        st = res.ebullets
        p_eid = res.player_eid
        lives = world.get_component(p_eid, Lives)
        if lives.invuln_t > 0.0:
            lives.invuln_t -= res.clock.dt_world
        px, py = res.player_pos
        moving = res.input.mx != 0.0 or res.input.my != 0.0

        a = st.active & (st.contact != R.CONTACT_NEVER)
        dx = st.x - px;  dy = st.y - py
        d2 = dx * dx + dy * dy

        # regra de contato + fase sólida
        harmful = a.copy()
        harmful &= ~((st.contact == R.CONTACT_IF_MOVING) & (not moving))
        harmful &= ~((st.contact == R.CONTACT_IF_STILL) & moving)
        ph = st.phase_p > 0.0
        harmful[ph] &= (st.phase_t[ph] % st.phase_p[ph]) < (st.phase_p[ph] * 0.5)

        hit_r2 = (self.HIT_R + st.radius) ** 2
        hits = harmful & (d2 <= hit_r2)
        if hits.any() and lives.invuln_t <= 0.0:
            res.events.player_hit = True             # PlayerDamageSystem resolve
            for i in np.where(hits)[0]:
                st.active[i] = False
                st._free.append(int(i))

        # graze — anel externo, uma vez por bala
        gz = a & ~st.grazed & (d2 <= self.GRAZE_R ** 2) & (d2 > hit_r2)
        n = int(gz.sum())
        if n:
            st.grazed[gz] = True
            gm = world.get_component(p_eid, GrazeMeter)
            gm.count += n
            sk = world.get_component(p_eid, SkillSlot)
            sk.cd_left = max(0.0, sk.cd_left - 0.08 * n)


class PlayerBulletVsBossSystem:
    """≤256 balas-entidade × AABBs do boss (BossPart). Loop Python é ok
    nesta escala. Trata: PierceOnHit (não consome + CD), ShrapnelOnHit
    (estilhaços no impacto), DoTBeam (dano contínuo SEM consumir — a regra
    que corrigiu o bug do plasma no legado), Damage normal (consome)."""

    def update(self, world, res):
        dt = res.clock.dt_world
        gc = 3.0 if res.mutators.glass_cannon else 1.0
        emp = world.get_component(res.player_eid, EmpBuff)
        mult = gc * (emp.mult if emp and emp.t_left > 0.0 else 1.0)

        for beid, bt, part, box in world.view(Transform, BossPart, AABBHitbox, Enabled):
            x0, x1 = bt.x - box.half_w, bt.x + box.half_w
            y0, y1 = bt.y - box.half_h, bt.y + box.half_h
            for eid, t, dmg in world.view(Transform, Damage, Enabled):
                if not (x0 <= t.x <= x1 and y0 <= t.y <= y1):
                    continue
                dot = world.get_component(eid, DoTBeam)
                if dot is not None:                    # plasma: nunca consome
                    push_damage(res, beid, dot.dps * dt * mult)
                    continue
                pierce = world.get_component(eid, PierceOnHit)
                if pierce is not None and pierce.t_left > 0.0:
                    continue                           # atravessando em CD
                push_damage(res, beid, dmg.amount * mult)
                shr = world.get_component(eid, ShrapnelOnHit)
                if shr is not None:
                    res.pools.spawn_shrapnel(world, t.x, t.y, shr)
                if pierce is not None:
                    pierce.t_left = pierce.cooldown    # segue viva
                else:
                    res.pools.despawn(world, eid)


def push_damage(res, target: int, amount: float):
    ring = res.damage
    if ring.n < len(ring.target):
        ring.target[ring.n] = target
        ring.amount[ring.n] = amount
        ring.n += 1


# ===========================================================================
# 5. Balas do jogador — comportamentos (loops pequenos, ≤256)
# ===========================================================================

class OrbitSystem:
    """SATÉLITE/TELEGUIADO+: escreve Transform a partir do âncora."""
    def update(self, world, res):
        dt = res.clock.dt_world
        for eid, orb, t in world.view(OrbitAround, Transform, Enabled):
            orb.angle = (orb.angle + orb.angular_speed * dt) % TWO_PI
            at = world.get_component(orb.anchor, Transform)
            t.x = at.x + math.cos(orb.angle) * orb.radius
            t.y = at.y + math.sin(orb.angle) * orb.radius


class DelayedAccelSystem:
    """BURST+: após arm_t, dispara a max_speed na direção capturada."""
    def update(self, world, res):
        dt = res.clock.dt_world
        for eid, da, v in world.view(DelayedAccel, Velocity, Enabled):
            if da.armed:
                continue
            da.arm_t -= dt
            if da.arm_t <= 0.0:
                da.armed = True
                v.vx = da.aim_x * da.max_speed
                v.vy = da.aim_y * da.max_speed


class FuseSystem:
    """FLAK: countdown → detona no padrão do JSON. FLAK+: fire segura o
    timer congelado; soltar (edge) zera tudo → detonação simultânea."""
    def update(self, world, res):
        dt = res.clock.dt_world
        ws = world.get_component(res.player_eid, WeaponSlot)
        for eid, fz, t in world.view(Fuse, Transform, Enabled):
            if ws.plus:
                fz.frozen = ws.fire_held
                if ws.fire_released:
                    fz.t_left = 0.0
            if not fz.frozen:
                fz.t_left -= dt
            if fz.t_left <= 0.0:
                res.pools.spawn_player_pattern(world, fz.spawn_pattern, t.x, t.y)
                res.pools.despawn(world, eid)


class ChakramSystem:
    """OUT: drag desacelera; |v|≈0 → RETURN (ou FROZEN com fire seguro no
    CHAKRAM+, aplicando frozen_dps). RETURN: acelera ao dono; captura a
    catch_radius devolve ao pool."""
    def update(self, world, res):
        dt = res.clock.dt_world
        ws = world.get_component(res.player_eid, WeaponSlot)
        pt = world.get_component(res.player_eid, Transform)
        for eid, ck, t, v in world.view(ChakramMotion, Transform, Velocity, Enabled):
            spd = math.hypot(v.vx, v.vy)
            if ck.state == CHAKRAM_OUT:
                if spd > 12.0:
                    f = max(0.0, 1.0 - ck.drag * dt / spd)
                    v.vx *= f;  v.vy *= f
                elif ws.plus and ws.fire_held:
                    ck.state = CHAKRAM_FROZEN
                    v.vx = v.vy = 0.0
                else:
                    ck.state = CHAKRAM_RETURN
            elif ck.state == CHAKRAM_FROZEN:
                if res.boss_eid >= 0:
                    push_damage(res, res.boss_eid, ck.frozen_dps * dt)
                if not ws.fire_held:
                    ck.state = CHAKRAM_RETURN
            else:                                      # RETURN
                dx, dy = pt.x - t.x, pt.y - t.y
                d = math.hypot(dx, dy) or 1.0
                v.vx = dx / d * 580.0;  v.vy = dy / d * 580.0
                if d < ck.catch_radius:
                    res.pools.despawn(world, eid)


class HomingToBossSystem:
    def update(self, world, res):
        dt = res.clock.dt_world
        bt = world.get_component(res.boss_eid, Transform)
        if bt is None:
            return
        for eid, hm, t, v in world.view(HomingToBoss, Transform, Velocity, Enabled):
            hm.t_left -= dt
            if hm.t_left <= 0.0:
                continue
            dx, dy = bt.x - t.x, bt.y - t.y
            d = math.hypot(dx, dy) or 1.0
            v.vx += dx / d * hm.turn_accel * dt
            v.vy += dy / d * hm.turn_accel * dt
            spd = math.hypot(v.vx, v.vy)
            if spd > hm.max_speed:
                v.vx *= hm.max_speed / spd;  v.vy *= hm.max_speed / spd


# ===========================================================================
# 6. Disparo do jogador (weapons.json — receitas de componentes)
# ===========================================================================

_RECIPE_TYPES = {c.__name__: c for c in (
    WallBounce, RangeLimit, PierceOnHit, ShrapnelOnHit, DelayedAccel,
    Fuse, ChakramMotion, DoTBeam, SpawnOnExpire, OrbitAround,
    AutoLaunch, HomingToBoss, Lifetime)}


class WeaponFireSystem:
    """Consome WeaponSlot + WeaponDef e spawna balas-entidade do pool.
    O QUE cada arma faz não vive aqui: vive na receita do JSON — este
    sistema só executa cadência (e os dois estados especiais: carga e
    rajada). Balas saem do pool pré-criado; a receita só RESETA campos
    dos componentes já anexados (zero alocação; MIGRATION.md §4)."""

    def update(self, world, res):
        dt = res.clock.dt_player
        eid = res.player_eid
        ws = world.get_component(eid, WeaponSlot)
        wd = res.db_weapons[ws.weapon_id if not ws.plus
                            else res.plus_id(ws.weapon_id)]
        t = world.get_component(eid, Transform)
        ws.fire_cd -= dt

        ch = world.get_component(eid, ChargeState)
        if ch is not None:                             # CARREGADO
            self._charged(world, res, ws, wd, ch, t, dt)
            return
        bs = world.get_component(eid, BurstState)
        if bs is not None and bs.shots_left > 0:       # meio da rajada
            bs.interval_t -= dt
            if bs.interval_t <= 0.0:
                bs.interval_t = 0.05
                bs.shots_left -= 1
                self._fire(world, res, ws, wd, t)
            return
        if ws.fire_held and ws.fire_cd <= 0.0:
            ws.fire_cd = wd.fire_rate
            if bs is not None:
                bs.shots_left = wd.shots - 1
                bs.interval_t = 0.05
            self._fire(world, res, ws, wd, t)

    def _fire(self, world, res, ws, wd, t):
        n, arc = wd.shots, wd.arc
        base = -math.pi / 2                            # para cima
        for i in range(n):
            th = base if n == 1 else base - arc / 2 + arc * i / (n - 1)
            beid = res.pools.take_player_bullet(world)
            if beid < 0:
                return
            bt = world.get_component(beid, Transform)
            bv = world.get_component(beid, Velocity)
            bt.x, bt.y = t.x, t.y
            bv.vx = math.cos(th) * wd.speed
            bv.vy = math.sin(th) * wd.speed
            world.get_component(beid, Damage).amount = wd.damage
            for comp_name, args in wd.recipe:          # receita do JSON
                c = world.get_component(beid, _RECIPE_TYPES[comp_name])
                for k, v in args:
                    setattr(c, k, v)

    def _charged(self, world, res, ws, wd, ch, t, dt):
        """Segurar acumula; soltar dispara escalado pela fração de carga.
        CARREGADO+ ≥85%: bala ganha ShrapnelOnHit (via receita plus)."""
        if ch.post_cd > 0.0:
            ch.post_cd -= dt
            return
        if ws.fire_held:
            ch.t = min(ch.t + dt, ch.max_t)
        elif ch.t > 0.0:
            frac = ch.t / ch.max_t
            dmg = 2.0 + 6.0 * frac                     # 2.0→8.0 do legado
            beid = res.pools.take_player_bullet(world)
            if beid >= 0:
                bt = world.get_component(beid, Transform)
                bv = world.get_component(beid, Velocity)
                bt.x, bt.y = t.x, t.y
                bv.vx, bv.vy = 0.0, -wd.speed
                world.get_component(beid, Damage).amount = dmg
                if ws.plus and frac >= 0.85:
                    for comp_name, args in wd.recipe:
                        c = world.get_component(beid, _RECIPE_TYPES[comp_name])
                        for k, v in args:
                            setattr(c, k, v)
            ch.t = 0.0
            ch.post_cd = wd.fire_rate                  # 1.5s


# ===========================================================================
# 7. Contratos dos sistemas restantes (mesma mecânica do legado; a
#    implementação segue os moldes acima — omitidos por brevidade)
# ===========================================================================
# InputSystem            pygame → res.input (edges fire/skill); escreve
#                        WeaponSlot.fire_held/fire_released.
# TimeScaleSystem        FOCUS (×0.32), hitstop e TimeStopField → res.clock.
# PlayerControlSystem    move via dt_player + res.player_pull (gravity wells);
#                        limita à arena (CLAUSTROFOBIA).
# Skill*Systems          1 sistema por habilidade lendo SkillSlot; DILATAÇÃO
#                        congela storage (vx/vy=0 temporário via máscara).
# ParrySystem            janela 0.13s: balas no raio → despawn do storage +
#                        spawn de bala-entidade (PARRY+ adiciona HomingToBoss).
# AutoLaunchSystem       SATÉLITE+: boss ≤250px → troca OrbitAround por
#                        Velocity+HomingToBoss na gema mais próxima.
# RangeLimit/PierceCD    decrementos triviais (t_left) no frame.
# Minion/Laser/Hazard    colisões restantes — mesmos moldes do PlayerHit.
# ParticleKernelSystem   kernel NumPy sobre ParticleStorage (visual).
