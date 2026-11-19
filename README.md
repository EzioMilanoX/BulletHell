# BULLET HELL

Bullet hell em Python/pygame-ce sobre a
[OuroborosEngine](https://github.com/EzioMilanoX/OuroborosEngine) — ECS
orientado a dados (pools SoA em NumPy, pré-alocadas, **zero alocação
dinâmica durante o game loop**): balas são entidades de verdade, milhares
simultâneas a 60 FPS.

Até a v1.0.0 o repositório trazia dois jogos: o **legado** (`main.py`/
`entities.py`, Python/pygame-ce puro) e o **port ECS**. A partir da
**v2.0.0** só o ECS existe — o legado foi aposentado depois de o port
alcançar a paridade (ver `bullethell/PARITY_PLAN.md`/
`bullethell/MIGRATION.md`). O último estado do legado continua acessível
pela tag **`legacy-final`** (`git checkout legacy-final`); as referências
`main.py:NNN`/`entities.py:NNN` nos comentários do código apontam pra ela.

## Baixar e jogar (sem instalar Python)

Ver [INSTALL.md](INSTALL.md) — um `.exe` standalone na
[página de Releases](https://github.com/EzioMilanoX/BulletHell/releases).
O que mudou em cada versão: [CHANGELOG.md](CHANGELOG.md).

## Requisitos (rodando do código-fonte)

- Python 3.12+ (desenvolvido em 3.14)
- pygame-ce e numpy (ver `requirements.txt`)
- a OuroborosEngine: o repo-irmão `../OuroborosEngine` (entra no
  `sys.path` sozinho, ver `bullethell/__init__.py`) **ou** o wheel
  versionado — `pip install wheels/ouroboros_engine-*.whl`

## Como rodar

```bash
pip install -r requirements.txt
python main_ecs.py                     # menu completo
python main_ecs.py --play --boss decalogue --weapon spread+   # atalho direto pra partida
```

No Windows também dá para usar o `run.bat` (repassa os argumentos).

## Controles

| Tecla | Ação |
|---|---|
| `WASD` | mover |
| `ESPAÇO` | atirar (segurar/soltar tem mecânicas por arma) |
| `SHIFT` | habilidade equipada |
| `1`–`0` | trocar de arma durante a partida |
| `W/S` + `D`/`ENTER` | navegar / confirmar nos menus |
| `A` / `ESC` | voltar |
| `T` / `R` | jogar de novo / voltar ao menu, no fim da run |
| `ESPAÇO` (nos menus de skill/arma) | alternar variante **+** (se desbloqueada) |

## Conteúdo

- **5 modos de jogo** — Clássico, Boss Rush, SINS Rush, Wave Survival e
  **Decálogo Rush**
- **Bosses** — Clássico, Enxame, Paredão, Mago do Tempo, Gêmeos,
  Invocador, Ômega ★ (secreto), os 8 bosses SINS e o **Decálogo** (10
  bosses temáticos dos Mandamentos + 1 final)
- **10 armas** e **8 habilidades**, com variantes evoluídas (**+**)
  desbloqueáveis por maestria
- **5 dificuldades** (Fácil → Abissal), com DDA, Segundo Fôlego e
  Fragmentação nas mais altas
- **Mutadores** de run (Predador, Fantasma, Canhão de Vidro,
  Claustrofobia, Horda, Berserker)
- **Conquistas, registros e progressão** persistentes (`save_ecs.json`,
  criado na primeira execução), **replay** da última run
- **Dev mode** (sequência secreta) — cheats e a "SEÇÃO DE TESTE" no menu
  principal, com acesso direto a qualquer boss difícil de alcançar

A documentação completa de mecânicas e balanceamento está em
[`docs.html`](docs.html) — abra no navegador.

## Estrutura

```
main_ecs.py        # entrada: argumentos, save, boot (GameLoop + SceneStack)
bullethell/        # o jogo (ver bullethell/MIGRATION.md)
  scenes.py        #   menus, gameplay, fim de run, replay (IScenes)
  game_systems.py  #   os ISystem do jogo (vetorizados)
  composition.py   #   monta o World (pools, arquétipos, sistemas)
  data/*.json      #   bosses, padrões, armas, skills, ondas, sfx, input
tests/             # suíte pytest headless (ver tests/conftest.py)
packaging/         # spec do PyInstaller (ver INSTALL.md)
tools/             # scripts de build do .exe e do wheel da engine
wheels/            # wheel versionado da OuroborosEngine (CI/build)
```

## Testes e lint

```bash
pytest              # headless (SDL "dummy"), ~20s
ruff check .
```

O CI (`.github/workflows/ci.yml`) roda os dois em todo push/PR pra
`main`; empurrar uma tag `vX.Y.Z` roda `release.yml` (testes + build do
`.exe` + Release no GitHub).
