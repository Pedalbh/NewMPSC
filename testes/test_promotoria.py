"""Espaço da promotoria (cartão C18): quem é da mesma promotoria vê a mesma mesa, ninguém de fora vê, só o promotor
envia ao SIG, quem sai perde o acesso na hora, e cada acesso fica registrado. DADOS FICTÍCIOS."""
import pytest
from sqlalchemy import create_engine, text

from app import cli, servicos
from app.cli import criar_usuario, desligar_usuario, mover_usuario
from app.config import Config
from app.main import criar_app
from app.modelos import Acesso, EntregaSig, Minuta, PedidoIA, Processo, Promotoria, Usuario, criar_banco
from testes.conftest import AGORA, SENHA, Cliente
from testes.test_processos import numeros_na_ordem

PJ, OUTRA = "1ª Promotoria de Justiça (fictícia)", "2ª Promotoria de Justiça (fictícia)"
NUMERO = "0000101-00.2026.8.24.0000"
BLOCO = [{"texto": "Texto do assessor.", "estilo": "corpo"}]


@pytest.fixture
def app():
    config = Config(ambiente="teste", segredo="s" * 40, banco_url="sqlite:///:memory:", motor="demo",
                    dados_ficticios=True, sig="simulado")
    return criar_app(config, agora=lambda: AGORA)


@pytest.fixture
def pessoas(banco):
    """Ana (promotora) e Caio (assessor) na mesma promotoria; Bruno (promotor) e Dora (assessora) em outra."""
    return {"ana": criar_usuario(banco, "ana@exemplo.invalid", "Ana Exemplo", SENHA, promotoria=PJ),
            "caio": criar_usuario(banco, "caio@exemplo.invalid", "Caio Exemplo", SENHA, promotoria=PJ,
                                  papel="assessor"),
            "bruno": criar_usuario(banco, "bruno@exemplo.invalid", "Bruno Exemplo", SENHA, promotoria=OUTRA),
            "dora": criar_usuario(banco, "dora@exemplo.invalid", "Dora Exemplo", SENHA, promotoria=OUTRA,
                                  papel="assessor")}


@pytest.fixture
def entrar(app, pessoas):
    abertos = []

    def _entrar(nome) -> Cliente:
        c = Cliente(app)
        c.__enter__()
        abertos.append(c)
        assert c.entrar(pessoas[nome].email).status_code == 303
        return c
    yield _entrar
    for c in abertos:
        c.__exit__(None, None, None)


def salvar(c, blocos=BLOCO, versao=None, processo=1):
    corpo = {"blocos": blocos} | ({"versao": versao} if versao is not None else {})
    return c.put(f"/api/processos/{processo}/minuta", json=corpo, headers={"X-CSRF-Token": c.csrf("/")})


def test_a_mesma_promotoria_ve_a_mesma_mesa(entrar):
    ana, caio = entrar("ana"), entrar("caio")
    caio.enviar("/processos/buscar")
    assert len(numeros_na_ordem(ana.get("/").text)) == 9 and PJ in ana.get("/").text
    assert salvar(caio).status_code == 200
    html = ana.get("/processos/1").text
    assert "Texto do assessor." in html and "Última alteração: Caio Exemplo" in html
    ana.enviar("/audiencias", {"numero": NUMERO, "data": "2026-11-16", "hora": "14:30",
                               "tipo": "Instrução e julgamento"}, pagina="/audiencias")
    assert NUMERO in caio.get("/audiencias").text and caio.get("/audiencias/1").status_code == 200
    # a fila é uma só: buscar de novo, por outra pessoa, não duplica
    ana.enviar("/processos/buscar")
    assert "9 já estavam na fila" in ana.get("/").text and len(numeros_na_ordem(caio.get("/").text)) == 9


