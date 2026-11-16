"""SIG simulado: a fila chega com um clique e a minuta volta como rascunho, sem arquivo. DADOS FICTÍCIOS.
Nada aqui fala com o SIG de verdade: o adaptador só existe em ambiente de dados fictícios."""
from pathlib import Path

import pytest

from app import servicos
from app.cli import criar_usuario
from app.config import Config, carregar
from app.main import criar_app
from app.modelos import EntregaSig, Processo, Usuario
from app.nucleo.tabela import dv_ok
from app.portas import ConexaoPlanilha, ConexaoSigSimulado, SigIndisponivel, criar_conexao, criar_motor
from testes.conftest import AGORA, SENHA, Cliente
from testes.test_processos import numeros_na_ordem


@pytest.fixture
def app():
    config = Config(ambiente="teste", segredo="s" * 40, banco_url="sqlite:///:memory:", motor="demo",
                    dados_ficticios=True, sig="simulado")
    return criar_app(config, agora=lambda: AGORA)


def test_buscar_traz_a_fila_ordenada_sem_arquivo(logada):
    assert "Buscar no SIG" in logada.get("/").text
    assert logada.enviar("/processos/buscar").status_code == 303
    html = logada.get("/").text
    assert "9 processos novos" in html
    ordem = numeros_na_ordem(html)
    assert len(ordem) == 9 and ordem[0] == "0000101-00.2026.8.24.0000"


def test_buscar_de_novo_nao_duplica_nem_apaga_edicao(logada):
    logada.enviar("/processos/buscar")
    logada.put("/api/processos/1/minuta", json={"blocos": [{"texto": "Texto meu.", "estilo": "corpo"}]},
               headers={"X-CSRF-Token": logada.csrf("/")})
    logada.enviar("/processos/buscar")
    html = logada.get("/").text
    assert "9 já estavam na fila" in html and len(numeros_na_ordem(html)) == 9
    assert "Texto meu." in logada.get("/processos/1").text


def test_enviar_ao_sig_guarda_o_rascunho_e_conclui(logada, banco):
    logada.enviar("/processos/buscar")
    logada.put("/api/processos/1/minuta", json={"blocos": [{"texto": "Manifestação pronta.", "estilo": "corpo"}]},
               headers={"X-CSRF-Token": logada.csrf("/")})
    r = logada.enviar("/processos/1/entregar")
    assert r.status_code == 303 and r.headers["location"] == "/"
    html = logada.get("/").text
    assert "foi para o SIG simulado como rascunho" in html and "assinar e protocolar" in html
    assert len(numeros_na_ordem(html)) == 8
    assert "Falta assinar no SIG" in logada.get("/?ver=concluido").text
    entrega = banco.query(EntregaSig).one()
    assert entrega.texto.strip() == "Manifestação pronta." and entrega.pendentes == 0
    assert entrega.recibo.startswith("SIM-") and entrega.recebida_em == AGORA
    assert banco.get(Processo, 1).situacao == "concluido"
    do_outro_lado = logada.get("/sig-simulado").text
    assert "Manifestação pronta." in do_outro_lado and entrega.recibo in do_outro_lado
    assert "Sem assinatura" in do_outro_lado
    assert "0 só no SIG · 8 no NewMPSC · 1 com rascunho recebido" in do_outro_lado
    assert "contenteditable" not in do_outro_lado   # do lado do SIG, o rascunho só é lido


def test_rascunho_com_trechos_a_completar_vai_marcado(logada, banco):
    logada.enviar("/processos/buscar")
    logada.enviar("/processos/1/entregar")   # a minuta de demonstração tem colchetes
    assert banco.query(EntregaSig).one().pendentes >= 3
    assert "a completar" in logada.get("/").text
    assert "a completar" in logada.get("/sig-simulado").text


