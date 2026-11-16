"""Fila: importação da planilha do SIG, colagem de números, prioridade e situação."""
import re

from app.servicos import grupo_de


def numeros_na_ordem(html: str) -> list[str]:
    fila = html.split('id="t-trazer"')[0]
    return re.findall(r'<span class="num">(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})</span>', fila)


def test_prioridade_da_fila():
    assert [grupo_de(True, "Intimação"), grupo_de(False, "Urgente"), grupo_de(False, "intimação"),
            grupo_de(False, "")] == [0, 1, 2, 3]


def test_importar_planilha_cria_fila_ordenada_com_minuta(logada):
    assert logada.importar_fila().status_code == 303
    html = logada.get("/").text
    assert "9 processos novos" in html
    ordem = numeros_na_ordem(html)
    assert len(ordem) == 9
    # réu preso primeiro (mais antigo antes), depois urgentes, depois intimações, por último os demais
    assert ordem[:2] == ["0000101-00.2026.8.24.0000", "0000105-00.2026.8.24.0000"]
    assert ordem[2:4] == ["0000106-00.2026.8.24.0000", "0000103-00.2026.8.24.0000"]
    assert ordem[-1] == "0000109-00.2026.8.24.0000"
    assert html.count("Minuta pronta") == 9


def test_importar_de_novo_nao_duplica_nem_apaga_edicao(logada):
    logada.importar_fila()
    token = logada.csrf("/")
    logada.put("/api/processos/1/minuta", json={"blocos": [{"texto": "Texto meu.", "estilo": "corpo"}]},
               headers={"X-CSRF-Token": token})
    logada.importar_fila()
    html = logada.get("/").text
    assert "9 já estavam na fila" in html and len(numeros_na_ordem(html)) == 9
    assert "Texto meu." in logada.get("/processos/1").text


def test_arquivo_que_nao_e_planilha_e_recusado_com_orientacao(logada):
    r = logada.enviar("/processos/importar", files={"planilha": ("x.xls", b"\x00\x01\x02 lixo")})
    assert r.status_code == 303
    assert "A planilha não foi lida" in logada.get("/").text


def test_planilha_sem_coluna_obrigatoria(logada):
    logada.enviar("/processos/importar", files={"planilha": ("x.csv", "Nome;Outra\na;b\n".encode("cp1252"))})
    assert "faltam colunas obrigatórias" in logada.get("/").text


def test_envio_sem_arquivo(logada):
    logada.enviar("/processos/importar")
    assert "Escolha a planilha" in logada.get("/").text


def test_colar_numeros_aceita_texto_solto_e_ignora_repetidos(logada):
    texto = "Seguem: 0000201-00.2026.8.24.0000, 0000202-00.2026.8.24.0000 e de novo 0000201-00.2026.8.24.0000."
    logada.enviar("/processos/colar", {"numeros": texto})
    html = logada.get("/").text
    assert "2 processos novos" in html and len(numeros_na_ordem(html)) == 2


def test_colar_sem_numero_avisa(logada):
    logada.enviar("/processos/colar", {"numeros": "nada aqui"})
    assert "nenhum número de processo reconhecido" in logada.get("/").text


def test_concluir_tira_da_fila_e_devolver_recoloca(logada):
    logada.importar_fila()
    logada.enviar("/processos/1/situacao", {"situacao": "concluido"})
    assert len(numeros_na_ordem(logada.get("/").text)) == 8
    assert len(numeros_na_ordem(logada.get("/?ver=concluido").text)) == 1
    logada.enviar("/processos/1/situacao", {"situacao": "a_fazer"})
    assert len(numeros_na_ordem(logada.get("/").text)) == 9
    assert logada.enviar("/processos/1/situacao", {"situacao": "inventada"}).status_code == 422