@pytest.mark.parametrize("de_fora", ["bruno", "dora"])
def test_ninguem_de_fora_ve_nem_mexe_em_rota_nenhuma(entrar, banco, de_fora):
    """Teste de isolamento exigido pelo limite 3: cada rota que recebe um processo ou uma audiência."""
    ana = entrar("ana")
    ana.enviar("/processos/buscar")
    salvar(ana)
    ana.enviar("/audiencias", {"numero": NUMERO, "data": "2026-11-16", "hora": "14:30",
                               "tipo": "Instrução e julgamento"}, pagina="/audiencias")
    ana.enviar("/processos/2/entregar")
    fora = entrar(de_fora)
    assert numeros_na_ordem(fora.get("/").text) == [] and NUMERO not in fora.get("/audiencias").text
    assert "Texto do assessor." not in fora.get("/sig-simulado").text.split('id="t-fila-sig"')[0]
    for caminho in ("/processos/1", "/processos/1/minuta.docx", "/processos/1/minuta.txt",
                    "/api/processos/1/escrita", "/audiencias/1"):
        assert fora.get(caminho).status_code == 404, caminho
    assert salvar(fora).status_code == 404
    for caminho, dados in (("/processos/1/situacao", {"situacao": "concluido"}), ("/processos/1/entregar", None),
                           ("/processos/2/situacao", {"situacao": "a_fazer"}), ("/processos/1/refazer", None),
                           ("/processos/1/escrever", None), ("/processos/1/autos/1/remover", None),
                           ("/audiencias/1/remover", None)):
        assert fora.enviar(caminho, dados).status_code == 404, caminho
    r = fora.enviar("/processos/1/autos", files={"autos": ("a.pdf", b"%PDF-1.4")})
    assert r.status_code == 404
    banco.expire_all()
    assert banco.get(Processo, 1).situacao == "a_fazer" and banco.query(EntregaSig).count() == 1
    assert banco.query(Minuta).filter_by(processo_id=1).one().blocos[0]["texto"] == "Texto do assessor."
    # o mesmo número pode existir nas duas promotorias, cada uma com o seu
    fora.enviar("/processos/colar", {"numeros": NUMERO})
    assert banco.query(Processo).filter_by(numero=NUMERO).count() == 2
    assert banco.query(Acesso).filter(Acesso.usuario_id == fora.app.state.Sessao().query(Usuario).filter_by(
        email=f"{de_fora}@exemplo.invalid").one().id, Acesso.processo_id == 1).count() == 0


def test_so_o_promotor_envia_ao_sig_e_tira_de_la(entrar, banco):
    ana, caio = entrar("ana"), entrar("caio")
    caio.enviar("/processos/buscar")
    html = caio.get("/processos/1").text
    assert "Só o promotor envia ao SIG" in html and 'id="form-entregar"' not in html
    assert "Concluir sem enviar ao SIG" in html   # concluir sem tocar o SIG o assessor pode
    r = caio.enviar("/processos/1/entregar")
    assert r.status_code == 403 and "Só o promotor envia ao SIG" in r.text
    assert banco.query(EntregaSig).count() == 0
    assert 'id="form-entregar"' in ana.get("/processos/1").text
    assert ana.enviar("/processos/1/entregar").status_code == 303
    entrega = banco.query(EntregaSig).one()
    assert entrega.usuario_id == banco.query(Usuario).filter_by(email="ana@exemplo.invalid").one().id
    # o rascunho aparece para a promotoria inteira; tirar do SIG é só do promotor
    assert entrega.recibo in caio.get("/sig-simulado").text
    html = caio.get("/processos/1").text
    assert "Só o promotor tira o rascunho do SIG" in html and "Tirar do SIG e voltar à mesa" not in html
    r = caio.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    assert r.status_code == 403 and banco.query(EntregaSig).count() == 1
    assert ana.enviar("/processos/1/situacao", {"situacao": "a_fazer"}).status_code == 303
    assert banco.query(EntregaSig).count() == 0
    # processo concluído sem envio o assessor devolve à fila
    caio.enviar("/processos/2/situacao", {"situacao": "concluido"})
    assert caio.enviar("/processos/2/situacao", {"situacao": "a_fazer"}).status_code == 303


