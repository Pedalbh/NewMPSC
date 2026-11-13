"""Login, sessão, CSRF, cabeçalhos e isolamento entre usuários."""
import pytest

from app.config import carregar
from app.seguranca import LimiteTentativas, conferir_senha, gerar_hash
from testes.conftest import Cliente


def test_pagina_protegida_manda_para_o_login(cliente):
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/entrar"


def test_api_sem_sessao_responde_401(cliente):
    assert cliente.put("/api/processos/1/minuta", json={}).status_code in (401, 403)


def test_login_certo_e_errado(cliente, ana):
    assert cliente.entrar(ana.email, "senha-errada-qualquer").status_code == 401
    assert cliente.entrar("ninguem@exemplo.invalid").status_code == 401
    assert cliente.entrar(ana.email).status_code == 303
    assert "Ana" in cliente.get("/").text


def test_login_bloqueia_depois_de_cinco_falhas(cliente, ana):
    for _ in range(5):
        assert cliente.entrar(ana.email, "senha-errada-qualquer").status_code == 401
    assert cliente.entrar(ana.email).status_code == 429   # nem a senha certa passa durante o bloqueio


def test_limite_expira_com_o_tempo():
    t = [0.0]
    limite = LimiteTentativas(maximo=2, janela=60, relogio=lambda: t[0])
    limite.registrar_falha("k")
    limite.registrar_falha("k")
    assert limite.bloqueado("k")
    t[0] = 61
    assert not limite.bloqueado("k")


def test_post_sem_csrf_e_recusado(logada):
    assert logada.post("/processos/colar", data={"numeros": "x"}).status_code == 403
    assert logada.post("/sair").status_code == 403
    assert logada.put("/api/processos/1/minuta", json={"blocos": []}).status_code == 403


def test_sair_encerra_a_sessao(logada):
    assert logada.enviar("/sair").status_code == 303
    assert logada.get("/", follow_redirects=False).headers["location"] == "/entrar"


def test_cabecalhos_de_seguranca(cliente):
    h = cliente.get("/entrar").headers
    assert "default-src 'self'" in h["content-security-policy"]
    assert "'unsafe-inline'" not in h["content-security-policy"]
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    assert h["cache-control"] == "no-store"


def test_cookie_de_sessao_e_httponly(cliente):
    assert "httponly" in cliente.get("/entrar").headers["set-cookie"].lower()


def test_um_usuario_nao_ve_dado_do_outro(app, logada, bruno):
    logada.importar_fila()
    logada.enviar("/audiencias", {"numero": "0000101-00.2026.8.24.0000", "data": "2026-11-20", "hora": "14:00",
                                  "tipo": "Custódia"}, pagina="/audiencias")
    assert logada.get("/processos/1").status_code == 200
    with Cliente(app) as outro:
        outro.entrar(bruno.email)
        assert "0000101" not in outro.get("/").text
        assert outro.get("/processos/1").status_code == 404
        assert outro.get("/processos/1/minuta.docx").status_code == 404
        assert outro.get("/audiencias/1").status_code == 404
        r = outro.put("/api/processos/1/minuta", json={"blocos": [{"texto": "x", "estilo": "corpo"}]},
                      headers={"X-CSRF-Token": outro.csrf("/")})
        assert r.status_code == 404


def test_senha_curta_e_recusada_e_hash_confere():
    with pytest.raises(ValueError):
        gerar_hash("curta")
    h = gerar_hash("uma-senha-bem-comprida")
    assert h.startswith("$argon2") and conferir_senha(h, "uma-senha-bem-comprida")
    assert not conferir_senha(h, "outra") and not conferir_senha(None, "qualquer")


def test_producao_exige_segredo():
    with pytest.raises(RuntimeError):
        carregar({"NEWMPSC_AMBIENTE": "producao"})
    assert carregar({"NEWMPSC_AMBIENTE": "producao", "NEWMPSC_SEGREDO": "x" * 32}).producao


def test_saude(cliente):
    assert cliente.get("/saude").json()["estado"] == "ok"
