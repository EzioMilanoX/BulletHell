"""
Cenas do jogo: menus do legado (modo → dificuldade → boss → habilidade →
arma → mutadores), gameplay com HUD textual, intro de boss, WIN/GAMEOVER
com T (retry) / R (menu), screen shake e overlays.

Camada de APRESENTAÇÃO do produto: usa draw_text/draw_ui_rect do
IRenderer (ROADMAP M1/M2) — permitido alocar aqui; o gameplay continua
inteiro dentro de World.step().
"""
from __future__ import annotations

import time

import numpy as np

from ouroboros.core.memory.component_pool import intersect_entity_indices

from bullethell.composition import DIFFICULTIES, build_world
from bullethell.game_systems import RUSH_ORDERS
from bullethell.ids import sid
from bullethell.loaders import GameData
from bullethell.schemas import SCREEN_H, SCREEN_W

# ---------------------------------------------------------------------------
# Estados / catálogos dos menus
# ---------------------------------------------------------------------------
(MENU_MAIN, MENU_MODE, MENU_DIFF, MENU_BOSS, MENU_SKILL, MENU_WEAPON,
 MENU_MUT, PLAYING, WIN, GAMEOVER, MENU_ACH) = range(11)

# Conquistas persistidas em save_ecs.json (id, nome, como desbloquear)
ACHIEVEMENTS = [
    ("first_blood", "PRIMEIRO SANGUE", "derrote o seu primeiro boss"),
    ("veterano", "VETERANO", "vença uma run no NORMAL"),
    ("mestre", "MESTRE", "vença uma run no DIFÍCIL"),
    ("perfeccionista", "PERFECCIONISTA", "vença sem perder nenhuma vida"),
    ("esquivador", "ESQUIVADOR", "acumule 100 grazes no total"),
    ("intocavel", "INTOCÁVEL", "vença sem habilidade equipada"),
    ("imparavel", "IMPARÁVEL", "complete o BOSS RUSH"),
    ("redencao", "REDENÇÃO", "complete o SINS RUSH"),
    ("sobrevivente", "SOBREVIVENTE", "vença o WAVE SURVIVAL"),
    ("vidro", "CORAÇÃO DE VIDRO", "vença com o CANHÃO DE VIDRO"),
    ("alem_limite", "ALÉM DO LIMITE", "vença com 3+ mutadores ativos"),
    ("o_fim", "O FIM", "derrote o ÔMEGA"),
    ("setimo_selo", "O SÉTIMO SELO", "sobreviva ao PECADO ORIGINAL"),
]

# clock.sfx → som registrado (bit, sound_id)
SFX_MAP = [(1, "hit"), (2, "boom"), (4, "emp"), (8, "shield"), (16, "mine")]

MODES = [("classic", "CLÁSSICO", "1 boss escolhido, até a vitória"),
         ("rush", "BOSS RUSH", "7 bosses em sequência, +1 vida entre eles"),
         ("sins", "SINS RUSH", "os 8 pecados até o Sétimo Selo"),
         ("waves", "WAVE SURVIVAL", "30 ondas; bosses nas 10/20/30")]

DIFFS = [("facil", "FÁCIL", "HP ×0.67 e velocidade ×0.75"),
         ("normal", "NORMAL", "a experiência padrão"),
         ("dificil", "DIFÍCIL", "HP ×1.33 e velocidade ×1.30 · +1 projétil"),
         ("expert", "EXPERT",
          "HP ×1.60 e velocidade ×1.50 · Segundo Fôlego: o boss resiste"
          " 3s com 1 HP ao morrer"),
         ("abissal", "ABISSAL",
          "HP ×1.87 e velocidade ×1.65 · balas fragmentam ao sair da tela"
          " · requer vitória no SINS RUSH")]

