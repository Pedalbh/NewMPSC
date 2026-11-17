"""Espaço da promotoria (cartão C18): quem é da mesma promotoria vê a mesma mesa, ninguém de fora vê, só o promotor
envia ao SIG, quem sai perde o acesso na hora, e cada acesso fica registrado. DADOS FICTÍCIOS."""
import pytest
from sqlalchemy import create_engine, text

from app import cli, servicos
from app.cli import criar_promotoria, criar_usuario, desligar_usuario, mover_usuario
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
    assert "Texto do assessor." in html and "Alterada por Caio Exemplo hoje às" in html
    # na fila, a promotora vê o que o assessor já preparou sem abrir processo por processo
    assert ana.get("/").text.count("Editada por Caio") == 1 and "Editada por" not in caio.get("/").text
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
    assert "Quem envia ao SIG é o promotor" in html and 'id="form-entregar"' not in html
    # concluir sem tocar o SIG o assessor pode, mas recolhido: não é o botão da tela dele
    assert 'id="concluir-assessor"' in html and 'id="concluir-assessor"' not in ana.get("/processos/1").text
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
    assert "Só o promotor troca ou tira o rascunho do SIG" in html and "Tirar do SIG e voltar à mesa" not in html
    assert "Os autos só voltam a aceitar arquivo se o promotor tirar o rascunho" in html
    assert html.count('action="/processos/1/situacao"') == 0   # sem botão, não sobra formulário vazio
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


@pytest.mark.parametrize("versao", [None, "2", 2.0, True, [2], -1, 10**30])
def test_sem_a_versao_certa_nada_e_gravado(entrar, banco, versao):
    """Achado nos pareceres: versão ausente ou de outro tipo gravava por cima sem conferência; grande demais, 500."""
    ana, caio = entrar("ana"), entrar("caio")
    ana.enviar("/processos/buscar")
    salvar(ana, [{"texto": "Texto da promotora.", "estilo": "corpo"}], versao=0)
    salvar(ana, [{"texto": "Texto da promotora.", "estilo": "corpo"}], versao=1)
    corpo = {"blocos": BLOCO, "versao": versao}
    if versao is None:
        del corpo["versao"]
    # pelo cliente cru: o de teste acrescentaria a versão certa, como a tela faz
    r = super(Cliente, caio).put("/api/processos/1/minuta", json=corpo, headers={"X-CSRF-Token": caio.csrf("/")})
    assert r.status_code == 409 and "ecarregue a página" in r.json()["erro"]
    banco.expire_all()
    assert banco.query(Minuta).filter_by(processo_id=1).one().blocos[0]["texto"] == "Texto da promotora."


def test_minuta_refeita_nao_volta_a_versao_zero_e_tela_antiga_nao_refaz(entrar, banco):
    """Achado nos pareceres: a minuta nova nascia na versão 0, e uma aba antiga salvava por cima dela sem aviso."""
    ana, caio = entrar("ana"), entrar("caio")
    ana.enviar("/processos/buscar")
    assert salvar(caio, versao=0).json()["versao"] == 1          # a aba de Caio fica na versão 1
    assert ana.enviar("/processos/1/refazer").status_code == 303   # Ana refaz com a tela em dia
    banco.expire_all()
    assert banco.query(Minuta).filter_by(processo_id=1).one().versao == 2
    assert salvar(ana, [{"texto": "Texto novo da Ana.", "estilo": "corpo"}], versao=2).json()["versao"] == 3
    for antiga in (0, 1, 2):
        assert salvar(caio, versao=antiga).status_code == 409
    # refazer com a tela antiga, ou sem versão, também não apaga o texto novo
    assert caio.enviar("/processos/1/refazer", {"versao": 1}).status_code == 409
    r = caio.post("/processos/1/refazer", data={"csrf": caio.csrf("/")}, follow_redirects=False)
    assert r.status_code == 409
    banco.expire_all()
    assert banco.query(Minuta).filter_by(processo_id=1).one().blocos[0]["texto"] == "Texto novo da Ana."


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


