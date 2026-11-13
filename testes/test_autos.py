"""Autos em PDF: leitura isolada, recusas, guarda só do texto, isolamento por usuário. DADOS FICTÍCIOS."""
import io
import subprocess
import sys

import pytest
from sqlalchemy import func, select, text

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


@pytest.fixture
def vagas_ocupadas(monkeypatch):
    monkeypatch.setattr(autos, "ESPERA_VAGA", 0.05)
    assert autos._vagas.acquire(blocking=False) and autos._vagas.acquire(blocking=False)
    yield
    autos._vagas.release()
    autos._vagas.release()


# ---------------------------------------------------------------- leitura
def test_le_o_texto_de_cada_pagina_e_conta_as_sem_texto():
    leitura = autos.ler(pdf(AUTOS_FICTICIOS + [""]))
    assert len(leitura.paginas) == 4 and leitura.sem_texto == 1
    assert "denúncia" in leitura.paginas[0] and NUMERO in leitura.paginas[0]
    assert leitura.paginas[2].startswith("Evento 3") and leitura.tamanho > 0 and len(leitura.sha256) == 64
    assert leitura.caracteres == sum(len(p) for p in leitura.paginas)


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


def _cifrado(senha_para_abrir: str, algoritmo: str) -> bytes:
    from pypdf import PdfReader, PdfWriter
    escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(PDF)))
    escritor.encrypt(user_password=senha_para_abrir, owner_password="dono-ficticio", algorithm=algoritmo)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def test_recusa_pdf_com_senha_para_abrir():
    with pytest.raises(autos.PdfRecusado, match="protegido por senha"):
        autos.ler(_cifrado("senha-ficticia", "RC4-128"))


@pytest.mark.parametrize("algoritmo", ["RC4-128", "AES-256"])
def test_le_pdf_so_com_restricao_de_impressao(algoritmo):
    """Defeito achado na revisão: arquivo que abre sem senha era recusado como protegido."""
    assert "denúncia" in autos.ler(_cifrado("", algoritmo)).paginas[0]


def test_recusa_por_tamanho_paginas_e_tempo(monkeypatch):
    monkeypatch.setattr(autos, "MAX_PAGINAS", 2)
    with pytest.raises(autos.PdfRecusado, match="3 páginas; o limite é 2"):
        autos.ler(PDF)
    with pytest.raises(autos.PdfRecusado, match="demorou demais"):
        autos.ler(PDF, tempo=0.001)
    with pytest.raises(autos.PdfRecusado, match="demorou demais"):
        autos.ler(PDF, tempo=-1)   # o prazo do envio acabou antes deste arquivo
    monkeypatch.setattr(autos, "TETO_PDF", 100)
    with pytest.raises(autos.PdfRecusado, match="passa de"):
        autos.ler(PDF)


def test_recusa_arquivo_pequeno_que_vira_texto_demais():
    """Defeito achado na revisão: centenas de páginas apontando para o mesmo conteúdo inflavam o banco."""
    pagina_cheia = "\n".join(["palavra " * 12] * 220)
    bomba = pdf([pagina_cheia], repetir=500)
    assert len(bomba) < 100_000
    with pytest.raises(autos.PdfRecusado, match="texto demais"):
        autos.ler(bomba)


def test_texto_que_o_banco_nao_grava_e_limpo():
    """Defeito achado na revisão: caractere inválido vindo do PDF derrubava o envio com erro 500."""
    assert autos.limpar("a\ud800b\x00c‮d ") == "abcd"
    leitura = autos.ler(pdf([f"AAA {NUMERO}"], a_vira="D800"))
    assert leitura.paginas == [NUMERO]
    leitura.paginas[0].encode("utf-8")