def test_conteudo_da_planilha_e_escapado_na_tela(logada):
    planilha = ("Nº Judiciário;Entrada;Classe TJ\n"
                "0000301-00.2026.8.24.0000;01/11/2026 10:00:00;<script>alert(1)</script>\n")
    logada.enviar("/processos/importar", files={"planilha": ("x.csv", planilha.encode())})
    html = logada.get("/").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_servidor_de_dados_ficticios_recusa_numero_real_na_planilha_e_na_colagem(logada):
    """Cartão C17: no ensaio só entra dado fictício; número com dígito verificador válido fica de fora."""
    from testes.test_autos import numero_real
    real = numero_real()
    planilha = f"Nº Judiciário;Entrada\n{real};01/11/2026 10:00:00\n0000101-00.2026.8.24.0000;01/11/2026 10:00:00\n"
    logada.enviar("/processos/importar", files={"planilha": ("fila.csv", planilha.encode("cp1252"))})
    html = logada.get("/").text
    assert "1 processo novo" in html and "1 linha não entrou" in html
    assert numeros_na_ordem(html) == ["0000101-00.2026.8.24.0000"]
    # achado na revisão: o número real fora da máscara entrava calado, e depois passava pelas outras travas
    solto = real.replace("-", "").replace(".", "")
    variantes = [solto, real.replace("-", " - "), real.replace(".", "/"), solto.lstrip("0")]
    planilha = "Nº Judiciário;Entrada;Classe TJ\n" + "".join(f"{v};01/11/2026 10:00:00;Ação\n" for v in variantes)
    planilha += f"0000102-00.2026.8.24.0000;01/11/2026 10:00:00;Apenso ao {solto}\n"   # número real na classe
    logada.enviar("/processos/importar", files={"planilha": ("fila.csv", planilha.encode("cp1252"))})
    html = logada.get("/").text
    assert "5 linhas não entraram" in html and "só aceita número de processo fictício" in html
    assert numeros_na_ordem(html) == ["0000101-00.2026.8.24.0000"] and solto not in html
    logada.enviar("/processos/colar", {"numeros": f"{real} e 0000102-00.2026.8.24.0000"})
    html = logada.get("/").text
    assert "1 processo novo" in html and "1 linha não entrou" in html and real not in html
    logada.enviar("/processos/colar", {"numeros": real})
    html = logada.get("/").text
    assert "só aceita número de processo fictício" in html and real not in html
    assert "Nenhum processo encontrado" not in html


def test_apagar_processo_pela_linha_de_comando_leva_tudo_e_so_o_da_pessoa(logada, banco, ana, bruno):
    """Parecer de segurança (0.5.1): o guia do ensaio promete apagar dado que entrou por engano."""
    from app import servicos
    from app.modelos import ArquivoAutos, Audiencia, Minuta, PaginaAutos, Processo
    from app.portas import criar_motor
    from testes.conftest import RAIZ
    numero = "0000101-00.2026.8.24.0000"
    logada.importar_fila()
    autos = (RAIZ / "dados_ficticios" / "autos-ficticios.pdf").read_bytes()
    logada.enviar("/processos/1/autos", files={"autos": ("autos.pdf", autos)}, pagina="/processos/1")
    logada.enviar("/audiencias", {"numero": numero, "data": "2026-11-16", "hora": "14:30",
                                  "tipo": "Instrução e julgamento"}, pagina="/audiencias")
    servicos.colar_numeros(banco, bruno, numero, criar_motor("demo"), True)
    assert banco.query(PaginaAutos).count() > 0
    assert not servicos.apagar_processo(banco, ana, "0000999-00.2026.8.24.0000")
    assert servicos.apagar_processo(banco, ana, numero)
    assert banco.query(Processo).filter_by(usuario_id=ana.id, numero=numero).count() == 0
    assert banco.query(Processo).filter_by(usuario_id=bruno.id, numero=numero).count() == 1   # o de Bruno fica
    assert banco.query(PaginaAutos).count() == 0 and banco.query(ArquivoAutos).count() == 0
    assert banco.query(Audiencia).count() == 0 and banco.query(Minuta).count() == 9   # 8 de Ana, 1 de Bruno
    assert numero not in logada.get("/").text
