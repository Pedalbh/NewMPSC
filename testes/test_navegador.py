"""Ensaio de ponta a ponta num navegador de verdade, do jeito que a pessoa usa: entrar, trazer a planilha, abrir a
minuta, editar, baixar o Word, juntar os autos, marcar audiência. DADOS FICTÍCIOS.
Guarda prints em NEWMPSC_PRINTS, se definido."""
import io
import os
import socket
import threading
import time
import zipfile
from pathlib import Path

import pytest
import uvicorn

from app.cli import criar_usuario
from app.config import Config
from app.main import criar_app
from testes.conftest import FILA, RAIZ, SENHA

pytestmark = pytest.mark.navegador
sync_api = pytest.importorskip("playwright.sync_api")
CHROME = os.environ.get("NEWMPSC_CHROME", "")
PRINTS = os.environ.get("NEWMPSC_PRINTS")


def _servir(pasta, motor_nome="demo", **opcoes):
    app = criar_app(Config("teste", "s" * 40, f"sqlite:///{pasta / 'newmpsc.db'}", motor_nome, True), **opcoes)
    with app.state.Sessao() as db:
        criar_usuario(db, "ana@exemplo.invalid", "Ana Exemplo", SENHA, "Promotora de Justiça")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    threading.Thread(target=servidor.run, daemon=True).start()
    for _ in range(100):
        if servidor.started:
            break
        time.sleep(0.05)
    return servidor, f"http://127.0.0.1:{porta}"


@pytest.fixture(scope="module")
def endereco(tmp_path_factory):
    servidor, url = _servir(tmp_path_factory.mktemp("banco"))
    yield url
    servidor.should_exit = True


@pytest.fixture(scope="module")
def endereco_ia(tmp_path_factory):
    """Servidor com o motor de IA ligado a um cliente de mentira, que demora um pouco para responder."""
    from app.motor_claude import MotorClaude
    from testes.test_motor import ClienteFalso

    class ClienteLento(ClienteFalso):
        def _stream(self, **pedido):
            time.sleep(1.5)
            return super()._stream(**pedido)

    resposta = {"relatorio": [{"texto": "A denúncia imputa a Pessoa A a subtração de um objeto.",
                               "fontes": [{"arquivo": 1, "pagina": 1}]},
                              {"texto": "A defesa pede a absolvição.", "fontes": [{"arquivo": 1, "pagina": 3}]}],
                "pontos_a_enfrentar": ["Há prova da autoria?"]}
    servidor, url = _servir(tmp_path_factory.mktemp("banco-ia"), "claude",
                            motor=MotorClaude(ClienteLento(resposta=resposta)))
    yield url
    servidor.should_exit = True


@pytest.fixture(scope="module")
def pagina():
    try:
        with sync_api.sync_playwright() as p:
            opcoes = {"executable_path": CHROME} if CHROME else {}
            navegador = p.chromium.launch(**opcoes)
            contexto = navegador.new_context(viewport={"width": 1360, "height": 900}, locale="pt-BR",
                                             accept_downloads=True)
            contexto.grant_permissions(["clipboard-read", "clipboard-write"])
            pg = contexto.new_page()
            pg.erros = []
            pg.on("console", lambda m: pg.erros.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: pg.erros.append(str(e)))
            yield pg
            navegador.close()
    except sync_api.Error as e:
        if os.environ.get("NEWMPSC_EXIGIR_NAVEGADOR") == "1":
            raise
        pytest.skip(f"navegador indisponível: {e}")


def foto(pg, nome):
    if PRINTS:
        Path(PRINTS).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=f"{PRINTS}/{nome}.png", full_page=True)


