"""Guarda dos autos (cartão C1) e impressão com chave do servidor (cartão C2). DADOS FICTÍCIOS."""
import hashlib
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text

from app import autos
from app.cli import criar_usuario
from app.config import Config
from app.main import criar_app
from app.modelos import ArquivoAutos, Minuta, PaginaAutos, Processo, criar_banco
from testes.conftest import SENHA, Cliente
from testes.fabrica_pdf import AUTOS_FICTICIOS, pdf

PDF = pdf(AUTOS_FICTICIOS)
INICIO = datetime(2026, 11, 13, 9, 0)


class Relogio:
    def __init__(self):
        self.agora = INICIO

    def __call__(self):
        return self.agora

    def passar(self, **kw):
        self.agora += timedelta(**kw)


def config(segredo="s" * 40, banco="sqlite:///:memory:"):
    return Config(ambiente="teste", segredo=segredo, banco_url=banco, motor="demo", dados_ficticios=True)


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def app_relogio(relogio):
    return criar_app(config(), agora=relogio)


@pytest.fixture
def banco(app_relogio):
    with app_relogio.state.Sessao() as db:
        yield db


def entrar(app, banco, email):
    criar_usuario(banco, email, "Pessoa Exemplo", SENHA)
    c = Cliente(app)
    c.__enter__()
    assert c.entrar(email).status_code == 303
    c.importar_fila()
    assert c.enviar("/processos/1/autos" if email.startswith("ana") else "/processos/10/autos",
                    files={"autos": ("autos.pdf", PDF)}).status_code == 303
    return c


def contar(banco, modelo) -> int:
    banco.expire_all()
    return banco.scalar(select(func.count()).select_from(modelo))


def concluir(c, processo=1):
    return c.enviar(f"/processos/{processo}/situacao", {"situacao": "concluido"})


# ---------------------------------------------------------------- C1: prazo de guarda
def test_concluir_avisa_e_mostra_a_data_em_que_os_autos_somem(app_relogio, banco):
    ana = entrar(app_relogio, banco, "ana@exemplo.invalid")
    concluir(ana)
    assert "Processo concluído. O texto dos autos será apagado em 30 dias." in ana.get("/").text
    assert "O texto destes autos será apagado em 13/12/2026." in ana.get("/processos/1").text


def test_apaga_o_texto_30_dias_depois_de_concluido_e_mantem_a_minuta(app_relogio, banco, relogio):
    ana = entrar(app_relogio, banco, "ana@exemplo.invalid")
    concluir(ana)
    relogio.passar(days=29, hours=23)
    ana.get("/")
    assert contar(banco, ArquivoAutos) == 1
    relogio.passar(hours=1)
    ana.get("/")   # a limpeza roda no máximo uma vez por hora, na passagem de uma requisição
    assert contar(banco, ArquivoAutos) == 0 and contar(banco, PaginaAutos) == 0
    assert contar(banco, Minuta) == 9 and contar(banco, Processo) == 9
    assert "O texto destes autos" not in ana.get("/processos/1").text


def test_voltar_a_fila_zera_o_prazo(app_relogio, banco, relogio):
    ana = entrar(app_relogio, banco, "ana@exemplo.invalid")
    concluir(ana)
    relogio.passar(days=20)
    ana.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    assert "será apagado" not in ana.get("/processos/1").text
    relogio.passar(days=20)
    ana.get("/")
    assert contar(banco, ArquivoAutos) == 1   # na fila, nada some
    concluir(ana)
    relogio.passar(days=29)
    ana.get("/")
    assert contar(banco, ArquivoAutos) == 1   # o prazo recomeçou na nova conclusão
    relogio.passar(days=1, hours=1)
    ana.get("/")
    assert contar(banco, ArquivoAutos) == 0


def test_concluir_de_novo_nao_adia_o_prazo(app_relogio, banco, relogio):
    ana = entrar(app_relogio, banco, "ana@exemplo.invalid")
    concluir(ana)
    relogio.passar(days=10)
    concluir(ana)
    assert banco.scalar(select(Processo.concluido_em).where(Processo.id == 1)) == INICIO


def test_o_prazo_de_um_usuario_nao_apaga_os_autos_de_outro(app_relogio, banco, relogio):
    ana = entrar(app_relogio, banco, "ana@exemplo.invalid")
    bruno = entrar(app_relogio, banco, "bruno@exemplo.invalid")
    concluir(ana)
    relogio.passar(days=31)
    bruno.get("/")
    banco.expire_all()
    assert banco.scalars(select(ArquivoAutos.processo_id)).all() == [10]   # só sobra o do Bruno, na fila dele


