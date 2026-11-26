# Changelog

O que mudou em cada versão, do ponto de vista de quem joga. Detalhes
técnicos de cada fase ficam em `bullethell/MIGRATION.md`.

## v2.1.0 (2026-11-26)

- **Replay mais confiável:** o "W — ver replay" do fim da run agora usa o
  replay da OuroborosEngine e confere, uma vez por segundo, se a partida
  reproduzida é mesmo a que você jogou. Se não for (por exemplo, com uma
  trapaça do dev mode ligada durante a run), o canto da tela mostra
  **REPLAY (DESSINCRONIZOU)** em vez de fingir que está tudo certo.
- A documentação (`docs.html`) não aponta mais para o jogo antigo: as gemas
  do SATÉLITE e os mísseis em espera do TELEGUIADO+ são posicionados pelo
  `OrbitSystem`, e o cabeçalho mostra a v2.0 (o jogo abre por `main_ecs.py`).
- Para quem compila: o replay depende de um módulo novo da engine
  (`ouroboros.bootstrap.replay`). O wheel em `wheels/` (engine 0.3.0, commit
  05ad40a) ainda não o tem — depois de commitar a engine, rode
  `tools/build_engine_wheel.ps1` e commite o wheel novo, senão o CI e o
  build do `.exe` quebram no import.

## v2.0.0

**Um jogo só, e onze bosses novos.**

### Um jogo só: `BulletHell.exe`

- A v1 trazia dois jogos lado a lado (o Legado e o ECS). A partir desta
  versão existe só o jogo sobre a OuroborosEngine — o mais completo dos
  dois — e o executável passa a se chamar simplesmente `BulletHell.exe`.
- **Seu progresso continua:** extraia o novo `.exe` na mesma pasta do
  `BulletHellECS.exe` antigo e ele lê o mesmo `save_ecs.json`. O save do
  Legado (`save.json`) não é importado.

### Novo: o Decálogo

Dez bosses inspirados nos Mandamentos, mais um chefe final — o
contraponto dos 7 Pecados, cada um com uma regra própria pra aprender:

- **MONÓLITO** — quatro pilares-isca que revidam quando atingidos.
- **ÍDOLO** — só um dos clones é o verdadeiro; acertar os falsos custa caro.
- **REVERÊNCIA** — trava sua habilidade e, depois, silencia sua arma.
- **SABBATH** — nas janelas de descanso, mover ou atirar tira vida.
- **LINHAGEM** — dois bosses ligados: deixar um muito mais ferido que o
  outro enfurece o mais forte.
- **MISERICÓRDIA** — Inocentes que não devem morrer, um mártir que não
  pode ser ferido e minas que punem quem as usa contra ele.
- **PUREZA** — zonas de cor: a bala da cor errada no lado errado dói em
  dobro; no fim, um anel que encolhe e puxa você pro centro.
- **RESTITUIÇÃO** — confisca sua velocidade e cadência; recupere-as
  coletando os orbes antes que as balas os afastem.
- **VERDADE** — a maior parte da espiral é ilusão; chegar perto revela o
  que é real.
- **ABNEGAÇÃO** — anéis que ganham gravidade quando cercam o vazio e
  corações falsos que congelam quem os pega.
- **DECALOGUE** — o final: grade de lasers, tábuas que empilham bolas, um
  pilar que mira em você e a "morte da diagonal" (só um eixo de cada vez).

E com eles:

- **Modo DECÁLOGO RUSH** — os 11 em sequência, na ordem dos Mandamentos.
  Destrava ao vencer o SINS RUSH; vencê-lo dá a conquista **O JUÍZO**.
- **SEÇÃO DE TESTE** — com o dev mode ligado (sequência secreta), um
  botão novo no menu principal leva direto a qualquer boss difícil de
  alcançar: Mago do Tempo, os 8 Pecados e todo o Decálogo.

### Menus, tela e som

- Os menus foram reconstruídos sobre a pilha de cenas da engine: voltar,
  sair, jogar de novo e ver o replay ficam consistentes entre todas as
  telas.
- **Tela Cheia** no menu SISTEMA — e agora o jogo lembra a escolha ao
  abrir de novo. (Se a tela cheia der problema no seu monitor, troque
  `"fullscreen": true` por `false` no `save_ecs.json`.)
- Partículas, tremor de tela e efeitos sonoros passam a vir da engine,
  com o mesmo comportamento de antes (o replay continua idêntico).
- O nome da versão aparece no título da janela.

### Correções

- **MISERICÓRDIA** não é mais empurrada pra fora da tela por tiros
  seguidos — vale pra qualquer boss, que agora sempre fica dentro da arena.
- O pilar do **Olho do Juiz** (DECALOGUE) avisa antes de disparar; antes
  acertava no mesmo instante em que aparecia, sem chance de desviar.
- O puxão final da **PUREZA** era mais rápido que o próprio jogador;
  agora dá pra resistir correndo pro lado oposto.
- Nos modos Rush, orbes, Inocentes, minas e névoas do boss derrotado não
  sobrevivem mais pro boss seguinte (no SINS RUSH, as minas da Avareza
  podiam sobrar até a luta da Luxúria).

### Save mais seguro

- O save é gravado de forma atômica: fechar o jogo, cair a energia ou
  encher o disco no meio da gravação não deixa mais um arquivo pela
  metade — fica o save anterior, intacto.
- A cada gravação, a versão anterior fica em `save_ecs.json.bak`, e o
  jogo recupera dela sozinho se o principal estiver ilegível.
- Se o jogo fechar com um erro, os detalhes ficam em `crash.log` na pasta
  do `.exe` — anexe esse arquivo ao reportar um bug.

## v1.0.0

Primeira versão publicada: o jogo Legado e o port ECS lado a lado, cada
um como um `.exe` standalone.