def test_quem_salva_sobre_versao_antiga_e_avisado_e_nao_apaga_a_do_outro(entrar, banco):
    ana, caio = entrar("ana"), entrar("caio")
    ana.enviar("/processos/buscar")
    assert 'data-versao="0"' in ana.get("/processos/1").text
    r = salvar(caio, versao=0)
    assert r.status_code == 200 and r.json()["versao"] == 1
    r = salvar(ana, [{"texto": "Texto da promotora.", "estilo": "corpo"}], versao=0)   # a tela dela é a antiga
    assert r.status_code == 409 and "Outra pessoa alterou esta minuta" in r.json()["erro"]
    banco.expire_all()
    assert banco.query(Minuta).filter_by(processo_id=1).one().blocos[0]["texto"] == "Texto do assessor."
    assert 'data-versao="1"' in ana.get("/processos/1").text
    assert salvar(ana, [{"texto": "Texto da promotora.", "estilo": "corpo"}], versao=1).json()["versao"] == 2
    assert salvar(ana, versao=True).status_code == 200   # valor que não é número não vale como versão


def test_quem_sai_perde_o_acesso_na_hora_e_o_trabalho_fica(entrar, banco, pessoas):
    ana, caio = entrar("ana"), entrar("caio")
    caio.enviar("/processos/buscar")
    salvar(caio)
    desligar_usuario(banco, "caio@exemplo.invalid")
    assert caio.get("/", follow_redirects=False).headers["location"] == "/entrar"   # a sessão aberta cai
    assert caio.get("/api/processos/1/escrita").status_code == 401
    r = caio.entrar("caio@exemplo.invalid")
    assert r.status_code == 403 and "não está em nenhuma promotoria" in r.text
    assert "Texto do assessor." in ana.get("/processos/1").text   # o que ele fez fica com a promotoria


def test_quem_muda_de_promotoria_passa_a_ver_so_a_nova(entrar, banco):
    ana, caio, bruno = entrar("ana"), entrar("caio"), entrar("bruno")
    ana.enviar("/processos/buscar")
    bruno.enviar("/processos/colar", {"numeros": "0000301-00.2026.8.24.0000"})
    mover_usuario(banco, "caio@exemplo.invalid", OUTRA)
    assert numeros_na_ordem(caio.get("/").text) == ["0000301-00.2026.8.24.0000"]
    assert caio.get("/processos/1").status_code == 404 and caio.get("/processos/10").status_code == 200
    assert banco.query(Usuario).filter_by(email="caio@exemplo.invalid").one().papel == "assessor"
    with pytest.raises(SystemExit, match="papel desconhecido"):
        mover_usuario(banco, "caio@exemplo.invalid", PJ, "chefe")


def test_conta_sem_promotoria_informada_ganha_mesa_propria(banco):
    um = criar_usuario(banco, "um@exemplo.invalid", "Um", SENHA)
    dois = criar_usuario(banco, "dois@exemplo.invalid", "Dois", SENHA)
    assert um.promotoria_id and dois.promotoria_id and um.promotoria_id != dois.promotoria_id


def test_registro_de_acessos_diz_quem_fez_o_que(entrar, banco, pessoas, capsys, monkeypatch):
    ana, caio = entrar("ana"), entrar("caio")
    caio.enviar("/processos/buscar")
    caio.get("/processos/1")
    salvar(caio)
    salvar(caio)   # a segunda gravação seguida da mesma pessoa não repete a linha
    ana.get("/processos/1")
    ana.get("/processos/1/minuta.docx")
    ana.enviar("/processos/1/entregar")
    ana.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    linhas = [(a.usuario_id, a.acao) for a in banco.query(Acesso).order_by(Acesso.id)]
    c, a = pessoas["caio"].id, pessoas["ana"].id
    assert linhas == [(c, "abriu"), (c, "editou a minuta"), (a, "abriu"), (a, "baixou a minuta"),
                      (a, "enviou ao SIG"), (a, "tirou do SIG")]
    assert all(x.promotoria_id == pessoas["ana"].promotoria_id and x.processo_id == 1 for x in banco.query(Acesso))
    assert len(servicos.acessos_da_promotoria(banco, pessoas["bruno"].promotoria_id)) == 0
    # nenhuma rota mostra, altera ou apaga o registro
    assert not [r.path for r in ana.app.routes if "acesso" in getattr(r, "path", "")]