def test_devolver_a_fila_retira_o_rascunho_e_enviar_de_novo_troca(logada, banco):
    logada.enviar("/processos/buscar")
    logada.enviar("/processos/1/entregar")
    logada.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    assert banco.query(EntregaSig).count() == 0
    assert "O rascunho saiu do SIG simulado" in logada.get("/processos/1").text
    logada.enviar("/processos/1/entregar")
    assert "O processo saiu da sua mesa" in logada.get("/").text
    logada.enviar("/processos/1/entregar")   # já concluído: troca o rascunho, não duplica
    aviso = logada.get("/").text
    assert "O rascunho anterior foi substituído." in aviso and "saiu da sua mesa" not in aviso
    assert banco.query(EntregaSig).count() == 1


def test_cada_usuario_so_ve_e_so_envia_o_que_e_seu(logada, app, bruno, banco):
    logada.enviar("/processos/buscar")
    logada.enviar("/processos/1/entregar")
    recibo = banco.query(EntregaSig).one().recibo
    with Cliente(app) as outro:
        outro.entrar(bruno.email, SENHA)
        assert recibo not in outro.get("/sig-simulado").text
        assert "9 só no SIG · 0 no NewMPSC · 0 com rascunho" in outro.get("/sig-simulado").text
        assert outro.enviar("/processos/1/entregar").status_code == 404
        outro.enviar("/processos/buscar")
        assert banco.query(Processo).count() == 18           # a fila de cada um é de cada um
    assert banco.query(EntregaSig).count() == 1


def test_enviar_exige_sessao_e_csrf(app, logada):
    logada.enviar("/processos/buscar")
    with Cliente(app) as anonimo:   # sem sessão: vai para o login, e nada é enviado
        for caminho in ("/processos/buscar", "/processos/1/entregar"):
            r = anonimo.enviar(caminho, pagina="/entrar")
            assert r.status_code == 303 and r.headers["location"] == "/entrar"
        assert anonimo.get("/sig-simulado", follow_redirects=False).headers["location"] == "/entrar"
    assert logada.post("/processos/1/entregar", data={"csrf": "errado"}, follow_redirects=False).status_code == 403
    assert logada.post("/processos/buscar", data={"csrf": "errado"}, follow_redirects=False).status_code == 403


def test_minuta_sendo_escrita_nao_e_enviada(logada, banco):
    from app.modelos import TarefaMinuta
    logada.enviar("/processos/buscar")
    banco.add(TarefaMinuta(processo_id=1, iniciada_em=__import__("datetime").datetime.now()))
    banco.commit()
    assert logada.enviar("/processos/1/entregar").status_code == 409
    assert banco.query(EntregaSig).count() == 0


def test_rascunho_e_copia_e_a_tela_avisa_quando_a_minuta_muda_depois(logada, banco):
    logada.enviar("/processos/buscar")
    logada.enviar("/processos/1/entregar")
    pagina = logada.get("/processos/1").text
    assert "Trocar o rascunho no SIG" in pagina and 'id="mudou"' not in pagina
    logada.put("/api/processos/1/minuta", json={"blocos": [{"texto": "Versão nova.", "estilo": "corpo"}]},
               headers={"X-CSRF-Token": logada.csrf("/")})
    assert "Versão nova." not in banco.query(EntregaSig).one().texto   # o rascunho no SIG é o que foi enviado
    assert "A minuta mudou depois do envio." in logada.get("/processos/1").text
    logada.enviar("/processos/1/entregar")
    banco.expire_all()
    assert banco.query(EntregaSig).one().texto == "Versão nova."
    assert 'id="mudou"' not in logada.get("/processos/1").text


def test_um_processo_novo_no_singular(logada):
    logada.enviar("/processos/colar", {"numeros": "0000201-00.2026.8.24.0000"})
    assert "1 processo novo, com a primeira minuta pronta." in logada.get("/").text
    logada.enviar("/processos/colar", {"numeros": "0000201-00.2026.8.24.0000"})
    assert "1 já estava na fila." in logada.get("/").text


