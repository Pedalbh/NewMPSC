"""Autos em PDF: leitura isolada, recusas, guarda só do texto, isolamento por usuário. DADOS FICTÍCIOS."""
import io

import pytest
from sqlalchemy import func, select

from app import autos
from app import main as rotas
from app.modelos import ArquivoAutos, PaginaAutos, Processo
from testes.fabrica_pdf import AUTOS_FICTICIOS, pdf

NUMERO = "0000101-00.2026.8.24.0000"   # primeiro da fila fictícia (processo 1)
PDF = pdf(AUTOS_FICTICIOS)


def enviar_pdf(cliente, dados=PDF, nome="autos.pdf", processo=1):
    return cliente.enviar(f"/processos/{processo}/autos", files={"autos": (nome, dados)})


def contar(banco, modelo) -> int:
    return banco.scalar(select(func.count()).select_from(modelo))


def numero_real() -> str:
    """Número com dígito verificador válido, calculado na hora (nenhum número real fica escrito no repositório)."""
    resto = int("0000001" + "2026" + "8" + "24" + "0000") * 100 % 97
    return f"0000001-{98 - resto:02d}.2026.8.24.0000"


@pytest.fixture
def com_fila(logada):
    logada.importar_fila()
    return logada


# ---------------------------------------------------------------- leitura
def test_le_o_texto_de_cada_pagina_e_conta_as_sem_texto():
    leitura = autos.ler(pdf(AUTOS_FICTICIOS + [""]))
    assert len(leitura.paginas) == 4 and leitura.sem_texto == 1
    assert "denúncia" in leitura.paginas[0] and NUMERO in leitura.paginas[0]
    assert leitura.paginas[2].startswith("Evento 3") and leitura.tamanho > 0 and len(leitura.sha256) == 64


def test_arquivo_ficticio_do_repositorio_e_o_da_fabrica():
    from testes.conftest import RAIZ
    assert (RAIZ / "dados_ficticios" / "autos-ficticios.pdf").read_bytes() == PDF


@pytest.mark.parametrize("dados, motivo", [
    (b"", "vazio"),
    (b"PK\x03\x04 isto e um zip", "não é um PDF"),
    (b"%PDF-1.4\nlixo sem estrutura", "danificado"),
    (pdf([]), "não tem páginas"),
])
def test_recusa_o_que_nao_e_pdf_legivel(dados, motivo):
    with pytest.raises(autos.PdfRecusado, match=motivo):
        autos.ler(dados)


def test_recusa_pdf_com_senha():
    from pypdf import PdfReader, PdfWriter
    escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(PDF)))
    escritor.encrypt("senha-ficticia", algorithm="RC4-128")
    protegido = io.BytesIO()
    escritor.write(protegido)
    with pytest.raises(autos.PdfRecusado, match="protegido por senha"):
        autos.ler(protegido.getvalue())


def test_recusa_por_tamanho_paginas_e_tempo(monkeypatch):
    monkeypatch.setattr(autos, "MAX_PAGINAS", 2)
    with pytest.raises(autos.PdfRecusado, match="3 páginas; o limite é 2"):
        autos.ler(PDF)
    monkeypatch.setattr(autos, "TEMPO", 0.001)
    with pytest.raises(autos.PdfRecusado, match="demorou demais"):
        autos.ler(PDF)
    monkeypatch.setattr(autos, "TETO_PDF", 100)
    with pytest.raises(autos.PdfRecusado, match="passa de"):
        autos.ler(PDF)


def test_leitura_roda_sem_os_segredos_da_aplicacao(monkeypatch):
    """O processo que abre o PDF não herda o ambiente (segredo da sessão, chaves)."""
    chamadas = {}
    original = autos.subprocess.run

    def espiar(*a, **kw):
        chamadas.update(kw)
        return original(*a, **kw)

    monkeypatch.setenv("NEWMPSC_SEGREDO", "s" * 40)
    monkeypatch.setattr(autos.subprocess, "run", espiar)
    autos.ler(PDF)
    assert "NEWMPSC_SEGREDO" not in chamadas["env"] and chamadas["timeout"] == autos.TEMPO


# ---------------------------------------------------------------- envio pela tela
def test_enviar_pdf_guarda_o_texto_por_pagina(com_fila, banco):
    assert enviar_pdf(com_fila).status_code == 303
    html = com_fila.get("/processos/1").text
    assert "autos.pdf: 3 página(s) lida(s)." in html and "3 página(s)</span>" in html
    arquivo = banco.scalar(select(ArquivoAutos))
    assert (arquivo.nome, arquivo.total_paginas, arquivo.sem_texto, arquivo.tamanho) == ("autos.pdf", 3, 0, len(PDF))
    assert [p.numero for p in arquivo.paginas] == [1, 2, 3] and "resposta à acusação" in arquivo.paginas[2].texto
    # só o texto fica: nenhuma coluna guarda o arquivo original
    assert not any(c.type.python_type is bytes for t in (ArquivoAutos, PaginaAutos) for c in t.__table__.columns)


