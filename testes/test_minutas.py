"""Minuta: edição, validação e exportação para o Word."""
import io
import zipfile

import pytest

from app.nucleo import documento


@pytest.fixture
def com_fila(logada):
    logada.importar_fila()
    logada.token = logada.csrf("/")
    return logada


def salvar(c, blocos, pid=1):
    return c.put(f"/api/processos/{pid}/minuta", json={"blocos": blocos}, headers={"X-CSRF-Token": c.token})


def test_minuta_abre_pronta_e_marcada_como_demonstracao(com_fila):
    html = com_fila.get("/processos/1").text
    assert "EXCELENTÍSSIMO" in html and "Autos n. 0000101-00.2026.8.24.0000" in html
    assert "[DEMONSTRAÇÃO]" in html and 'contenteditable="true"' in html


def test_salvar_edicao(com_fila):
    r = salvar(com_fila, [{"texto": "  Parágrafo novo.  ", "estilo": "corpo"}, {"texto": "", "estilo": "corpo"}])
    assert r.status_code == 200 and r.json()["paragrafos"] == 1
    assert "Parágrafo novo." in com_fila.get("/processos/1").text
    assert "Em edição" in com_fila.get("/").text


@pytest.mark.parametrize("blocos", [
    None, [], "texto", [{"texto": "x", "estilo": "inventado"}], [{"texto": 3, "estilo": "corpo"}],
    [{"texto": "x" * 6001, "estilo": "corpo"}], [{"texto": "   ", "estilo": "corpo"}],
    [{"texto": "x", "estilo": "corpo"}] * 401,
])
def test_salvar_recusa_formato_invalido(com_fila, blocos):
    assert salvar(com_fila, blocos).status_code == 422


def test_docx_e_um_word_valido_com_o_texto_editado(com_fila):
    salvar(com_fila, [{"texto": "MM. Juízo", "estilo": "endereco"}, {"texto": "A & B < C", "estilo": "corpo"}])
    r = com_fila.get("/processos/1/minuta.docx")
    assert r.status_code == 200 and "minuta-0000101-00.2026.8.24.0000.docx" in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert z.testzip() is None
        xml = z.read("word/document.xml").decode()
    assert "A &amp; B &lt; C" in xml and 'w:ascii="Arial"' in xml and 'w:firstLine="1701"' in xml


def test_texto_simples(com_fila):
    salvar(com_fila, [{"texto": "Um.", "estilo": "corpo"}, {"texto": "Dois.", "estilo": "corpo"}])
    assert com_fila.get("/processos/1/minuta.txt").text == "Um.\n\nDois.\n"


def test_refazer_substitui_a_edicao(com_fila):
    salvar(com_fila, [{"texto": "Texto meu.", "estilo": "corpo"}])
    com_fila.enviar("/processos/1/refazer", pagina="/processos/1")
    html = com_fila.get("/processos/1").text
    assert "Texto meu." not in html and "EXCELENTÍSSIMO" in html


def test_folha_monta_pedidos_em_alineas():
    m = {"enderecamento": "E", "autos": "N", "paragrafos": [{"secao": "S", "texto": "T"}],
         "pedidos": ["um;", "dois.", "três"], "fecho": "F", "verbo": "requer"}
    textos = [b["texto"] for b in documento.folha(m)]
    assert textos[-4:-1] == ["a) um;", "b) dois; e", "c) três."]
    assert textos[-5].endswith("requer:") and textos[-1] == "F"


def test_caracteres_de_controle_nao_quebram_o_word():
    blocos = documento.normalizar([{"texto": "a\x00b\x0bc", "estilo": "corpo"}])
    assert blocos[0]["texto"] == "abc"
    zipfile.ZipFile(io.BytesIO(documento.docx(blocos))).read("word/document.xml").decode()
