"""Os autos fictícios do teste com a API (cartão C10) são lidos pela aplicação e não trazem dado real."""
import re

import pytest

from app import autos, servicos
from app.nucleo.tabela import dv_ok
from testes.autos_de_teste import CASOS, PASTA, pdf


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_o_pdf_do_repositorio_e_o_da_fabrica(nome):
    _, paginas = CASOS[nome]
    assert (PASTA / f"{nome}.pdf").read_bytes() == pdf(paginas), "rode: python -m testes.autos_de_teste"


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_e_lido_cita_o_proprio_processo_e_so_traz_numero_ficticio(nome):
    numero, paginas = CASOS[nome]
    leitura = autos.ler((PASTA / f"{nome}.pdf").read_bytes())
    assert len(leitura.paginas) == len(paginas) and leitura.sem_texto == 0
    texto = "\n".join(leitura.paginas)
    numeros = servicos.numeros_no_texto(texto)
    assert numeros == {numero} and not any(dv_ok(n) for n in numeros)
    assert "AUTOS FICTÍCIOS" in leitura.paginas[0]
    assert not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", texto)   # nada com cara de CPF
    assert not re.search(r"\bart(igo)?s?\.?\s*\d|\blei\b", texto, re.IGNORECASE)   # sem citação jurídica


def test_cada_linha_cabe_na_pagina():
    for _, paginas in CASOS.values():
        for pagina in paginas:
            linhas = pagina.split("\n")
            assert len(linhas) <= 44 and max(len(linha) for linha in linhas) <= 85
