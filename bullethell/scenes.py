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
from bullethell.game_systems import PLAYER_HIT_R, RUSH_ORDERS
from bullethell.ids import sid
from bullethell.loaders import DATA_DIR, GameData, load_all
from bullethell.replay import ReplayInputProvider, encode_frame
from bullethell.schemas import SCREEN_H, SCREEN_W

# ---------------------------------------------------------------------------
# Estados / catálogos dos menus
# ---------------------------------------------------------------------------
(MENU_MAIN, MENU_MODE, MENU_DIFF, MENU_BOSS, MENU_SKILL, MENU_WEAPON,
 MENU_MUT, PLAYING, WIN, GAMEOVER, MENU_ACH, MENU_RECORDS,
 MENU_SETTINGS, REPLAYING) = range(14)

# Conquistas persistidas em save_ecs.json: (id, nome, descrição, recompensa,
# secreta, progresso). `progresso` = (chave, alvo) para as com barra —
# chave lida de `save["total_graze"/"total_parries"] + totals[...]` (run
# atual incluída). As 15 primeiras são as não-mastery do legado
# (ACHIEVEMENTS_DEF, main.py:1896-1986 — mesmos nomes/recompensas onde
# aplicável); as 5 últimas são conclusões de modo que o port já tinha e o
# legado não lista como conquista dedicada — mantidas como bônus.
# As 17 masteries de skill+/arma+ do legado (sp_*/wp_*) ficam de fora por
# ora: exigiriam instrumentação nova em vários sistemas (ver PARITY_PLAN
# P1-7) e uma conquista que nunca pode ser ganha é pior que não listá-la.
ACHIEVEMENTS = [
    ("easy_win", "INICIANTE", "Complete a dificuldade Fácil.",
     "Habilidade: PARRY", False, None),
    ("normal_win", "VETERANO", "Complete a dificuldade Normal.",
     "Habilidade: FOCO", False, None),
    ("hard_win", "MESTRE", "Complete a dificuldade Difícil.", "—", False, None),
    ("grazes_100", "ESQUIVADOR", "Acumule 100 grazes no total.",
     "Habilidade: EMP", False, ("graze", 100)),
    ("parries_50", "ESPADACHIM", "Deflita 50 balas com o Parry.",
     "Habilidade: ESCUDO", False, ("parries", 50)),
    ("no_hit_win", "PERFECCIONISTA", "Vença sem perder nenhuma vida.",
     "Habilidade: BLINK", False, None),
    ("mutator_hard", "RISCO MÁXIMO",
     "Vença Difícil com 1+ mutador ativo.", "Habilidade: OVERCLOCK",
     False, None),
    ("omega_unlock", "IMPARÁVEL",
     "Vença Difícil com 3+ mutadores simultâneos.", "Boss: ÔMEGA ★",
     False, None),
    ("equilibrio_perfeito", "EQUILÍBRIO PERFEITO",
     "Derrote os Gêmeos.", "Habilidade: DILATAÇÃO", False, None),
    ("pacifista_elite", "PACIFISTA DE ELITE",
     "Derrote o Invocador.", "Mutador: CLAUSTROFOBIA", False, None),
    ("parries_200", "SENHOR DO PARRY", "Deflita 200 balas no total.",
     "—", True, ("parries", 200)),
    ("speed_hard", "SPEED RUNNER",
     "Vença Difícil em menos de 3 minutos.", "—", True, None),
    ("all_mutators", "ALÉM DO LIMITE", "Vença com 3+ mutadores ativos.",
     "—", True, None),
    ("no_skill", "INTOCÁVEL", "Vença com habilidade NENHUMA.", "—",
     True, None),
    ("omega_hard", "O FIM", "Derrote o ÔMEGA na dificuldade Difícil.",
     "—", True, None),
    ("first_blood", "PRIMEIRO SANGUE", "Derrote o seu primeiro boss.",
     "—", False, None),
    ("boss_rush_win", "CONQUISTADOR", "Complete o BOSS RUSH.", "—",
     False, None),
    ("sins_rush_win", "REDENÇÃO", "Complete o SINS RUSH.", "—",
     False, None),
    ("waves_win", "SOBREVIVENTE", "Vença o WAVE SURVIVAL.", "—",
     False, None),
    ("glass_win", "CORAÇÃO DE VIDRO", "Vença com o CANHÃO DE VIDRO.",
     "—", False, None),
]

# clock.sfx → som registrado (bit, sound_id)
SFX_MAP = [(1, "hit"), (2, "boom"), (4, "emp"), (8, "shield"), (16, "mine")]

# Catálogos dos menus: (id, label, [linhas de descrição], cor de destaque).
# As cores seguem a paleta do legado item a item (main.py: _DIFF_COLORS,
# _BOSS_COLORS, _SKILL_COLORS, _WEAPON_COLORS, _MUTATOR_COLORS) — usadas na
# barra do card, no título do painel direito e na seta do cursor.
MAIN_ITEMS = [("play", "JOGAR", (80, 220, 80)),
              ("ach", "CONQUISTAS", (255, 200, 40)),
              ("records", "REGISTROS", (80, 200, 140)),
              ("settings", "SISTEMA", (100, 160, 255)),
              ("quit", "SAIR", (220, 50, 50))]

MODES = [("classic", "CLÁSSICO",
         ("1 boss escolhido, até a vitória.",
          "Modo original — focado, sem surpresas."), (200, 200, 200)),
         ("rush", "BOSS RUSH",
         ("7 bosses em ordem fixa — do Clássico ao Ômega, +1 vida entre eles.",
          "Sem aleatoriedade, HP sem escala — domine cada padrão."),
         (255, 140, 30)),
         ("sins", "SINS RUSH",
         ("7 pecados em ordem fixa + o Pecado Original ao fim.",
          "HP escala ×1.15 por estágio.",
          "Vencer libera a dificuldade ABISSAL."), (180, 40, 255)),
         ("waves", "WAVE SURVIVAL",
         ("30 ondas; bosses nas ondas 10/20/30.",
          "Sobreviva até o fim para vencer."), (80, 200, 100))]

DIFFS = [("facil", "FÁCIL",
         ("HP ×0.67 e velocidade ×0.75.",
          "Para conhecer o jogo sem pressão."), (80, 220, 80)),
         ("normal", "NORMAL",
         ("A experiência padrão.",
          "Todos os ataques, ritmo equilibrado."), (255, 220, 0)),
         ("dificil", "DIFÍCIL",
         ("HP ×1.33, velocidade ×1.30, +1 projétil.",
          "Libera todas as variantes '+' ao vencer."), (220, 20, 60)),
         ("expert", "EXPERT",
         ("HP ×1.60, velocidade ×1.50.",
          "★ Segundo Fôlego — o boss resiste 3s com 1 HP ao morrer."),
         (255, 80, 200)),
         ("abissal", "ABISSAL",
         ("HP ×1.87, velocidade ×1.65.",
          "Balas fragmentam ao sair da tela.",
          "⚠ Requer vitória no SINS RUSH"), (120, 0, 255))]

BOSSES = [("classic", "CLÁSSICO", (128, 0, 0)),
          ("swarm", "ENXAME", (140, 60, 220)),
          ("wall", "PAREDÃO", (60, 120, 220)),
          ("timemage", "MAGO DO TEMPO", (80, 200, 220)),
          ("twins", "GÊMEOS", (80, 120, 255)),
          ("summoner", "INVOCADOR", (160, 40, 220)),
          ("omega", "ÔMEGA *", (255, 60, 120)),
          ("pride", "SOBERBA *", (255, 215, 0)),
          ("sloth", "PREGUIÇA *", (130, 60, 200)),
          ("envy", "INVEJA *", (0, 220, 80)),
          ("gluttony", "GULA *", (180, 40, 40)),
          ("greed", "AVAREZA *", (200, 160, 0)),
          ("lust", "LUXÚRIA *", (220, 80, 160)),
          ("wrath", "IRA *", (220, 50, 20)),
          ("sin", "PECADO ORIGINAL **", (180, 0, 220))]

