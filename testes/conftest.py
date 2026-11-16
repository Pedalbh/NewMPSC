"""DADOS FICTÍCIOS: tudo o que os testes criam é inventado; números de processo com dígito verificador inválido."""
import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cli import criar_usuario
from app.config import Config
from app.main import criar_app

RAIZ = Path(__file__).parent.parent
FILA = RAIZ / "dados_ficticios" / "fila-sig-ficticia.csv"
SENHA = "senha-ficticia-de-teste"
AGORA = datetime(2026, 11, 13, 9, 0)


@pytest.fixture
def app():
    config = Config(ambiente="teste", segredo="s" * 40, banco_url="sqlite:///:memory:", motor="demo",
                    dados_ficticios=True)
    return criar_app(config, agora=lambda: AGORA)


@pytest.fixture
def banco(app):
    with app.state.Sessao() as db:
        yield db


@pytest.fixture
def ana(banco):
    return criar_usuario(banco, "ana@exemplo.invalid", "Ana Exemplo", SENHA)


@pytest.fixture
def bruno(banco):
    return criar_usuario(banco, "bruno@exemplo.invalid", "Bruno Exemplo", SENHA)


def csrf_de(resposta) -> str:
    return re.search(r'name="csrf" content="([^"]+)"', resposta.text).group(1)


class Cliente(TestClient):
    """Cliente que cuida do token CSRF e da versão da minuta como o navegador faria."""

    def csrf(self, caminho="/entrar") -> str:
        return csrf_de(self.get(caminho))

    def versao(self, processo) -> int | None:
        """A versão da minuta que a tela do processo mostra agora (a que a casca manda de volta ao salvar)."""
        achado = re.search(r'data-versao="(\d+)"', self.get(f"/processos/{processo}").text)
        return int(achado.group(1)) if achado else None

    def put(self, url, *a, json=None, **kw):
        achado = re.fullmatch(r"/api/processos/(\d+)/minuta", str(url))
        if achado and isinstance(json, dict) and "blocos" in json and "versao" not in json:
            json = json | {"versao": self.versao(achado.group(1))}
        return super().put(url, *a, json=json, **kw)

    def entrar(self, email, senha=SENHA):
        return self.post("/entrar", data={"email": email, "senha": senha, "csrf": self.csrf()},
                         follow_redirects=False)

    def enviar(self, caminho, dados=None, pagina="/", **kw):
        dados = dict(dados or {}, csrf=self.csrf(pagina))
        achado = re.fullmatch(r"/processos/(\d+)/(refazer|escrever)", caminho)
        if achado and "versao" not in dados:   # os formulários da tela levam a versão que ela carregou
            versao = self.versao(achado.group(1))
            dados |= {} if versao is None else {"versao": versao}
        return self.post(caminho, data=dados, follow_redirects=False, **kw)

    def importar_fila(self):
        return self.enviar("/processos/importar", files={"planilha": ("fila.xls", FILA.read_bytes())})


@pytest.fixture
def cliente(app):
    with Cliente(app) as c:
        yield c


@pytest.fixture
def logada(cliente, ana):
    assert cliente.entrar(ana.email).status_code == 303
    return cliente
