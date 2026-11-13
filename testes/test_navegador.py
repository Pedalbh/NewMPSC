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


@pytest.fixture(scope="module")
def endereco(tmp_path_factory):
    banco = tmp_path_factory.mktemp("banco") / "newmpsc.db"
    app = criar_app(Config("teste", "s" * 40, f"sqlite:///{banco}", "demo", True))
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
    yield f"http://127.0.0.1:{porta}"
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
    with pg.expect_download() as d:
        pg.get_by_role("link", name="Baixar para o SIG").click()
    assert d.value.suggested_filename == "minuta-0000101-00.2026.8.24.0000.docx"
    xml = zipfile.ZipFile(io.BytesIO(Path(d.value.path()).read_bytes())).read("word/document.xml").decode()
    assert "Parágrafo novo do teste." in xml

    pg.get_by_role("button", name="Copiar texto").click()
    pg.get_by_role("button", name="Copiado").wait_for()
    assert "Parágrafo novo do teste." in pg.evaluate("navigator.clipboard.readText()")

    # autos: escolher o PDF já envia; a tela mostra o que foi lido e deixa remover
    pg.set_input_files("#autos-pdf", str(RAIZ / "dados_ficticios" / "autos-ficticios.pdf"))
    pg.get_by_text("autos-ficticios.pdf: 3 página(s) lida(s).").wait_for()
    assert pg.locator(".arquivos li").count() == 1
    foto(pg, "5b-autos")
    pg.get_by_role("button", name="Remover autos-ficticios.pdf").click()
    pg.get_by_text("Arquivo removido dos autos.").wait_for()
    assert pg.locator(".arquivos li").count() == 0
    pg.set_input_files("#autos-pdf", str(RAIZ / "dados_ficticios" / "autos-ficticios.pdf"))
    pg.locator(".arquivos li").wait_for()

    # concluir tira da fila
    pg.get_by_role("button", name="Marcar como concluído").click()
    pg.get_by_text("Processo concluído.").wait_for()
    assert pg.locator(".fila .proc").count() == 8

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
