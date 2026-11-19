"""Save do jogo (main_ecs.py): carga com fallback pro .bak, escrita
atômica via SaveFile da engine, backup de 1 geração que nunca é
sobrescrito por um principal corrompido, e a Tela Cheia salva reaplicada
no boot.
"""
import json

import pytest

import main_ecs


@pytest.fixture
def caminhos(tmp_path, monkeypatch):
    save = tmp_path / "save_ecs.json"
    bak = tmp_path / "save_ecs.json.bak"
    monkeypatch.setattr(main_ecs, "SAVE_PATH", save)
    monkeypatch.setattr(main_ecs, "BACKUP_PATH", bak)
    return save, bak


def _totais(**kw):
    t = {"runs": 0, "kills": 0, "deaths": 0, "graze": 0, "parries": 0}
    t.update(kw)
    return t


def test_sem_arquivo_carrega_defaults_travados(caminhos):
    s = main_ecs._load_save()
    assert s["runs"] == 0
    assert s["unlocked_skills"] == ["none", "dash"]
    assert s["highest_cleared_diff"] == 0
    assert s["settings"]["fullscreen"] is False


def test_persist_e_load_ida_e_volta(caminhos):
    save_path, _ = caminhos
    s = main_ecs._load_save()
    main_ecs._persist(s, _totais(runs=2, kills=5, graze=40), {"first_blood"})
    assert save_path.exists()
    s2 = main_ecs._load_save()
    assert s2["runs"] == 2
    assert s2["total_kills"] == 5
    assert s2["total_graze"] == 40
    assert s2["achievements"] == ["first_blood"]


def test_persist_acumula_entre_sessoes(caminhos):
    for _ in range(3):
        s = main_ecs._load_save()
        main_ecs._persist(s, _totais(runs=1, kills=2), set())
    assert main_ecs._load_save()["total_kills"] == 6


def test_escrita_atomica_nao_deixa_tmp(caminhos):
    save_path, bak = caminhos
    main_ecs._persist(main_ecs._load_save(), _totais(runs=1), set())
    main_ecs._persist(main_ecs._load_save(), _totais(runs=1), set())
    sobras = [p.name for p in save_path.parent.iterdir()
              if p.name not in (save_path.name, bak.name)]
    assert sobras == []


def test_backup_guarda_a_geracao_anterior(caminhos):
    _, bak = caminhos
    main_ecs._persist(main_ecs._load_save(), _totais(runs=1), set())
    main_ecs._persist(main_ecs._load_save(), _totais(runs=1), set())
    assert json.loads(bak.read_text(encoding="utf-8"))["runs"] == 1


def test_principal_corrompido_recupera_do_bak(caminhos):
    save_path, bak = caminhos
    bak.write_text(json.dumps({"runs": 7, "highest_cleared_diff": 2}),
                   encoding="utf-8")
    save_path.write_text('{"runs": 9, "total_kil', encoding="utf-8")  # meio JSON
    s = main_ecs._load_save()
    assert s["runs"] == 7
    assert s["highest_cleared_diff"] == 2


def test_principal_corrompido_nao_sobrescreve_o_bak(caminhos):
    save_path, bak = caminhos
    bak.write_text(json.dumps({"runs": 7}), encoding="utf-8")
    save_path.write_text("lixo{", encoding="utf-8")
    s = main_ecs._load_save()
    main_ecs._persist(s, _totais(runs=1), set())
    assert json.loads(bak.read_text(encoding="utf-8"))["runs"] == 7
    assert json.loads(save_path.read_text(encoding="utf-8"))["runs"] == 8


def test_raiz_que_nao_e_objeto_conta_como_ausente(caminhos):
    save_path, _ = caminhos
    save_path.write_text("[1, 2, 3]", encoding="utf-8")
    assert main_ecs._load_save()["runs"] == 0


def test_falha_de_escrita_nao_derruba(caminhos, monkeypatch):
    """Pasta impossível (um ARQUIVO no lugar do diretório): perde a sessão,
    não levanta exceção ao sair do jogo."""
    save_path, _ = caminhos
    bloqueio = save_path.parent / "bloqueio"
    bloqueio.write_text("", encoding="utf-8")
    monkeypatch.setattr(main_ecs, "SAVE_PATH", bloqueio / "save_ecs.json")
    main_ecs._persist(main_ecs._load_save(), _totais(runs=1), set())
    assert not (bloqueio / "save_ecs.json").exists()


# ---------------------------------------------------------------------------
# Tela Cheia no boot
# ---------------------------------------------------------------------------

class _RendererFake:
    def __init__(self, falha=False):
        self.chamadas = []
        self._falha = falha

    def set_fullscreen(self, enabled):
        self.chamadas.append(enabled)
        if self._falha:
            raise RuntimeError("modo de vídeo indisponível")


def test_boot_reaplica_tela_cheia_salva():
    r = _RendererFake()
    main_ecs._apply_boot_settings(r, {"settings": {"fullscreen": True}})
    assert r.chamadas == [True]


def test_boot_em_janela_nao_troca_modo_de_tela():
    r = _RendererFake()
    main_ecs._apply_boot_settings(r, {"settings": {"fullscreen": False}})
    main_ecs._apply_boot_settings(r, {})
    assert r.chamadas == []


def test_boot_tela_cheia_que_falha_volta_pra_janela():
    r = _RendererFake(falha=True)
    save = {"settings": {"fullscreen": True}}
    main_ecs._apply_boot_settings(r, save)
    assert save["settings"]["fullscreen"] is False


def test_boot_com_renderer_null_da_engine():
    from ouroboros.interfaces.null.null_renderer import NullRenderer

    r = NullRenderer()
    r.initialize(800, 600, "teste")
    main_ecs._apply_boot_settings(r, {"settings": {"fullscreen": True}})
    assert r._is_fullscreen is True