BOSSES = [("classic", "CLÁSSICO"), ("swarm", "ENXAME"), ("wall", "PAREDÃO"),
          ("timemage", "MAGO DO TEMPO"), ("twins", "GÊMEOS"),
          ("summoner", "INVOCADOR"), ("omega", "ÔMEGA *"),
          ("pride", "SOBERBA *"), ("sloth", "PREGUIÇA *"),
          ("envy", "INVEJA *"), ("gluttony", "GULA *"),
          ("greed", "AVAREZA *"), ("lust", "LUXÚRIA *"),
          ("wrath", "IRA *"), ("sin", "PECADO ORIGINAL **")]

SKILLS = [("none", "NENHUMA", "confie apenas nos reflexos"),
          ("dash", "DASH", "SHIFT: 6× velocidade por 0.18s"),
          ("parry", "PARRY", "SHIFT: reflete balas contra o boss"),
          ("focus", "FOCO", "segure SHIFT: câmera lenta (energia)"),
          ("emp", "EMP", "SHIFT: limpa 340px + stun 1s"),
          ("blink", "BLINK", "SHIFT: teleporte de 190px"),
          ("overclock", "OVERCLOCK", "SHIFT: cadência ×2.2 por 3s"),
          ("shield", "ESCUDO", "SHIFT: absorve o próximo hit"),
          ("timedil", "DILATAÇÃO", "SHIFT: congela balas por 2s")]

WEAPONS = [("padrao", "PADRÃO"), ("spread", "SPREAD"), ("agulha", "AGULHA"),
           ("carregado", "CARREGADO"), ("burst", "BURST"),
           ("teleguiado", "TELEGUIADO"), ("flak", "FLAK"),
           ("chakram", "CHAKRAM"), ("plasma", "PLASMA"),
           ("satelite", "SATÉLITE")]

MUTATORS = [("predador", "PREDADOR", "boss mira 0.5s à frente"),
            ("fantasma", "FANTASMA", "balas somem entre 200-400px do boss"),
            ("glass", "CANHÃO DE VIDRO", "1 vida, dano ×3"),
            ("claustro", "CLAUSTROFOBIA", "arena 14% menor por borda"),
            ("horde", "HORDA", "boss: +50% HP, −15% velocidade"),
            ("berserker", "BERSERKER", "boss: −25% HP, +35% velocidade")]

BOSS_INTROS = {
    "classic": ("O CLÁSSICO", "Oito padrões. Nenhuma piedade."),
    "swarm": ("O ENXAME", "Três corpos, uma vontade."),
    "wall": ("O PAREDÃO", "O céu está caindo — literalmente."),
    "timemage": ("O MAGO DO TEMPO", "Suas balas chegam antes de partir."),
    "twins": ("OS GÊMEOS", "Yin pune o movimento. Yang pune a espera."),
    "summoner": ("O INVOCADOR", "Nunca lute sozinho. Ele não luta."),
    "omega": ("ÔMEGA *", "Quatro chefes em um. Não baixe a guarda."),
    "pride": ("SOBERBA *", "Só sob a luz dela você pode feri-la."),
    "sloth": ("PREGUIÇA *", "Acordá-la será o seu último erro."),
    "envy": ("INVEJA *", "Tudo o que é seu, ela copia. E devolve."),
    "gluttony": ("GULA *", "A gravidade é a boca dela."),
    "greed": ("AVAREZA *", "Cada corredor tem um preço."),
    "lust": ("LUXÚRIA *", "Não confie nos seus próprios passos."),
    "wrath": ("IRA *", "Quando o sangue ferve, o chão treme."),
    "sin": ("PECADO ORIGINAL **", "Sete pecados. Um selo. Trinta segundos."),
}

WIN_GOALS = {"classic": 1, "rush": len(RUSH_ORDERS[1]),
             "sins": len(RUSH_ORDERS[2]), "waves": 3}

ACCENT = (124, 80, 255, 255)
TXT = (221, 218, 245, 255)
MUTED = (136, 136, 170, 255)
GOLD = (245, 197, 24, 255)
RED = (255, 60, 90, 255)


