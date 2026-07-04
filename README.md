# BULLET HELL

Engine de bullet hell escrita do zero em Python/pygame-ce, com arquitetura
**Data-Oriented Design (DOD/SoA)**: todos os projéteis vivem em arrays NumPy
paralelos, com pools pré-alocados e **zero alocação dinâmica durante o game
loop** — 5000+ balas simultâneas a 60 FPS.

## Requisitos

- Python 3.12+ (desenvolvido em 3.14)
- pygame-ce e numpy (ver `requirements.txt`)

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

No Windows também dá para usar o `run.bat`.

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
main.py         # loop de jogo, render e menus
entities.py     # constantes, pools SoA, bosses, colisão, save
waves.json      # composição das ondas do Wave Survival
patterns.json   # padrões de tiro data-driven
balance.json    # overrides de balanceamento
tests/          # suíte pytest (FSM de bosses, pools, gameplay)
src/            # referência em C++ (estudo; não é compilada nem usada)
ouroboros/      # rascunho da migração para ECS (em andamento)
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