def test_o_pedido_a_ia_fica_em_nome_de_quem_pediu(banco, pessoas):
    class MotorDeIA:
        usa_autos, nome = True, "ia"

    servicos.colar_numeros(banco, pessoas["ana"], NUMERO, MotorDeIA(), True)
    p = banco.query(Processo).one()
    servicos.juntar_autos(banco, p, "a.pdf", type("L", (), {
        "sha256": "0" * 64, "paginas": [f"Autos {NUMERO}"], "sem_texto": 0, "caracteres": 30})(), True, b"k" * 32)
    servicos.pedir_escrita(banco, p, pessoas["caio"], MotorDeIA(), True)
    assert banco.query(PedidoIA).one().usuario_id == pessoas["caio"].id
    with pytest.raises(servicos.EscritaRecusada, match="outra promotoria"):
        servicos.pedir_escrita(banco, p, pessoas["bruno"], MotorDeIA(), True)


def test_a_cota_de_texto_e_da_promotoria(banco, pessoas, monkeypatch):
    motor = type("M", (), {"usa_autos": True, "nome": "ia"})()
    servicos.colar_numeros(banco, pessoas["ana"], NUMERO, motor, True)
    servicos.colar_numeros(banco, pessoas["bruno"], NUMERO, motor, True)
    meu, alheio = banco.query(Processo).order_by(Processo.id).all()
    leitura = type("L", (), {"sha256": "0" * 64, "paginas": [f"Autos {NUMERO}"], "sem_texto": 0, "caracteres": 3000})()
    servicos.juntar_autos(banco, alheio, "a.pdf", leitura, True, b"k" * 32)
    monkeypatch.setattr(servicos, "COTA_TEXTO_AUTOS", 4000)
    assert servicos.texto_guardado(banco, meu.promotoria_id) == 0   # o texto da outra promotoria não conta
    servicos.juntar_autos(banco, meu, "a.pdf", leitura, True, b"k" * 32)
    assert servicos.texto_guardado(banco, meu.promotoria_id) == 3000


