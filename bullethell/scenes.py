"""
Cenas do jogo: menus do legado (modo → dificuldade → boss → habilidade →
arma → mutadores), gameplay com HUD textual, intro de boss, WIN/GAMEOVER
com T (retry) / R (menu), screen shake e overlays.

Camada de APRESENTAÇÃO do produto: usa draw_text/draw_ui_rect do
IRenderer (ROADMAP M1/M2) — permitido alocar aqui; o gameplay continua
inteiro dentro de World.step().
"""
from __future__ import annotations

import numpy as np

from ouroboros.bootstrap.audio_bank_loader import load_audio_bank
from ouroboros.bootstrap.scene import IScene
from ouroboros.bootstrap.screen_shake import ScreenShake
from ouroboros.core.memory.component_pool import intersect_entity_indices
from ouroboros.core.particle_storage import ParticleStorage

from bullethell.composition import build_world
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
 MENU_SETTINGS, REPLAYING, MENU_TEST) = range(15)

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
    ("decalogue_rush_win", "O JUÍZO", "Complete o DECÁLOGO RUSH.", "—",
     False, None),
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
          "Sobreviva até o fim para vencer."), (80, 200, 100)),
         ("decalogo", "DECÁLOGO RUSH",
         ("11 bosses em ordem fixa — dos Mandamentos ao Juízo Final.",
          "HP sem escala — a lei fica mais complexa, não mais forte.",
          "⚠ Requer vitória no SINS RUSH"), (245, 245, 240))]

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
          ("sin", "PECADO ORIGINAL **", (180, 0, 220)),
          # Decálogo (em andamento, ver bullethell/MIGRATION.md): marcador
          # "†" pra distinguir da linhagem dos Pecados ("*"/"**").
          ("monolith", "MONÓLITO †", (140, 130, 120)),
          ("icon", "ÍDOLO †", (200, 170, 60)),
          ("lineage", "LINHAGEM †", (255, 210, 90)),
          ("truth", "VERDADE †", (230, 230, 230)),
          ("silence", "REVERÊNCIA †", (150, 100, 200)),
          ("sabbath", "SABBATH †", (230, 190, 60)),
          ("ascetic", "ABNEGAÇÃO †", (120, 140, 130)),
          ("purity", "PUREZA †", (120, 170, 255)),
          ("restitution", "RESTITUIÇÃO †", (230, 190, 90)),
          ("mercy", "MISERICÓRDIA †", (140, 220, 160)),
          ("decalogue", "DECALOGUE †", (245, 245, 240))]

# Legado: SELECT_BOSS só lista CLASSIC_BOSS_IDS — os 8 pecados só são
# jogáveis via SINS RUSH, "Mago do Tempo" (invenção do port) via BOSS RUSH.
# Preservar a ordem de BOSSES já dá a ordem exata do legado (spec menus §6).
# Decálogo fica de fora de propósito — ainda não tem um modo "rush" próprio
# (arco em construção, ver bullethell/MIGRATION.md); acessível só via
# --boss <nome> (CLI) e smoke_ecs.py por enquanto.
CLASSIC_BOSS_NAMES = ("classic", "swarm", "wall", "twins", "summoner", "omega")
CLASSIC_BOSSES = [b for b in BOSSES if b[0] in CLASSIC_BOSS_NAMES]

# "Seção de teste": QUALQUER boss fora de CLASSIC_BOSS_NAMES — não é uma
# lista de nomes fixa, é o complemento genérico. Cobre o Mago do Tempo
# (só via Boss Rush), os 8 pecados (só via SINS Rush) e os 10 do Decálogo
# (sem modo "rush" próprio ainda) — todos difíceis de alcançar normalmente
# ou que exigem condições chatas de replicar (vencer um Rush inteiro só
# pra testar 1 boss específico). Só visível com o cheat (dev_mode)
# ligado, num botão próprio no menu principal — não mistura com
# CLASSIC_BOSSES (ver MENU_TEST/_main_items).
TEST_BOSSES = [b for b in BOSSES if b[0] not in CLASSIC_BOSS_NAMES]

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
    # Decálogo: flavor autoral, sem equivalente no legado.
    "monolith": ("MONÓLITO †",
                "Os pilares são isca — atingi-los custa caro. Mire além deles."),
    "icon": ("ÍDOLO †",
            "Quatro rostos, um só real. Observe antes de atirar."),
    "lineage": ("LINHAGEM †",
               "Sol e Lua — fira um demais e o outro acorda com raiva."),
    "truth": ("VERDADE †",
             "A maioria do que você vê não pode te tocar. Confie no brilho."),
    "silence": ("REVERÊNCIA †",
               "Não invoque nada. Só o corpo e o silêncio."),
    "sabbath": ("SABBATH †",
               "Quando a luz dourada acender, pare de vez."),
    "ascetic": ("ABNEGAÇÃO †",
               "O vazio perfeito é a armadilha mais cara."),
    "purity": ("PUREZA †",
              "Azul na luz, vermelho na sombra. Nunca o contrário."),
    "restitution": ("RESTITUIÇÃO †",
                   "O que foi tomado só volta pelas próprias mãos."),
    "mercy": ("MISERICÓRDIA †",
             "Poupe os inocentes. Contenha a mão que atira."),
    "decalogue": ("DECALOGUE †",
                 "Nenhuma curva. Nenhum caos. Apenas a Lei."),
}

