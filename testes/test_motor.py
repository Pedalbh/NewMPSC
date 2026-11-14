"""Motor de IA: o adaptador da API do Claude contra um cliente de mentira (sem rede, sem chave), o pedido de escrita
pela tela e o que acontece quando o serviço falha. DADOS FICTÍCIOS."""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from sqlalchemy import select

from app import servicos
from app.config import Config, carregar
from app.main import criar_app
from app.modelos import TarefaMinuta
from app.motor_claude import MAX_CARACTERES, SISTEMA, MotorClaude
from app.portas import DadosProcesso, MotorIndisponivel, PaginaDosAutos, criar_motor
from testes.conftest import AGORA, SENHA, Cliente
from testes.fabrica_pdf import AUTOS_FICTICIOS, pdf

NUMERO = "0000101-00.2026.8.24.0000"
AUTOS = (PaginaDosAutos("autos.pdf", 1, "Evento 1: denúncia. Pessoa A é acusada de subtrair um objeto."),
         PaginaDosAutos("autos.pdf", 2, ""),
         PaginaDosAutos("laudo.pdf", 1, "Laudo: o objeto foi avaliado."))
PROCESSO = DadosProcesso(NUMERO, "Ação Penal - Procedimento Ordinário", "Roubo", autos=AUTOS)
RESPOSTA = {"relatorio": [{"texto": "A denúncia imputa a Pessoa A a subtração de um objeto.",
                           "fontes": [{"arquivo": 1, "pagina": 1}]},
                          {"texto": "O objeto foi avaliado em laudo.", "fontes": [{"arquivo": 2, "pagina": 1}]}],
            "pontos_a_enfrentar": ["Há prova da autoria?", "Aplica-se o art. 157 do Código Penal?"]}


class Fluxo:
    def __init__(self, mensagem):
        self._mensagem = mensagem

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        return self._mensagem


class ClienteFalso:
    """Imita só o que o adaptador usa: `beta.messages.stream(...)` como contexto com `get_final_message()`."""

    def __init__(self, resposta=None, stop_reason="end_turn", erro=None, texto=None):
        self.pedidos, self._erro, self._stop = [], erro, stop_reason
        self._texto = json.dumps(resposta if resposta is not None else RESPOSTA) if texto is None else texto
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **pedido):
        self.pedidos.append(pedido)
        if self._erro:
            raise self._erro
        return Fluxo(SimpleNamespace(stop_reason=self._stop,
                                     content=[SimpleNamespace(type="thinking", thinking=""),
                                              SimpleNamespace(type="text", text=self._texto)]))


cliente_falso = ClienteFalso


def _erro_da_api(classe, status):
    resposta = httpx2.Response(status, request=httpx2.Request("POST", "https://api.exemplo.invalid/v1/messages"))
    return classe("falha de teste", response=resposta, body=None)


# ---------------------------------------------------------------- adaptador
def test_minuta_traz_o_relatorio_com_a_pagina_de_cada_paragrafo():
    cliente = cliente_falso()
    m = MotorClaude(cliente).elaborar_minuta(PROCESSO)
    textos = [p["texto"] for p in m["paragrafos"]]
    assert m["tipo"] == "Manifestação em ação penal" and m["autos"] == NUMERO
    assert "A denúncia imputa a Pessoa A a subtração de um objeto. (autos.pdf, p. 1)" in textos
    assert "O objeto foi avaliado em laudo. (laudo.pdf, p. 1)" in textos
    assert [p["secao"] for p in m["paragrafos"]].count("RELATÓRIO") == 1


def test_fundamentacao_e_pedido_ficam_com_o_promotor():
    """Limite 5: sem verificação de fontes, o motor não escreve conteúdo jurídico."""
    m = MotorClaude(cliente_falso()).elaborar_minuta(PROCESSO)
    textos = [p["texto"] for p in m["paragrafos"]]
    assert any(t.startswith("[A ESCREVER PELO PROMOTOR]") for t in textos)
    assert "[PONTO] Há prova da autoria?" in textos
    assert "[PONTO] [CITAÇÃO NÃO CONFERIDA] Aplica-se o art. 157 do Código Penal?" in textos
    assert m["pedidos"] == ["[A DEFINIR PELO PROMOTOR]"]