def test_varios_arquivos_de_uma_vez_e_repetido_nao_duplica(com_fila, banco):
    outro = pdf([f"Processo {NUMERO}\nEvento 4: laudo."])
    com_fila.post("/processos/1/autos", data={"csrf": com_fila.csrf("/")}, follow_redirects=False,
                  files=[("autos", ("a.pdf", PDF)), ("autos", ("b.pdf", outro))])
    assert contar(banco, ArquivoAutos) == 2 and contar(banco, PaginaAutos) == 4
    enviar_pdf(com_fila, nome="de-novo.pdf")
    assert "de-novo.pdf não entrou: este arquivo já está nos autos." in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 2


def test_envio_sem_arquivo_e_arquivo_que_nao_e_pdf(com_fila, banco):
    com_fila.enviar("/processos/1/autos")
    assert "Escolha o PDF dos autos." in com_fila.get("/processos/1").text
    enviar_pdf(com_fila, b"MZ\x90 programa disfarcado", "autos.pdf")
    assert "autos.pdf não entrou: o arquivo não é um PDF." in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0


def test_servidor_de_dados_ficticios_recusa_numero_de_processo_real(com_fila, banco):
    enviar_pdf(com_fila, pdf([f"Autos {numero_real()}\nTexto."]))
    assert "só aceita dados fictícios" in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0 and contar(banco, PaginaAutos) == 0


def test_avisa_pagina_digitalizada_e_arquivo_de_outro_processo(com_fila):
    enviar_pdf(com_fila, pdf(["Processo 0000999-00.2026.8.24.0000\nOutro caso.", ""]))
    html = com_fila.get("/processos/1").text
    assert "1 página(s) sem texto para ler (digitalizadas)" in html and "1 sem texto" in html
    assert "o número deste processo não aparece no texto" in html
    enviar_pdf(com_fila, pdf(["", ""]), "digitalizado.pdf")
    assert "nenhuma página tem texto para ler" in com_fila.get("/processos/1").text


def test_nome_do_arquivo_e_escapado_na_tela(com_fila):
    enviar_pdf(com_fila, nome="<script>alert(1)</script>.pdf")
    html = com_fila.get("/processos/1").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_remover_apaga_o_arquivo_e_as_paginas(com_fila, banco):
    enviar_pdf(com_fila)
    r = com_fila.enviar("/processos/1/autos/1/remover")
    assert r.status_code == 303 and "Arquivo removido dos autos." in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0 and contar(banco, PaginaAutos) == 0
    assert com_fila.enviar("/processos/1/autos/1/remover").status_code == 404


def test_limite_de_arquivos_por_processo(com_fila, banco, monkeypatch):
    monkeypatch.setattr("app.servicos.MAX_ARQUIVOS_AUTOS", 1)
    enviar_pdf(com_fila)
    enviar_pdf(com_fila, pdf([f"Processo {NUMERO}\nOutra peça."]), "segundo.pdf")
    assert "segundo.pdf não entrou: o processo já tem 1 arquivos" in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 1


# ---------------------------------------------------------------- isolamento e proteção
def test_autos_de_um_usuario_sao_invisiveis_e_intocaveis_para_outro(com_fila, bruno, app, banco):
    from testes.conftest import Cliente
    enviar_pdf(com_fila)
    with Cliente(app) as outro:
        outro.entrar(bruno.email)
        assert enviar_pdf(outro).status_code == 404                              # não junta no processo alheio
        assert outro.enviar("/processos/1/autos/1/remover").status_code == 404   # nem remove
        outro.enviar("/processos/colar", {"numeros": "0000201-00.2026.8.24.0000"})
        meu = banco.scalar(select(Processo.id).where(Processo.usuario_id == bruno.id))
        assert outro.get(f"/processos/{meu}").status_code == 200
        # arquivo da Ana pedido pelo caminho do processo do Bruno
        assert outro.enviar(f"/processos/{meu}/autos/1/remover").status_code == 404
    assert contar(banco, ArquivoAutos) == 1 and contar(banco, PaginaAutos) == 3


def test_envio_exige_login_e_csrf(cliente, com_fila):
    r = com_fila.post("/processos/1/autos", files={"autos": ("autos.pdf", PDF)}, follow_redirects=False)
    assert r.status_code == 403
    com_fila.enviar("/sair")
    r = com_fila.enviar("/processos/1/autos", files={"autos": ("autos.pdf", PDF)}, pagina="/entrar")
    assert r.status_code == 303 and r.headers["location"] == "/entrar"


def test_teto_do_corpo_da_requisicao(com_fila, cliente, banco, monkeypatch):
    monkeypatch.setattr(rotas, "TETO_CORPO", 500)
    assert enviar_pdf(com_fila).status_code == 413
    assert contar(banco, ArquivoAutos) == 0
    monkeypatch.undo()
    com_fila.enviar("/sair")
    # quem não entrou não consegue fazer o servidor receber arquivo
    grande = com_fila.post("/entrar", data={"email": "a@exemplo.invalid", "senha": "x" * 70_000, "csrf": "x"})
    assert grande.status_code == 413 and "Envio grande demais" in grande.text