class GameApp:
    """Máquina de cenas + loop principal (substitui o GameLoop da engine
    para poder intercalar menus e gameplay)."""

    def __init__(self, renderer, input_provider, audio_engine,
                 data: GameData, save_data: dict | None = None) -> None:
        self._r = renderer
        self._input = input_provider
        self._audio = audio_engine
        self._data = data
        self.state = MENU_MAIN
        self.cursor = 0
        self.sel = {"mode": "classic", "diff": "normal", "boss": "classic",
                    "skill": "none", "skill_plus": False,
                    "weapon": "padrao", "weapon_plus": False,
                    "muts": set()}
        self.world = None
        self.intro_t = 0.0
        self.intro_boss = "classic"
        self.run_t = 0.0
        self.end_stats = (0, 0, 0)
        self.totals = {"kills": 0, "deaths": 0, "graze": 0, "runs": 0}
        self.save = save_data or {}
        self.achieved: set = set(self.save.get("achievements", []))
        self.new_achievements: list = []
        self._running = True
        if self._audio is not None:                  # SFX procedurais (M4)
            self._audio.register_tone("hit", "noise", 220.0, 0.16)
            self._audio.register_tone("boom", "sweep", 190.0, 0.45)
            self._audio.register_tone("emp", "zap", 260.0, 0.35)
            self._audio.register_tone("shield", "square", 660.0, 0.10)
            self._audio.register_tone("mine", "noise", 330.0, 0.22)
            self._audio.register_tone("ui_move", "square", 520.0, 0.04)
            self._audio.register_tone("ui_ok", "square", 780.0, 0.08)

    def _play(self, sound_id: str, volume: float = 0.5) -> None:
        if self._audio is not None:
            self._audio.play_one_shot(sound_id, volume)

    # ------------------------------------------------------------------
    def run(self) -> None:
        last = time.perf_counter()
        while self._running and not self._input.wants_quit():
            self._input.poll()
            now = time.perf_counter()
            dt = min(now - last, 1 / 30)
            last = now
            self._r.begin_frame()
            self.tick(dt)
            self._r.end_frame()
            elapsed = time.perf_counter() - now
            if elapsed < 1 / 60:
                time.sleep(1 / 60 - elapsed)

    # ------------------------------------------------------------------
    def tick(self, dt: float) -> None:
        s = self.state
        if s == PLAYING:
            self._tick_playing(dt)
        elif s == MENU_MAIN:
            self._menu(["JOGAR", "CONQUISTAS", "SAIR"], "BULLET HELL",
                       subtitle="OuroborosEngine · port ECS",
                       on_confirm=self._main_confirm)
        elif s == MENU_ACH:
            self._achievements_screen()
        elif s == MENU_MODE:
            self._menu([m[1] for m in MODES], "MODO DE JOGO",
                       descs=[m[2] for m in MODES],
                       on_confirm=self._mode_confirm, back_to=MENU_MAIN)
        elif s == MENU_DIFF:
            self._menu([d[1] for d in DIFFS], "DIFICULDADE",
                       descs=[d[2] for d in DIFFS],
                       on_confirm=self._diff_confirm, back_to=MENU_MODE)
        elif s == MENU_BOSS:
            self._menu([b[1] for b in BOSSES], "ESCOLHA O BOSS",
                       on_confirm=self._boss_confirm, back_to=MENU_DIFF)
        elif s == MENU_SKILL:
            items = [n + (" +" if self.sel["skill_plus"] and k == self.cursor
                          and self._has_plus(SKILLS[k][0], self._data.skills)
                          else "") for k, (sk, n, _) in enumerate(SKILLS)]
            self._menu(items, "HABILIDADE",
                       descs=[d for (_, _, d) in SKILLS],
                       on_confirm=self._skill_confirm,
                       back_to=MENU_BOSS if self.sel["mode"] == "classic"
                       else MENU_DIFF,
                       hint_extra="ESPAÇO alterna a variante +")
            if self._input.is_action_pressed("fire"):
                self.sel["skill_plus"] = not self.sel["skill_plus"]
        elif s == MENU_WEAPON:
            items = [n + (" +" if self.sel["weapon_plus"] and k == self.cursor
                          and self._has_plus(WEAPONS[k][0], self._data.weapons)
                          else "") for k, (w, n) in enumerate(WEAPONS)]
            self._menu(items, "ARMA",
                       on_confirm=self._weapon_confirm, back_to=MENU_SKILL,
                       hint_extra="ESPAÇO alterna a variante +")
            if self._input.is_action_pressed("fire"):
                self.sel["weapon_plus"] = not self.sel["weapon_plus"]
        elif s == MENU_MUT:
            items = [(("[x] " if m in self.sel["muts"] else "[ ] ") + n)
                     for (m, n, _) in MUTATORS] + ["► COMEÇAR"]
            self._menu(items, "MUTADORES",
                       descs=[d for (_, _, d) in MUTATORS] + [
                           "cada mutador ativo aumenta o desafio"],
                       on_confirm=self._mut_confirm, back_to=MENU_WEAPON)
        elif s in (WIN, GAMEOVER):
            self._end_screen(s)

    # ------------------------------------------------------------------
    # menus
    # ------------------------------------------------------------------
    @staticmethod
    def _has_plus(name: str, table) -> bool:
        return sid(name + "+") in table

    def _menu(self, items, title, descs=None, subtitle="", on_confirm=None,
              back_to=None, hint_extra="") -> None:
        inp = self._input
        n = len(items)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            self._play("ui_move", 0.25)
        if back_to is not None and (inp.is_action_pressed("back")
                                    or inp.is_action_pressed("move_left")):
            self.state = back_to
            self.cursor = 0
            return
        if on_confirm and (inp.is_action_pressed("confirm")
                           or inp.is_action_pressed("move_right")):
            self._play("ui_ok", 0.35)
            on_confirm(self.cursor)
            return
        self.cursor = min(self.cursor, n - 1)

        r = self._r
        r.draw_text(SCREEN_W / 2, 64, title, 42, ACCENT, anchor="center")
        if subtitle:
            r.draw_text(SCREEN_W / 2, 104, subtitle, 16, MUTED, anchor="center")
        top = 170
        row_h = 34 if n > 12 else 40
        for k, label in enumerate(items):
            y = top + k * row_h
            if k == self.cursor:
                r.draw_ui_rect(SCREEN_W / 2 - 240, y - 5, 480, row_h - 6,
                               (124, 80, 255, 60))
                r.draw_text(SCREEN_W / 2 - 224, y, "►", 20, GOLD)
            r.draw_text(SCREEN_W / 2 - 190, y, label, 20,
                        TXT if k == self.cursor else MUTED)
        if descs and 0 <= self.cursor < len(descs):
            r.draw_text(SCREEN_W / 2, SCREEN_H - 96, descs[self.cursor],
                        16, TXT, anchor="center")
        hint = "W/S navegar  ·  D/ENTER confirmar  ·  A/ESC voltar"
        if hint_extra:
            hint += "  ·  " + hint_extra
        r.draw_text(SCREEN_W / 2, SCREEN_H - 44, hint, 14, MUTED,
                    anchor="center")

    def _main_confirm(self, k: int) -> None:
        if k == 0:
            self.state, self.cursor = MENU_MODE, 0
        elif k == 1:
            self.state, self.cursor = MENU_ACH, 0
        else:
            self._running = False

    def _achievements_screen(self) -> None:
        inp = self._input
        if inp.is_action_pressed("back") or inp.is_action_pressed("confirm") \
                or inp.is_action_pressed("move_left"):
            self.state, self.cursor = MENU_MAIN, 0
            return
        r = self._r
        r.draw_text(SCREEN_W / 2, 56, "CONQUISTAS", 40, GOLD, anchor="center")
        done = sum(1 for aid, _, _ in ACHIEVEMENTS if aid in self.achieved)
        r.draw_text(SCREEN_W / 2, 100,
                    f"{done} / {len(ACHIEVEMENTS)} desbloqueadas",
                    16, MUTED, anchor="center")
        top = 150
        for k, (aid, name, desc) in enumerate(ACHIEVEMENTS):
            y = top + k * 40
            got = aid in self.achieved
            mark = "[x]" if got else "[ ]"
            r.draw_text(SCREEN_W / 2 - 330, y, mark, 18,
                        GOLD if got else MUTED)
            r.draw_text(SCREEN_W / 2 - 270, y, name, 18,
                        TXT if got else MUTED)
            r.draw_text(SCREEN_W / 2 + 40, y + 2, desc, 14, MUTED)
        r.draw_text(SCREEN_W / 2, SCREEN_H - 44, "A/ESC voltar", 14, MUTED,
                    anchor="center")

    def _mode_confirm(self, k: int) -> None:
        self.sel["mode"] = MODES[k][0]
        self.state, self.cursor = MENU_DIFF, 1

    def _diff_confirm(self, k: int) -> None:
        self.sel["diff"] = DIFFS[k][0]
        self.state = MENU_BOSS if self.sel["mode"] == "classic" else MENU_SKILL
        self.cursor = 0

    def _boss_confirm(self, k: int) -> None:
        self.sel["boss"] = BOSSES[k][0]
        self.state, self.cursor = MENU_SKILL, 0

    def _skill_confirm(self, k: int) -> None:
        self.sel["skill"] = SKILLS[k][0]
        self.state, self.cursor = MENU_WEAPON, 0

    def _weapon_confirm(self, k: int) -> None:
        self.sel["weapon"] = WEAPONS[k][0]
        self.state, self.cursor = MENU_MUT, 0

    def _mut_confirm(self, k: int) -> None:
        if k < len(MUTATORS):
            m = MUTATORS[k][0]
            if m in self.sel["muts"]:
                self.sel["muts"].discard(m)
            else:
                self.sel["muts"].add(m)
        else:
            self.start_game()

    # ------------------------------------------------------------------
    # gameplay
    # ------------------------------------------------------------------
    def start_game(self) -> None:
        skill = self.sel["skill"]
        if self.sel["skill_plus"] and self._has_plus(skill, self._data.skills):
            skill += "+"
        weapon = self.sel["weapon"]
        if self.sel["weapon_plus"] and self._has_plus(weapon, self._data.weapons):
            weapon += "+"
        self.world = build_world(
            self._data, self._input, boss_name=self.sel["boss"],
            weapon_name=weapon, skill_name=skill,
            mutators=frozenset(self.sel["muts"]), mode=self.sel["mode"],
            difficulty=self.sel["diff"], arcade=True)
        mode = self.sel["mode"]
        self.intro_boss = (RUSH_ORDERS[1][0] if mode == "rush" else
                           RUSH_ORDERS[2][0] if mode == "sins" else
                           self.sel["boss"])
        self.intro_t = 0.0 if mode == "waves" else 2.4
        self.run_t = 0.0
        self.state = PLAYING

    def _tick_playing(self, dt: float) -> None:
        w = self.world
        self.run_t += dt
        w.step(dt)
        self._pump_sfx()
        self._apply_shake(dt)
        self._render_world()
        self._render_hud()
        if self.intro_t > 0.0:
            self.intro_t -= dt
            self._render_intro()

        if self._input.is_action_pressed("back"):   # ESC abandona a run
            self._finish_run("abandon")
            self.state, self.cursor = MENU_MAIN, 0
            return
        pl = w.get_pool("player")
        if pl.count and int(pl.active_view()["lives"][0]) < 0:
            self._finish_run("lose")
            self.state = GAMEOVER
            return
        kills = int(w.get_pool("stats").active_view()["kills"][0])
        if kills >= WIN_GOALS[self.sel["mode"]]:
            self._finish_run("win")
            self.state = WIN

    def _pump_sfx(self) -> None:
        """Toca os eventos sonoros marcados pelos sistemas e limpa a máscara."""
        ck = self.world.get_pool("clock")
        if not ck.count:
            return
        cv = ck.active_view()
        bits = int(cv["sfx"][0])
        if bits:
            for bit, sound_id in SFX_MAP:
                if bits & bit:
                    self._play(sound_id, 0.45)
            cv["sfx"][0] = 0

    def _finish_run(self, outcome: str) -> None:
        w = self.world
        st = w.get_pool("stats").active_view()
        pl = w.get_pool("player")
        graze = int(pl.active_view()["graze"][0]) if pl.count else 0
        lives = int(pl.active_view()["lives"][0]) if pl.count else -1
        self.end_stats = (int(st["kills"][0]), int(st["deaths"][0]), graze)
        self.totals["kills"] += self.end_stats[0]
        self.totals["deaths"] += self.end_stats[1]
        self.totals["graze"] += graze
        self.totals["runs"] += 1
        self._r.set_camera_offset(0.0, 0.0)
        self._check_achievements(outcome, lives, graze)

    def _check_achievements(self, outcome: str, lives: int, graze: int) -> None:
        """Avalia as conquistas ao fim da run (persistidas ao sair)."""
        self.new_achievements = []

        def grant(aid: str) -> None:
            if aid not in self.achieved:
                self.achieved.add(aid)
                name = next(n for a, n, _ in ACHIEVEMENTS if a == aid)
                self.new_achievements.append(name)

        if self.end_stats[0] >= 1:
            grant("first_blood")
        total_graze = int(self.save.get("total_graze", 0)) + self.totals["graze"]
        if total_graze >= 100:
            grant("esquivador")
        if outcome != "win":
            return
        mode, diff = self.sel["mode"], self.sel["diff"]
        muts = self.sel["muts"]
        if diff in ("normal", "dificil"):
            grant("veterano")
        if diff == "dificil":
            grant("mestre")
        full = 0 if "glass" in muts else 3
        if lives >= full:
            grant("perfeccionista")
        if self.sel["skill"] == "none":
            grant("intocavel")
        if mode == "rush":
            grant("imparavel")
        if mode == "sins":
            grant("redencao")
            grant("setimo_selo")
        if mode == "waves":
            grant("sobrevivente")
        if "glass" in muts:
            grant("vidro")
        if len(muts) >= 3:
            grant("alem_limite")
        if mode == "classic" and self.sel["boss"] == "omega":
            grant("o_fim")
        if mode == "classic" and self.sel["boss"] == "sin":
            grant("setimo_selo")
        if self.new_achievements:
            self._play("ui_ok", 0.6)

    def _apply_shake(self, dt: float) -> None:
        ck = self.world.get_pool("clock")
        if not ck.count:
            return
        cv = ck.active_view()
        amt = float(cv["shake"][0])
        if amt > 0.0:
            cv["shake"][0] = max(0.0, amt - 26.0 * dt)
            j = int(self.run_t * 997)
            dx = (((j * 2654435761) % 200) / 100.0 - 1.0) * amt
            dy = (((j * 40503 + 7) % 200) / 100.0 - 1.0) * amt
            self._r.set_camera_offset(dx, dy)
        else:
            self._r.set_camera_offset(0.0, 0.0)

    def _render_world(self) -> None:
        t = self.world.get_pool("transform")
        s = self.world.get_pool("sprite")
        idx = intersect_entity_indices(t, s)
        count = int(idx.shape[0])
        if count == 0:
            return
        trows = t.dense_rows_of(idx)
        srows = s.dense_rows_of(idx)
        tv = t.active_view()
        sv = s.active_view()
        pos = np.stack([tv["position_x"][trows], tv["position_y"][trows]], axis=1)
        scl = np.stack([tv["scale_x"][trows], tv["scale_y"][trows]], axis=1)
        tint = np.stack([sv["tint_r"][srows], sv["tint_g"][srows],
                         sv["tint_b"][srows], sv["tint_a"][srows]], axis=1)
        self._r.draw_batch(pos, tv["rotation_rad"][trows], scl,
                           sv["texture_id"][srows], tint,
                           sv["layer_z"][srows], count)

    def _render_hud(self) -> None:
        r = self._r
        w = self.world
        mode = self.sel["mode"]
        r.draw_text(14, 10, f"{dict(MODES_SHORT)[mode]} · "
                            f"{dict((d[0], d[1]) for d in DIFFS)[self.sel['diff']]}",
                    14, MUTED)
        bp = w.get_pool("boss")
        if bp.count:
            bv = bp.active_view()
            hp = float(np.sum(bv["hp"][: bp.count]))
            mx = float(np.sum(bv["max_hp"][: bp.count]))
            tier = int(np.max(bv["tier"][: bp.count]))   # DDA — pior tier vivo
            name = self._boss_display(int(bv["boss_id"][0]))
            r.draw_text(SCREEN_W / 2, 26,
                        f"{name}   {hp:.0f} / {mx:.0f}   T{tier}",
                        16, TXT, anchor="center")
        if mode == "waves":
            wv = w.get_pool("wave").active_view()
            r.draw_text(SCREEN_W / 2, SCREEN_H - 30,
                        f"ONDA {max(1, int(wv['idx'][0]) + 1)} / "
                        f"{len(self._data.waves)}",
                        15, GOLD, anchor="center")
        skill = self.sel["skill"]
        if skill != "none":
            r.draw_text(SCREEN_W - 14, SCREEN_H - 40,
                        skill.upper() + ("+" if self.sel["skill_plus"] else ""),
                        14, MUTED, anchor="topright")
        r.draw_text(96, SCREEN_H - 26, "VIDAS", 13, MUTED)

    def _boss_display(self, boss_id: int) -> str:
        for name, label in BOSSES:
            if sid(name) == boss_id:
                return label
        for name in ("twin_yin", "twin_yang"):
            if sid(name) == boss_id:
                return "OS GÊMEOS"
        return "???"

    def _render_intro(self) -> None:
        r = self._r
        a = max(0.0, min(1.0, self.intro_t / 0.5))   # fade-out no fim
        r.draw_ui_rect(0, SCREEN_H / 2 - 90, SCREEN_W, 180,
                       (8, 8, 14, int(200 * a)))
        title, flavor = BOSS_INTROS.get(self.intro_boss, ("???", ""))
        r.draw_text(SCREEN_W / 2, SCREEN_H / 2 - 30, title, 44,
                    (RED[0], RED[1], RED[2], int(255 * a)), anchor="center")
        r.draw_text(SCREEN_W / 2, SCREEN_H / 2 + 26, flavor, 18,
                    (TXT[0], TXT[1], TXT[2], int(255 * a)), anchor="center")

    # ------------------------------------------------------------------
    def _end_screen(self, which: int) -> None:
        r = self._r
        self._render_world()                          # cena congelada atrás
        r.draw_ui_rect(0, 0, SCREEN_W, SCREEN_H, (8, 8, 14, 190))
        kills, deaths, graze = self.end_stats
        if which == WIN:
            r.draw_text(SCREEN_W / 2, 220, "VITÓRIA", 56, GOLD, anchor="center")
        else:
            r.draw_text(SCREEN_W / 2, 220, "GAME OVER", 56, RED, anchor="center")
        r.draw_text(SCREEN_W / 2, 320,
                    f"bosses: {kills}   ·   grazes: {graze}   ·   "
                    f"tempo: {self.run_t:.0f}s", 20, TXT, anchor="center")
        for k, name in enumerate(self.new_achievements[:4]):
            r.draw_text(SCREEN_W / 2, 370 + k * 28,
                        f"* NOVA CONQUISTA: {name}", 17, GOLD, anchor="center")
        r.draw_text(SCREEN_W / 2, 500, "T  jogar de novo      R  menu",
                    18, MUTED, anchor="center")
        if self._input.is_action_pressed("retry"):
            self.start_game()
        elif self._input.is_action_pressed("to_menu") \
                or self._input.is_action_pressed("back"):
            self.state, self.cursor = MENU_MAIN, 0


MODES_SHORT = [("classic", "CLÁSSICO"), ("rush", "BOSS RUSH"),
               ("sins", "SINS RUSH"), ("waves", "WAVES")]