WIN_GOALS = {"classic": 1, "rush": len(RUSH_ORDERS[1]),
             "sins": len(RUSH_ORDERS[2]), "waves": 3,
             "decalogo": len(RUSH_ORDERS[4])}

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
        # `game_loop` e setado externamente logo apos a construcao (main_ecs.py/
        # smoke scripts) -- so entao `state`/`cursor`/`world` (properties abaixo)
        # passam a refletir a cena/World reais. `state`/`cursor` NAO sao mais
        # atributos simples: cada cena de menu tem seu proprio `cursor`, e
        # "estado" e derivado de QUAL cena esta no topo da pilha do GameLoop --
        # nunca mais reatribuidos direto (`self.state = X`), de proposito: um
        # site esquecido na migracao quebra alto e cedo (AttributeError), nao
        # silenciosamente.
        self.game_loop = None
        # dificuldade/skill inicial = a única sempre destravada (legado:
        # main.py — estado inicial sel_diff=EASY, sel_skill=NONE)
        self.sel = {"mode": "classic", "diff": "facil", "boss": "classic",
                    "skill": "none", "skill_plus": False,
                    "weapon": "padrao", "weapon_plus": False,
                    "muts": set()}
        self._screen_shake = ScreenShake()  # recriado a cada start_game() -- ver ali
        self._particles = ParticleStorage(capacity=1024)  # idem
        self.intro_t = 0.0
        self.intro_boss = "classic"
        self.run_t = 0.0
        self.end_stats = (0, 0, 0)
        self.totals = {"kills": 0, "deaths": 0, "graze": 0, "runs": 0,
                       "parries": 0}
        self.save = save_data or {}
        # `setdefault` cobre tanto um save novo (sem a chave "settings"
        # ainda) quanto um save ANTIGO que ja tem "settings" mas foi salvo
        # antes deste toggle existir (sem a chave "fullscreen").
        settings = self.save.setdefault(
            "settings", {"screen_shake": True, "show_hitbox": False, "fullscreen": False})
        settings.setdefault("fullscreen", False)
        # NAO reaplicamos "fullscreen" salvo aqui no boot (chegou a ser
        # feito, e foi revertido): alternar o modo de exibicao logo na
        # construcao -- por cima do modo janela que `renderer.initialize()`
        # ja deixou pronto -- e uma segunda troca de modo de tela em
        # sequencia rapida, e um usuario real relatou tela preta ao abrir o
        # jogo com "fullscreen": true salvo (nunca testado em hardware real,
        # so sob o driver SDL dummy, que nao pega falha de troca de modo de
        # verdade). O toggle em SISTEMA continua funcionando -- só não é
        # mais reaplicado automaticamente a cada boot.
        self.replay_frames: list = []   # [(bitmask, dt), ...] da run atual
        self._last_cfg: dict | None = None
        self._replay_input: ReplayInputProvider | None = None
        self.achieved: set = set(self.save.get("achievements", []))
        self.new_achievements: list = []
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
        if self._audio is not None:                  # SFX data-driven (bullethell/data/sfx.json)
            load_audio_bank(self._audio, str(DATA_DIR / "sfx.json"))

    @property
    def world(self):
        """Espelho somente-leitura de `game_loop.world` -- a autoridade e o
        `GameLoop` (via `replace_world`), nao um atributo separado aqui que
        poderia dessincronizar."""
        return self.game_loop.world if self.game_loop is not None else None

    @property
    def state(self) -> int:
        """Deriva o estado antigo (MENU_MAIN, PLAYING, etc.) de QUAL cena
        esta no topo da pilha do GameLoop -- `WizardScene`/`EndScreenScene`
        cobrem mais de um estado antigo cada (7 passos do assistente; WIN
        ou GAMEOVER), entao expõem seu proprio `.step`/`.which` em vez de
        mapear 1:1 por tipo."""
        scene = self.game_loop.current_scene
        if isinstance(scene, WizardScene):
            return scene.step
        if isinstance(scene, EndScreenScene):
            return scene.which
        return _SCENE_STATE.get(type(scene), MENU_MAIN)

    @property
    def cursor(self) -> int:
        """Repasse pro `cursor` proprio da cena atual (cada cena de menu
        tem o seu, em vez de um `self.cursor` compartilhado como antes)."""
        return getattr(self.game_loop.current_scene, "cursor", 0)

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
        self.save["decalogue_rush_cleared"] = True
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
            "decalogue_rush_cleared": False,
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
    # Compatibilidade: `tick(dt)` continua existindo com o mesmo nome/
    # assinatura (smoke scripts chamam assim) -- so repassa pro GameLoop
    # real agora. O antigo dispatch de 15 estados (if/elif em `state`) foi
    # substituido pelas IScenes no fim deste arquivo; dev-mode/overlay
    # cross-cutting viram uma chamada explicita no inicio/fim de cada
    # update()/render() de cena, em vez de um wrapper unico aqui.
    # ------------------------------------------------------------------
    def tick(self, dt: float) -> None:
        self.game_loop.tick_once(dt)

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

    def _mode_locked(self, idx: int) -> bool:
        if MODES[idx][0] == "decalogo":   # desafio final: só pelo SINS RUSH
            return not self.save.get("sins_rush_cleared", False)
        return False

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

    # `_header`/`_menu` (renderizacao+navegacao+transicao fundidas do
    # assistente de nova partida) e as telas MAIN/RECORDS/SETTINGS/ACH e
    # seus `_xxx_confirm` foram MOVIDOS pra `WizardScene`/`MainMenuScene`/
    # `RecordsScene`/`SettingsScene`/`AchievementsScene` (fim deste arquivo)
    # -- todos tocavam `self.state`/`self.cursor` diretamente, que agora sao
    # properties somente-leitura derivadas da pilha de cenas do GameLoop.
    # `_main_items`/`_achievement_progress` ficam aqui (nao tocam state/
    # cursor) -- reaproveitados por `MainMenuScene`/`AchievementsScene`.

    def _main_items(self) -> list:
        """Itens do menu principal — "SEÇÃO DE TESTE" só aparece com o
        cheat (dev_mode) ligado: acesso direto a qualquer boss difícil
        de alcançar normalmente (Mago do Tempo, os 8 pecados, os 10 do
        Decálogo), sem precisar replicar a condição especial de cada um."""
        items = list(MAIN_ITEMS)
        if self.dev_mode:
            items.insert(1, ("test", "SEÇÃO DE TESTE", (255, 60, 200)))
        return items

    def _achievement_progress(self, key: str) -> int:
        """Valor atual do contador de progresso (save persistido + total
        já acumulado nesta sessão, incluindo a run em andamento)."""
        base = int(self.save.get(f"total_{key}", 0))
        return base + int(self.totals.get(key, 0))

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
        if self._mode_locked([m[0] for m in MODES].index(self.sel["mode"])):
            self.sel["mode"] = "classic"
        skill = self.sel["skill"]
        if self.sel["skill_plus"] and self._has_plus(skill, self._data.skills) \
                and self._plus_unlocked("skill", skill):
            skill += "+"
        weapon = self.sel["weapon"]
        if self.sel["weapon_plus"] and self._has_plus(weapon, self._data.weapons) \
                and self._plus_unlocked("weapon", weapon):
            weapon += "+"
        muts = frozenset(self.sel["muts"])
        new_world = build_world(
            self._data, self._input, boss_name=self.sel["boss"],
            weapon_name=weapon, skill_name=skill,
            mutators=muts, mode=self.sel["mode"],
            difficulty=self.sel["diff"], arcade=True)
        # ScreenShake/ParticleStorage sao estado por-run (o antigo clock.shake
        # e a pool "particle" nasciam zerados a cada World novo) -- sem isto,
        # shake/particulas ainda ativos no instante do fim de uma run vazariam
        # pros primeiros frames da PROXIMA.
        self._screen_shake = ScreenShake()
        self._particles = ParticleStorage(capacity=1024)
        mode = self.sel["mode"]
        self.intro_boss = (RUSH_ORDERS[1][0] if mode == "rush" else
                           RUSH_ORDERS[2][0] if mode == "sins" else
                           RUSH_ORDERS[4][0] if mode == "decalogo" else
                           self.sel["boss"])
        self.intro_t = 0.0 if mode == "waves" else 2.4
        self.run_t = 0.0
        self.replay_frames = []           # nova gravação (legado: W — replay)
        self._last_cfg = {"boss": self.sel["boss"], "weapon": weapon,
                          "skill": skill, "muts": muts, "mode": mode,
                          "diff": self.sel["diff"]}
        # reset_scenes (nao push_scene): comeca uma partida e um modo novo
        # inteiro, nao um overlay temporario sobre o que tava rodando --
        # troca o World, e substitui a pilha inteira por so a cena de
        # gameplay (nunca deixa a WizardScene/EndScreenScene/MainMenuScene
        # anteriores empilhadas por baixo, o que cresceria sem limite ao
        # longo de uma sessao com varios retries).
        self.game_loop.replace_world(new_world)
        self.game_loop.reset_scenes(BulletHellGameplayScene(self))

    # ------------------------------------------------------------------
    # replay (legado: ReplayRecorder — ver bullethell/replay.py)
    # ------------------------------------------------------------------
    def _start_replay(self) -> None:
        if not self.replay_frames or self._last_cfg is None:
            return
        cfg = self._last_cfg
        self._replay_input = ReplayInputProvider(list(self.replay_frames))
        new_world = build_world(
            self._data, self._replay_input, boss_name=cfg["boss"],
            weapon_name=cfg["weapon"], skill_name=cfg["skill"],
            mutators=cfg["muts"], mode=cfg["mode"],
            difficulty=cfg["diff"], arcade=True)
        self.run_t = 0.0
        self.intro_t = 0.0                # legado: replay não mostra intro
        self.game_loop.replace_world(new_world)
        self.game_loop.reset_scenes(ReplayScene(self))

    def _replay_end(self, scene: "ReplayScene") -> None:
        """Fim dos frames gravados (ou ESC): WIN se o boss morreu nesse
        ponto, senão GAMEOVER — igual ao legado (main.py:2612-2614). `scene`
        (a `ReplayScene` que acabou de concluir) e quem `EndScreenScene`
        redesenha por baixo do seu overlay."""
        bp = self.world.get_pool("boss")
        dead = (not bp.count) or \
            float(np.sum(bp.active_view()["hp"][: bp.count])) <= 0.0
        which = WIN if dead else GAMEOVER
        self.game_loop.push_scene(EndScreenScene(self, scene, which))

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
        if mode == "decalogo":
            grant("decalogue_rush_win")
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
        if self.sel["mode"] == "decalogo":
            self.save["decalogue_rush_cleared"] = True

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
        """`add_shake()` (game_systems.py) continua escrevendo em clock.shake
        exatamente como antes -- nao muda nenhum dos varios ISystems que a
        chamam. Aqui, o UNICO consumidor, e onde clock.shake vira um evento
        PENDENTE somado (com teto 18.0) ao ScreenShake ja em andamento via
        current_magnitude() (nao um novo trigger que substituiria o shake
        atual). A formula de dx/dy (hash deterministico de run_t, critico
        pra replay byte-a-byte) fica INALTERADA -- so a contabilidade de
        decaimento/teto migrou pro ScreenShake; o offset em si nunca vem do
        retorno de ScreenShake.update() (que decai ANTES de calcular,
        divergindo da ordem leitura-antes-de-decair daqui)."""
        ck = self.world.get_pool("clock")
        if not ck.count:
            return
        cv = ck.active_view()
        pending = float(cv["shake"][0])
        if pending > 0.0:
            new_total = min(self._screen_shake.current_magnitude() + pending, 18.0)
            self._screen_shake.trigger(new_total, new_total / 26.0)
            cv["shake"][0] = 0.0

        amt = self._screen_shake.current_magnitude()
        shake_on = self.save.get("settings", {}).get("screen_shake", True)
        if amt > 0.0 and shake_on:
            j = int(self.run_t * 997)
            dx = (((j * 2654435761) % 200) / 100.0 - 1.0) * amt
            dy = (((j * 40503 + 7) % 200) / 100.0 - 1.0) * amt
            self._r.set_camera_offset(dx, dy)
        else:
            self._r.set_camera_offset(0.0, 0.0)
        self._screen_shake.update(dt)

    def _drain_particle_requests(self, dt: float) -> None:
        """Consome os pedidos de burst gravados por spawn_particles() (pool
        'particle_request' -- mesmo idioma de clock.shake/clock.sfx: varios
        ISystems escrevem um evento cada, este e o UNICO consumidor, uma vez
        por frame) e emite de fato na ParticleStorage compartilhada.

        O angulo/velocidade por particula usa a MESMA formula de hash
        deterministico por (seed, indice) que antes rodava num laco Python
        dentro de spawn_particles() -- aqui, vetorizada sobre `np.arange(n)`
        -- byte-a-byte identica pro mesmo (seed, n), o que importa pra
        replay. A gravidade constante (220 px/s^2) e aplicada aqui porque
        ParticleStorage.update() so integra posicao/decrementa ttl -- nao
        sabe nada de gravidade (generico de proposito, ver seu docstring)."""
        w = self.world
        pr = w.get_pool("particle_request")
        if pr.count:
            view = pr.active_view()
            indices = pr.active_entity_indices()
            pending = pr.count
            for row in range(pending):
                x = float(view["x"][row])
                y = float(view["y"][row])
                n = int(view["n"][row])
                speed = float(view["speed"][row])
                ttl = float(view["ttl"][row])
                seed = int(view["seed"][row])
                color_r = int(view["color_r"][row])
                color_g = int(view["color_g"][row])
                color_b = int(view["color_b"][row])

                j = np.arange(n, dtype=np.int64)
                a = ((seed * 2654435761 + j * 97561) % 6283) / 1000.0
                spd = speed * (0.4 + ((seed * 40503 + j * 131) % 601) / 1000.0)
                position_x = np.full(n, x, dtype=np.float32)
                position_y = np.full(n, y, dtype=np.float32)
                velocity_x = (np.cos(a) * spd).astype(np.float32)
                velocity_y = (np.sin(a) * spd).astype(np.float32)
                ttl_seconds = np.full(n, ttl, dtype=np.float32)
                size = np.full(n, 6.0, dtype=np.float32)  # ~ 8*0.75 (scale antigo) de diametro
                tint_rgba = np.tile(
                    np.array([color_r, color_g, color_b, 255], dtype=np.uint8), (n, 1))
                self._particles.emit_burst(position_x, position_y, velocity_x,
                                          velocity_y, ttl_seconds, size, tint_rgba)

            for index in indices[:pending].tolist():
                w.destroy_entity(w.pack_current(int(index)))

        if self._particles.count:
            self._particles.active_view()["velocity_y"] += 220.0 * dt
        self._particles.update(dt)

    def _render_particles(self) -> None:
        if not self._particles.count:
            return
        view = self._particles.active_view()
        positions_xy = np.stack([view["position_x"], view["position_y"]], axis=1)
        frac = np.clip(view["ttl_seconds"] / np.maximum(view["ttl0_seconds"], 1e-3), 0.0, 1.0)
        tint_rgba = np.stack(
            [view["tint_r"], view["tint_g"], view["tint_b"], (frac * 255).astype(np.uint8)],
            axis=1)
        self._r.draw_particles(positions_xy, view["size"], tint_rgba, self._particles.count)

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
        for name in ("lineage_sol", "lineage_lua"):
            if sid(name) == boss_id:
                return "LINHAGEM †"
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

    # `_end_screen` foi movido pra `EndScreenScene` (fim deste arquivo) --
    # tocava `self.state`/`self.cursor` diretamente.


