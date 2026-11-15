"""SIG simulado: a fila chega com um clique e a minuta volta como rascunho, sem arquivo. DADOS FICTÍCIOS.
Nada aqui fala com o SIG de verdade: o adaptador só existe em ambiente de dados fictícios."""
import pytest

from app.config import Config, carregar
from app.main import criar_app
from app.modelos import EntregaSig, Processo
from app.portas import ConexaoPlanilha, ConexaoSigSimulado, criar_conexao
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
    assert "9 processo(s) novo(s)" in html
    ordem = numeros_na_ordem(html)
    assert len(ordem) == 9 and ordem[0] == "0000101-00.2026.8.24.0000"


def test_buscar_de_novo_nao_duplica_nem_apaga_edicao(logada):
    logada.enviar("/processos/buscar")
    logada.put("/api/processos/1/minuta", json={"blocos": [{"texto": "Texto meu.", "estilo": "corpo"}]},
               headers={"X-CSRF-Token": logada.csrf("/")})
    logada.enviar("/processos/buscar")
    html = logada.get("/").text
    assert "9 já estava(m) na fila" in html and len(numeros_na_ordem(html)) == 9
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
    assert "No SIG, para assinar" in logada.get("/?ver=concluido").text
    entrega = banco.query(EntregaSig).one()
    assert entrega.texto.strip() == "Manifestação pronta." and entrega.pendentes == 0
    assert entrega.recibo.startswith("SIM-") and entrega.recebida_em == AGORA
    assert banco.get(Processo, 1).situacao == "concluido"
    do_outro_lado = logada.get("/sig-simulado").text
    assert "Manifestação pronta." in do_outro_lado and entrega.recibo in do_outro_lado
    assert "Sem assinatura" in do_outro_lado


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
    logada.enviar("/processos/1/entregar")   # já concluído: troca o rascunho, não duplica
    assert banco.query(EntregaSig).count() == 1


def test_cada_usuario_so_ve_e_so_envia_o_que_e_seu(logada, app, bruno, banco):
    logada.enviar("/processos/buscar")
    logada.enviar("/processos/1/entregar")
    recibo = banco.query(EntregaSig).one().recibo
    with Cliente(app) as outro:
        outro.entrar(bruno.email, SENHA)
        assert recibo not in outro.get("/sig-simulado").text
        assert "0 de 9" in outro.get("/sig-simulado").text   # a fila dele ainda não foi buscada
        assert outro.enviar("/processos/1/entregar").status_code == 404
        outro.enviar("/processos/buscar")
        assert banco.query(Processo).count() == 18           # a fila de cada um é de cada um
    assert banco.query(EntregaSig).count() == 1


def test_enviar_exige_sessao_e_csrf(cliente, logada):
    logada.enviar("/processos/buscar")
    assert logada.post("/processos/1/entregar", data={"csrf": "errado"}, follow_redirects=False).status_code == 403
    assert logada.post("/processos/buscar", data={"csrf": "errado"}, follow_redirects=False).status_code == 403


def test_minuta_sendo_escrita_nao_e_enviada(logada, banco):
    from app.modelos import TarefaMinuta
    logada.enviar("/processos/buscar")
    banco.add(TarefaMinuta(processo_id=1, iniciada_em=__import__("datetime").datetime.now()))
    banco.commit()
    assert logada.enviar("/processos/1/entregar").status_code == 409
    assert banco.query(EntregaSig).count() == 0


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
    with pytest.raises(RuntimeError, match="NEWMPSC_SIG inválido"):
        carregar({"NEWMPSC_SIG": "oficial"})
    # a trava vale também para quem monta a aplicação sem passar pela leitura do ambiente
    with pytest.raises(RuntimeError, match="SIG simulado só com dados fictícios"):
        criar_app(Config("teste", "s" * 40, "sqlite:///:memory:", "demo", False, sig="simulado"))


def test_adaptadores():
    assert isinstance(criar_conexao("planilha"), ConexaoPlanilha) and not ConexaoPlanilha.busca_direta
    simulado = criar_conexao("simulado")
    assert isinstance(simulado, ConexaoSigSimulado) and simulado.busca_direta
    fila = simulado.buscar_fila()
    assert len(fila["linhas"]) == 9
    assert not any(linha["dv_ok"] for linha in fila["linhas"])   # só números fictícios
    with pytest.raises(RuntimeError, match="conexão desconhecida"):
        criar_conexao("oficial")
    with pytest.raises(NotImplementedError):
        ConexaoPlanilha().buscar_fila()
