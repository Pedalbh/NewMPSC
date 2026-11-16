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
PROMOTORIA = "1ª Promotoria de Justiça (fictícia)"


def _servir(pasta, motor_nome="demo", sig="planilha", **opcoes):
    app = criar_app(Config("teste", "s" * 40, f"sqlite:///{pasta / 'newmpsc.db'}", motor_nome, True, sig=sig),
                    **opcoes)
    with app.state.Sessao() as db:
        criar_usuario(db, "ana@exemplo.invalid", "Ana Exemplo", SENHA, "Promotora de Justiça", PROMOTORIA)
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
def endereco_sig(tmp_path_factory):
    """Servidor com o SIG simulado: a fila chega e a minuta volta sem arquivo."""
    servidor, url = _servir(tmp_path_factory.mktemp("banco-sig"), sig="simulado")
    yield url
    servidor.should_exit = True


@pytest.fixture(scope="module")
def endereco_promotoria(tmp_path_factory):
    """Servidor com o SIG simulado e duas pessoas na mesma promotoria: Ana, promotora, e Caio, assessor."""
    servidor, url = _servir(tmp_path_factory.mktemp("banco-promotoria"), sig="simulado")
    with servidor.config.app.state.Sessao() as db:
        criar_usuario(db, "caio@exemplo.invalid", "Caio Exemplo", SENHA, "Assessor", PROMOTORIA, "assessor")
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
    pg.get_by_text("9 processos novos").wait_for()
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
    sync_api.expect(pg.get_by_role("button", name="Apagar as alterações e escrever")).to_be_visible()

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