def test_jornada_completa(endereco, pagina):
    pg = pagina
    pg.goto(endereco)
    assert pg.url.endswith("/entrar")
    foto(pg, "1-entrar")
    pg.get_by_label("E-mail").fill("ana@exemplo.invalid")
    pg.get_by_label("Senha").fill(SENHA)
    pg.get_by_role("button", name="Entrar").click()
    pg.get_by_text("Sua mesa está limpa").wait_for()
    foto(pg, "2-mesa-vazia")

    # trazer a planilha: escolher o arquivo já envia
    pg.set_input_files("#planilha", str(FILA))
    pg.get_by_text("9 processo(s) novo(s)").wait_for()
    assert pg.locator(".fila .proc").count() == 9
    assert pg.locator(".fila .proc .num").first.inner_text() == "0000101-00.2026.8.24.0000"
    foto(pg, "3-mesa-com-fila")

    # um clique: processo com a minuta pronta
    pg.locator(".fila .proc").first.click()
    pg.locator("#folha").wait_for()
    assert "EXCELENTÍSSIMO" in pg.locator("#folha").inner_text()
    foto(pg, "4-minuta")

    # editar: digitar no fim de um parágrafo, Enter abre outro, salva sozinha
    paragrafo = pg.locator("#folha .b-corpo").first
    paragrafo.click()
    pg.keyboard.press("End")
    pg.keyboard.type(" Frase acrescentada no teste.")
    pg.keyboard.press("Enter")
    pg.keyboard.type("Parágrafo novo do teste.")
    pg.locator("#estado-salvar", has_text="Salva às").wait_for()
    pg.reload()
    texto = pg.locator("#folha").inner_text()
    assert "Frase acrescentada no teste." in texto and "Parágrafo novo do teste." in texto
    foto(pg, "5-minuta-editada")

    # baixar o Word com o texto editado
    # a minuta de demonstração tem trechos entre colchetes: baixar e copiar pedem confirmação
    perguntas = []
    pg.once("dialog", lambda d: (perguntas.append(d.message), d.accept()))
    with pg.expect_download() as d:
        pg.get_by_role("link", name="Baixar para o SIG").click()
    assert "entre colchetes a completar. Baixar assim mesmo?" in perguntas[0]
    assert d.value.suggested_filename == "minuta-0000101-00.2026.8.24.0000.docx"
    xml = zipfile.ZipFile(io.BytesIO(Path(d.value.path()).read_bytes())).read("word/document.xml").decode()
    assert "Parágrafo novo do teste." in xml

    pg.once("dialog", lambda d: d.accept())
    pg.get_by_role("button", name="Copiar texto").click()
    pg.get_by_role("button", name="Copiado").wait_for()
    assert "Parágrafo novo do teste." in pg.evaluate("navigator.clipboard.readText()")

    # autos: escolher o PDF já envia; a tela mostra o que foi lido e deixa remover
    pg.set_input_files("#autos-pdf", str(RAIZ / "dados_ficticios" / "autos-ficticios.pdf"))
    # o resultado e o título do cartão ficam à vista, abaixo do cabeçalho fixo
    resultado = pg.get_by_text("autos-ficticios.pdf: 3 páginas lidas.")
    sync_api.expect(resultado).to_be_in_viewport()
    sync_api.expect(pg.locator("#resultado-autos")).to_be_focused()   # leitor de tela anuncia o resultado
    assert pg.evaluate("document.querySelector('#autos h2').getBoundingClientRect().top >= "
                       "document.querySelector('.topo').getBoundingClientRect().bottom")
    assert pg.locator(".arquivos li").count() == 1
    foto(pg, "5b-autos")
    pg.get_by_role("button", name="Remover autos-ficticios.pdf").click()
    sync_api.expect(pg.get_by_text("Arquivo removido dos autos.")).to_be_in_viewport()
    assert pg.locator(".arquivos li").count() == 0
    # a coluna lateral cabe na janela: o botão de concluir é alcançável com a minuta rolada
    pg.get_by_role("button", name="Marcar como concluído").focus()
    sync_api.expect(pg.get_by_role("button", name="Marcar como concluído")).to_be_in_viewport()
    pg.set_input_files("#autos-pdf", str(RAIZ / "dados_ficticios" / "autos-ficticios.pdf"))
    pg.locator(".arquivos li").wait_for()

    # concluir tira da fila; os autos de processo concluído somem em 30 dias, e a tela diz quando
    endereco = pg.url.split("#")[0]
    pg.get_by_role("button", name="Marcar como concluído").click()
    pg.get_by_text("Processo concluído. A minuta fica; o texto dos autos será apagado em").wait_for()
    assert pg.locator(".fila .proc").count() == 8
    pg.goto(endereco)
    prazo = pg.get_by_text("A minuta fica. O texto destes autos será apagado em")
    sync_api.expect(prazo).to_be_visible()
    foto(pg, "5c-concluido")
    pg.set_viewport_size({"width": 390, "height": 800})
    sync_api.expect(prazo).to_be_visible()
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")   # sem rolagem lateral
    foto(pg, "5c-celular-concluido")
    pg.set_viewport_size({"width": 1360, "height": 900})

    # audiência com ficha
    pg.get_by_role("link", name="Audiências").click()
    pg.get_by_label("Número do processo").fill("0000102-00.2026.8.24.0000")
    pg.get_by_label("Dia", exact=True).fill("2030-03-11")
    pg.get_by_label("Hora", exact=True).fill("14:30")
    pg.get_by_role("button", name="Marcar e preparar a ficha").click()
    pg.locator(".selo", has_text="Ficha pronta").wait_for()
    foto(pg, "6-audiencias")
    pg.locator(".agenda a").first.click()
    pg.get_by_role("heading", name="Perguntas sugeridas").wait_for()
    foto(pg, "7-ficha")

    assert pg.erros == [], pg.erros   # nenhuma violação da política de conteúdo nem erro de script