def test_pedido_ao_modelo_leva_os_autos_como_dado_e_nada_alem_do_processo():
    cliente = cliente_falso()
    MotorClaude(cliente, modelo="modelo-de-teste").elaborar_minuta(PROCESSO)
    (pedido,) = cliente.pedidos
    conteudo = pedido["messages"][0]["content"]
    assert pedido["model"] == "modelo-de-teste" and pedido["system"][0]["text"] == SISTEMA
    assert '<pagina arquivo="1" numero="1">' in conteudo and '<pagina arquivo="2" numero="1">' in conteudo
    assert 'numero="2"' not in conteudo                      # página sem texto não é enviada
    assert "autos.pdf" not in conteudo and "laudo.pdf" not in conteudo   # o nome do arquivo não sai do servidor
    assert pedido["output_config"]["format"]["type"] == "json_schema"
    assert pedido["fallbacks"] == "default" and "thinking" not in pedido and "temperature" not in pedido


def test_referencia_a_pagina_que_nao_foi_enviada_e_descartada_e_o_paragrafo_fica_marcado():
    resposta = {"relatorio": [{"texto": "Fato sem lastro.", "fontes": [{"arquivo": 1, "pagina": 99},
                                                                        {"arquivo": 7, "pagina": 1},
                                                                        {"arquivo": 1, "pagina": 2}]},
                              {"texto": "Fato sem fonte.", "fontes": []}],
                "pontos_a_enfrentar": []}
    m = MotorClaude(cliente_falso(resposta=resposta)).elaborar_minuta(PROCESSO)
    textos = [p["texto"] for p in m["paragrafos"]]
    assert "[SEM PÁGINA DOS AUTOS: confira] Fato sem lastro." in textos
    assert "[SEM PÁGINA DOS AUTOS: confira] Fato sem fonte." in textos


def test_texto_dos_autos_que_parece_ordem_nao_muda_a_estrutura_da_minuta():
    """O que o modelo devolve é só texto de parágrafo: mesmo obedecendo a uma ordem escondida nos autos,
    ele não tem campo para pedido nem para fundamentação."""
    resposta = {"relatorio": [{"texto": "Requer-se a absolvição.", "fontes": [{"arquivo": 1, "pagina": 1}]}],
                "pontos_a_enfrentar": [], "pedidos": ["a absolvição sumária"], "tipo": "Alvará de soltura"}
    m = MotorClaude(cliente_falso(resposta=resposta)).elaborar_minuta(PROCESSO)
    assert m["pedidos"] == ["[A DEFINIR PELO PROMOTOR]"] and m["tipo"] == "Manifestação em ação penal"


@pytest.mark.parametrize("processo, motivo", [
    (DadosProcesso(NUMERO, autos=(PaginaDosAutos("a.pdf", 1, ""),)), "não têm texto"),
    (DadosProcesso(NUMERO), "não têm texto"),
    (DadosProcesso(NUMERO, autos=(PaginaDosAutos("a.pdf", 1, "x" * (MAX_CARACTERES + 1)),)), "grandes demais"),
])
def test_autos_sem_texto_ou_grandes_demais_nao_chegam_ao_modelo(processo, motivo):
    cliente = cliente_falso()
    with pytest.raises(MotorIndisponivel, match=motivo):
        MotorClaude(cliente).elaborar_minuta(processo)
    assert cliente.pedidos == []