def test_registro_de_acessos_diz_quem_fez_o_que(entrar, banco, pessoas, monkeypatch):
    ana, caio = entrar("ana"), entrar("caio")
    caio.enviar("/processos/buscar")
    caio.get("/processos/1")
    salvar(caio, versao=0)
    salvar(caio, versao=1)   # a segunda gravação seguida da mesma pessoa não repete a linha
    ana.get("/processos/1")
    ana.get("/processos/1/minuta.docx")
    caio.enviar("/processos/1/entregar")   # tentativa negada também fica
    ana.enviar("/processos/1/entregar")
    caio.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    ana.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    ana.enviar("/audiencias", {"numero": NUMERO, "data": "2026-11-16", "hora": "14:30",
                               "tipo": "Instrução e julgamento"}, pagina="/audiencias")
    ana.get("/audiencias/1")
    ana.enviar("/sair")
    c, a = pessoas["caio"].id, pessoas["ana"].id
    da_mesa = banco.query(Acesso).filter_by(promotoria_id=pessoas["ana"].promotoria_id).order_by(Acesso.id)
    linhas = [(x.usuario_id, x.acao) for x in da_mesa if not x.acao.startswith("administração")]
    assert linhas == [
        (a, "entrou"), (c, "entrou"), (c, "trouxe processos"), (c, "abriu"), (c, "editou a minuta"),
        (a, "abriu"), (a, "baixou a minuta"), (c, "negado: enviar ao SIG"), (a, "enviou ao SIG"),
        (c, "negado: tirar do SIG"), (a, "tirou do SIG"), (a, "marcou audiência"),
        (a, "abriu ficha de audiência"), (a, "saiu")]
    # quem volta a editar mais tarde ganha linha nova, mesmo sem ninguém no meio
    minuta = banco.query(Minuta).filter_by(processo_id=1).one()
    minuta.atualizada_em -= servicos.EDICAO_NOVA * 2
    banco.commit()
    salvar(caio, versao=caio.versao(1))
    assert [x.acao for x in banco.query(Acesso).filter_by(usuario_id=c)].count("editou a minuta") == 2
    # a tentativa de quem é de fora fica no registro da promotoria de quem tentou, sem o id do processo alheio
    bruno = entrar("bruno")
    assert bruno.get("/processos/1").status_code == 404 and bruno.get("/audiencias/1").status_code == 404
    assert bruno.get("/processos/999").status_code == 404   # o que não existe não é tentativa
    de_fora = [(x.acao, x.processo_id) for x in servicos.acessos_da_promotoria(banco, pessoas["bruno"].promotoria_id)
               if x.acao.startswith("negado")]
    assert sorted(de_fora) == [("negado: audiência de fora", None), ("negado: processo de fora", None)]
    # nenhuma rota mostra, altera ou apaga o registro
    assert not [r.path for r in bruno.app.routes if "acesso" in getattr(r, "path", "")]


def test_atos_de_administracao_ficam_no_registro(banco, pessoas):
    caio, pj, outra = pessoas["caio"], pessoas["ana"].promotoria_id, pessoas["bruno"].promotoria_id
    mover_usuario(banco, caio.email, OUTRA, "promotor")
    desligar_usuario(banco, caio.email)
    desligar_usuario(banco, caio.email)   # de novo: nada a registrar
    atos = [(x.promotoria_id, x.acao) for x in banco.query(Acesso).filter_by(usuario_id=caio.id).order_by(Acesso.id)]
    assert atos == [(pj, "administração: entrou como assessor"), (pj, "administração: saiu (movido)"),
                    (outra, "administração: entrou como promotor"), (outra, "administração: desligado")]


def test_o_registro_so_acrescenta_mesmo_para_quem_escreve_no_banco(entrar, banco):
    ana = entrar("ana")
    ana.enviar("/processos/buscar")
    total = banco.query(Acesso).count()
    for comando in ("UPDATE acessos SET acao = 'x'", "DELETE FROM acessos"):
        with pytest.raises(Exception, match="só acrescenta"):
            banco.execute(text(comando))
        banco.rollback()
    assert banco.query(Acesso).count() == total and banco.query(Acesso).filter_by(acao="x").count() == 0