def test_envelope_do_sig_simulado(endereco_sig, pagina):
    """O fluxo sem arquivo: buscar a fila no SIG, corrigir a minuta, enviar como rascunho e ver o outro lado."""
    pg = pagina
    pg.set_viewport_size({"width": 1360, "height": 900})
    pg.context.clear_cookies()
    pg.goto(endereco_sig)
    pg.get_by_label("E-mail").fill("ana@exemplo.invalid")
    pg.get_by_label("Senha").fill(SENHA)
    pg.get_by_role("button", name="Entrar").click()
    pg.get_by_text("Use Buscar no SIG simulado").wait_for()
    sync_api.expect(pg.locator(".faixa")).to_contain_text("SIG simulado")
    foto(pg, "16-sig-mesa-vazia")
    # no celular, com a mesa vazia, o botão de buscar fica à vista sem rolar
    pg.set_viewport_size({"width": 390, "height": 800})
    sync_api.expect(pg.get_by_role("button", name="Buscar no SIG simulado")).to_be_in_viewport()
    foto(pg, "16b-sig-celular-mesa-vazia")
    pg.set_viewport_size({"width": 1360, "height": 900})

    # um clique traz a fila, sem exportar nem escolher arquivo
    pg.get_by_role("button", name="Buscar no SIG simulado").click()
    pg.get_by_text("9 processos novos").wait_for()
    assert pg.locator(".fila .proc").count() == 9
    foto(pg, "17-sig-fila")

    # abrir, corrigir e enviar: o rascunho leva a última versão digitada, sem esperar o salvamento automático
    pg.locator(".fila .proc").first.click()
    pg.locator("#folha").wait_for()
    enviar = pg.get_by_role("button", name="Enviar ao SIG simulado")
    sync_api.expect(enviar).to_be_in_viewport()
    sync_api.expect(pg.get_by_role("button", name="Concluir sem enviar ao SIG")).to_be_in_viewport()
    # com trechos a completar, a contagem aparece e o envio não é a ação principal
    sync_api.expect(pg.locator("#trechos")).to_have_text("5 trechos entre colchetes a completar")
    assert "principal" not in enviar.get_attribute("class")
    assert pg.get_by_role("link", name="Baixar em Word").is_hidden()   # a saída por arquivo fica recolhida
    foto(pg, "18-sig-minuta")
    pg.locator("#folha .b-corpo").first.click()
    pg.keyboard.press("End")
    pg.keyboard.type(" Frase do envelope.")
    # a contagem acompanha a digitação: completar um trecho baixa o número
    pg.locator("#folha .b-centro").click()
    pg.keyboard.press("Control+Home")   # início do fecho: "[COMARCA], data da assinatura digital."
    for _ in range(len("[COMARCA]")):
        pg.keyboard.press("Shift+ArrowRight")
    pg.keyboard.type("Cidade Fictícia")
    sync_api.expect(pg.locator("#trechos")).to_have_text("4 trechos entre colchetes a completar")
    perguntas = []
    pg.once("dialog", lambda d: (perguntas.append(d.message), d.dismiss()))
    enviar.click()
    assert "entre colchetes a completar. Enviar ao SIG assim mesmo?" in perguntas[0]
    assert "/processos/" in pg.url   # recusou: continua no processo
    pg.once("dialog", lambda d: d.accept())
    enviar.click()
    pg.get_by_text("como rascunho (recibo SIM-").wait_for()
    sync_api.expect(pg.get_by_text("Falta você assinar e protocolar no SIG.")).to_be_visible()
    sync_api.expect(pg.get_by_role("link", name="Abrir o processo enviado")).to_be_visible()
    assert pg.locator(".fila .proc").count() == 8
    foto(pg, "19-sig-enviada")

    # o outro lado: o SIG simulado mostra o rascunho, sem assinatura, com o texto digitado
    pg.get_by_role("link", name="SIG simulado").click()
    pg.get_by_role("heading", name="Rascunhos recebidos").wait_for()
    assert pg.locator(".recebidas li").count() == 1
    sync_api.expect(pg.locator(".recebidas .selo", has_text="Sem assinatura")).to_be_visible()
    sync_api.expect(pg.locator("#conta-fila")).to_have_text(
        "0 só no SIG · 8 no NewMPSC · 1 com rascunho recebido")
    pg.locator(".recebidas summary").click()
    rascunho = pg.locator(".folha.recebida")
    sync_api.expect(rascunho).to_contain_text("Frase do envelope.")
    # o rascunho chega com a formatação da folha, e não é editável do lado do SIG
    assert rascunho.locator(".b-endereco").evaluate("e => getComputedStyle(e).fontWeight") == "700"
    assert rascunho.locator("[contenteditable]").count() == 0
    assert pg.evaluate("CSS.highlights.get('marca').size") == 4   # os trechos a completar, destacados como na mesa
    foto(pg, "20-sig-outro-lado")
    pg.emulate_media(color_scheme="dark")
    pg.wait_for_timeout(300)   # a troca de tema tem transição de cor
    aba = pg.locator(".aba[aria-current]")
    assert aba.evaluate("e => getComputedStyle(e).backgroundColor != getComputedStyle(e).color")
    foto(pg, "20b-sig-outro-lado-escuro")
    pg.emulate_media(color_scheme="light")
    pg.set_viewport_size({"width": 390, "height": 800})
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    foto(pg, "20c-sig-celular-rascunho")
    pg.set_viewport_size({"width": 1360, "height": 900})

    # na mesa, o processo concluído diz onde está; devolver à fila retira o rascunho
    pg.get_by_role("link", name="Abrir na mesa").click()
    sync_api.expect(pg.locator("#no-sig")).to_contain_text("Falta assinar e protocolar lá.")
    troca = pg.get_by_role("button", name="Trocar o rascunho no SIG")
    sync_api.expect(troca).to_be_visible()
    assert troca.evaluate("e => e.getBoundingClientRect().height") <= 46   # o texto cabe numa linha
    assert pg.locator("#mudou").count() == 0
    # desfazer fica junto do envio, à vista, sem rolar a coluna lateral
    sync_api.expect(pg.get_by_role("button", name="Tirar do SIG e voltar à mesa")).to_be_in_viewport()
    # mexer na minuta depois do envio avisa que o rascunho no SIG ficou para trás
    pg.locator("#folha .b-corpo").first.click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type(" Depois do envio.")
    pg.locator("#estado-salvar", has_text="Salva às").wait_for()
    pg.reload()
    sync_api.expect(pg.locator("#mudou")).to_contain_text("A minuta mudou depois do envio.")
    foto(pg, "21-sig-processo-enviado")
    pg.get_by_role("button", name="Tirar do SIG e voltar à mesa").click()
    pg.get_by_text("O rascunho saiu do SIG simulado.").wait_for()
    pg.get_by_role("link", name="SIG simulado").click()
    pg.get_by_text("Nenhum rascunho recebido").wait_for()

    # celular: sem rolagem lateral nas duas telas novas
    pg.set_viewport_size({"width": 390, "height": 800})
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    foto(pg, "22-sig-celular-outro-lado")
    pg.goto(endereco_sig)
    pg.locator(".fila .proc").first.wait_for()
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    foto(pg, "23-sig-celular-mesa")
    pg.set_viewport_size({"width": 1360, "height": 900})
    assert pg.erros == [], pg.erros


