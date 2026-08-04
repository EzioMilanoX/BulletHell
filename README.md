# BULLET HELL

Engine de bullet hell escrita do zero em Python/pygame-ce, com arquitetura
**Data-Oriented Design (DOD/SoA)**: todos os projéteis vivem em arrays NumPy
paralelos, com pools pré-alocados e **zero alocação dinâmica durante o game
loop** — 5000+ balas simultâneas a 60 FPS.

Duas versões no mesmo repositório: o jogo **legado** (`main.py`, Python/
pygame-ce puro) e o port **ECS** (`bullethell/`, sobre a
[OuroborosEngine](https://github.com/EzioMilanoX/OuroborosEngine)) — ver
`bullethell/PARITY_PLAN.md`/`bullethell/MIGRATION.md` pro histórico da
migração.

## Baixar e jogar (sem instalar Python)

Ver [INSTALL.md](INSTALL.md) — dois `.exe` standalone na
[página de Releases](https://github.com/EzioMilanoX/BulletHell/releases).

## Requisitos (rodando do código-fonte)

- Python 3.12+ (desenvolvido em 3.14)
- pygame-ce e numpy (ver `requirements.txt`)

## Como rodar

```bash
pip install -r requirements.txt
python main.py          # legado
python main_ecs.py       # port ECS — precisa também do repo-irmão OuroborosEngine
```

No Windows também dá para usar o `run.bat` (legado).

## Controles

| Tecla | Ação |
|---|---|
| `WASD` | mover |
| `ESPAÇO` / `Z` | atirar (segurar/soltar tem mecânicas por arma) |
| `SHIFT` | habilidade equipada |
| `W/S` + `D`/`ENTER` | navegar / confirmar nos menus |
| `A` / `ESC` | voltar |
| `T` | retry rápido após derrota |
| `ESPAÇO` (nos menus de skill/arma) | alternar variante **+** (se desbloqueada) |

## Conteúdo

- **3 modos de jogo** — Clássico, Boss Rush e Wave Survival
- **Bosses** — Clássico, Enxame, Paredão, Mago do Tempo, Gêmeos, Invocador,
  Ômega ★ (secreto) e os bosses SINS
- **10 armas**, cada uma com variante evoluída (**Arma+**) desbloqueável por maestria
- **8 habilidades**, cada uma com variante **Habilidade+**
- **Mutadores** de run (Predador, Fantasma, Canhão de Vidro, Claustrofobia…)
- **Conquistas e progressão** persistentes (`save.json`, criado na primeira execução)

A documentação completa de mecânicas, arquitetura e balanceamento está em
[`docs.html`](docs.html) — abra no navegador.

## Estrutura

```
main.py            # legado — loop de jogo, render e menus
entities.py        # legado — constantes, pools SoA, bosses, colisão, save
waves.json         # legado — composição das ondas do Wave Survival
patterns.json      # legado — padrões de tiro data-driven
balance.json       # legado — overrides de balanceamento
tests/             # suíte pytest do legado (FSM de bosses, pools, gameplay)
src/               # referência em C++ (estudo; não é compilada nem usada)

main_ecs.py        # port ECS — entrada
bullethell/        # port ECS — pacote (ver bullethell/MIGRATION.md)
smoke_*.py         # port ECS — smoke tests headless (ver cada bullethell/*.md)

packaging/         # specs do PyInstaller pros dois .exe (ver INSTALL.md)
tools/             # scripts de build dos .exe
wheels/            # wheel versionado da OuroborosEngine (build, não dev)
```

## Testes

```bash
pytest
```

## Arquitetura (resumo)

- **SoA + pools com free-list** — `BulletPool`, `PlayerBulletPool`, `LaserPool`,
  `HazardPool`, `EnemyPool`, `ParticlePool`, todos pré-alocados
- **Spatial hash** para colisão bala×jogador (nada de O(N²))
- **Separação estrita update/render** por frame
- **I/O de arquivo proibido durante gameplay** — save só em menu/vitória/derrota