def test_a_porta_recebe_quem_pede_e_quem_envia():
    """A integração oficial age com a identidade da pessoa: a aplicação já passa quem é."""
    vistos = []

    class Anota(ConexaoSigSimulado):
        def buscar_fila(self, quem):
            vistos.append(("fila", quem))
            return super().buscar_fila(quem)

        def entregar_rascunho(self, quem, numero, texto):
            vistos.append(("rascunho", quem, numero))
            return super().entregar_rascunho(quem, numero, texto)

    config = Config("teste", "s" * 40, "sqlite:///:memory:", "demo", True, sig="simulado")
    outra = criar_app(config, agora=lambda: AGORA, conexao=Anota())
    with outra.state.Sessao() as db:
        criar_usuario(db, "dora@exemplo.invalid", "Dora Exemplo", SENHA)
    with Cliente(outra) as c:
        c.entrar("dora@exemplo.invalid", SENHA)
        c.enviar("/processos/buscar")
        c.enviar("/processos/1/entregar")
    assert vistos == [("fila", "dora@exemplo.invalid"),
                      ("rascunho", "dora@exemplo.invalid", "0000101-00.2026.8.24.0000")]


def test_numero_real_nao_e_enviado_em_servidor_de_dados_ficticios(logada, banco):
    real = next(n for n in (f"0000301-{dv:02d}.2026.8.24.0000" for dv in range(100)) if dv_ok(n))
    # a colagem já recusa número real; este é o caso do processo que entrou antes da recusa existir
    servicos.colar_numeros(banco, banco.query(Usuario).one(), real, criar_motor("demo"), False)
    r = logada.enviar("/processos/1/entregar")
    assert r.status_code == 409 and "só aceita dados fictícios" in r.text
    assert banco.query(EntregaSig).count() == 0 and banco.get(Processo, 1).situacao == "a_fazer"


def test_dois_envios_ao_mesmo_tempo_nao_viram_erro_interno(tmp_path):
    """Achado na revisão: duas abas enviando o mesmo processo; a segunda gravação batia na restrição única."""
    config = Config("teste", "s" * 40, f"sqlite:///{tmp_path / 'corrida.db'}", "demo", True, sig="simulado")
    app = criar_app(config, agora=lambda: AGORA)
    conexao = ConexaoSigSimulado()
    with app.state.Sessao() as db:
        ana = criar_usuario(db, "ana@exemplo.invalid", "Ana Exemplo", SENHA)
        servicos.buscar_fila(db, ana, conexao, app.state.motor, True)
    with app.state.Sessao() as a, app.state.Sessao() as b:
        pa, pb = a.get(Processo, 1), b.get(Processo, 1)
        assert pa.entrega is None and pb.entrega is None   # as duas leram antes de qualquer gravação
        servicos.entregar_ao_sig(a, pa, a.get(Usuario, ana.id), conexao, AGORA, True)
        with pytest.raises(ValueError, match="já estava sendo enviado"):
            servicos.entregar_ao_sig(b, pb, b.get(Usuario, ana.id), conexao, AGORA, True)
    with app.state.Sessao() as db:
        assert db.query(EntregaSig).count() == 1 and db.get(Processo, 1).situacao == "concluido"


class SigForaDoAr(ConexaoSigSimulado):
    def buscar_fila(self, quem):
        raise SigIndisponivel

    def entregar_rascunho(self, quem, numero, texto):
        raise SigIndisponivel


