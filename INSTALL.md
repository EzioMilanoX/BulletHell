# Instalar e jogar

Duas versões, dois `.exe` — nenhuma exige Python instalado.

| | **Legado** | **ECS** |
|---|---|---|
| Arquivo | `BulletHellLegado.exe` | `BulletHellECS.exe` |
| Motor | Python/pygame-ce puro (`main.py`) | Port sobre a [OuroborosEngine](https://github.com/EzioMilanoX/OuroborosEngine) (ECS/DOD) |
| Conteúdo | Jogo original | Mesmo jogo + dev overlay, replay, masteries, DDA (ver `bullethell/PARITY_PLAN.md`) |
| Save | `save.json` | `save_ecs.json` |

Ambos vêm na [página de Releases](https://github.com/EzioMilanoX/BulletHell/releases) —
baixe o `.zip` da versão mais recente.

## Como rodar

1. Baixe e extraia o `.zip` numa pasta qualquer (não precisa ser
   `Arquivos de Programas` — o jogo não escreve nada fora da própria
   pasta).
2. **`BulletHellLegado.exe` precisa dos arquivos `balance.json` e
   `waves.json` na mesma pasta** — eles já vêm juntos no `.zip`, só
   não separe o `.exe` deles. `BulletHellECS.exe` não tem essa
   exigência — é 100% autocontido, um arquivo só.
3. Dê duplo clique. Se o Windows Defender/SmartScreen avisar
   "Windows protegeu o seu PC" (comum pra `.exe` sem assinatura
   digital — assinar custa uma licença de certificado que este
   projeto não tem), clique em **Mais informações → Executar assim
   mesmo**.
4. O progresso (conquistas, dificuldades destravadas, masteries) fica
   em `save.json`/`save_ecs.json`, criado na mesma pasta do `.exe` na
   primeira execução. Apagar esse arquivo reseta o progresso.

## Requisitos

- Windows 10/11 de 64 bits.
- Nenhuma instalação de Python, pygame ou runtime separado — está tudo
  dentro do `.exe`.

## Se algo não abrir

Ambos os `.exe` são "windowed" (sem console) — se o jogo não abrir e
nenhum erro aparecer, o motivo mais provável é o SmartScreen do
Windows bloqueando silenciosamente. Confira o aviso do Explorer
(clique direito no `.exe` → Propriedades → se tiver um botão
"Desbloquear" no rodapé, clique nele) antes de reportar bug.

---

## Para quem for buildar a partir do código-fonte

Isto é só pra quem quer gerar os `.exe` de novo (ex.: depois de mudar
o código) — quem só quer jogar usa a seção acima.

### Por que não é só `pyinstaller main.py`

O port ECS (`main_ecs.py`) depende da
[OuroborosEngine](https://github.com/EzioMilanoX/OuroborosEngine), que
não está no PyPI. Em desenvolvimento isso é resolvido de duas formas
soltas — um `sys.path.insert` direto pro repo-irmão
(`bullethell/__init__.py`) ou um `pip install -e ../OuroborosEngine`
manual — e nenhuma das duas funciona bem com o PyInstaller:

- A análise estática do PyInstaller (`modulegraph`) **não executa** o
  `sys.path.insert` — ele só roda de verdade quando o processo já
  está vivo, não durante o build.
- O editable install moderno do `setuptools` (PEP 660) registra um
  **finder de import** (não uma pasta normal com arquivos reais) —
  o `modulegraph` as vezes não consegue seguir esse finder e o pacote
  fica de fora do bundle, silenciosamente.

A solução usada aqui: buildar um **wheel de verdade** da engine a
partir de um commit conhecido do repo-irmão (arquivos reais, sem
finder), instalar ele **não-editável** num venv limpo, e só então
rodar o PyInstaller nesse venv. Isso deixa o build reproduzível mesmo
que o repo-irmão não esteja no disco de quem for buildar (o wheel já
fica versionado em `wheels/`).

### Passo a passo

```powershell
# 1. (opcional) rebuildar o wheel da engine a partir do repo-irmão —
#    só precisa disso se OuroborosEngine tiver mudado. Sem o repo-irmão
#    no disco, pule este passo: o wheel já versionado em wheels/ basta.
.\tools\build_engine_wheel.ps1

# 2. buildar os dois .exe (cria um venv limpo em .build_venv, instala
#    requirements-build.txt, roda o PyInstaller pros dois specs em
#    packaging/, copia balance.json/waves.json pra dist/)
.\tools\build_exes.ps1
```

Resultado em `dist/`: `BulletHellLegado.exe`, `BulletHellECS.exe`,
`balance.json`, `waves.json`.

### Ou deixa o CI buildar

`git push` numa tag `vX.Y.Z` roda `.github/workflows/release.yml`, que
faz exatamente os dois passos acima (sem precisar do repo-irmão — usa
o wheel já versionado) e publica os dois `.zip` como assets da Release
automaticamente. `.github/workflows/ci.yml` roda os 6 smoke tests
headless em todo push/PR pra `main` (não builda `.exe`, só valida que
nada quebrou).

### Arquivos relevantes

```
packaging/legado.spec         # spec do PyInstaller — main.py, sem engine
packaging/ecs.spec            # spec do PyInstaller — main_ecs.py, com a engine
requirements-build.txt        # deps pinadas do venv de build (não confundir com requirements.txt, que é pra dev)
wheels/ouroboros_engine-*.whl # wheel versionado da engine (ver ENGINE_COMMIT.txt ao lado)
tools/build_engine_wheel.ps1  # gera o wheel a partir do repo-irmão
tools/build_exes.ps1          # orquestra venv + PyInstaller + cópia dos JSONs
.github/workflows/ci.yml      # smoke tests em todo push/PR
.github/workflows/release.yml # build + publish automático em tag vX.Y.Z
```

### Pegadinhas que já mordemos (documentadas pra não repetir)

- **`pygame` vs `pygame-ce`**: são pacotes *diferentes* no PyPI que
  exportam o mesmo nome de import (`import pygame`). A
  `OuroborosEngine` chegou a declarar dependência do `pygame`
  original — nenhum código do projeto usa ele de fato (é sempre
  `pygame-ce`), mas o `pip` tentava buildar o `pygame` original do
  zero (sem wheel pra Python 3.14 ainda), quebrando em qualquer venv
  sem toolchain de build C. Corrigido na própria `OuroborosEngine`
  (`pyproject.toml`).
- **`Path(__file__).parent` sob `--onefile`**: pra um script rodado
  via `python main_ecs.py`, `__file__` aponta pro arquivo de verdade.
  Congelado pelo PyInstaller em modo `--onefile`, ele aponta pra uma
  pasta temporária de extração **nova a cada execução** — qualquer
  caminho de save calculado assim perde o progresso entre sessões.
  `main_ecs.py` usa `Path(sys.executable).parent` quando
  `sys.frozen` está setado.
- **`balance.json`/`waves.json` do legado**: `main.py` os abre por
  string relativa (`"balance.json"`), resolvida contra o **cwd** do
  processo — não contra `__file__` nem `sys._MEIPASS`. Embutir esses
  JSONs no bundle onefile não ajudaria (ficariam na pasta temp de
  extração, não no cwd); por isso eles vão soltos ao lado do `.exe`
  em vez de embutidos.
