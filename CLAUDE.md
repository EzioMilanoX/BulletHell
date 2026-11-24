# CLAUDE.md — BulletHell

Guia para o Claude Code neste projeto. Idioma: PT-BR.

## O que é
Bullet hell sobre a **OuroborosEngine** (repo irmão `../OuroborosEngine`): balas são
entidades ECS em pools SoA de NumPy, milhares a 60 FPS. Foi a prova de carga da engine
(blueprint SYS-10). Desde a v2.0.0 só existe o port ECS; o jogo legado (`main.py`/
`entities.py`) está na tag `legacy-final` — as referências `main.py:NNN` nos comentários
apontam para ela, não para um arquivo atual.

## Rodar / testar
```bash
pip install -r requirements.txt
python main_ecs.py                 # ponto de entrada (ou run.bat); --play --boss X pula o menu
pytest                             # headless, ~20 s
ruff check .                       # só pyflakes ("F"), ver ruff.toml
```
A engine entra no `sys.path` sozinha (`bullethell/__init__.py`) a partir do repo irmão. O CI
e o build do `.exe` usam o wheel versionado em `wheels/` (commit em `wheels/ENGINE_COMMIT.txt`):
se o jogo passar a usar algo novo da engine, rebuild com `tools/build_engine_wheel.ps1`
depois do commit da engine, e commite o wheel.

## Mapa
- `main_ecs.py` — argumentos, save (`save_ecs.json` ao lado do exe, atômico pelo `SaveFile`),
  boot (GameLoop + SceneStack).
- `bullethell/composition.py` — monta o World (pools, arquétipos, sistemas).
- `bullethell/game_systems.py` — os `ISystem` do jogo, vetorizados.
- `bullethell/scenes.py` — menus, gameplay, fim de run, **replay** (`REPLAY_ACTIONS`,
  `REPLAY_HASH_POOLS`), dev mode.
- `bullethell/data/*.json` — bosses, padrões, armas, skills, ondas, sfx, input.
- `docs.html` — documentação de mecânicas (abrir no navegador).

## Replay
Gravação e reprodução são da engine (`ouroboros.bootstrap.replay`). O jogo grava os bits de
`REPLAY_ACTIONS` + dt por quadro (`GameApp.replay`, um `ReplayRecorder`) e confere o hash
de `REPLAY_HASH_POOLS` a cada 60 quadros. Regras para não quebrar replays:
- **Nada de RNG global nem relógio real nos sistemas**: toda "aleatoriedade" é hash
  determinístico por contador (é por isso que a semente gravada é 0).
- `REPLAY_ACTIONS`: só acrescentar no fim (a ordem é o formato).
- Ação nova lida no gameplay precisa entrar em `REPLAY_ACTIONS`, senão o replay não a vê.
- Estado mudado fora do input (godmode, cheats) dessincroniza — e o replay avisa.

## Regras de trabalho
- Mudança de comportamento compartilhado (render, input, áudio, replay, save) começa na
  engine; depois rode `../OuroborosEngine/tools/testar_jogos.ps1`.
- Versão em `bullethell/__init__.py`; o CHANGELOG tem seção `## vX.Y.Z` por release
  (`release.yml` confere) e "Ainda sem versão" para o que entrou depois.
- Só commitar/push quando o Enzo pedir.