# Legado: SELECT_BOSS só lista CLASSIC_BOSS_IDS — os 8 pecados só são
# jogáveis via SINS RUSH, "Mago do Tempo" (invenção do port) via BOSS RUSH.
# Preservar a ordem de BOSSES já dá a ordem exata do legado (spec menus §6).
CLASSIC_BOSS_NAMES = ("classic", "swarm", "wall", "twins", "summoner", "omega")
CLASSIC_BOSSES = [b for b in BOSSES if b[0] in CLASSIC_BOSS_NAMES]

SKILLS = [("none", "NENHUMA", ("Confie apenas nos reflexos.",), (64, 64, 64)),
          ("dash", "DASH",
          ("SHIFT — 6× velocidade por 0.18s.",), (80, 200, 255)),
          ("parry", "PARRY",
          ("SHIFT — reflete balas num raio de 17.5px.",), (0, 255, 200)),
          ("focus", "FOCO",
          ("Segure SHIFT — câmera lenta (drena energia).",), (255, 220, 60)),
          ("emp", "EMP",
          ("SHIFT — limpa balas em 340px + stun 1s no boss.",),
          (255, 80, 200)),
          ("blink", "BLINK",
          ("SHIFT — teleporte instantâneo de 190px.",), (140, 80, 255)),
          ("overclock", "OVERCLOCK",
          ("SHIFT — cadência ×2.2 por 3s.",), (255, 140, 40)),
          ("shield", "ESCUDO",
          ("SHIFT — absorve o próximo hit (2.5s).",), (80, 255, 140)),
          ("timedil", "DILATAÇÃO",
          ("SHIFT — congela as balas inimigas por 2s.",), (160, 200, 255))]

WEAPONS = [("padrao", "PADRÃO",
           ("1 bala reta · 1.0× dano · CD 0.10s.",), (160, 160, 160)),
           ("spread", "SPREAD",
           ("3 balas em cone ±14° · 0.6× dano cada.",), (255, 165, 0)),
           ("agulha", "AGULHA",
           ("1 bala a 900px/s · 1.5× dano.",), (80, 255, 180)),
           ("carregado", "CARREGADO",
           ("Segure até 2.5s · dano 2.0×→8.0×.",), (255, 200, 60)),
           ("burst", "BURST",
           ("3 tiros em rajada · 1.0× dano cada.",), (255, 100, 100)),
           ("teleguiado", "TELEGUIADO",
           ("5 mísseis que curvam ao boss.",), (100, 255, 140)),
           ("flak", "FLAK",
           ("Projétil lento → 5 estilhaços em leque.",), (255, 160, 40)),
           ("chakram", "CHAKRAM",
           ("Disco que desacelera, inverte e retorna.",), (0, 220, 255)),
           ("plasma", "PLASMA",
           ("Feixe curto · 10 DPS contínuo por contato.",), (160, 60, 255)),
           ("satelite", "SATÉLITE",
           ("Até 4 gemas orbitando o jogador.",), (255, 220, 0))]

MUTATORS = [("predador", "PREDADOR",
            ("Boss mira 0.5s à frente do jogador.",), (255, 60, 60)),
            ("fantasma", "FANTASMA",
            ("Balas somem entre 200-400px do boss.",), (140, 100, 255)),
            ("glass", "CANHÃO DE VIDRO",
            ("1 vida · dano ×3 ao boss.",), (255, 200, 40)),
            ("claustro", "CLAUSTROFOBIA",
            ("Arena reduzida 14% em cada borda.",), (80, 180, 80)),
            ("horde", "HORDA",
            ("Boss +50% HP, −15% velocidade.",), (200, 80, 30)),
            ("berserker", "BERSERKER",
            ("Boss −25% HP, +35% velocidade.",), (255, 80, 160))]

BOSS_INTROS = {
    # flavor = texto exato de main.py:_BOSS_INTRO (1066-1079) onde o boss
    # existe em ambos os jogos — "timemage" é invenção do port, mantém
    # texto próprio. Nome/estilização (" *"/" **") seguem a convenção do
    # port, não o legado.
    "classic": ("O CLÁSSICO",
               "10 padrões. Cada ataque tem uma abertura — encontre-a."),
    "swarm": ("O ENXAME", "3 unidades em formação. Destrua uma por uma."),
    "wall": ("O PAREDÃO",
            "Uma muralha que desce. Elimine os canhões ou esquive das colunas."),
    "timemage": ("O MAGO DO TEMPO", "Suas balas chegam antes de partir."),
    "twins": ("OS GÊMEOS",
             "Azul para quem se move. Laranja para quem para. Nenhum lado é seguro."),
    "summoner": ("O INVOCADOR",
                "Canto a canto, invocação a invocação. O chefe não luta sozinho."),
    "omega": ("ÔMEGA *",
             "Quatro chefes em um. Teleporte periódico. Não baixe a guarda."),
    "pride": ("SOBERBA *",
             "Atire dentro do holofote. Fora da luz, é invulnerável."),
    "sloth": ("PREGUIÇA *",
             "Fase de sombras: mate os três fantasmas para expô-lo."),
    "envy": ("INVEJA *",
            "Ele copia o que você usa. Mude de estratégia, não de posição."),
    "gluttony": ("GULA *", "A gravidade muda em cada fase. Aprenda antes de reagir."),
    "greed": ("AVAREZA *", "Moedas explodem. Destrua-as longe de você."),
    "lust": ("LUXÚRIA *",
            "Fase 2: seus controles estão invertidos. Confie na memória muscular."),
    "wrath": ("IRA *", "O mergulho cria ondas de choque. Nunca fique no chão."),
    "sin": ("PECADO ORIGINAL **",
           "Fase 4: invulnerável por 30 segundos. A única saída é sobreviver."),
}

WIN_GOALS = {"classic": 1, "rush": len(RUSH_ORDERS[1]),
             "sins": len(RUSH_ORDERS[2]), "waves": 3}

ACCENT = (124, 80, 255, 255)
TXT = (221, 218, 245, 255)
MUTED = (136, 136, 170, 255)
GOLD = (245, 197, 24, 255)
RED = (255, 60, 90, 255)

# Layout dos menus de passo (DIFF/BOSS/SKILL/WEAPON/MUTADOR) — mesmas
# posições do legado (main.py: _MLL_*/_MRP_*/_MC_*), a mesma resolução
# 1280×720 (schemas.SCREEN_W/H) permite reusar os números exatos.
MLL_X, MLL_W = 80, 338
MRP_X, MRP_W = 450, 742
MC_Y0, MC_Y1 = 150, 666
STEP_COLS = [(80, 220, 80), (80, 180, 255), (255, 220, 0),
            (220, 50, 60), (140, 80, 255)]
STEP_NAMES = ["DIFICULDADE", "BOSS", "HABILIDADE", "ARMA", "MUTADORES"]