def test_leitura_roda_sem_os_segredos_da_aplicacao(monkeypatch):
    """O processo que abre o PDF não herda o ambiente (segredo da sessão, chaves) e roda em modo isolado."""
    chamadas = {}
    original = autos.subprocess.run

    def espiar(comando, **kw):
        chamadas.update(kw, comando=comando)
        return original(comando, **kw)

    monkeypatch.setenv("NEWMPSC_SEGREDO", "s" * 40)
    monkeypatch.setattr(autos.subprocess, "run", espiar)
    autos.ler(PDF)
    assert "NEWMPSC_SEGREDO" not in chamadas["env"] and chamadas["timeout"] == autos.TEMPO
    assert chamadas["comando"][1] == "-I" and "exigir" not in chamadas["comando"]
    autos.ler(PDF, exigir_limites=True)
    assert chamadas["comando"][-1] == "exigir"


def test_tetos_de_memoria_e_processador_valem_no_filho():
    codigo = ("import resource; from app import autos; ok = autos.limitar(); "
              "print(ok, resource.getrlimit(resource.RLIMIT_AS)[0] <= autos.MEMORIA, "
              "resource.getrlimit(resource.RLIMIT_CPU)[0] <= autos.TEMPO)")
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True).stdout
    assert saida.split() == ["True", "True", "True"]


def test_em_producao_nao_le_sem_os_tetos(monkeypatch, capsysbinary):
    monkeypatch.setattr(autos, "limitar", lambda: False)
    autos._filho(["10", "exigir"])
    assert "não está preparado".encode() in capsysbinary.readouterr().out


def test_vagas_ocupadas_recusam_na_hora_em_vez_de_enfileirar(vagas_ocupadas):
    with pytest.raises(autos.Ocupado, match="tente de novo"):
        autos.ler(PDF)


# ---------------------------------------------------------------- envio pela tela
def test_enviar_pdf_guarda_o_texto_por_pagina(com_fila, banco):
    assert enviar_pdf(com_fila).status_code == 303
    html = com_fila.get("/processos/1").text
    assert "autos.pdf: 3 páginas lidas." in html and "3 páginas</span>" in html
    arquivo = banco.scalar(select(ArquivoAutos))
    assert (arquivo.nome, arquivo.total_paginas, arquivo.sem_texto, arquivo.tamanho) == ("autos.pdf", 3, 0, len(PDF))
    assert arquivo.cita_processo and arquivo.caracteres == sum(len(p.texto) for p in arquivo.paginas)
    assert [p.numero for p in arquivo.paginas] == [1, 2, 3] and "resposta à acusação" in arquivo.paginas[2].texto
    # só o texto fica: nenhuma coluna guarda o arquivo original
    assert not any(c.type.python_type is bytes for t in (ArquivoAutos, PaginaAutos) for c in t.__table__.columns)


def test_resultado_aparece_dentro_do_cartao_dos_autos(com_fila):
    """Defeito achado na revisão: o aviso ficava no topo, fora da vista depois da rolagem até o cartão."""
    r = enviar_pdf(com_fila)
    assert r.headers["location"] == "/processos/1#resultado-autos"
    html = com_fila.get("/processos/1").text
    antes, cartao = html.split('id="autos"')
    assert 'id="resultado-autos"' in cartao and "autos.pdf: 3 páginas lidas." in cartao
    assert "autos.pdf: 3 páginas lidas." not in antes
    assert 'id="resultado-autos"' not in com_fila.get("/processos/1").text   # o aviso aparece uma vez


def test_varios_arquivos_de_uma_vez_e_repetido_nao_duplica(com_fila, banco):
    outro = pdf([f"Processo {NUMERO}\nEvento 4: laudo."])
    com_fila.post("/processos/1/autos", data={"csrf": com_fila.csrf("/")}, follow_redirects=False,
                  files=[("autos", ("a.pdf", PDF)), ("autos", ("b.pdf", outro))])
    assert contar(banco, ArquivoAutos) == 2 and contar(banco, PaginaAutos) == 4
    assert "b.pdf: 1 página lida." in com_fila.get("/processos/1").text
    enviar_pdf(com_fila, nome="de-novo.pdf")
    assert "de-novo.pdf não entrou: este arquivo já está nos autos." in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 2


