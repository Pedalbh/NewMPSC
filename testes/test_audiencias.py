"""Pauta de audiências e ficha."""

NUM = "0000101-00.2026.8.24.0000"


def marcar(c, **kw):
    dados = {"numero": NUM, "data": "2026-11-16", "hora": "14:30", "tipo": "Instrução e julgamento"} | kw
    return c.enviar("/audiencias", dados, pagina="/audiencias")


def test_marcar_audiencia_gera_ficha_e_aparece_na_pauta(logada):
    assert marcar(logada).status_code == 303
    html = logada.get("/audiencias").text
    assert "Audiência marcada para 16/11 às 14:30" in html and NUM in html and "segunda-feira, 16 de novembro" in html
    ficha = logada.get("/audiencias/1").text
    assert "Ficha de audiência" in ficha and "Perguntas sugeridas" in ficha and "[DEMONSTRAÇÃO]" in ficha


def test_pauta_em_ordem_e_sem_audiencia_passada(logada):
    marcar(logada, data="2026-11-18", hora="09:00")
    marcar(logada, data="2026-11-16", hora="16:00", numero="0000102-00.2026.8.24.0000")
    marcar(logada, data="2026-11-01", hora="10:00", numero="0000103-00.2026.8.24.0000")   # antes de "hoje" (13/11)
    html = logada.get("/audiencias").text
    assert html.index("0000102") < html.index("0000101") and "0000103" not in html


def test_inicio_mostra_so_os_proximos_sete_dias(logada):
    marcar(logada, data="2026-11-16")
    marcar(logada, data="2026-12-10", numero="0000102-00.2026.8.24.0000")
    html = logada.get("/").text
    assert "1 audiência nos próximos 7 dias" in html and "0000102" not in html


def test_dados_invalidos_sao_recusados_com_mensagem(logada):
    for campo, valor, mensagem in (("numero", "123", "número do processo"), ("data", "ontem", "data e a hora"),
                                   ("hora", "", "data e a hora"), ("tipo", "Inventado", "Tipo de audiência")):
        marcar(logada, **{campo: valor})
        assert mensagem in logada.get("/audiencias").text
    assert "Nenhuma audiência na pauta" in logada.get("/audiencias").text


def test_remover_da_pauta(logada):
    marcar(logada)
    logada.enviar("/audiencias/1/remover", pagina="/audiencias/1")
    assert "Nenhuma audiência na pauta" in logada.get("/audiencias").text
    assert logada.get("/audiencias/1").status_code == 404