def test_sig_fora_do_ar_orienta_e_nao_muda_nada(banco, ana):
    config = Config("teste", "s" * 40, "sqlite:///:memory:", "demo", True, sig="simulado")
    fora = criar_app(config, agora=lambda: AGORA, conexao=SigForaDoAr())
    with fora.state.Sessao() as db:
        criar_usuario(db, "carla@exemplo.invalid", "Carla Exemplo", SENHA)
    with Cliente(fora) as c:
        c.entrar("carla@exemplo.invalid", SENHA)
        assert c.enviar("/processos/buscar").status_code == 303
        html = c.get("/").text
        assert "O SIG simulado não respondeu. Nada mudou na sua mesa." in html and "use a planilha exportada" in html
        assert c.get("/sig-simulado").status_code == 503
        c.importar_fila()   # a planilha continua servindo
        r = c.enviar("/processos/1/entregar")
        assert r.headers["location"] == "/processos/1"
        pagina = c.get("/processos/1").text
        assert "A minuta não foi enviada e continua aqui." in pagina and "Baixar ou copiar" in pagina
    with fora.state.Sessao() as db:
        assert db.query(EntregaSig).count() == 0 and db.get(Processo, 1).situacao == "a_fazer"


class TestComPlanilha:
    """Sem o SIG simulado (o padrão), nada da busca direta existe."""

    @pytest.fixture
    def app(self):
        config = Config(ambiente="teste", segredo="s" * 40, banco_url="sqlite:///:memory:", motor="demo",
                        dados_ficticios=True)
        return criar_app(config, agora=lambda: AGORA)

    def test_rotas_da_busca_direta_nao_existem(self, logada):
        html = logada.get("/").text
        assert "Buscar no SIG" not in html and "SIG simulado" not in html
        logada.importar_fila()
        assert logada.enviar("/processos/buscar").status_code == 404
        assert logada.enviar("/processos/1/entregar").status_code == 404
        assert logada.get("/sig-simulado").status_code == 404
        assert "Enviar ao SIG" not in logada.get("/processos/1").text


def test_sig_simulado_so_com_dados_ficticios():
    assert carregar({"NEWMPSC_SIG": "simulado"}).sig == "simulado"
    assert carregar({}).sig == "planilha"
    with pytest.raises(RuntimeError, match="SIG simulado só com dados fictícios"):
        carregar({"NEWMPSC_SIG": "simulado", "NEWMPSC_DADOS_FICTICIOS": "0"})
    # a trava depende deste valor: só 0 ou 1; "false", vazio ou espaço não passam por "fictício"
    for errado in ("false", "FALSE", "no", "nao", "", "0 ", " 1", "2"):
        with pytest.raises(RuntimeError, match="NEWMPSC_DADOS_FICTICIOS inválido"):
            carregar({"NEWMPSC_DADOS_FICTICIOS": errado, "NEWMPSC_SIG": "simulado", "NEWMPSC_MOTOR": "claude"})
    assert carregar({"NEWMPSC_DADOS_FICTICIOS": "0"}).dados_ficticios is False
    assert carregar({"NEWMPSC_DADOS_FICTICIOS": "1"}).dados_ficticios is True
    with pytest.raises(RuntimeError, match="NEWMPSC_SIG inválido"):
        carregar({"NEWMPSC_SIG": "oficial"})
    # a trava vale também para quem monta a aplicação sem passar pela leitura do ambiente
    with pytest.raises(RuntimeError, match="SIG simulado só com dados fictícios"):
        criar_app(Config("teste", "s" * 40, "sqlite:///:memory:", "demo", False, sig="simulado"))


def test_adaptadores():
    assert isinstance(criar_conexao("planilha"), ConexaoPlanilha) and not ConexaoPlanilha.busca_direta
    simulado = criar_conexao("simulado")
    assert isinstance(simulado, ConexaoSigSimulado) and simulado.busca_direta
    fila = simulado.buscar_fila("ana@exemplo.invalid")
    assert len(fila["linhas"]) == 9
    assert not any(linha["dv_ok"] for linha in fila["linhas"])   # só números fictícios
    with pytest.raises(RuntimeError, match="conexão desconhecida"):
        criar_conexao("oficial")
    with pytest.raises(NotImplementedError):
        ConexaoPlanilha().buscar_fila("ana@exemplo.invalid")
    with pytest.raises(SigIndisponivel):   # arquivo da fila ausente não vira erro interno
        ConexaoSigSimulado(Path("nao-existe.csv")).buscar_fila("ana@exemplo.invalid")