MODES_SHORT = [("classic", "CLÁSSICO"), ("rush", "BOSS RUSH"),
               ("sins", "SINS RUSH"), ("waves", "WAVES"),
               ("decalogo", "DECÁLOGO RUSH")]


# ---------------------------------------------------------------------------
# IScenes (ROADMAP M8c) -- substituem o dispatch de 15 estados via if/elif
# que `GameApp.tick()` fazia sozinho. `GameApp` continua existindo como
# objeto de SESSAO (save/sel/achieved/totals/replay_frames/etc.) + os
# helpers que nenhuma cena tem motivo pra duplicar (_render_world,
# _apply_shake, _finish_run, ...) -- so quem POSSUI o loop principal e a
# transicao de estado mudou, de `self.state = X` direto pra
# push_scene/pop_scene/reset_scenes do GameLoop real.
# ---------------------------------------------------------------------------

class MainMenuScene(IScene):
    """Tela inicial (JOGAR/CONQUISTAS/REGISTROS/SISTEMA/SAIR + SEÇÃO DE
    TESTE se dev_mode). Base efetiva da pilha -- instalada via
    `game_loop.reset_scenes(...)` no boot e sempre que se volta ao menu."""

    def __init__(self, app: "GameApp") -> None:
        self._app = app
        self.cursor = 0

    def on_enter(self, world, renderer) -> None:
        """Reseta o cursor toda vez que esta cena assume o topo -- fresca
        (reset_scenes no boot) OU revelada de novo por um pop_scene() (voltar
        de CONQUISTAS/REGISTROS/SISTEMA/wizard). Mesmo comportamento de
        antes da migração, onde TODO "back"/reatribuição de estado já
        zerava `self.cursor` no destino (`_menu()`/`_xxx_screen()`) --
        `pop_scene()` sozinho só revela a instância como estava, sem tocar
        seu `cursor`; este hook é quem repõe o reset."""
        self.cursor = 0

    def _items(self) -> list:
        return self._app._main_items()

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        inp = app._input
        items = self._items()
        n = len(items)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("confirm") or inp.is_action_pressed("move_right"):
            app._play("ui_ok", 0.35)
            self._confirm(self.cursor)

    def _confirm(self, k: int) -> None:
        app = self._app
        dest = self._items()[k][0]
        if dest == "play":
            app.game_loop.push_scene(WizardScene(app))
        elif dest == "test":
            app.game_loop.push_scene(WizardScene(app, start_step=MENU_TEST))
        elif dest == "ach":
            app.game_loop.push_scene(AchievementsScene(app))
        elif dest == "records":
            app.game_loop.push_scene(RecordsScene(app))
        elif dest == "settings":
            app.game_loop.push_scene(SettingsScene(app))
        else:
            app.game_loop.stop()

    def render(self, world, renderer) -> None:
        app = self._app
        r = app._r
        cx = SCREEN_W / 2
        r.draw_text(cx, 128, "BULLET HELL", 46, TXT, anchor="center")
        r.draw_text(cx, 168, "OuroborosEngine · port ECS", 15, MUTED,
                    anchor="center")
        items = self._items()
        card_w, ih, gap = 360, 62, 12
        top = 240
        for k, (_, label, col) in enumerate(items):
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
        app._render_dev_overlay()