def test_id_de_processo_apagado_nao_e_reaproveitado(banco, pessoas):
    """Achado no parecer de segurança: o registro de acessos passava a apontar para o processo de outra promotoria."""
    motor = type("M", (), {"usa_autos": True, "nome": "ia"})()
    servicos.colar_numeros(banco, pessoas["ana"], NUMERO, motor, True)
    antigo = banco.query(Processo).one().id
    servicos.registrar_acesso(banco, pessoas["ana"], "abriu", banco.get(Processo, antigo))
    assert servicos.apagar_processo(banco, pessoas["ana"], NUMERO)
    servicos.colar_numeros(banco, pessoas["bruno"], NUMERO, motor, True)
    assert banco.query(Processo).one().id != antigo
    # conta desligada não apaga nada, nem linha sem promotoria de banco antigo
    desligar_usuario(banco, "bruno@exemplo.invalid")
    assert not servicos.apagar_processo(banco, pessoas["bruno"], NUMERO)


def test_duas_pessoas_trazendo_a_mesma_fila_ao_mesmo_tempo_nao_viram_erro(banco, pessoas, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    motor = type("M", (), {"usa_autos": True, "nome": "ia"})()
    monkeypatch.setattr(banco, "commit", lambda: (_ for _ in ()).throw(IntegrityError("x", {}, Exception())))
    res = servicos.colar_numeros(banco, pessoas["ana"], NUMERO, motor, True)
    assert res.novos == 0 and "ao mesmo tempo" in res.conferir[0]


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
        criar_promotoria(db, "Terceira")
        mover_usuario(db, "bruno@exemplo.invalid", "Terceira")
        assert servicos.colar_numeros(db, bruno, NUMERO, motor, True).novos == 1
    criar_banco(url, b"k" * 32)   # de novo: nada a converter
    with create_engine(url).connect() as c:
        ddl = c.execute(text("SELECT sql FROM sqlite_master WHERE name = 'processos'")).scalar()
        assert "UNIQUE (promotoria_id, numero)" in ddl and "UNIQUE (usuario_id, numero)" not in ddl
        for tabela in ("processos", "audiencias"):   # o id deixa de ser reaproveitado também no banco antigo
            assert "AUTOINCREMENT" in c.execute(text("SELECT sql FROM sqlite_master WHERE name = :t"),
                                                {"t": tabela}).scalar()
        indice = "SELECT count(*) FROM sqlite_master WHERE name = 'ix_processos_usuario_id'"
        assert c.execute(text(indice)).scalar() == 1


def test_linha_de_comando_cria_move_desliga_e_lista(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NEWMPSC_BANCO", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("NEWMPSC_SEGREDO", "s" * 40)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: SENHA)
    with pytest.raises(SystemExit, match="não há promotoria"):   # nome errado não cria promotoria em silêncio
        cli.main(["criar-usuario", "ana@exemplo.invalid", "Ana Exemplo", PJ])
    cli.main(["criar-promotoria", PJ])
    cli.main(["criar-promotoria", OUTRA])
    with pytest.raises(SystemExit, match="já existe"):
        cli.main(["criar-promotoria", PJ])
    cli.main(["criar-usuario", "ana@exemplo.invalid", "Ana Exemplo", PJ])
    cli.main(["criar-usuario", "caio@exemplo.invalid", "Caio Exemplo", PJ, "assessor"])
    saida = capsys.readouterr().out
    assert "como assessor" in saida and "ana@exemplo.invalid (promotor), caio@exemplo.invalid (assessor)" in saida
    with pytest.raises(SystemExit):
        cli.main(["criar-usuario", "eva@exemplo.invalid", "Eva", PJ, "chefe"])
    cli.main(["mover-usuario", "caio@exemplo.invalid", OUTRA])
    assert f"agora está em {OUTRA}, como assessor" in capsys.readouterr().out
    cli.main(["desligar-usuario", "caio@exemplo.invalid"])
    cli.main(["acessos", PJ])
    assert "administração: saiu (movido)" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="não há promotoria"):
        cli.main(["acessos", "Inexistente"])


def test_so_o_promotor_le_o_registro_e_so_o_da_sua_promotoria(entrar, banco, pessoas):
    """Cartão C20, com o teste de isolamento que o limite 3 exige."""
    ana, caio, bruno = entrar("ana"), entrar("caio"), entrar("bruno")
    caio.enviar("/processos/buscar")
    caio.get("/processos/1")
    bruno.enviar("/processos/colar", {"numeros": "0000301-00.2026.8.24.0000"})
    bruno.get("/processos/10")
    html = ana.get("/registro").text
    assert ">Registro</a>" in html and "Caio Exemplo</strong> abriu" in html and NUMERO in html
    assert "Bruno Exemplo" not in html and "0000301" not in html   # nada da outra promotoria
    de_bruno = bruno.get("/registro").text
    assert "Bruno Exemplo</strong> abriu" in de_bruno and "Caio Exemplo" not in de_bruno and NUMERO not in de_bruno
    # o assessor não lê, e a aba nem aparece para ele; a tentativa fica anotada
    r = caio.get("/registro")
    assert r.status_code == 403 and "Só o promotor lê o registro" in r.text
    assert ">Registro</a>" not in caio.get("/").text
    acoes = [x.acao for x in servicos.acessos_da_promotoria(banco, pessoas["ana"].promotoria_id)]
    assert "negado: ler o registro" in acoes and acoes.count("abriu o registro de acessos") == 1
    # processo apagado: a linha fica, sem número; e a página seguinte não mostra o que já foi visto
    assert servicos.apagar_processo(banco, pessoas["ana"], NUMERO)
    assert "Processo apagado" in ana.get("/registro").text
    ultima = servicos.acessos_da_promotoria(banco, pessoas["ana"].promotoria_id)[-1].id
    assert "Nada registrado antes disso" in ana.get(f"/registro?antes={ultima}").text


def test_linha_do_registro_com_mais_de_um_ano_e_apagada_e_a_recente_fica(entrar, banco, pessoas):
    from datetime import datetime, timedelta
    ana = entrar("ana")
    ana.enviar("/processos/buscar")
    velha = Acesso(usuario_id=pessoas["ana"].id, promotoria_id=pessoas["ana"].promotoria_id, acao="abriu",
                   quando=datetime.now() - timedelta(days=400))
    banco.add(velha)
    banco.commit()
    total = banco.query(Acesso).count()
    assert servicos.apagar_acessos_vencidos(banco, datetime.now()) == 1
    assert banco.query(Acesso).count() == total - 1
    # o prazo vale também para quem escreve direto no banco: linha recente não sai, nem com relógio adiantado
    with pytest.raises(Exception, match="só acrescenta"):
        servicos.apagar_acessos_vencidos(banco, datetime.now() + timedelta(days=800))
    banco.rollback()
    assert banco.query(Acesso).count() == total - 1


def test_o_limite_de_pedidos_a_ia_e_da_promotoria(banco, pessoas, monkeypatch):
    """Cartão C21: promotor e assessor pedem; mais gente na mesa não aumenta o que sai para o serviço de IA."""
    motor = type("M", (), {"usa_autos": True, "nome": "ia"})()
    leitura = type("L", (), {"sha256": "0" * 64, "paginas": [f"Autos {NUMERO}"], "sem_texto": 0, "caracteres": 30})()
    monkeypatch.setattr(servicos, "ESCRITAS_POR_HORA", 2)
    numeros = [f"000040{i}-00.2026.8.24.0000" for i in range(3)]
    servicos.colar_numeros(banco, pessoas["ana"], " ".join(numeros), motor, True)
    servicos.colar_numeros(banco, pessoas["bruno"], numeros[0], motor, True)
    da_pj = banco.query(Processo).filter_by(promotoria_id=pessoas["ana"].promotoria_id).order_by(Processo.id).all()
    de_fora = banco.query(Processo).filter_by(promotoria_id=pessoas["bruno"].promotoria_id).one()
    for p in [*da_pj, de_fora]:
        servicos.juntar_autos(banco, p, "a.pdf", leitura, True, b"k" * 32)

    def pedir(processo, quem):
        tarefa = servicos.pedir_escrita(banco, processo, pessoas[quem], motor, True)
        servicos._fechar_escrita(banco, processo.id, tarefa.chave, "falhou", "x", None, None)

    pedir(da_pj[0], "ana")
    pedir(da_pj[1], "caio")
    with pytest.raises(servicos.EscritaRecusada, match="a promotoria chegou ao limite de pedidos por hora"):
        pedir(da_pj[2], "caio")   # o terceiro pedido da mesa, de quem for
    pedir(de_fora, "bruno")       # o limite de uma promotoria não gasta o da outra


def test_toda_leitura_do_registro_fica_anotada_e_a_tela_le_como_frase(entrar, banco, pessoas):
    """Achados dos pareceres do C20: com `antes` a leitura não deixava rastro; `antes` enorme dava erro 500;
    as ações saíam em jargão; entrada e saída mostravam o horário de trabalho do colega."""
    from datetime import datetime, timedelta
    ana, caio = entrar("ana"), entrar("caio")
    caio.enviar("/processos/buscar")
    for _ in range(3):
        caio.get("/processos/1")
    caio.enviar("/processos/1/entregar")
    lidas = lambda: banco.query(Acesso).filter_by(acao=servicos.LEITURA_DO_REGISTRO).count()   # noqa: E731
    assert ana.get("/registro?antes=2147483647").status_code == 200 and lidas() == 1
    ana.get("/registro")
    assert lidas() == 1   # dez minutos de leitura viram uma linha só
    banco.add(Acesso(usuario_id=pessoas["ana"].id, promotoria_id=pessoas["ana"].promotoria_id, acao="abriu",
                     quando=datetime.now() - timedelta(days=2)))
    banco.commit()
    for errado in ("99999999999999999999999", "0", "-1", "abc"):
        assert ana.get(f"/registro?antes={errado}").status_code == 422
    html = ana.get("/registro").text
    assert "tentou enviar ao SIG" in html and "Barrado" in html and "negado:" not in html
    assert "entrou na promotoria, para preparar minutas" in html and "administração:" not in html
    assert "· 3 vezes" in html and html.count("Caio Exemplo</strong> abriu") == 1
    assert ">Hoje</h2>" in html and (datetime.now() - timedelta(days=2)).strftime("%d/%m/%Y</h2>") in html
    # entrada e saída ficam gravadas, mas não aparecem para o promotor
    assert banco.query(Acesso).filter_by(acao="entrou").count() == 2
    assert "</strong> entrou<" not in html.replace(" <", "<") and "Ver as anteriores" not in html
    assert "Ver as mais recentes" in ana.get("/registro?antes=5").text


def test_com_cem_linhas_exatas_nao_ha_pagina_seguinte_vazia(banco, pessoas):
    for _ in range(100):
        banco.add(Acesso(usuario_id=pessoas["ana"].id, promotoria_id=pessoas["bruno"].promotoria_id, acao="abriu"))
    banco.commit()
    ja = banco.query(Acesso).filter(Acesso.promotoria_id == pessoas["bruno"].promotoria_id,
                                    Acesso.acao.not_in(servicos.FORA_DA_TELA)).count()
    _, mais = servicos.registro_para_o_promotor(banco, pessoas["bruno"], ja)
    assert mais is None
    _, mais = servicos.registro_para_o_promotor(banco, pessoas["bruno"], ja - 1)
    assert mais is not None


def test_limpeza_na_fronteira_do_prazo_e_gatilho_com_dois_processos_subindo(tmp_path):
    """Achados do parecer de qualidade: uma linha vencendo naquele segundo travava a limpeza inteira, e dois
    processos chamando `criar_banco` juntos falhavam ao recriar o gatilho."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta
    url = f"sqlite:///{tmp_path / 'registro.db'}"
    _, Sessao = criar_banco(url, b"k" * 32)
    with ThreadPoolExecutor(8) as varios:
        list(varios.map(lambda _: criar_banco(url, b"k" * 32), range(24)))
    agora = datetime.now()
    with Sessao() as db:
        for dias in (500, 365, 364, 1):
            db.add(Acesso(usuario_id=1, promotoria_id=1, acao="abriu", quando=agora - timedelta(days=dias)))
        db.commit()
        assert servicos.apagar_acessos_vencidos(db, agora) == 2   # 500 e 365 dias; a de 364 ainda não venceu
        assert db.query(Acesso).count() == 2
        with pytest.raises(Exception, match="só acrescenta"):
            db.execute(text("DELETE FROM acessos"))
        db.rollback()
    with create_engine(url).connect() as c:
        gatilhos = set(c.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).scalars())
    assert gatilhos == {"acessos_sem_update", "acessos_so_sai_vencido"}