def test_nenhuma_recusa_some_quando_ha_muitos_arquivos(com_fila, banco):
    """Defeito achado na revisão: o corte das mensagens escondia recusas e o aviso de arquivos não lidos."""
    com_ressalva = [("autos", (f"r{i}.pdf", pdf([f"Processo 0000999-00.2026.8.24.0000\nPeça {i}.", ""])))
                    for i in range(4)]
    extras = [("autos", ("recusado.pdf", b"MZ programa")), ("autos", ("sexto.pdf", PDF))]
    com_fila.post("/processos/1/autos", data={"csrf": com_fila.csrf("/")}, follow_redirects=False,
                  files=com_ressalva + extras)
    html = com_fila.get("/processos/1").text
    assert "recusado.pdf não entrou: o arquivo não é um PDF." in html
    assert "Só os 5 primeiros arquivos foram lidos; envie os demais em seguida." in html
    assert all(f"r{i}.pdf: 2 páginas lidas, 1 sem texto" in html for i in range(4))
    assert html.index("recusado.pdf não entrou") < html.index("r0.pdf: 2 páginas")   # recusas primeiro
    assert contar(banco, ArquivoAutos) == 4


def test_envio_sem_arquivo_e_arquivo_que_nao_e_pdf(com_fila, banco):
    com_fila.enviar("/processos/1/autos")
    assert "Escolha o PDF dos autos." in com_fila.get("/processos/1").text
    enviar_pdf(com_fila, b"MZ\x90 programa disfarcado", "autos.pdf")
    assert "autos.pdf não entrou: o arquivo não é um PDF." in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0


@pytest.mark.parametrize("como", ["mascara", "so_digitos", "com_espacos", "em_duas_linhas", "com_barras", "no_nome"])
def test_servidor_de_dados_ficticios_alerta_numero_de_processo_real(com_fila, banco, como):
    """Defeito achado na revisão: só o número com a máscara exata era percebido."""
    real = numero_real()
    escrito = {"mascara": real, "so_digitos": real.replace("-", "").replace(".", ""),
               "com_espacos": real.replace(".", " . "), "em_duas_linhas": real[:10] + "\n" + real[10:],
               "com_barras": real.replace(".", "/"), "no_nome": NUMERO}[como]
    nome = f"IP {real}.pdf" if como == "no_nome" else "autos.pdf"
    enviar_pdf(com_fila, pdf([f"Autos {escrito}\nTexto."]), nome)
    assert "só aceita dados fictícios" in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0 and contar(banco, PaginaAutos) == 0


def test_pagina_digitalizada_e_arquivo_de_outro_processo_ficam_marcados_na_lista(com_fila):
    enviar_pdf(com_fila, pdf(["Processo 0000999-00.2026.8.24.0000\nOutro caso.", ""]))
    html = com_fila.get("/processos/1").text
    assert "1 sem texto para ler (digitalizadas ou ilegíveis)" in html
    assert "o número deste processo não aparece no texto" in html
    # a ressalva continua na lista depois que o aviso some
    html = com_fila.get("/processos/1").text
    assert "1 sem texto</span>" in html and "Outro processo?</span>" in html
    enviar_pdf(com_fila, pdf(["", ""]), "digitalizado.pdf")
    html = com_fila.get("/processos/1").text
    assert "nenhuma com texto para ler (arquivo digitalizado)" in html and html.count("Outro processo?") == 1


def test_nome_do_arquivo_e_escapado_e_limpo(com_fila, banco):
    enviar_pdf(com_fila, nome="<script>alert(1)</script>.pdf")
    html = com_fila.get("/processos/1").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    enviar_pdf(com_fila, pdf([f"Processo {NUMERO}\nPeça dois."]), "laudo‮fdp.exe")
    assert banco.scalars(select(ArquivoAutos.nome)).all()[-1] == "laudofdp.exe"   # sem marca que inverte o texto