class WizardScene(IScene):
    """Os 7 passos do assistente de nova partida (MODE->DIFF->BOSS/TEST->
    SKILL->WEAPON->MUT) como UMA cena com um passo interno (`self.step`) --
    decompor em 7 cenas separadas seria mais churn sem benefício real (já
    eram uma única wizard fundida por um helper `_menu()` antes da
    migração; `self.step`/`self.cursor` cobrem o mesmo papel agora)."""

    def __init__(self, app: "GameApp", start_step: int = MENU_MODE) -> None:
        self._app = app
        self.step = start_step
        self.cursor = 0
        self._menu_draw_args = None

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        step = self.step
        if step == MENU_MODE:
            self._menu([m[1] for m in MODES], "MODO DE JOGO",
                       colors=[m[3] for m in MODES],
                       descs=[m[2] for m in MODES],
                       on_confirm=self._mode_confirm, back_to="POP",
                       locked=[app._mode_locked(k) for k in range(len(MODES))])
        elif step == MENU_DIFF:
            self._menu([d[1] for d in DIFFS], "BULLET HELL",
                       colors=[d[3] for d in DIFFS],
                       descs=[d[2] for d in DIFFS],
                       on_confirm=self._diff_confirm, back_to=MENU_MODE,
                       locked=[app._diff_locked(k) for k in range(len(DIFFS))],
                       step=1)
        elif step == MENU_BOSS:
            self._menu([b[1] for b in CLASSIC_BOSSES], "BULLET HELL",
                       colors=[b[2] for b in CLASSIC_BOSSES],
                       descs=[[BOSS_INTROS.get(b[0], ("", ""))[1]]
                             for b in CLASSIC_BOSSES],
                       on_confirm=self._boss_confirm, back_to=MENU_DIFF,
                       locked=[app._boss_locked(b[0]) for b in CLASSIC_BOSSES],
                       step=2, crumb=app._crumb()[:1])
        elif step == MENU_TEST:
            self._menu([b[1] for b in TEST_BOSSES], "SEÇÃO DE TESTE",
                       colors=[b[2] for b in TEST_BOSSES],
                       descs=[[BOSS_INTROS.get(b[0], ("", ""))[1]]
                             for b in TEST_BOSSES],
                       on_confirm=self._test_boss_confirm, back_to="POP")
        elif step == MENU_SKILL:
            items = [n + (" +" if app.sel["skill_plus"] and k == self.cursor
                          and app._has_plus(SKILLS[k][0], app._data.skills)
                          else "") for k, (sk, n, _, _) in enumerate(SKILLS)]
            skill_locked = [app._skill_locked(sk) for (sk, _, _, _) in SKILLS]
            self._menu(items, "BULLET HELL",
                       colors=[s_[3] for s_ in SKILLS],
                       descs=[d for (_, _, d, _) in SKILLS],
                       on_confirm=self._skill_confirm,
                       back_to=MENU_BOSS if app.sel["mode"] == "classic"
                       else MENU_DIFF,
                       hint_extra="ESPAÇO alterna a variante +",
                       locked=skill_locked, step=3,
                       crumb=app._crumb()[:2])
            if app._input.is_action_pressed("fire") and \
                    not skill_locked[self.cursor] and \
                    app._has_plus(SKILLS[self.cursor][0], app._data.skills) \
                    and app._plus_unlocked("skill", SKILLS[self.cursor][0]):
                app.sel["skill_plus"] = not app.sel["skill_plus"]
        elif step == MENU_WEAPON:
            items = [n + (" +" if app.sel["weapon_plus"] and k == self.cursor
                          and app._has_plus(WEAPONS[k][0], app._data.weapons)
                          else "") for k, (w, n, _, _) in enumerate(WEAPONS)]
            self._menu(items, "BULLET HELL",
                       colors=[w_[3] for w_ in WEAPONS],
                       descs=[d for (_, _, d, _) in WEAPONS],
                       on_confirm=self._weapon_confirm, back_to=MENU_SKILL,
                       hint_extra="ESPAÇO alterna a variante +",
                       step=4, crumb=app._crumb()[:3])
            if app._input.is_action_pressed("fire") and \
                    app._has_plus(WEAPONS[self.cursor][0], app._data.weapons) \
                    and app._plus_unlocked("weapon", WEAPONS[self.cursor][0]):
                app.sel["weapon_plus"] = not app.sel["weapon_plus"]
        elif step == MENU_MUT:
            items = [(("[x] " if m in app.sel["muts"] else "[ ] ") + n)
                     for (m, n, _, _) in MUTATORS] + ["► COMEÇAR"]
            self._menu(items, "BULLET HELL",
                       colors=[m_[3] for m_ in MUTATORS] + [GOLD[:3]],
                       descs=[d for (_, _, d, _) in MUTATORS] + [
                           ("Cada mutador ativo aumenta o desafio",)],
                       on_confirm=self._mut_confirm, back_to=MENU_WEAPON,
                       locked=[app._mutator_locked(m)
                              for (m, _, _, _) in MUTATORS] + [False],
                       step=5, crumb=app._crumb()[:4])

    def render(self, world, renderer) -> None:
        """`update()` roda ANTES de `begin_frame()` no SceneStack (ver
        `GameLoop._render_frame`) -- desenhar de lá seria apagado antes do
        frame ser apresentado. `_menu()` (chamada só de `update()`) por
        isso só cuida de input/estado e guarda os argumentos de desenho em
        `self._menu_draw_args`; aqui é onde o card/painel de fato aparece
        na tela (bug real corrigido: a wizard inteira -- MODE/DIFF/BOSS/
        TEST/SKILL/WEAPON/MUT -- ficava com a navegação funcionando mas
        nada desenhado, "tela preta com botões invisíveis")."""
        if self._menu_draw_args is not None:
            self._menu_draw(*self._menu_draw_args)
        self._app._render_dev_overlay()

    # -- transições internas (equivalentes aos antigos `_xxx_confirm`) --

    def _mode_confirm(self, k: int) -> None:
        app = self._app
        if app._mode_locked(k):
            return
        app.sel["mode"] = MODES[k][0]
        self.step, self.cursor = MENU_DIFF, 1

    def _diff_confirm(self, k: int) -> None:
        app = self._app
        if app._diff_locked(k):
            return
        app.sel["diff"] = DIFFS[k][0]
        self.step = MENU_BOSS if app.sel["mode"] == "classic" else MENU_SKILL
        self.cursor = 0

    def _boss_confirm(self, k: int) -> None:
        app = self._app
        if app._boss_locked(CLASSIC_BOSSES[k][0]):
            return
        app.sel["boss"] = CLASSIC_BOSSES[k][0]
        self.step, self.cursor = MENU_SKILL, 0

    def _test_boss_confirm(self, k: int) -> None:
        """Seção de teste (dev_mode): joga o boss escolhido como uma
        partida CLÁSSICA avulsa — nenhum boss aqui fica travado, é acesso
        direto pra testar sem replicar a condição especial."""
        app = self._app
        app.sel["mode"] = "classic"
        app.sel["boss"] = TEST_BOSSES[k][0]
        self.step, self.cursor = MENU_SKILL, 0

    def _skill_confirm(self, k: int) -> None:
        app = self._app
        if app._skill_locked(SKILLS[k][0]):
            return
        app.sel["skill"] = SKILLS[k][0]
        app.sel["skill_plus"] = False    # nova skill: reseta o toggle +
        self.step, self.cursor = MENU_WEAPON, 0

    def _weapon_confirm(self, k: int) -> None:
        app = self._app
        app.sel["weapon"] = WEAPONS[k][0]
        app.sel["weapon_plus"] = False    # nova arma: reseta o toggle +
        self.step, self.cursor = MENU_MUT, 0

    def _mut_confirm(self, k: int) -> None:
        app = self._app
        if k < len(MUTATORS):
            m = MUTATORS[k][0]
            if app._mutator_locked(m):
                return
            if m in app.sel["muts"]:
                app.sel["muts"].discard(m)
            else:
                app.sel["muts"].add(m)
        else:
            app.start_game()   # start_game() ja faz replace_world+reset_scenes

    # -- equivalentes a `GameApp._menu()`/`_header()` de antes da migração,
    # usando `self.cursor`/`self.step` em vez de `app.cursor`/`app.state` --

    def _menu(self, items, title, colors=None, descs=None, on_confirm=None,
              back_to=None, hint_extra="", locked=None, step=0,
              crumb=()) -> None:
        """Só input/estado (cursor, back, confirm) -- chamada de `update()`.
        O desenho em si (card colorido à esquerda + painel de descrição à
        direita) fica em `_menu_draw()`, chamada de `render()` com os
        argumentos guardados em `self._menu_draw_args` -- ver o porquê da
        separação no docstring de `render()`.
        `back_to`: um passo interno (int) pra voltar, ou o sentinela "POP"
        pra sair da wizard inteira (`pop_scene()` de volta ao MainMenuScene
        que a empilhou -- MODE e TEST são os únicos passos "de entrada")."""
        app = self._app
        inp = app._input
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
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            for _ in range(n):
                self.cursor = (self.cursor + 1) % n
                if not locked[self.cursor]:
                    break
            app._play("ui_move", 0.25)
        if back_to is not None and (inp.is_action_pressed("back")
                                    or inp.is_action_pressed("move_left")):
            self._menu_draw_args = None
            if back_to == "POP":
                app.game_loop.pop_scene()
            else:
                self.step, self.cursor = back_to, 0
            return
        if on_confirm and not locked[self.cursor] and (
                inp.is_action_pressed("confirm")
                or inp.is_action_pressed("move_right")):
            app._play("ui_ok", 0.35)
            self._menu_draw_args = None
            on_confirm(self.cursor)
            return
        self.cursor = min(self.cursor, n - 1)
        self._menu_draw_args = (items, title, colors, descs, hint_extra,
                                 locked, step, crumb)

    def _menu_draw(self, items, title, colors, descs, hint_extra, locked,
                   step, crumb) -> None:
        app = self._app
        self._header(title, step, crumb)
        r = app._r
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

    def _header(self, title: str, step: int = 0, crumb: tuple = ()) -> None:
        r = self._app._r
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