def test_banco_de_antes_do_espaco_passa_cada_conta_para_a_sua_promotoria(tmp_path):
    """Contas antigas com o mesmo texto de promotoria NÃO são juntadas, e o número deixa de ser único por conta."""
    url = f"sqlite:///{tmp_path / 'antigo.db'}"
    antigo = create_engine(url)
    with antigo.begin() as c:
        c.execute(text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, email VARCHAR(254) UNIQUE, nome VARCHAR(120), "
                       "cargo VARCHAR(120), promotoria VARCHAR(160), senha_hash VARCHAR(255), criado_em DATETIME)"))
        c.execute(text("CREATE TABLE processos (id INTEGER NOT NULL, usuario_id INTEGER NOT NULL, "
                       "numero VARCHAR(25) NOT NULL, numero_sig VARCHAR(30), classe VARCHAR(200), "
                       "assunto VARCHAR(200), "
                       "vista VARCHAR(40), reu_preso BOOLEAN, entrada DATETIME, dv_ok BOOLEAN, grupo INTEGER, "
                       "situacao VARCHAR(20), concluido_em DATETIME, origem VARCHAR(20), criado_em DATETIME, "
                       "PRIMARY KEY (id), UNIQUE (usuario_id, numero), "
                       "FOREIGN KEY(usuario_id) REFERENCES usuarios (id))"))
        c.execute(text("CREATE INDEX ix_processos_usuario_id ON processos (usuario_id)"))
        c.execute(text("CREATE TABLE minutas (id INTEGER PRIMARY KEY, processo_id INTEGER UNIQUE, tipo VARCHAR(120), "
                       "blocos JSON, motor VARCHAR(40), editada BOOLEAN, atualizada_em DATETIME)"))
        c.execute(text("CREATE TABLE audiencias (id INTEGER PRIMARY KEY, usuario_id INTEGER, numero VARCHAR(25), "
                       "inicio DATETIME, tipo VARCHAR(80), ficha JSON, motor VARCHAR(40), criado_em DATETIME)"))
        c.execute(text("INSERT INTO usuarios (id, email, nome, promotoria, senha_hash) VALUES "
                       "(1, 'ana@exemplo.invalid', 'Ana', 'Mesma', 'x'), "
                       "(2, 'bruno@exemplo.invalid', 'Bruno', 'Mesma', 'x')"))
        c.execute(text("INSERT INTO processos (id, usuario_id, numero, situacao, grupo) VALUES "
                       "(1, 1, :n, 'a_fazer', 3), (2, 2, :n, 'a_fazer', 3)"), {"n": NUMERO})
        c.execute(text("INSERT INTO minutas (id, processo_id, tipo, blocos, motor, editada) VALUES "
                       "(1, 1, 'Peça', '[]', 'demo', 0)"))
        c.execute(text("INSERT INTO audiencias (id, usuario_id, numero, inicio, ficha, motor) VALUES "
                       "(1, 2, :n, '2026-11-20 14:00:00', '{}', 'demo')"), {"n": NUMERO})
    antigo.dispose()
    _, Sessao = criar_banco(url, b"k" * 32)
    with Sessao() as db:
        ana, bruno = db.get(Usuario, 1), db.get(Usuario, 2)
        assert ana.promotoria_id and bruno.promotoria_id and ana.promotoria_id != bruno.promotoria_id
        assert ana.papel == "promotor" and db.query(Promotoria).count() == 2
        assert [p.id for p in servicos.fila(db, ana)] == [1] and [p.id for p in servicos.fila(db, bruno)] == [2]
        assert db.get(Minuta, 1).versao == 0
        assert [a.id for a in servicos.pauta(db, bruno, AGORA)] == [1] and servicos.pauta(db, ana, AGORA) == []
        # juntar é ato de quem administra; aí o número repetido na mesma promotoria é barrado pela regra nova
        mover_usuario(db, "bruno@exemplo.invalid", ana.espaco.nome, "assessor")
        assert [p.id for p in servicos.fila(db, bruno)] == [1]
        motor = type("M", (), {"usa_autos": True, "nome": "ia"})()
        # a regra antiga (único por conta) saiu: Bruno traz para a promotoria nova um número que já trouxe na antiga
        mover_usuario(db, "bruno@exemplo.invalid", "Terceira")
        assert servicos.colar_numeros(db, bruno, NUMERO, motor, True).novos == 1
    criar_banco(url, b"k" * 32)   # de novo: nada a converter
    with create_engine(url).connect() as c:
        ddl = c.execute(text("SELECT sql FROM sqlite_master WHERE name = 'processos'")).scalar()
        assert "UNIQUE (promotoria_id, numero)" in ddl and "UNIQUE (usuario_id, numero)" not in ddl
        indice = "SELECT count(*) FROM sqlite_master WHERE name = 'ix_processos_usuario_id'"
        assert c.execute(text(indice)).scalar() == 1


def test_linha_de_comando_cria_move_desliga_e_lista(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NEWMPSC_BANCO", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("NEWMPSC_SEGREDO", "s" * 40)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: SENHA)
    cli.main(["criar-usuario", "ana@exemplo.invalid", "Ana Exemplo", PJ])
    cli.main(["criar-usuario", "caio@exemplo.invalid", "Caio Exemplo", PJ, "assessor"])
    assert "como assessor" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["criar-usuario", "eva@exemplo.invalid", "Eva", PJ, "chefe"])
    cli.main(["mover-usuario", "caio@exemplo.invalid", OUTRA])
    assert f"agora está em {OUTRA}, como assessor" in capsys.readouterr().out
    cli.main(["desligar-usuario", "caio@exemplo.invalid"])
    cli.main(["acessos", PJ])
    with pytest.raises(SystemExit, match="não há promotoria"):
        cli.main(["acessos", "Inexistente"])
