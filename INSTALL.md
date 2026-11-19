# Instalar e jogar

Um `.exe` só — `BulletHell.exe` — que não exige Python instalado. Ele
vem num `.zip` na [página de Releases](https://github.com/EzioMilanoX/BulletHell/releases)
— baixe o da versão mais recente.

> Vindo da v1.x? Ela trazia dois `.exe` (`BulletHellLegado.exe` e
> `BulletHellECS.exe`). A partir da v2.0.0 só existe o jogo ECS, agora
> chamado só `BulletHell.exe`. Pra manter o progresso, extraia o novo
> `.exe` **na mesma pasta** do `BulletHellECS.exe` antigo — o save
> (`save_ecs.json`) é o mesmo arquivo. O `save.json` do Legado não é
> lido pela v2.

## Como rodar

1. Baixe e extraia o `.zip` numa pasta qualquer (não precisa ser
   `Arquivos de Programas` — o jogo não escreve nada fora da própria
   pasta).
2. Dê duplo clique em `BulletHell.exe`. Ele é 100% autocontido, um
   arquivo só. Se o Windows Defender/SmartScreen avisar "Windows
   protegeu o seu PC" (comum pra `.exe` sem assinatura digital —
   assinar custa uma licença de certificado que este projeto não tem),
   clique em **Mais informações → Executar assim mesmo**.
3. O progresso (conquistas, dificuldades destravadas, masteries,
   registros, opções de SISTEMA) fica em `save_ecs.json`, criado na
   mesma pasta do `.exe` na primeira execução. Apagar esse arquivo
   reseta o progresso.
4. O save é gravado de forma atômica (arquivo temporário + troca), e a
   cada gravação o jogo guarda a geração anterior em
   `save_ecs.json.bak`. Se o arquivo principal estiver ilegível na
   próxima abertura, o jogo recupera do `.bak` sozinho em vez de
   resetar o progresso.

## Requisitos

- Windows 10/11 de 64 bits.
- Nenhuma instalação de Python, pygame ou runtime separado — está tudo
  dentro do `.exe`.

## Se algo não abrir

O `.exe` é "windowed" (sem console) — se o jogo não abrir e nenhum erro
aparecer, o motivo mais provável é o SmartScreen do Windows bloqueando
silenciosamente. Confira o aviso do Explorer (clique direito no `.exe` →
Propriedades → se tiver um botão "Desbloquear" no rodapé, clique nele)
antes de reportar bug.

Se o jogo abrir e fechar sozinho com um erro, confira `crash.log` na
mesma pasta do `.exe` — todo erro não tratado é registrado ali (com
data/hora e o traceback completo) antes do jogo fechar. Anexe esse
arquivo ao reportar um bug.

Se a **Tela Cheia** (menu SISTEMA) deixar a tela preta no seu monitor,
apague a linha `"fullscreen": true` de `save_ecs.json` (ou troque por
`false`) — o jogo volta a abrir em janela.

---

## Para quem for buildar a partir do código-fonte

Isto é só pra quem quer gerar o `.exe` de novo (ex.: depois de mudar o
código) — quem só quer jogar usa a seção acima.

### Por que não é só `pyinstaller main_ecs.py`

O jogo depende da
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
  o `modulegraph` às vezes não consegue seguir esse finder e o pacote
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

# 2. buildar o .exe (cria um venv limpo em .build_venv, instala
#    requirements-build.txt e roda o PyInstaller com packaging/ecs.spec)
.\tools\build_exes.ps1
```

Resultado em `dist/`: `BulletHell.exe`.

### Ou deixa o CI buildar

`git push` numa tag `vX.Y.Z` roda `.github/workflows/release.yml`: roda
a suíte pytest, faz exatamente o passo 2 acima (sem precisar do
repo-irmão — usa o wheel já versionado) e publica
`BulletHell-vX.Y.Z-win64.zip` como asset da Release, com as notas da
seção correspondente do [CHANGELOG.md](CHANGELOG.md).
`.github/workflows/ci.yml` roda `ruff check .` + `pytest` em todo
push/PR pra `main` (não builda `.exe`, só valida que nada quebrou).

### Arquivos relevantes

```
packaging/ecs.spec            # spec do PyInstaller — main_ecs.py + bullethell/data, com a engine
requirements-build.txt        # deps pinadas do venv de build (não confundir com requirements.txt, que é pra dev)
wheels/ouroboros_engine-*.whl # wheel versionado da engine (ver ENGINE_COMMIT.txt ao lado)
tools/build_engine_wheel.ps1  # gera o wheel a partir do repo-irmão
tools/build_exes.ps1          # orquestra venv + PyInstaller
.github/workflows/ci.yml      # lint + pytest em todo push/PR
.github/workflows/release.yml # pytest + build + publish automático em tag vX.Y.Z
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
- **`pip wheel` do repo-irmão suja a pasta dele**: o build in-tree do
  setuptools deixa `build/` e `*.egg-info` no repo da engine. Pra um
  wheel limpo sem tocar no repo-irmão, builde a partir de um
  `git archive` do commit desejado numa pasta temporária.