class AchievementsScene(IScene):
    def __init__(self, app: "GameApp") -> None:
        self._app = app
        self.cursor = 0

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        inp = app._input
        n = len(ACHIEVEMENTS)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("back") or inp.is_action_pressed("move_left"):
            app.game_loop.pop_scene()
            return
        self.cursor = min(self.cursor, n - 1)

    def render(self, world, renderer) -> None:
        app = self._app
        r = app._r
        r.draw_text(SCREEN_W / 2, 56, "CONQUISTAS", 40, GOLD, anchor="center")
        n = len(ACHIEVEMENTS)
        done = sum(1 for a in ACHIEVEMENTS if a[0] in app.achieved)
        r.draw_text(SCREEN_W / 2, 100, f"{done} / {n} desbloqueadas",
                    16, MUTED, anchor="center")

        top, bottom, ih, gap = 140, 560, 26, 2
        row_h = ih + gap
        center_y = top + ((bottom - top) - ih) / 2
        for k, (aid, name, desc, reward, secret, progress) in enumerate(ACHIEVEMENTS):
            y = center_y + (k - self.cursor) * row_h
            if y + ih < top or y > bottom:
                continue
            got = aid in app.achieved
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
        got = aid in app.achieved
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
            cur = min(progress[1], app._achievement_progress(progress[0]))
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
        app._render_dev_overlay()