def test_remover_apaga_o_arquivo_e_as_paginas(com_fila, banco):
    enviar_pdf(com_fila)
    r = com_fila.enviar("/processos/1/autos/1/remover")
    assert r.status_code == 303 and "Arquivo removido dos autos." in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0 and contar(banco, PaginaAutos) == 0
    assert com_fila.enviar("/processos/1/autos/1/remover").status_code == 404
    assert banco.execute(text("PRAGMA secure_delete")).scalar() == 1   # o texto removido sai do arquivo do banco


def test_limite_de_arquivos_por_processo_e_cota_de_texto(com_fila, banco, monkeypatch):
    monkeypatch.setattr("app.servicos.MAX_ARQUIVOS_AUTOS", 1)
    enviar_pdf(com_fila)
    enviar_pdf(com_fila, pdf([f"Processo {NUMERO}\nOutra peça."]), "segundo.pdf")
    assert "segundo.pdf não entrou: o processo já tem 1 arquivos" in com_fila.get("/processos/1").text
    monkeypatch.setattr("app.servicos.COTA_TEXTO_AUTOS", 300)   # a cota soma todos os processos do usuário
    enviar_pdf(com_fila, pdf(["Processo 0000102-00.2026.8.24.0000\nPeça."]), "terceiro.pdf", processo=2)
    assert "terceiro.pdf não entrou: você chegou ao limite de texto guardado" in com_fila.get("/processos/2").text
    assert contar(banco, ArquivoAutos) == 1


# ---------------------------------------------------------------- servidor ocupado
def test_com_as_vagas_ocupadas_o_envio_e_recusado_e_o_servidor_responde(com_fila, banco, vagas_ocupadas):
    """Defeito achado na revisão: envios em fila prendiam threads e conexões do banco e derrubavam o servidor."""
    assert enviar_pdf(com_fila).status_code == 303
    assert com_fila.get("/saude").status_code == 200
    assert "o servidor está lendo outros arquivos; tente de novo em instantes" in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0


def test_um_envio_em_leitura_por_usuario(com_fila, ana, banco):
    with autos.vez_do_usuario(ana.id):
        enviar_pdf(com_fila)
    assert "Nada foi enviado: já há um envio seu em leitura" in com_fila.get("/processos/1").text
    assert contar(banco, ArquivoAutos) == 0
    enviar_pdf(com_fila)   # terminada a leitura, a vez volta
    assert contar(banco, ArquivoAutos) == 1


def test_a_conexao_do_banco_e_devolvida_durante_a_leitura(tmp_path, monkeypatch):
    """Com banco em arquivo (o de memória usa uma conexão só): nenhuma conexão fica presa enquanto o PDF é lido."""
    from app.cli import criar_usuario
    from app.config import Config
    from app.main import criar_app
    from testes.conftest import SENHA, Cliente
    app = criar_app(Config("teste", "s" * 40, f"sqlite:///{tmp_path}/b.db", "demo", True))
    with app.state.Sessao() as db:
        criar_usuario(db, "ana@exemplo.invalid", "Ana Exemplo", SENHA)
        conexoes = db.get_bind().pool
    em_uso, original = [], autos.ler

    def espiar(dados, **kw):
        em_uso.append(conexoes.checkedout())
        return original(dados, **kw)

    monkeypatch.setattr(autos, "ler", espiar)
    with Cliente(app) as c:
        c.entrar("ana@exemplo.invalid")
        c.importar_fila()
        enviar_pdf(c)
        assert "3 páginas lidas" in c.get("/processos/1").text
    assert em_uso == [0]


def test_prazo_do_envio_vale_para_a_soma_dos_arquivos(com_fila, banco, monkeypatch):
    monkeypatch.setattr(rotas, "TEMPO_ENVIO", 0)
    enviar_pdf(com_fila)
    assert "o envio demorou demais" in com_fila.get("/processos/1").text and contar(banco, ArquivoAutos) == 0


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