@pytest.mark.parametrize("falha, motivo", [
    (dict(stop_reason="refusal"), "declinou"),
    (dict(stop_reason="max_tokens"), "incompleta"),
    (dict(texto="isto não é JSON"), "formato inesperado"),
    (dict(texto="[1, 2]"), "formato inesperado"),
    (dict(resposta={"relatorio": [], "pontos_a_enfrentar": []}), "não devolveu relatório"),
    (dict(erro=_erro_da_api(anthropic.AuthenticationError, 401)), "chave da API"),
    (dict(erro=_erro_da_api(anthropic.RateLimitError, 429)), "limite de uso"),
    (dict(erro=_erro_da_api(anthropic.InternalServerError, 500)), "fora do ar"),
    (dict(erro=_erro_da_api(anthropic.BadRequestError, 400)), "recusou o pedido"),
    (dict(erro=anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.exemplo.invalid"))),
     "não foi possível falar"),
])
def test_falha_do_servico_vira_orientacao_e_nunca_meia_minuta(falha, motivo):
    with pytest.raises(MotorIndisponivel, match=motivo):
        MotorClaude(cliente_falso(**falha)).elaborar_minuta(PROCESSO)


def test_ficha_de_audiencia_ainda_nao_e_do_motor_de_ia():
    with pytest.raises(MotorIndisponivel):
        MotorClaude(cliente_falso()).elaborar_ficha(NUMERO, "Custódia")


# ---------------------------------------------------------------- configuração
def test_motor_de_ia_nao_liga_com_dado_real():
    """Cartão C4: texto de processo real não vai para serviço de IA sem contrato institucional."""
    with pytest.raises(RuntimeError, match="só com dados fictícios"):
        carregar({"NEWMPSC_MOTOR": "claude", "NEWMPSC_DADOS_FICTICIOS": "0"})
    config = carregar({"NEWMPSC_MOTOR": "claude", "NEWMPSC_MODELO": "modelo-x"})
    assert config.motor == "claude" and config.modelo == "modelo-x" and config.dados_ficticios


def test_criar_motor(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-ficticia-de-teste")
    motor = criar_motor("claude", "modelo-x")
    assert motor.usa_autos and motor.modelo == "modelo-x" and not criar_motor("demo").usa_autos
    with pytest.raises(RuntimeError, match="motor desconhecido"):
        criar_motor("outro")


# ---------------------------------------------------------------- pela tela
@pytest.fixture
def cliente_ia():
    return cliente_falso()


@pytest.fixture
def app_ia(cliente_ia):
    """Aplicação com o motor de IA de mentira; a escrita roda na hora, dentro do pedido."""
    config = Config("teste", "s" * 40, "sqlite:///:memory:", "claude", True)
    return criar_app(config, agora=lambda: AGORA, motor=MotorClaude(cliente_ia),
                     em_segundo_plano=lambda tarefa, *a: tarefa(*a))


@pytest.fixture
def ana_ia(app_ia):
    from app.cli import criar_usuario
    with app_ia.state.Sessao() as db:
        criar_usuario(db, "ana@exemplo.invalid", "Ana Exemplo", SENHA)
    with Cliente(app_ia) as c:
        c.entrar("ana@exemplo.invalid")
        c.importar_fila()
        yield c


def enviar_autos(c, processo=1):
    return c.enviar(f"/processos/{processo}/autos", files={"autos": ("autos.pdf", pdf(AUTOS_FICTICIOS))})


def test_importar_a_fila_nao_chama_o_modelo(ana_ia, cliente_ia):
    html = ana_ia.get("/processos/1").text
    assert cliente_ia.pedidos == []
    assert "[A ESCREVER] Envie os autos em PDF e peça o relatório" in html
    assert "Escrever o relatório" not in html   # sem autos, o botão não aparece


def test_pedir_a_escrita_com_os_autos_troca_a_minuta_e_avisa_que_e_de_ia(ana_ia, cliente_ia):
    enviar_autos(ana_ia)
    assert "Escrever o relatório" in ana_ia.get("/processos/1").text
    assert ana_ia.enviar("/processos/1/escrever").status_code == 303
    html = ana_ia.get("/processos/1").text
    assert len(cliente_ia.pedidos) == 1 and "Evento 1: denúncia." in cliente_ia.pedidos[0]["messages"][0]["content"]
    assert "A denúncia imputa a Pessoa A a subtração de um objeto. (autos.pdf, p. 1)" in html
    assert "Relatório escrito por IA a partir dos autos. Confira cada página citada" in html
    assert "Claude, não conferido" in html
    assert ana_ia.get("/api/processos/1/escrita").json() == {"estado": "pronta"}


def test_sem_autos_a_escrita_e_recusada_sem_chamar_o_modelo(ana_ia, cliente_ia):
    ana_ia.enviar("/processos/1/escrever")
    assert "A minuta não foi pedida: envie antes os autos em PDF" in ana_ia.get("/processos/1").text
    assert cliente_ia.pedidos == []


def test_falha_do_servico_mantem_a_minuta_e_mostra_o_motivo(app_ia, ana_ia, cliente_ia):
    enviar_autos(ana_ia)
    token = ana_ia.csrf("/")
    ana_ia.put("/api/processos/1/minuta", json={"blocos": [{"texto": "Texto meu.", "estilo": "corpo"}]},
               headers={"X-CSRF-Token": token})
    cliente_ia._erro = _erro_da_api(anthropic.InternalServerError, 503)
    ana_ia.enviar("/processos/1/escrever")
    html = ana_ia.get("/processos/1").text
    assert "A minuta não foi escrita: o serviço de IA está fora do ar" in html and "Texto meu." in html
    assert ana_ia.get("/api/processos/1/escrita").json() == {"estado": "falhou"}


def test_enquanto_escreve_a_tela_espera_e_nao_aceita_edicao_nem_outro_pedido(app_ia, ana_ia):
    enviar_autos(ana_ia)
    enviar_autos(ana_ia, processo=2)
    with app_ia.state.Sessao() as db:   # uma escrita em curso, como se o motor ainda trabalhasse
        servicos.pedir_escrita(db, servicos.processo_do_usuario(db, db.get(servicos.Usuario, 1), 1),
                               app_ia.state.motor)
    html = ana_ia.get("/processos/1").text
    assert 'id="escrevendo"' in html and 'id="folha"' not in html
    assert ana_ia.get("/api/processos/1/escrita").json() == {"estado": "escrevendo"}
    token = ana_ia.csrf("/")
    r = ana_ia.put("/api/processos/1/minuta", json={"blocos": [{"texto": "x", "estilo": "corpo"}]},
                   headers={"X-CSRF-Token": token})
    assert r.status_code == 422 and "sendo escrita" in r.json()["erro"]
    ana_ia.enviar("/processos/2/escrever")
    assert "já há uma minuta sua sendo escrita" in ana_ia.get("/processos/2").text
    assert ana_ia.enviar("/processos/1/refazer").status_code == 409


def test_servidor_que_reinicia_nao_deixa_escrita_presa(tmp_path, cliente_ia):
    from app.cli import criar_usuario
    config = Config("teste", "s" * 40, f"sqlite:///{tmp_path}/b.db", "claude", True)
    nunca = lambda tarefa, *a: None   # noqa: E731 (o servidor "cai" antes de escrever)
    app = criar_app(config, motor=MotorClaude(cliente_ia), em_segundo_plano=nunca)
    with app.state.Sessao() as db:
        criar_usuario(db, "ana@exemplo.invalid", "Ana Exemplo", SENHA)
    with Cliente(app) as c:
        c.entrar("ana@exemplo.invalid")
        c.importar_fila()
        enviar_autos(c)
        c.enviar("/processos/1/escrever")
        assert c.get("/api/processos/1/escrita").json() == {"estado": "escrevendo"}
    app = criar_app(config, motor=MotorClaude(cliente_ia), em_segundo_plano=nunca)
    with app.state.Sessao() as db:
        tarefa = db.scalar(select(TarefaMinuta))
        assert tarefa.estado == "falhou" and "reiniciou" in tarefa.erro


def test_limite_de_pedidos_por_hora(ana_ia, cliente_ia, monkeypatch):
    enviar_autos(ana_ia)
    for _ in range(20):
        ana_ia.enviar("/processos/1/escrever")
    assert len(cliente_ia.pedidos) == 20
    ana_ia.enviar("/processos/1/escrever")
    assert "limite de pedidos por hora" in ana_ia.get("/processos/1").text and len(cliente_ia.pedidos) == 20


def test_escrita_e_estado_de_um_usuario_sao_fechados_para_outro(app_ia, ana_ia, cliente_ia):
    from app.cli import criar_usuario
    enviar_autos(ana_ia)
    with app_ia.state.Sessao() as db:
        criar_usuario(db, "bruno@exemplo.invalid", "Bruno Exemplo", SENHA)
    with Cliente(app_ia) as outro:
        outro.entrar("bruno@exemplo.invalid")
        assert outro.enviar("/processos/1/escrever").status_code == 404
        assert outro.get("/api/processos/1/escrita").status_code == 404
    assert cliente_ia.pedidos == []
    assert ana_ia.post("/processos/1/escrever", follow_redirects=False).status_code == 403   # sem CSRF


def test_motor_de_demonstracao_nao_oferece_a_escrita(logada):
    logada.importar_fila()
    logada.enviar("/processos/1/autos", files={"autos": ("autos.pdf", pdf(AUTOS_FICTICIOS))})
    assert "Escrever o relatório" not in logada.get("/processos/1").text
    logada.enviar("/processos/1/escrever")
    assert "o motor em uso não escreve a partir dos autos" in logada.get("/processos/1").text
