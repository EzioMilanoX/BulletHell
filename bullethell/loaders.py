"""
Loaders: data/*.json → registries imutáveis indexados por crc32 (ids.sid).
Carregados UMA vez na composição — I/O proibido durante o gameplay.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from bullethell.ids import sid
from bullethell.schemas import (
    BEH_BOOMERANG, BEH_NONE, BEH_SLEEPER, BEH_STOPGO,
    CONTACT_ALWAYS, CONTACT_IF_MOVING, CONTACT_IF_STILL, CONTACT_NEVER,
)

DATA_DIR = Path(__file__).parent / "data"

_CONTACT = {"always": CONTACT_ALWAYS, "if_moving": CONTACT_IF_MOVING,
            "if_still": CONTACT_IF_STILL, "never": CONTACT_NEVER}
_BEH = {"none": BEH_NONE, "stopgo": BEH_STOPGO,
        "boomerang": BEH_BOOMERANG, "sleeper": BEH_SLEEPER}


@dataclass(frozen=True, slots=True)
class BulletArchetypeDef:
    name: str
    contact: int
    color: int
    radius: float
    beh: int
    p1: float
    p2: float
    p3: float
    homing_t: float
    spin: float
    phase_period: float
    gravity: float
    bounces: int
    fragment: bool
    tether: bool


@dataclass(frozen=True, slots=True)
class PatternDef:
    name: str
    emit: str
    bullet: int
    period: float
    count: int
    speed: float
    arc: float
    aim: str
    gap: float
    gap_step: float
    spin_speed: float
    arms: int
    track: str
    warmup: float
    hp: float             # summon: HP do lacaio invocado
    kind: int             # summon: MINION_* (0=kamikaze, 1=sentinela, 2=bolha)
    dda: bool             # arc/ring/spiral: escala por tier da Difficulty (DDA)


@dataclass(frozen=True, slots=True)
class WeaponDef:
    """`pools` = pools extras anexadas à bala (arquétipo próprio da arma);
    `init` = valores iniciais por pool. `special` marca armas cuja
    mecânica exige sistema dedicado ainda não portado."""
    name: str
    fire_rate: float
    damage: float
    speed: float
    size: float
    shots: int
    arc: float
    pools: Tuple[str, ...]
    init: Tuple[Tuple[str, Tuple[Tuple[str, float], ...]], ...]
    special: str


@dataclass(frozen=True, slots=True)
class SkillDef:
    """Campos numéricos genéricos — cada habilidade usa os seus; 0 = n/a."""
    name: str
    cd: float
    duration: float
    radius: float
    power: float
    drain: float
    regen: float
    scale: float
    stun: float
    fr: float
    speed: float
    aux: float
    buff_dur: float
    buff_per: float
    refund: float
    ring_n: int
    ring_spd: float
    perfect: float


def _skill_from(name: str, e: dict) -> SkillDef:
    return SkillDef(
        name=name,
        cd=float(e.get("cd", 0.0)), duration=float(e.get("duration", 0.0)),
        radius=float(e.get("radius", 0.0)), power=float(e.get("power", 0.0)),
        drain=float(e.get("drain", 0.0)), regen=float(e.get("regen", 0.0)),
        scale=float(e.get("scale", 1.0)), stun=float(e.get("stun", 0.0)),
        fr=float(e.get("fr", 1.0)), speed=float(e.get("speed", 1.0)),
        aux=float(e.get("aux", 0.0)),
        buff_dur=float(e.get("buff_dur", 0.0)), buff_per=float(e.get("buff_per", 0.0)),
        refund=float(e.get("refund", 0.0)), ring_n=int(e.get("ring_n", 0)),
        ring_spd=float(e.get("ring_spd", 0.0)), perfect=float(e.get("perfect", 0.0)),
    )


def load_skills(path=DATA_DIR / "skills.json") -> Dict[int, SkillDef]:
    out: Dict[int, SkillDef] = {}
    for e in json.loads(path.read_text(encoding="utf-8"))["skills"]:
        out[sid(e["name"])] = _skill_from(e["name"], e)
        if "plus" in e:
            merged = {**e, **e["plus"]}
            out[sid(e["name"] + "+")] = _skill_from(e["name"] + "+", merged)
    return out


@dataclass(frozen=True, slots=True)
class BossPhaseDef:
    hp_above: float
    # (pattern_sid, off_x, off_y, part_idx) — part_idx -1 = origem na raiz
    emitters: Tuple[Tuple[int, float, float, int], ...]
    force: Tuple[float, float]    # px/s empurrando o jogador (Gula/Soberba)
    gimmick: str                  # "" | "spotlight" | "gate_minions"
    # (n, kind, hp, speed) — lacaios spawnados na ENTRADA da fase
    minions: Tuple[int, int, float, float]


@dataclass(frozen=True, slots=True)
class BossDef:
    name: str
    hp: float
    motion: str          # "" | "swarm_orbit" | "descend" | "teleport" | "track_x"
    motion_rate: float   # track_x: taxa do lerp em direção ao jogador
    hitbox: Tuple[float, float]   # semi-extensões da raiz (boss simples)
    route: Tuple[Tuple[float, float, float], ...]
    parts: Tuple[Tuple[float, float, float, float], ...]
    phases: Tuple[BossPhaseDef, ...]


def load_bullet_archetypes(path=DATA_DIR / "bullet_archetypes.json") -> Dict[int, BulletArchetypeDef]:
    out: Dict[int, BulletArchetypeDef] = {}
    for e in json.loads(path.read_text(encoding="utf-8"))["archetypes"]:
        params = list(e.get("behavior_params", ())) + [0.0, 0.0, 0.0]
        d = BulletArchetypeDef(
            name=e["name"],
            contact=_CONTACT[e.get("contact", "always")],
            color=e.get("color", 0),
            radius=e.get("radius", 4.0),
            beh=_BEH[e.get("behavior", "none")],
            p1=params[0], p2=params[1], p3=params[2],
            homing_t=e.get("homing_t", 0.0),
            spin=e.get("spin", 0.0),
            phase_period=e.get("phase_period", 0.0),
            gravity=e.get("gravity", 0.0),
            bounces=e.get("bounces", 0),
            fragment=e.get("fragment", False),
            tether=e.get("tether", False),
        )
        out[sid(d.name)] = d
    return out


def load_patterns(path=DATA_DIR / "patterns.json") -> Dict[int, PatternDef]:
    out: Dict[int, PatternDef] = {}
    for e in json.loads(path.read_text(encoding="utf-8"))["patterns"]:
        d = PatternDef(
            name=e["name"], emit=e["emit"], bullet=sid(e["bullet"]),
            period=float(e["period"]), count=e.get("count", 1),
            speed=e.get("speed", 150.0), arc=e.get("arc", 0.0),
            aim=e.get("aim", "player"), gap=e.get("gap", 0.0),
            gap_step=e.get("gap_step", 0.0),
            spin_speed=e.get("spin_speed", 0.0), arms=e.get("arms", 1),
            track=e.get("track", ""), warmup=e.get("warmup", 0.0),
            hp=e.get("hp", 3.0), kind=e.get("kind", 0),
            dda=bool(e.get("dda", False)),
        )
        out[sid(d.name)] = d
    return out


def _weapon_from(base_name: str, e: dict) -> WeaponDef:
    pools_dict = e.get("pools", {})
    return WeaponDef(
        name=base_name,
        fire_rate=float(e["fire_rate"]), damage=float(e["damage"]),
        speed=float(e.get("speed", 500.0)), size=float(e.get("size", 4.0)),
        shots=int(e.get("shots", 1)), arc=float(e.get("arc", 0.0)),
        pools=tuple(sorted(pools_dict.keys())),
        init=tuple(sorted((pname, tuple(sorted(vals.items())))
                          for pname, vals in pools_dict.items())),
        special=e.get("special", ""),
    )


def load_weapons(path=DATA_DIR / "weapons.json") -> Dict[int, WeaponDef]:
    """Retorna base e variante + já resolvidas: sid("padrao"), sid("padrao+")."""
    out: Dict[int, WeaponDef] = {}
    for e in json.loads(path.read_text(encoding="utf-8"))["weapons"]:
        base = _weapon_from(e["name"], e)
        out[sid(base.name)] = base
        if "plus" in e:
            merged = {**e, **e["plus"]}
            merged["pools"] = {**e.get("pools", {}), **e["plus"].get("pools", {})}
            out[sid(e["name"] + "+")] = _weapon_from(e["name"] + "+", merged)
    return out


def load_bosses(path=DATA_DIR / "bosses.json") -> Dict[int, BossDef]:
    out: Dict[int, BossDef] = {}
    for e in json.loads(path.read_text(encoding="utf-8"))["bosses"]:
        d = BossDef(
            name=e["name"], hp=float(e["hp"]),
            motion=e.get("motion", ""),
            motion_rate=float(e.get("motion_rate", 1.0)),
            hitbox=tuple(map(float, e.get("hitbox", [24.0, 24.0]))),
            route=tuple(tuple(map(float, p)) for p in e.get("route", ())),
            parts=tuple(tuple(map(float, p)) for p in e.get("parts", ())),
            phases=tuple(
                BossPhaseDef(
                    hp_above=float(ph["hp_above"]),
                    emitters=tuple(
                        (sid(em["pattern"]),
                         float(em.get("offset", [0, 0])[0]),
                         float(em.get("offset", [0, 0])[1]),
                         int(em.get("part", -1)))
                        for em in ph["emitters"]),
                    force=tuple(map(float, ph.get("force", [0.0, 0.0]))),
                    gimmick=ph.get("gimmick", ""),
                    minions=tuple(ph.get("minions", [0, 0, 0.0, 0.0])),
                )
                for ph in e["phases"]),
        )
        out[sid(d.name)] = d
    return out


@dataclass(frozen=True, slots=True)
class WaveDef:
    enemies: int
    kamikaze_ratio: float
    interval: float
    boss: str             # "" = onda normal; nome = boss wave


def load_waves(path=DATA_DIR / "waves.json") -> Tuple[WaveDef, ...]:
    return tuple(
        WaveDef(enemies=e.get("enemies", 0),
                kamikaze_ratio=float(e.get("kamikaze_ratio", 1.0)),
                interval=float(e.get("spawn_interval", 1.0)),
                boss=e.get("boss", ""))
        for e in json.loads(path.read_text(encoding="utf-8"))["waves"])


@dataclass(frozen=True, slots=True)
class GameData:
    archetypes: Dict[int, BulletArchetypeDef]
    patterns: Dict[int, PatternDef]
    weapons: Dict[int, WeaponDef]
    bosses: Dict[int, BossDef]
    skills: Dict[int, SkillDef]
    waves: Tuple[WaveDef, ...]


def load_all() -> GameData:
    return GameData(
        archetypes=load_bullet_archetypes(),
        patterns=load_patterns(),
        weapons=load_weapons(),
        bosses=load_bosses(),
        skills=load_skills(),
        waves=load_waves(),
    )