# Sequência secreta do dev mode (legado: W W S S A D A D, main.py:1719-1724)
DEV_SEQ_TARGET = ("move_up", "move_up", "move_down", "move_down",
                  "move_left", "move_right", "move_left", "move_right")


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
        # dificuldade/skill inicial = a única sempre destravada (legado:
        # main.py — estado inicial sel_diff=EASY, sel_skill=NONE)
        self.sel = {"mode": "classic", "diff": "facil", "boss": "classic",
                    "skill": "none", "skill_plus": False,
                    "weapon": "padrao", "weapon_plus": False,
                    "muts": set()}
        self.world = None
        self.intro_t = 0.0
        self.intro_boss = "classic"
        self.run_t = 0.0
        self.end_stats = (0, 0, 0)
        self.totals = {"kills": 0, "deaths": 0, "graze": 0, "runs": 0,
                       "parries": 0}
        self.save = save_data or {}
        self.replay_frames: list = []   # [(bitmask, dt), ...] da run atual
        self._last_cfg: dict | None = None
        self._replay_input: ReplayInputProvider | None = None
        self.achieved: set = set(self.save.get("achievements", []))
        self.new_achievements: list = []
        self._running = True
        # dev overlay (legado: sequência secreta W W S S A D A D, main.py:
        # 1719-1734) — F9/F10 em qualquer estado; F5/F3/F4/F7 só em PLAYING
        self.dev_mode = False
        self.godmode = False
        self._dev_seq: list = []
        self.dev_flash_t = 0.0
        self.dev_flash_msg = ""
        # hot-reload de data/*.json (legado: balance.json, main.py:28-44 —
        # só em dev_mode, checado a cada ~1s por mtime). Aplica-se à
        # PRÓXIMA partida — não repatcha sistemas de uma run já em curso.
        self._data_mtime = self._data_dir_mtime()
        self._reload_check_t = 0.0
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
    # dev overlay / cheats (legado: main.py:1717-1775, 2371-2418)
    # ------------------------------------------------------------------
    def _update_dev_mode(self, dt: float) -> None:
        inp = self._input
        for action in ("move_up", "move_down", "move_left", "move_right"):
            if inp.is_action_pressed(action):
                self._dev_seq.append(action)
                del self._dev_seq[:-8]
        if tuple(self._dev_seq) == DEV_SEQ_TARGET:
            self.dev_mode = not self.dev_mode
            self._dev_seq = []
            self.dev_flash_t = 1.8
            self.dev_flash_msg = "CHEAT ATIVADO" if self.dev_mode else \
                "CHEAT DESATIVADO"
            self._play("ui_ok", 0.5)
        if self.dev_flash_t > 0.0:
            self.dev_flash_t = max(0.0, self.dev_flash_t - dt)
        if not self.dev_mode:
            return
        if inp.is_action_pressed("cheat_unlock"):
            self._cheat_unlock_all()
            self.dev_flash_t, self.dev_flash_msg = 1.8, "CHEAT ATIVADO"
        if inp.is_action_pressed("cheat_wipe"):
            self._cheat_wipe_save()
            self.dev_flash_t, self.dev_flash_msg = 1.8, "SAVE APAGADO"
        if inp.is_action_pressed("cheat_godmode"):
            self.godmode = not self.godmode
        self._reload_check_t += dt              # balance.json (data/*.json)
        if self._reload_check_t >= 1.0:          # hot-reload, checado a ~1s
            self._reload_check_t = 0.0
            mtime = self._data_dir_mtime()
            if mtime > self._data_mtime:
                self._data_mtime = mtime
                self._data = load_all()          # vale pra PRÓXIMA partida
                self.dev_flash_t = 2.0
                self.dev_flash_msg = "BALANCE RELOADED"
        if self.state != PLAYING or self.world is None:
            return
        bp = self.world.get_pool("boss")
        if not bp.count:
            return
        bv = bp.active_view()
        if inp.is_action_pressed("cheat_kill"):
            bv["hp"][: bp.count] = 0.0
        if inp.is_action_pressed("cheat_hp50"):
            bv["hp"][: bp.count] = bv["max_hp"][: bp.count] * 0.5
        if inp.is_action_pressed("cheat_hp10"):
            bv["hp"][: bp.count] = bv["max_hp"][: bp.count] * 0.1
        if inp.is_action_pressed("cheat_phase"):
            self._cheat_advance_phase(bp)

    @staticmethod
    def _data_dir_mtime() -> float:
        """Maior mtime entre `data/*.json` — usado pelo hot-reload do dev
        mode (legado: balance.json, main.py:28-44)."""
        try:
            return max((p.stat().st_mtime for p in DATA_DIR.glob("*.json")),
                       default=0.0)
        except OSError:
            return 0.0

    def _cheat_unlock_all(self) -> None:
        self.save["highest_cleared_diff"] = len(DIFFS) - 1
        self.save["sins_rush_cleared"] = True
        self.save["unlocked_skills"] = [s[0] for s in SKILLS]
        self.save["unlocked_mutators"] = [m[0] for m in MUTATORS]
        self.save["omega_unlocked"] = True
        self.save["skill_plus_unlocked"] = [s[0] for s in SKILLS if s[0] != "none"]
        self.save["weapon_plus_unlocked"] = [w[0] for w in WEAPONS]

    def _cheat_wipe_save(self) -> None:
        settings = self.save.get("settings",
                                 {"screen_shake": True, "show_hitbox": False})
        self.save.clear()
        self.save.update({
            "runs": 0, "total_kills": 0, "total_deaths": 0, "total_graze": 0,
            "total_parries": 0, "achievements": [],
            "highest_cleared_diff": 0, "sins_rush_cleared": False,
            "unlocked_skills": ["none", "dash"], "unlocked_mutators": [],
            "omega_unlocked": False, "skill_plus_unlocked": [],
            "weapon_plus_unlocked": [], "best_time_dificil": 0.0,
            "settings": settings,
        })
        self.achieved = set()
        self.sel.update(diff="facil", skill="none", skill_plus=False,
                        weapon="padrao", weapon_plus=False, muts=set())

    def _cheat_advance_phase(self, boss_pool) -> None:
        bv = boss_pool.active_view()
        for k in range(boss_pool.count):
            bdef = self._data.bosses[int(bv["boss_id"][k])]
            nxt = int(bv["phase_idx"][k]) + 1
            if nxt < len(bdef.phases):
                frac = max(0.001, bdef.phases[nxt - 1].hp_above - 0.01)
                bv["hp"][k] = bv["max_hp"][k] * frac

    def _render_dev_overlay(self) -> None:
        r = self._r
        badge = (255, 60, 200, 255) if self.dev_mode else (60, 60, 80, 255)
        r.draw_text(SCREEN_W - 14, 34, "[ DEV ]", 13, badge, anchor="topright")
        if self.dev_flash_t > 0.0:
            a = min(255, int(self.dev_flash_t * 200))
            r.draw_text(SCREEN_W - 14, 54, self.dev_flash_msg, 13,
                        (80, 255, 160, a), anchor="topright")
        if not self.dev_mode:
            return
        px, py, pw, ph = SCREEN_W - 268, 74, 260, 138
        r.draw_ui_rect(px, py, pw, ph, (10, 10, 20, 200))
        cmds = [("F9", "Desbloquear tudo"), ("F10", "Apagar save"),
               ("F5", "Matar boss [PLAYING]"),
               ("F6", "God mode: " + ("ON" if self.godmode else "off")),
               ("F3", "Boss HP -> 50% [PLAYING]"),
               ("F4", "Boss HP -> 10% [PLAYING]"),
               ("F7", "Avançar fase [PLAYING]")]
        for i, (key, desc) in enumerate(cmds):
            y = py + 10 + i * 18
            key_c = (0, 255, 160, 255) if key == "F6" and self.godmode \
                else (255, 220, 60, 255)
            r.draw_text(px + 8, y, key, 12, key_c)
            r.draw_text(px + 46, y, desc, 12, (160, 160, 180, 255))

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
        self._update_dev_mode(dt)
        s = self.state
        if s == PLAYING:
            self._tick_playing(dt)
        elif s == REPLAYING:
            self._tick_replaying()
        elif s == MENU_MAIN:
            self._main_menu_screen()
        elif s == MENU_ACH:
            self._achievements_screen()
        elif s == MENU_RECORDS:
            self._records_screen()
        elif s == MENU_SETTINGS:
            self._settings_screen()
        elif s == MENU_MODE:
            self._menu([m[1] for m in MODES], "MODO DE JOGO",
                       colors=[m[3] for m in MODES],
                       descs=[m[2] for m in MODES],
                       on_confirm=self._mode_confirm, back_to=MENU_MAIN)
        elif s == MENU_DIFF:
            self._menu([d[1] for d in DIFFS], "BULLET HELL",
                       colors=[d[3] for d in DIFFS],
                       descs=[d[2] for d in DIFFS],
                       on_confirm=self._diff_confirm, back_to=MENU_MODE,
                       locked=[self._diff_locked(k) for k in range(len(DIFFS))],
                       step=1)
        elif s == MENU_BOSS:
            self._menu([b[1] for b in CLASSIC_BOSSES], "BULLET HELL",
                       colors=[b[2] for b in CLASSIC_BOSSES],
                       descs=[[BOSS_INTROS.get(b[0], ("", ""))[1]]
                             for b in CLASSIC_BOSSES],
                       on_confirm=self._boss_confirm, back_to=MENU_DIFF,
                       locked=[self._boss_locked(b[0]) for b in CLASSIC_BOSSES],
                       step=2, crumb=self._crumb()[:1])
        elif s == MENU_SKILL:
            items = [n + (" +" if self.sel["skill_plus"] and k == self.cursor
                          and self._has_plus(SKILLS[k][0], self._data.skills)
                          else "") for k, (sk, n, _, _) in enumerate(SKILLS)]
            skill_locked = [self._skill_locked(sk) for (sk, _, _, _) in SKILLS]
            self._menu(items, "BULLET HELL",
                       colors=[s_[3] for s_ in SKILLS],
                       descs=[d for (_, _, d, _) in SKILLS],
                       on_confirm=self._skill_confirm,
                       back_to=MENU_BOSS if self.sel["mode"] == "classic"
                       else MENU_DIFF,
                       hint_extra="ESPAÇO alterna a variante +",
                       locked=skill_locked, step=3,
                       crumb=self._crumb()[:2])
            if self._input.is_action_pressed("fire") and \
                    not skill_locked[self.cursor] and \
                    self._has_plus(SKILLS[self.cursor][0], self._data.skills) \
                    and self._plus_unlocked("skill", SKILLS[self.cursor][0]):
                self.sel["skill_plus"] = not self.sel["skill_plus"]
        elif s == MENU_WEAPON:
            items = [n + (" +" if self.sel["weapon_plus"] and k == self.cursor
                          and self._has_plus(WEAPONS[k][0], self._data.weapons)
                          else "") for k, (w, n, _, _) in enumerate(WEAPONS)]
            self._menu(items, "BULLET HELL",
                       colors=[w_[3] for w_ in WEAPONS],
                       descs=[d for (_, _, d, _) in WEAPONS],
                       on_confirm=self._weapon_confirm, back_to=MENU_SKILL,
                       hint_extra="ESPAÇO alterna a variante +",
                       step=4, crumb=self._crumb()[:3])
            if self._input.is_action_pressed("fire") and \
                    self._has_plus(WEAPONS[self.cursor][0], self._data.weapons) \
                    and self._plus_unlocked("weapon", WEAPONS[self.cursor][0]):
                self.sel["weapon_plus"] = not self.sel["weapon_plus"]
        elif s == MENU_MUT:
            items = [(("[x] " if m in self.sel["muts"] else "[ ] ") + n)
                     for (m, n, _, _) in MUTATORS] + ["► COMEÇAR"]
            self._menu(items, "BULLET HELL",
                       colors=[m_[3] for m_ in MUTATORS] + [GOLD[:3]],
                       descs=[d for (_, _, d, _) in MUTATORS] + [
                           ("Cada mutador ativo aumenta o desafio",)],
                       on_confirm=self._mut_confirm, back_to=MENU_WEAPON,
                       locked=[self._mutator_locked(m)
                              for (m, _, _, _) in MUTATORS] + [False],
                       step=5, crumb=self._crumb()[:4])
        elif s in (WIN, GAMEOVER):
            self._end_screen(s)
        self._render_dev_overlay()               # por cima de tudo (legado)

    # ------------------------------------------------------------------
    # menus
    # ------------------------------------------------------------------
    @staticmethod
    def _has_plus(name: str, table) -> bool:
        return sid(name + "+") in table

    def _plus_unlocked(self, category: str, name: str) -> bool:
        """Gate das variantes '+' (PARITY_PLAN P1-7): cada skill/arma tem
        sua própria mastery rastreada de verdade (ver `_apply_progression`/
        `_pull_mastery`), igual ao legado."""
        return name in self.save.get(f"{category}_plus_unlocked", [])

    def _diff_locked(self, idx: int) -> bool:
        if DIFFS[idx][0] == "abissal":     # só pelo SINS RUSH, não por tier
            return not self.save.get("sins_rush_cleared", False)
        return idx > int(self.save.get("highest_cleared_diff", 0))

    def _skill_locked(self, name: str) -> bool:
        return name not in self.save.get("unlocked_skills", ["none", "dash"])

    def _mutator_locked(self, name: str) -> bool:
        return name == "claustro" and \
            "claustro" not in self.save.get("unlocked_mutators", [])

    def _boss_locked(self, name: str) -> bool:
        return name == "omega" and not self.save.get("omega_unlocked", False)

    def _crumb(self) -> tuple:
        """Breadcrumb do assistente de seleção (legado: main.py `_mheader`).
        Fora do modo clássico não há tela de boss — o nome do MODO ocupa o
        lugar dela na trilha."""
        diff_label = next(d[1] for d in DIFFS if d[0] == self.sel["diff"])
        if self.sel["mode"] == "classic":
            slot2 = next(b[1] for b in BOSSES if b[0] == self.sel["boss"])
        else:
            slot2 = next(m[1] for m in MODES if m[0] == self.sel["mode"])
        skill_label = next(s[1] for s in SKILLS if s[0] == self.sel["skill"])
        weapon_label = next(w[1] for w in WEAPONS if w[0] == self.sel["weapon"])
        return (diff_label, slot2, skill_label, weapon_label)

    def _header(self, title: str, step: int = 0, crumb: tuple = ()) -> None:
        r = self._r
        cx = SCREEN_W / 2
        r.draw_text(cx, 8, title, 36, TXT, anchor="center")
        if step <= 0:
            return
        dot_r, gap = 5, 30
        x0 = cx - gap * 2
        for i in range(5):
            cxi = x0 + i * gap
            col = STEP_COLS[i]
            if i < step - 1:
                c = tuple(v // 2 for v in col)
                r.draw_ui_rect(cxi - dot_r, 82 - dot_r, dot_r * 2, dot_r * 2,
                              (*c, 255))
            elif i == step - 1:
                r.draw_ui_rect(cxi - dot_r - 3, 82 - dot_r - 3,
                              (dot_r + 3) * 2, (dot_r + 3) * 2, (255, 255, 255, 255))
                r.draw_ui_rect(cxi - dot_r, 82 - dot_r, dot_r * 2, dot_r * 2,
                              (*col, 255))
            else:
                r.draw_ui_rect(cxi - dot_r, 82 - dot_r, dot_r * 2, dot_r * 2,
                              (30, 30, 50, 255))
        r.draw_text(cx, 96, STEP_NAMES[step - 1], 13, MUTED, anchor="center")
        if crumb:
            r.draw_text(cx, 116, "  ›  ".join(crumb), 13,
                        (90, 90, 120, 255), anchor="center")
        r.draw_ui_rect(72, 140, SCREEN_W - 144, 1, (26, 26, 46, 255))

    def _menu(self, items, title, colors=None, descs=None, on_confirm=None,
              back_to=None, hint_extra="", locked=None, step=0,
              crumb=()) -> None:
        """Card colorido à esquerda + painel de descrição à direita, igual
        ao legado (main.py `_left_item`/`_right_panel`) — carrossel
        centralizado no cursor quando a lista não cabe na área visível."""
        inp = self._input
        n = len(items)
        locked = locked or [False] * n
        colors = colors or [ACCENT[:3]] * n
        if locked[self.cursor]:            # entrou numa tela com o cursor
            for _ in range(n):             # travado (default de _xxx_confirm)
                self.cursor = (self.cursor + 1) % n
                if not locked[self.cursor]:
                    break
        if inp.is_action_pressed("move_up"):
            for _ in range(n):
                self.cursor = (self.cursor - 1) % n
                if not locked[self.cursor]:
                    break
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            for _ in range(n):
                self.cursor = (self.cursor + 1) % n
                if not locked[self.cursor]:
                    break
            self._play("ui_move", 0.25)
        if back_to is not None and (inp.is_action_pressed("back")
                                    or inp.is_action_pressed("move_left")):
            self.state = back_to
            self.cursor = 0
            return
        if on_confirm and not locked[self.cursor] and (
                inp.is_action_pressed("confirm")
                or inp.is_action_pressed("move_right")):
            self._play("ui_ok", 0.35)
            on_confirm(self.cursor)
            return
        self.cursor = min(self.cursor, n - 1)

        self._header(title, step, crumb)
        r = self._r
        ih, gap = 58, 8
        row_h = ih + gap
        visible_h = MC_Y1 - MC_Y0
        center_y = MC_Y0 + (visible_h - ih) / 2
        for k, label in enumerate(items):
            y = center_y + (k - self.cursor) * row_h
            if y + ih < MC_Y0 or y > MC_Y1:
                continue
            col = colors[k]
            sel = k == self.cursor
            bg = (22, 22, 40, 255) if sel else (13, 13, 22, 255)
            r.draw_ui_rect(MLL_X, y, MLL_W, ih, bg)
            bar = col if sel else tuple(c * 2 // 5 for c in col)
            r.draw_ui_rect(MLL_X, y, 4, ih, (*bar, 255))
            disp = label + ("  [BLOQUEADO]" if locked[k] else "")
            name_c = (70, 70, 90, 255) if locked[k] else \
                ((255, 255, 255, 255) if sel else MUTED)
            r.draw_text(MLL_X + 18, y + ih / 2 - 9, disp, 15, name_c)
            if sel:
                r.draw_text(MLL_X + MLL_W + 6, y + ih / 2 - 8, "►", 16,
                            (*col, 255))
            r.draw_ui_rect(MLL_X, y + ih, MLL_W, 1, (20, 20, 36, 255))

        sel_col = colors[self.cursor]
        rx, ry, rw = MRP_X, MC_Y0, MRP_W
        rh = MC_Y1 - MC_Y0
        r.draw_ui_rect(rx, ry, rw, rh, (11, 11, 21, 255))
        r.draw_ui_rect(rx, ry, rw, 3, (*sel_col, 255))
        r.draw_text(rx + 28, ry + 20, items[self.cursor], 28, (*sel_col, 255))
        r.draw_ui_rect(rx + 28, ry + 96, rw - 56, 1,
                      (sel_col[0] // 3, sel_col[1] // 3, sel_col[2] // 3, 255))
        if descs:
            lines = descs[self.cursor]
            if isinstance(lines, str):
                lines = [lines]
            for i, ln in enumerate(lines):
                r.draw_text(rx + 28, ry + 114 + i * 28, ln, 15,
                            (168, 168, 196, 255))

        r.draw_ui_rect(0, 672, SCREEN_W, 48, (8, 8, 18, 255))
        hint = "W/S navegar  ·  D/ENTER confirmar  ·  A/ESC voltar"
        if hint_extra:
            hint += "  ·  " + hint_extra
        r.draw_text(SCREEN_W / 2, 688, hint, 13, (58, 58, 80, 255),
                    anchor="center")

    def _main_menu_screen(self) -> None:
        inp = self._input
        n = len(MAIN_ITEMS)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("confirm") or inp.is_action_pressed("move_right"):
            self._play("ui_ok", 0.35)
            self._main_confirm(self.cursor)
            return

        r = self._r
        cx = SCREEN_W / 2
        r.draw_text(cx, 128, "BULLET HELL", 46, TXT, anchor="center")
        r.draw_text(cx, 168, "OuroborosEngine · port ECS", 15, MUTED,
                    anchor="center")
        card_w, ih, gap = 360, 62, 12
        top = 240
        for k, (_, label, col) in enumerate(MAIN_ITEMS):
            y = top + k * (ih + gap)
            sel = k == self.cursor
            bg = (22, 22, 40, 255) if sel else (12, 12, 20, 255)
            r.draw_ui_rect(cx - card_w / 2, y, card_w, ih, bg)
            bar = col if sel else tuple(c // 3 for c in col)
            r.draw_ui_rect(cx - card_w / 2, y, 4, ih, (*bar, 255))
            r.draw_text(cx - card_w / 2 + 22, y + ih / 2 - 9, label, 18,
                        (255, 255, 255, 255) if sel else MUTED)
            if sel:
                r.draw_text(cx + card_w / 2 - 22, y + ih / 2 - 8, "►", 16,
                            (*col, 255))
        r.draw_text(cx, SCREEN_H - 44, "W/S navegar  ·  D/ENTER confirmar",
                    14, MUTED, anchor="center")

    def _main_confirm(self, k: int) -> None:
        dest = MAIN_ITEMS[k][0]
        if dest == "play":
            self.state, self.cursor = MENU_MODE, 0
        elif dest == "ach":
            self.state, self.cursor = MENU_ACH, 0
        elif dest == "records":
            self.state, self.cursor = MENU_RECORDS, 0
        elif dest == "settings":
            self.state, self.cursor = MENU_SETTINGS, 0
        else:
            self._running = False

    def _records_screen(self) -> None:
        inp = self._input
        if inp.is_action_pressed("back") or inp.is_action_pressed("confirm") \
                or inp.is_action_pressed("move_left"):
            self.state, self.cursor = MENU_MAIN, 0
            return
        r = self._r
        cx = SCREEN_W / 2
        r.draw_text(cx, 80, "REGISTROS", 40, GOLD, anchor="center")
        r.draw_ui_rect(180, 162, SCREEN_W - 360, 1, (50, 50, 20, 255))
        total_deaths = int(self.save.get("total_deaths", 0)) + self.totals["deaths"]
        total_parries = int(self.save.get("total_parries", 0)) + self.totals["parries"]
        best = float(self.save.get("best_time_dificil", 0.0))
        bm, bs = divmod(int(best), 60)
        hcd = int(self.save.get("highest_cleared_diff", 0))
        diff_label = DIFFS[min(hcd, len(DIFFS) - 1)][1] if hcd > 0 else "NENHUMA"
        unlocked_skills = [s[1] for s in SKILLS if s[0] in
                          self.save.get("unlocked_skills", ["none", "dash"])]
        rows = [
            ("Mortes totais", str(total_deaths)),
            ("Melhor tempo (Difícil+)",
             f"{bm:02d}:{bs:02d}" if best > 0 else "—"),
            ("Balas refletidas (Parry)", str(total_parries)),
            ("Dificuldade desbloqueada", diff_label),
            ("Habilidades desbloqueadas", "  ".join(unlocked_skills)),
        ]
        top = 210
        for k, (label, value) in enumerate(rows):
            y = top + k * 52
            r.draw_text(220, y, label, 16, (120, 120, 140, 255))
            r.draw_text(SCREEN_W - 220, y, value, 16, TXT, anchor="topright")
            r.draw_ui_rect(180, y + 32, SCREEN_W - 360, 1, (24, 24, 36, 255))
        r.draw_text(cx, SCREEN_H - 44, "ESC   voltar ao menu principal", 14,
                    (35, 35, 50, 255), anchor="center")

    def _settings_screen(self) -> None:
        """Só 2 dos 3 toggles do legado: Tela Cheia exigiria um método
        novo no IRenderer da engine (fora do escopo deste port agora) —
        melhor não expor um toggle que não faz nada de verdade."""
        inp = self._input
        settings = self.save.setdefault(
            "settings", {"screen_shake": True, "show_hitbox": False})
        items = [("screen_shake", "Screen Shake"),
                 ("show_hitbox", "Mostrar Hitbox")]
        n = len(items)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("confirm") or inp.is_action_pressed("fire"):
            key = items[self.cursor][0]
            settings[key] = not settings.get(key, key != "show_hitbox")
            self._play("ui_ok", 0.3)
        if inp.is_action_pressed("back") or inp.is_action_pressed("move_left"):
            self.state, self.cursor = MENU_MAIN, 0
            return

        r = self._r
        cx = SCREEN_W / 2
        r.draw_text(cx, 80, "SISTEMA", 40, (100, 160, 255, 255),
                    anchor="center")
        r.draw_ui_rect(180, 162, SCREEN_W - 360, 1, (30, 50, 80, 255))
        top, ih, gap = 210, 70, 12
        for k, (key, label) in enumerate(items):
            y = top + k * (ih + gap)
            sel = k == self.cursor
            on = bool(settings.get(key, key != "show_hitbox"))
            bg = (20, 28, 44, 255) if sel else (12, 12, 20, 255)
            r.draw_ui_rect(180, y, SCREEN_W - 360, ih, bg)
            r.draw_ui_rect(180, y, 4, ih,
                          (100, 160, 255, 255) if sel else (40, 60, 100, 255))
            r.draw_text(210, y + ih / 2 - 9, label, 16,
                        (255, 255, 255, 255) if sel else MUTED)
            val_txt = "[ LIGADO ]" if on else "[ DESLIGADO ]"
            val_col = (0, 220, 0, 255) if on else (220, 20, 60, 255)
            r.draw_text(SCREEN_W - 220, y + ih / 2 - 9, val_txt, 16, val_col,
                        anchor="topright")
        r.draw_text(cx, SCREEN_H - 44,
                    "W/S navegar  ·  ENTER/D toggle  ·  ESC voltar", 14,
                    (35, 35, 50, 255), anchor="center")

    def _achievement_progress(self, key: str) -> int:
        """Valor atual do contador de progresso (save persistido + total
        já acumulado nesta sessão, incluindo a run em andamento)."""
        base = int(self.save.get(f"total_{key}", 0))
        return base + int(self.totals.get(key, 0))

    def _achievements_screen(self) -> None:
        inp = self._input
        n = len(ACHIEVEMENTS)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            self._play("ui_move", 0.25)
        if inp.is_action_pressed("back") or inp.is_action_pressed("move_left"):
            self.state, self.cursor = MENU_MAIN, 0
            return
        self.cursor = min(self.cursor, n - 1)

        r = self._r
        r.draw_text(SCREEN_W / 2, 56, "CONQUISTAS", 40, GOLD, anchor="center")
        done = sum(1 for a in ACHIEVEMENTS if a[0] in self.achieved)
        r.draw_text(SCREEN_W / 2, 100, f"{done} / {n} desbloqueadas",
                    16, MUTED, anchor="center")

        top, bottom, ih, gap = 140, 560, 26, 2
        row_h = ih + gap
        center_y = top + ((bottom - top) - ih) / 2
        for k, (aid, name, desc, reward, secret, progress) in enumerate(ACHIEVEMENTS):
            y = center_y + (k - self.cursor) * row_h
            if y + ih < top or y > bottom:
                continue
            got = aid in self.achieved
            hidden = secret and not got
            sel = k == self.cursor
            if sel:
                r.draw_ui_rect(SCREEN_W / 2 - 340, y - 2, 680, ih,
                              (124, 80, 255, 40))
            mark = "[x]" if got else ("[?]" if hidden else "[ ]")
            r.draw_text(SCREEN_W / 2 - 330, y, mark, 16,
                        GOLD if got else MUTED)
            disp_name = "???" if hidden else name
            r.draw_text(SCREEN_W / 2 - 280, y, disp_name, 16,
                        GOLD if got else (TXT if sel else MUTED))
            disp_desc = "Conquista secreta." if hidden else desc
            r.draw_text(SCREEN_W / 2 + 10, y + 1, disp_desc, 13, MUTED)

        aid, name, desc, reward, secret, progress = ACHIEVEMENTS[self.cursor]
        got = aid in self.achieved
        hidden = secret and not got
        y0 = 590
        r.draw_ui_rect(SCREEN_W / 2 - 340, y0, 680, 100, (11, 11, 21, 255))
        r.draw_text(SCREEN_W / 2 - 320, y0 + 10,
                    "???" if hidden else name, 18, GOLD if got else TXT)
        r.draw_text(SCREEN_W / 2 - 320, y0 + 34,
                    "Descubra as condições jogando." if hidden else desc,
                    13, (168, 168, 196, 255))
        if got:
            status = "[ DESBLOQUEADO ]"
        elif progress and not hidden:
            cur = min(progress[1], self._achievement_progress(progress[0]))
            status = f"Progresso: {cur}/{progress[1]}"
        else:
            status = "[ BLOQUEADO ]" if not hidden else ""
        r.draw_text(SCREEN_W / 2 - 320, y0 + 56, status, 13,
                    (0, 220, 0, 255) if got else MUTED)
        if not hidden and reward != "—":
            r.draw_text(SCREEN_W / 2 - 320, y0 + 76, f"Recompensa: {reward}",
                        13, (168, 168, 196, 255))

        r.draw_text(SCREEN_W / 2, SCREEN_H - 20, "W/S navegar  ·  A/ESC voltar",
                    14, MUTED, anchor="center")

    def _mode_confirm(self, k: int) -> None:
        self.sel["mode"] = MODES[k][0]
        self.state, self.cursor = MENU_DIFF, 1

    def _diff_confirm(self, k: int) -> None:
        if self._diff_locked(k):
            return
        self.sel["diff"] = DIFFS[k][0]
        self.state = MENU_BOSS if self.sel["mode"] == "classic" else MENU_SKILL
        self.cursor = 0

    def _boss_confirm(self, k: int) -> None:
        if self._boss_locked(CLASSIC_BOSSES[k][0]):
            return
        self.sel["boss"] = CLASSIC_BOSSES[k][0]
        self.state, self.cursor = MENU_SKILL, 0

    def _skill_confirm(self, k: int) -> None:
        if self._skill_locked(SKILLS[k][0]):
            return
        self.sel["skill"] = SKILLS[k][0]
        self.sel["skill_plus"] = False    # nova skill: reseta o toggle +
        self.state, self.cursor = MENU_WEAPON, 0

    def _weapon_confirm(self, k: int) -> None:
        self.sel["weapon"] = WEAPONS[k][0]
        self.sel["weapon_plus"] = False    # nova arma: reseta o toggle +
        self.state, self.cursor = MENU_MUT, 0

    def _mut_confirm(self, k: int) -> None:
        if k < len(MUTATORS):
            m = MUTATORS[k][0]
            if self._mutator_locked(m):
                return
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
        # defesa (legado: main.py:2468-2470) — se a seleção ficou travada
        # entre a hora que foi escolhida e agora (save recarregado, etc.)
        if self._skill_locked(self.sel["skill"]):
            self.sel["skill"] = "none"
        if self._diff_locked([d[0] for d in DIFFS].index(self.sel["diff"])):
            self.sel["diff"] = "facil"
        skill = self.sel["skill"]
        if self.sel["skill_plus"] and self._has_plus(skill, self._data.skills) \
                and self._plus_unlocked("skill", skill):
            skill += "+"
        weapon = self.sel["weapon"]
        if self.sel["weapon_plus"] and self._has_plus(weapon, self._data.weapons) \
                and self._plus_unlocked("weapon", weapon):
            weapon += "+"
        muts = frozenset(self.sel["muts"])
        self.world = build_world(
            self._data, self._input, boss_name=self.sel["boss"],
            weapon_name=weapon, skill_name=skill,
            mutators=muts, mode=self.sel["mode"],
            difficulty=self.sel["diff"], arcade=True)
        mode = self.sel["mode"]
        self.intro_boss = (RUSH_ORDERS[1][0] if mode == "rush" else
                           RUSH_ORDERS[2][0] if mode == "sins" else
                           self.sel["boss"])
        self.intro_t = 0.0 if mode == "waves" else 2.4
        self.run_t = 0.0
        self.replay_frames = []           # nova gravação (legado: W — replay)
        self._last_cfg = {"boss": self.sel["boss"], "weapon": weapon,
                          "skill": skill, "muts": muts, "mode": mode,
                          "diff": self.sel["diff"]}
        self.state = PLAYING

    def _tick_playing(self, dt: float) -> None:
        w = self.world
        self.replay_frames.append((encode_frame(self._input), dt))
        self.run_t += dt
        if self.godmode:                          # F6 (dev mode)
            pl = w.get_pool("player")
            pi = pl.active_entity_indices()
            if pi.size:
                pl.active_view()["invuln_t"][pl.dense_row_of(int(pi[0]))] = 999.0
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

    # ------------------------------------------------------------------
    # replay (legado: ReplayRecorder — ver bullethell/replay.py)
    # ------------------------------------------------------------------
    def _start_replay(self) -> None:
        if not self.replay_frames or self._last_cfg is None:
            return
        cfg = self._last_cfg
        self._replay_input = ReplayInputProvider(list(self.replay_frames))
        self.world = build_world(
            self._data, self._replay_input, boss_name=cfg["boss"],
            weapon_name=cfg["weapon"], skill_name=cfg["skill"],
            mutators=cfg["muts"], mode=cfg["mode"],
            difficulty=cfg["diff"], arcade=True)
        self.run_t = 0.0
        self.intro_t = 0.0                # legado: replay não mostra intro
        self.state = REPLAYING

    def _tick_replaying(self) -> None:
        ri = self._replay_input
        ri.poll()
        if not ri.has_more():
            self._replay_end()
            return
        dt = ri.current_dt()
        w = self.world
        self.run_t += dt
        w.step(dt)
        self._pump_sfx()
        self._apply_shake(dt)
        self._render_world()
        self._render_hud()
        self._render_replay_tag()

        if self._input.is_action_pressed("back"):   # ESC sai do replay
            self._replay_end()

    def _replay_end(self) -> None:
        """Fim dos frames gravados (ou ESC): WIN se o boss morreu nesse
        ponto, senão GAMEOVER — igual ao legado (main.py:2612-2614)."""
        bp = self.world.get_pool("boss")
        dead = (not bp.count) or \
            float(np.sum(bp.active_view()["hp"][: bp.count])) <= 0.0
        self.state = WIN if dead else GAMEOVER

    def _render_replay_tag(self) -> None:
        self._r.draw_text(SCREEN_W - 14, 14, "REPLAY", 14, RED,
                          anchor="topright")

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
        self.totals["parries"] += int(st["parries"][0])
        self.totals["runs"] += 1
        self._r.set_camera_offset(0.0, 0.0)
        self._pull_mastery()
        self._check_achievements(outcome, lives, graze)
        self._apply_progression(outcome)

    def _pull_mastery(self) -> None:
        """Junta os contadores de mastery da run (pool `mastery`) ao save
        — soma para os cumulativos, máximo para os "melhor valor", OR
        sticky para os booleanos (PARITY_PLAN P1-7)."""
        mp = self.world.get_pool("mastery")
        if not mp.count:
            return
        mv = mp.active_view()
        s = self.save

        def bump_max(key: str, value) -> None:
            s[key] = max(float(s.get(key, 0.0)), float(value))

        def bump_sum(key: str, value) -> None:
            s[key] = s.get(key, 0) + value

        bump_sum("mastery_dash_graze", int(mv["dash_graze"][0]))
        bump_max("mastery_parry_burst_max", mv["parry_burst_max"][0])
        bump_max("mastery_emp_max", mv["emp_max"][0])
        bump_max("mastery_oc_dmg_max", mv["oc_dmg_max"][0])
        bump_sum("mastery_shield_perfects", int(mv["shield_perfects"][0]))
        s["mastery_blink_pass"] = bool(s.get("mastery_blink_pass", False)) \
            or bool(mv["blink_pass"][0])
        s["mastery_timedil_close"] = bool(s.get("mastery_timedil_close", False)) \
            or bool(mv["timedil_close"][0])
        bump_max("mastery_default_max", mv["default_max"][0])
        bump_sum("mastery_spread_close", int(mv["spread_close"][0]))
        bump_max("mastery_plasma_max", mv["plasma_max"][0])
        bump_sum("mastery_orbit_damage", float(mv["orbit_damage"][0]))

    def _check_achievements(self, outcome: str, lives: int, graze: int) -> None:
        """Avalia as conquistas ao fim da run (persistidas ao sair). IDs e
        recompensas batem com o legado onde aplicável (ACHIEVEMENTS_DEF,
        main.py:1896-1986) — ver a tabela `ACHIEVEMENTS` para a lista
        completa e quais são aproximações documentadas."""
        self.new_achievements = []

        def grant(aid: str) -> None:
            if aid not in self.achieved:
                self.achieved.add(aid)
                name = next(n for a, n, _, _, _, _ in ACHIEVEMENTS if a == aid)
                self.new_achievements.append(name)

        if self.end_stats[0] >= 1:
            grant("first_blood")
        if self._achievement_progress("graze") >= 100:
            grant("grazes_100")
        if self._achievement_progress("parries") >= 50:
            grant("parries_50")
        if self._achievement_progress("parries") >= 200:
            grant("parries_200")
        if outcome != "win":
            return
        mode, diff, boss = self.sel["mode"], self.sel["diff"], self.sel["boss"]
        muts = self.sel["muts"]
        if diff == "facil":
            grant("easy_win")
        if diff == "normal":
            grant("normal_win")
        if diff == "dificil":
            grant("hard_win")
            if len(muts) >= 1:
                grant("mutator_hard")
            if len(muts) >= 3:
                grant("omega_unlock")
            if self.run_t < 180.0:
                grant("speed_hard")
        full = 0 if "glass" in muts else 3
        if lives >= full:
            grant("no_hit_win")
        if self.sel["skill"] == "none":
            grant("no_skill")
        if mode == "classic" and boss == "twins":
            grant("equilibrio_perfeito")           # aproximação — ver P1-6
        if mode == "classic" and boss == "summoner":
            grant("pacifista_elite")               # aproximação — ver P1-6
        if mode == "classic" and boss == "omega" and diff == "dificil":
            grant("omega_hard")
        if mode == "rush":
            grant("boss_rush_win")
        if mode == "sins":
            grant("sins_rush_win")
        if mode == "waves":
            grant("waves_win")
        if "glass" in muts:
            grant("glass_win")
        if len(muts) >= 3:
            grant("all_mutators")
        if self.new_achievements:
            self._play("ui_ok", 0.6)

    def _apply_progression(self, outcome: str) -> None:
        """Gating de progresso ao vencer (legado: SaveManager.on_win,
        entities.py:5365-5409 — PARITY_PLAN P0-1). Onde o port ainda não
        rastreia a mesma mastery do legado (equilíbrio perfeito, pacifista
        de elite, as 17 masteries de skill+/arma+), usa uma condição
        aproximada e documentada — ver PARITY_PLAN.md P1-6/P1-7."""
        if outcome != "win":
            return
        diff_idx = [d[0] for d in DIFFS].index(self.sel["diff"])
        hcd = max(int(self.save.get("highest_cleared_diff", 0)), diff_idx + 1)
        self.save["highest_cleared_diff"] = hcd
        if self.sel["mode"] == "sins":
            self.save["sins_rush_cleared"] = True

        unlocked = set(self.save.get("unlocked_skills", ["none", "dash"]))
        if hcd >= 1:                                  # venceu FÁCIL
            unlocked.add("parry")
        if hcd >= 2:                                  # venceu NORMAL
            unlocked.add("focus")
        if "grazes_100" in self.achieved:              # 100 grazes (exato)
            unlocked.add("emp")
        if "no_hit_win" in self.achieved:              # no-hit win (exato)
            unlocked.add("blink")
        if self.sel["diff"] == "dificil" and len(self.sel["muts"]) >= 1:
            unlocked.add("overclock")                  # DIFÍCIL + mutador
        if self._achievement_progress("parries") >= 50:
            unlocked.add("shield")                      # 50 parries totais
        if self.sel["mode"] == "classic" and self.sel["boss"] == "twins":
            unlocked.add("timedil")                      # aprox. de Gêmeos
        self.save["unlocked_skills"] = sorted(unlocked)

        if "omega_unlock" in self.achieved:             # HARD c/ 3+ mutadores
            self.save["omega_unlocked"] = True
        if self.sel["mode"] == "classic" and self.sel["boss"] == "summoner":
            muts = set(self.save.get("unlocked_mutators", []))
            muts.add("claustro")                         # aprox. de Invocador
            self.save["unlocked_mutators"] = sorted(muts)
        # variantes '+' de SKILL — as 7 masteries do legado (entities.py:
        # 129-133) são todas rastreadas de verdade (ver PlayerHitSystem/
        # SkillSystem/PlayerBulletVsBossSystem + _pull_mastery)
        skill_plus = set(self.save.get("skill_plus_unlocked", []))
        if self.save.get("mastery_dash_graze", 0) >= 50:
            skill_plus.add("dash")
        if self.save.get("mastery_parry_burst_max", 0) >= 5:
            skill_plus.add("parry")
        if self.save.get("mastery_emp_max", 0) >= 200:
            skill_plus.add("emp")
        if self.save.get("mastery_oc_dmg_max", 0.0) >= 500.0:
            skill_plus.add("overclock")
        if self.save.get("mastery_shield_perfects", 0) >= 10:
            skill_plus.add("shield")
        if self.save.get("mastery_blink_pass", False):
            skill_plus.add("blink")
        if self.save.get("mastery_timedil_close", False):
            skill_plus.add("timedil")
        self.save["skill_plus_unlocked"] = sorted(skill_plus)

        # variantes '+' de ARMA — 4 masteries que o legado realmente
        # rastreia (default_hits/spread_close/plasma_contact/orbit_damage).
        # As outras 6 nunca são rastreadas nem no legado (bug documentado,
        # PARITY_PLAN P1-7) — aqui destravam vencendo com a arma equipada,
        # estritamente melhor que nunca destravar.
        weapon_plus = set(self.save.get("weapon_plus_unlocked", []))
        if self.save.get("mastery_default_max", 0) >= 150:
            weapon_plus.add("padrao")
        if self.save.get("mastery_spread_close", 0) >= 50:
            weapon_plus.add("spread")
        if self.save.get("mastery_plasma_max", 0.0) >= 4.0:
            weapon_plus.add("plasma")
        if self.save.get("mastery_orbit_damage", 0.0) >= 400.0:
            weapon_plus.add("satelite")
        if self.sel["weapon"] in ("agulha", "carregado", "burst",
                                  "teleguiado", "flak", "chakram"):
            weapon_plus.add(self.sel["weapon"])
        self.save["weapon_plus_unlocked"] = sorted(weapon_plus)
        if diff_idx >= 2:                # tela RECORDS: melhor tempo Difícil+
            best = float(self.save.get("best_time_dificil", 0.0))
            if best <= 0.0 or self.run_t < best:
                self.save["best_time_dificil"] = self.run_t

    def _apply_shake(self, dt: float) -> None:
        ck = self.world.get_pool("clock")
        if not ck.count:
            return
        cv = ck.active_view()
        amt = float(cv["shake"][0])
        if amt > 0.0:
            cv["shake"][0] = max(0.0, amt - 26.0 * dt)
        shake_on = self.save.get("settings", {}).get("screen_shake", True)
        if amt > 0.0 and shake_on:
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
            pat_txt = self._active_pattern_text(bp)
            r.draw_text(SCREEN_W / 2, 26,
                        f"{name}   {hp:.0f} / {mx:.0f}{pat_txt}   T{tier}",
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
        if self.save.get("settings", {}).get("show_hitbox", False):
            self._render_hitbox_debug()

    def _render_hitbox_debug(self) -> None:
        """Tela SISTEMA › Mostrar Hitbox: raio de colisão real do jogador
        (legado: quadrado branco 5×5 sempre visível, main.py:875). Não
        recria a grade da spatial hash nem os AABBs de boss do legado —
        ver PARITY_PLAN.md."""
        pl = self.world.get_pool("player")
        pi = pl.active_entity_indices()
        if not pi.size:
            return
        tp = self.world.get_pool("transform")
        prow = tp.dense_row_of(int(pi[0]))
        tv = tp.active_view()
        px = float(tv["position_x"][prow]); py = float(tv["position_y"][prow])
        hr = PLAYER_HIT_R
        self._r.draw_ui_rect(px - hr, py - hr, hr * 2, hr * 2, (0, 255, 200, 110))

    def _active_pattern_text(self, boss_pool) -> str:
        """Nome do(s) padrão(ões) ativo(s) do boss para a barra de HP
        (legado: `{PATTERN_NAME}` dentro do texto, main.py:986-989)."""
        ep = self.world.get_pool("emitter")
        if not ep.count:
            return ""
        boss_idxs = set(int(x) for x in boss_pool.active_entity_indices())
        ev = ep.active_view()
        names, seen = [], set()
        for k in range(ep.count):                      # ≤32 emitters
            if int(ev["root"][k]) not in boss_idxs:
                continue
            pat = self._data.patterns.get(int(ev["pattern_id"][k]))
            if pat is None or pat.name in seen:
                continue
            seen.add(pat.name)
            names.append(pat.name.rsplit("/", 1)[-1].upper().replace("_", " "))
        return ("   " + "+".join(names[:2])) if names else ""

    def _boss_display(self, boss_id: int) -> str:
        for name, label, _ in BOSSES:
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
        has_replay = bool(self.replay_frames)
        hint = "T  jogar de novo      R  menu"
        if has_replay:
            hint = "T  jogar de novo      W  ver replay      R  menu"
        r.draw_text(SCREEN_W / 2, 500, hint, 18, MUTED, anchor="center")
        if self._input.is_action_pressed("retry"):
            self.start_game()
        elif has_replay and self._input.is_action_pressed("move_up"):
            self._start_replay()
        elif self._input.is_action_pressed("to_menu") \
                or self._input.is_action_pressed("back"):
            self.state, self.cursor = MENU_MAIN, 0


MODES_SHORT = [("classic", "CLÁSSICO"), ("rush", "BOSS RUSH"),
               ("sins", "SINS RUSH"), ("waves", "WAVES")]