def test_celular(endereco, pagina):
    pg = pagina
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.goto(endereco)
    pg.locator(".fila .proc").first.wait_for()
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")   # sem rolagem lateral
    foto(pg, "8-celular")
    pg.locator(".fila .proc").first.click()
    pg.locator("#folha").wait_for()
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    foto(pg, "9-celular-minuta")
    # no celular o cabeçalho fixo é mais alto: o resultado do envio continua à vista
    pg.set_input_files("#autos-pdf", str(RAIZ / "dados_ficticios" / "autos-ficticios.pdf"))
    sync_api.expect(pg.get_by_text("autos-ficticios.pdf: 3 páginas lidas")).to_be_in_viewport()
    assert pg.evaluate("document.querySelector('#autos h2').getBoundingClientRect().top >= "
                       "document.querySelector('.topo').getBoundingClientRect().bottom")
    foto(pg, "10-celular-autos")
    # largura de tablet: uma coluna só, e a lateral não vira caixa com rolagem própria
    pg.set_viewport_size({"width": 900, "height": 700})
    pg.reload()
    estilo = ("(() => { const e = getComputedStyle(document.querySelector('.lateral')); "
              "return e.position + ' ' + e.overflowY; })()")
    assert pg.evaluate(estilo) == "static visible"
    foto(pg, "11-tablet")
    pg.set_viewport_size({"width": 1030, "height": 700})   # janela em que a barra de rolagem tiraria a 2ª coluna
    assert pg.evaluate(estilo) == "static visible"
    assert pg.erros == [], pg.erros