class RecordsScene(IScene):
    def __init__(self, app: "GameApp") -> None:
        self._app = app
        self.cursor = 0

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        inp = app._input
        if inp.is_action_pressed("back") or inp.is_action_pressed("confirm") \
                or inp.is_action_pressed("move_left"):
            app.game_loop.pop_scene()

    def render(self, world, renderer) -> None:
        app = self._app
        r = app._r
        cx = SCREEN_W / 2
        r.draw_text(cx, 80, "REGISTROS", 40, GOLD, anchor="center")
        r.draw_ui_rect(180, 162, SCREEN_W - 360, 1, (50, 50, 20, 255))
        total_deaths = int(app.save.get("total_deaths", 0)) + app.totals["deaths"]
        total_parries = int(app.save.get("total_parries", 0)) + app.totals["parries"]
        best = float(app.save.get("best_time_dificil", 0.0))
        bm, bs = divmod(int(best), 60)
        hcd = int(app.save.get("highest_cleared_diff", 0))
        diff_label = DIFFS[min(hcd, len(DIFFS) - 1)][1] if hcd > 0 else "NENHUMA"
        unlocked_skills = [s[1] for s in SKILLS if s[0] in
                          app.save.get("unlocked_skills", ["none", "dash"])]
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
        app._render_dev_overlay()