def test_a_limpeza_roda_na_partida(tmp_path, relogio):
    url = f"sqlite:///{tmp_path / 'b.db'}"
    app = criar_app(config(banco=url), agora=relogio)
    with app.state.Sessao() as db:
        ana = entrar(app, db, "ana@exemplo.invalid")
        concluir(ana)
    relogio.passar(days=30)
    app = criar_app(config(banco=url), agora=relogio)
    with app.state.Sessao() as db:
        assert db.scalar(select(func.count()).select_from(ArquivoAutos)) == 0


# ---------------------------------------------------------------- C2: impressão com chave do servidor
def test_o_banco_nao_guarda_o_sha256_do_arquivo(app_relogio, banco):
    entrar(app_relogio, banco, "ana@exemplo.invalid")
    guardada = banco.scalar(select(ArquivoAutos.impressao))
    assert guardada != hashlib.sha256(PDF).hexdigest()
    assert guardada == autos.impressao(hashlib.sha256(PDF).hexdigest(), config().chave_impressao)
    assert "sha256" not in {c.name for c in ArquivoAutos.__table__.columns}


def test_a_impressao_depende_da_chave_do_servidor():
    resumo = hashlib.sha256(PDF).hexdigest()
    a, b = config("a" * 40).chave_impressao, config("b" * 40).chave_impressao
    assert autos.impressao(resumo, a) != autos.impressao(resumo, b)
    assert autos.impressao(resumo, a) == autos.impressao(resumo, a)


def test_arquivo_repetido_continua_avisado(app_relogio, banco):
    ana = entrar(app_relogio, banco, "ana@exemplo.invalid")
    ana.enviar("/processos/1/autos", files={"autos": ("de-novo.pdf", PDF)})
    assert "de-novo.pdf não entrou: este arquivo já está nos autos." in ana.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 1


def test_banco_antigo_e_convertido_na_partida(tmp_path):
    """Banco da versão anterior: guarda o sha256 e não tem a data de conclusão."""
    url = f"sqlite:///{tmp_path / 'antigo.db'}"
    antigo = create_engine(url)
    resumo = hashlib.sha256(PDF).hexdigest()
    with antigo.begin() as c:
        c.execute(text("CREATE TABLE processos (id INTEGER PRIMARY KEY, usuario_id INTEGER, numero VARCHAR(25), "
                       "numero_sig VARCHAR(30), classe VARCHAR(200), assunto VARCHAR(200), vista VARCHAR(40), "
                       "reu_preso BOOLEAN, entrada DATETIME, dv_ok BOOLEAN, grupo INTEGER, situacao VARCHAR(20), "
                       "origem VARCHAR(20), criado_em DATETIME)"))
        c.execute(text("CREATE TABLE arquivos_autos (id INTEGER PRIMARY KEY, processo_id INTEGER, nome VARCHAR(200), "
                       "tamanho INTEGER, sha256 VARCHAR(64), total_paginas INTEGER, sem_texto INTEGER, "
                       "caracteres INTEGER, cita_processo BOOLEAN, enviado_em DATETIME, "
                       "UNIQUE (processo_id, sha256))"))
        c.execute(text("INSERT INTO processos (id, usuario_id, numero, situacao) "
                       "VALUES (1, 1, '0000101-00.2026.8.24.0000', 'concluido'), "
                       "(2, 1, '0000102-00.2026.8.24.0000', 'a_fazer')"))
        c.execute(text("INSERT INTO arquivos_autos (id, processo_id, nome, tamanho, sha256, total_paginas) "
                       "VALUES (1, 1, 'a.pdf', 1, :r, 3)"), {"r": resumo})
    antigo.dispose()
    with pytest.raises(RuntimeError, match="chave do servidor"):
        criar_banco(url)
    chave = config().chave_impressao
    motor, _ = criar_banco(url, chave)
    with motor.connect() as c:
        assert c.execute(text("SELECT impressao FROM arquivos_autos")).scalar() == autos.impressao(resumo, chave)
        datas = dict(c.execute(text("SELECT id, concluido_em FROM processos")).all())
    assert datas[1] is not None and datas[2] is None   # o prazo do já concluído começa a contar na conversão
    criar_banco(url, chave)   # de novo: nada a converter