def _entrar(pg, url, email):
    pg.goto(url)
    pg.get_by_label("E-mail").fill(email)
    pg.get_by_label("Senha").fill(SENHA)
    pg.get_by_role("button", name="Entrar").click()
    pg.locator("#promotoria").wait_for()


def test_espaco_da_promotoria(endereco_promotoria, pagina):
    """Cartão C18: o assessor prepara, a promotora confere na mesma mesa e só ela envia. Quem salva por cima de
    uma versão que já mudou é avisado, e o texto da outra pessoa fica."""
    de_ana = pagina
    de_ana.set_viewport_size({"width": 1360, "height": 900})
    de_ana.context.clear_cookies()
    contexto = de_ana.context.browser.new_context(viewport={"width": 1360, "height": 900}, locale="pt-BR")
    contexto.grant_permissions(["clipboard-read", "clipboard-write"])
    de_caio = contexto.new_page()
    erros = []
    de_caio.on("pageerror", lambda e: erros.append(str(e)))

    # o assessor traz a fila e prepara a minuta
    _entrar(de_caio, endereco_promotoria, "caio@exemplo.invalid")
    sync_api.expect(de_caio.locator("#promotoria")).to_have_text(PROMOTORIA)
    de_caio.get_by_role("button", name="Buscar no SIG simulado").click()
    de_caio.get_by_text("9 processos novos").wait_for()
    de_caio.locator(".fila .proc").first.click()
    de_caio.locator("#folha .b-corpo").first.click()
    de_caio.keyboard.press("Control+End")
    de_caio.keyboard.type(" Preparado pelo assessor.")
    de_caio.get_by_text("Salva às").wait_for()
    # ele não envia: a tela diz por quê, e o que ele pode fazer continua à vista
    sync_api.expect(de_caio.locator("#so-promotor")).to_be_visible()
    assert de_caio.locator("#form-entregar").count() == 0
    # concluir tiraria o processo da mesa da promotora: para ele fica recolhido, não é o botão da tela
    sync_api.expect(de_caio.get_by_role("button", name="Concluir sem enviar ao SIG")).to_be_hidden()
    sync_api.expect(de_caio.locator("#concluir-assessor summary")).to_be_visible()
    foto(de_caio, "21-promotoria-assessor")
    de_caio.set_viewport_size({"width": 390, "height": 800})
    assert de_caio.evaluate("document.documentElement.scrollWidth") <= 390
    foto(de_caio, "21b-promotoria-assessor-celular")
    de_caio.set_viewport_size({"width": 1360, "height": 900})

    # a promotora vê a mesma mesa, com o texto dele e quem mexeu por último
    _entrar(de_ana, endereco_promotoria, "ana@exemplo.invalid")
    assert de_ana.locator(".fila .proc").count() == 9
    # na fila ela já vê qual minuta o assessor preparou, sem abrir uma por uma
    sync_api.expect(de_ana.locator(".fila .proc").first).to_contain_text("Editada por Caio")
    assert de_ana.get_by_text("Editada por Caio").count() == 1
    foto(de_ana, "22a-promotoria-fila-da-promotora")
    de_ana.locator(".fila .proc").first.click()
    sync_api.expect(de_ana.locator("#folha")).to_contain_text("Preparado pelo assessor.")
    sync_api.expect(de_ana.locator("#quem-editou")).to_contain_text("Alterada por Caio Exemplo hoje às")
    foto(de_ana, "22-promotoria-promotora-confere")

    # os dois com a mesma minuta aberta: ela salva primeiro; o que ele digita depois não apaga o dela
    de_ana.locator("#folha .b-corpo").first.click()
    de_ana.keyboard.press("Control+End")
    de_ana.keyboard.type(" Conferido pela promotora.")
    de_ana.get_by_text("Salva às").wait_for()
    de_caio.locator("#folha .b-corpo").first.click()
    de_caio.keyboard.type("Por cima. ")
    sync_api.expect(de_caio.locator("#conflito")).to_be_visible()
    sync_api.expect(de_caio.locator("#conflito")).to_be_focused()
    sync_api.expect(de_caio.locator("#estado-salvar")).to_have_text("Não salvou")
    # a folha trava: nada digitado daqui em diante se perde calado; o texto dele sai pelo botão de copiar
    assert de_caio.locator("#folha .b[contenteditable=true]").count() == 0
    de_caio.get_by_role("button", name="Copiar o que escrevi").click()
    sync_api.expect(de_caio.get_by_role("button", name="Copiado")).to_be_visible()
    assert "Por cima." in de_caio.evaluate("navigator.clipboard.readText()")
    nova = de_caio.get_by_role("link", name="Carregar a versão nova")
    assert nova.evaluate("e => e.getBoundingClientRect().height") >= 44
    foto(de_caio, "23-promotoria-conflito")
    de_caio.set_viewport_size({"width": 390, "height": 800})
    sync_api.expect(nova).to_be_in_viewport()
    assert de_caio.evaluate("document.documentElement.scrollWidth") <= 390
    foto(de_caio, "23b-promotoria-conflito-celular")
    de_caio.set_viewport_size({"width": 1360, "height": 900})
    de_caio.emulate_media(color_scheme="dark")
    de_caio.wait_for_timeout(300)   # a troca de tema tem transição de cor
    foto(de_caio, "23c-promotoria-conflito-escuro")
    de_caio.emulate_media(color_scheme="light")
    nova.click()
    sync_api.expect(de_caio.locator("#folha")).to_contain_text("Conferido pela promotora.")
    sync_api.expect(de_caio.locator("#folha")).not_to_contain_text("Por cima.")
    sync_api.expect(de_caio.locator("#conflito")).to_be_hidden()

    # só ela envia; depois do envio, ele vê o rascunho mas não o tira do SIG
    de_ana.once("dialog", lambda d: d.accept())
    de_ana.get_by_role("button", name="Enviar ao SIG simulado").click()
    de_ana.get_by_text("como rascunho (recibo SIM-").wait_for()
    de_caio.goto(endereco_promotoria + "/processos/1")
    sync_api.expect(de_caio.locator("#so-promotor-tira")).to_be_visible()
    assert de_caio.get_by_role("button", name="Tirar do SIG e voltar à mesa").count() == 0
    foto(de_caio, "24-promotoria-assessor-depois-do-envio")
    de_caio.goto(endereco_promotoria + "/configuracoes")
    sync_api.expect(de_caio.locator("#meu-papel")).to_have_text("Prepara as minutas")
    sync_api.expect(de_caio.locator("#minha-promotoria")).to_have_text(PROMOTORIA)
    foto(de_caio, "25-promotoria-seus-dados")
    assert not erros and not de_ana.erros
    contexto.close()