class SettingsScene(IScene):
    _DEFAULTS = {"screen_shake": True, "show_hitbox": False, "fullscreen": False}
    _ITEMS = [("screen_shake", "Screen Shake"), ("show_hitbox", "Mostrar Hitbox"),
              ("fullscreen", "Tela Cheia")]

    def __init__(self, app: "GameApp") -> None:
        self._app = app
        self.cursor = 0

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        inp = app._input
        settings = app.save.setdefault("settings", dict(self._DEFAULTS))
        n = len(self._ITEMS)
        if inp.is_action_pressed("move_up"):
            self.cursor = (self.cursor - 1) % n
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("move_down"):
            self.cursor = (self.cursor + 1) % n
            app._play("ui_move", 0.25)
        if inp.is_action_pressed("confirm") or inp.is_action_pressed("fire"):
            key = self._ITEMS[self.cursor][0]
            settings[key] = not settings.get(key, self._DEFAULTS[key])
            if key == "fullscreen":
                app._r.set_fullscreen(settings[key])
            app._play("ui_ok", 0.3)
        if inp.is_action_pressed("back") or inp.is_action_pressed("move_left"):
            app.game_loop.pop_scene()

    def render(self, world, renderer) -> None:
        app = self._app
        r = app._r
        settings = app.save.setdefault("settings", dict(self._DEFAULTS))
        cx = SCREEN_W / 2
        r.draw_text(cx, 80, "SISTEMA", 40, (100, 160, 255, 255),
                    anchor="center")
        r.draw_ui_rect(180, 162, SCREEN_W - 360, 1, (30, 50, 80, 255))
        top, ih, gap = 210, 70, 12
        for k, (key, label) in enumerate(self._ITEMS):
            y = top + k * (ih + gap)
            sel = k == self.cursor
            on = bool(settings.get(key, self._DEFAULTS[key]))
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
        app._render_dev_overlay()