def test_relatorio_escrito_pelo_motor_de_ia(endereco_ia, pagina):
    """Enviar os autos, pedir o relatório, esperar na tela e receber a minuta com as páginas citadas."""
    pg = pagina
    pg.set_viewport_size({"width": 1360, "height": 900})
    pg.context.clear_cookies()   # outro servidor no mesmo endereço: a sessão do anterior não vale aqui
    pg.goto(endereco_ia)
    pg.get_by_label("E-mail").fill("ana@exemplo.invalid")
    pg.get_by_label("Senha").fill(SENHA)
    pg.get_by_role("button", name="Entrar").click()
    pg.set_input_files("#planilha", str(FILA))
    pg.get_by_text("prontos para receber os autos").wait_for()
    assert pg.locator(".fila .selo", has_text="Envie os autos").count() == 9
    foto(pg, "12-mesa-ia")
    pg.locator(".fila .proc").first.click()
    assert "[ESCREVER: relatório]" in pg.locator("#folha").inner_text()
    assert pg.get_by_role("button", name="Escrever o relatório").count() == 0
    pg.set_input_files("#autos-pdf", str(RAIZ / "dados_ficticios" / "autos-ficticios.pdf"))
    pg.get_by_role("button", name="Escrever o relatório").click()
    pg.get_by_text("Escrevendo o relatório a partir dos autos").wait_for()
    # enquanto escreve, não há folha, nem como baixar, copiar, enviar ou remover autos
    for some in ("#folha", "#baixar-docx", "#copiar", "#autos-pdf"):
        assert pg.locator(some).count() == 0
    assert pg.get_by_role("button", name="Remover autos-ficticios.pdf").count() == 0
    foto(pg, "13-escrevendo")
    pg.locator("#folha").wait_for(timeout=15000)   # a tela recarrega sozinha quando a escrita termina
    chegada = pg.locator("#resultado-escrita")
    sync_api.expect(chegada).to_be_focused()        # leitor de tela anuncia que o relatório chegou
    sync_api.expect(chegada).to_contain_text("Relatório pronto. O relatório foi escrito por IA")
    folha = pg.locator("#folha").inner_text()
    assert "A denúncia imputa a Pessoa A a subtração de um objeto. (p. 1)" in folha and "[DEFINIR: pedido]" in folha
    assert "Há prova da autoria?" in pg.locator("#pontos").inner_text() and "autoria" not in folha
    assert pg.evaluate("CSS.highlights.get('marca').size") >= 3   # os trechos a completar ficam destacados
    foto(pg, "14-relatorio-de-ia")

    # baixar com trechos a completar pede confirmação; recusando, nada é baixado
    perguntas = []
    pg.once("dialog", lambda d: (perguntas.append(d.message), d.dismiss()))
    pg.get_by_role("link", name="Baixar para o SIG").click()
    assert "trechos entre colchetes a completar. Baixar assim mesmo?" in perguntas[0]
    pg.once("dialog", lambda d: d.accept())
    with pg.expect_download() as d:
        pg.get_by_role("link", name="Baixar para o SIG").click()
    xml = zipfile.ZipFile(io.BytesIO(Path(d.value.path()).read_bytes())).read("word/document.xml").decode()
    assert "subtração de um objeto. (p. 1)" in xml and "autoria" not in xml

    # depois de editar, escrever de novo exige abrir o aviso e confirmar
    pg.locator("#folha .b-corpo").first.click()
    pg.keyboard.type("Edição minha. ")
    pg.locator("#estado-salvar", has_text="Salva às").wait_for()
    pg.reload()
    assert pg.get_by_role("button", name="Escrever de novo").count() == 0
    recolhido = pg.locator("summary", has_text="Escrever o relatório de novo")
    assert recolhido.evaluate("e => getComputedStyle(e).display") == "list-item"   # com o triângulo de abrir
    recolhido.click()
    sync_api.expect(pg.get_by_role("button", name="Apagar minhas alterações e escrever")).to_be_visible()

    # a mesa mostra o estado do relatório
    pg.get_by_role("link", name="‹ Processos").click()
    assert pg.locator(".fila .selo", has_text="Em edição").count() == 1
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.locator(".fila .proc").first.click()
    pg.locator("#folha").wait_for()
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # no celular, o aviso de conferência vem antes da peça
    assert pg.evaluate("document.querySelector('#resultado-escrita').getBoundingClientRect().top < "
                       "document.querySelector('#folha').getBoundingClientRect().top")
    foto(pg, "15-relatorio-celular")
    assert pg.erros == [], pg.erros