class BulletHellGameplayScene(IScene):
    """Substitui a `GameplayScene` genérica da engine pra este produto --
    reaproveita os helpers já existentes de `GameApp` (`_pump_sfx`,
    `_apply_shake`, `_drain_particle_requests`, `_render_*`, `_finish_run`)
    em vez de duplicar seus corpos; só a TRANSIÇÃO de estado (abandono,
    vitória/derrota) muda de `self.state = X` pra push/reset de cena."""

    def __init__(self, app: "GameApp") -> None:
        self._app = app

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        app.replay_frames.append((encode_frame(app._input), delta_time))
        app.run_t += delta_time
        if app.godmode:                          # F6 (dev mode)
            pl = world.get_pool("player")
            pi = pl.active_entity_indices()
            if pi.size:
                pl.active_view()["invuln_t"][pl.dense_row_of(int(pi[0]))] = 999.0
        world.step(delta_time)
        app._pump_sfx()
        app._apply_shake(delta_time)
        app._drain_particle_requests(delta_time)
        if app.intro_t > 0.0:
            app.intro_t -= delta_time

        if app._input.is_action_pressed("back"):   # ESC abandona a run
            app._finish_run("abandon")
            app.game_loop.reset_scenes(MainMenuScene(app))
            return
        pl = world.get_pool("player")
        if pl.count and int(pl.active_view()["lives"][0]) < 0:
            app._finish_run("lose")
            app.game_loop.push_scene(EndScreenScene(app, self, GAMEOVER))
            return
        kills = int(world.get_pool("stats").active_view()["kills"][0])
        if kills >= WIN_GOALS[app.sel["mode"]]:
            app._finish_run("win")
            app.game_loop.push_scene(EndScreenScene(app, self, WIN))

    def render_frozen(self, world, renderer) -> None:
        """Conteudo visual sem o overlay de dev-mode -- usado por
        `EndScreenScene` pra redesenhar esta cena por baixo do seu proprio
        overlay SEM desenhar o overlay de dev duas vezes (ele mesmo chama
        `_render_dev_overlay()` por cima de tudo, no final)."""
        app = self._app
        app._render_world()
        app._render_particles()
        app._render_hud()
        if app.intro_t > 0.0:
            app._render_intro()

    def render(self, world, renderer) -> None:
        self.render_frozen(world, renderer)
        self._app._render_dev_overlay()


class ReplayScene(IScene):
    """Mirror de `BulletHellGameplayScene`, dirigida por `ReplayInputProvider`
    em vez do input real -- reproduz `app.replay_frames` gravados na run
    anterior."""

    def __init__(self, app: "GameApp") -> None:
        self._app = app

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        ri = app._replay_input
        ri.poll()
        if not ri.has_more():
            app._replay_end(self)
            return
        dt = ri.current_dt()
        app.run_t += dt
        world.step(dt)
        app._pump_sfx()
        app._apply_shake(dt)
        app._drain_particle_requests(dt)
        if app._input.is_action_pressed("back"):   # ESC sai do replay
            app._replay_end(self)

    def render_frozen(self, world, renderer) -> None:
        app = self._app
        app._render_world()
        app._render_particles()
        app._render_hud()
        app._render_replay_tag()

    def render(self, world, renderer) -> None:
        self.render_frozen(world, renderer)
        self._app._render_dev_overlay()


class EndScreenScene(IScene):
    """Tela de fim de jogo (VITÓRIA/GAME OVER). Guarda a cena de gameplay
    (`BulletHellGameplayScene` ou `ReplayScene`) de baixo e redesenha ela
    POR INTEIRO (mundo+partículas+HUD, não só o mundo como antes da
    migração -- mesmo padrão de `PauseScene`/`EndScene` já estabelecido na
    engine, que sempre redesenham a cena base inteira congelada)."""

    def __init__(self, app: "GameApp", beneath, which: int) -> None:
        self._app = app
        self._beneath = beneath
        self.which = which

    def update(self, world, delta_time: float) -> None:
        app = self._app
        app._update_dev_mode(delta_time)
        inp = app._input
        if inp.is_action_pressed("retry"):
            app.start_game()
        elif bool(app.replay_frames) and inp.is_action_pressed("move_up"):
            app._start_replay()
        elif inp.is_action_pressed("to_menu") or inp.is_action_pressed("back"):
            app.game_loop.reset_scenes(MainMenuScene(app))

    def render(self, world, renderer) -> None:
        app = self._app
        self._beneath.render_frozen(world, renderer)
        r = app._r
        r.draw_ui_rect(0, 0, SCREEN_W, SCREEN_H, (8, 8, 14, 190))
        kills, deaths, graze = app.end_stats
        if self.which == WIN:
            r.draw_text(SCREEN_W / 2, 220, "VITÓRIA", 56, GOLD, anchor="center")
        else:
            r.draw_text(SCREEN_W / 2, 220, "GAME OVER", 56, RED, anchor="center")
        r.draw_text(SCREEN_W / 2, 320,
                    f"bosses: {kills}   ·   grazes: {graze}   ·   "
                    f"tempo: {app.run_t:.0f}s", 20, TXT, anchor="center")
        for k, name in enumerate(app.new_achievements[:4]):
            r.draw_text(SCREEN_W / 2, 370 + k * 28,
                        f"* NOVA CONQUISTA: {name}", 17, GOLD, anchor="center")
        has_replay = bool(app.replay_frames)
        hint = "T  jogar de novo      R  menu"
        if has_replay:
            hint = "T  jogar de novo      W  ver replay      R  menu"
        r.draw_text(SCREEN_W / 2, 500, hint, 18, MUTED, anchor="center")
        app._render_dev_overlay()


# Estado antigo (int, `range(15)`) derivado do TIPO da cena atual --
# `GameApp.state` (property) usa isto, exceto pra WizardScene/EndScreenScene
# (cobrem mais de um estado antigo cada, ver seus `.step`/`.which`).
_SCENE_STATE = {
    MainMenuScene: MENU_MAIN,
    AchievementsScene: MENU_ACH,
    RecordsScene: MENU_RECORDS,
    SettingsScene: MENU_SETTINGS,
    BulletHellGameplayScene: PLAYING,
    ReplayScene: REPLAYING,
}
