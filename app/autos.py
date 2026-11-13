"""Leitura dos autos em PDF. O arquivo vem de fora, então é aberto num processo filho, sem os segredos da aplicação
e com teto de tempo e de memória; só o texto de cada página volta. O arquivo original não é guardado.

Rodado como `python -m app.autos MAX_PAGINAS`, lê o PDF da entrada padrão e escreve o resultado em JSON."""
import hashlib
import io
import json
import re
import subprocess  # noqa: S404 (o filho é este mesmo módulo, com argumentos fixos)
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

TETO_PDF = 50 * 1024 * 1024
MAX_PAGINAS = 2000
MAX_TEXTO_PAGINA = 20_000
TEMPO = 90                      # segundos para ler um arquivo
MEMORIA = 1024 * 1024 * 1024    # teto de memória do processo filho
_vagas = threading.BoundedSemaphore(2)   # leituras ao mesmo tempo
_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class PdfRecusado(Exception):
    """A mensagem é a orientação mostrada ao usuário."""


@dataclass(frozen=True)
class Leitura:
    sha256: str
    tamanho: int
    paginas: list[str]

    @property
    def sem_texto(self) -> int:
        return sum(1 for p in self.paginas if not p)


def extrair(dados: bytes, max_paginas: int = MAX_PAGINAS) -> list[str]:
    """Texto de cada página, na ordem. Roda dentro do processo filho."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        leitor = PdfReader(io.BytesIO(dados))
        if leitor.is_encrypted:
            raise PdfRecusado("o arquivo está protegido por senha")
        total = len(leitor.pages)
        if total == 0:
            raise PdfRecusado("o arquivo não tem páginas")
        if total > max_paginas:
            raise PdfRecusado(f"o arquivo tem {total} páginas; o limite é {max_paginas}. Divida o arquivo")
        paginas = []
        for pagina in leitor.pages:
            try:
                texto = pagina.extract_text() or ""
            except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, IndexError):
                texto = ""   # página que não se deixa ler conta como página sem texto
            paginas.append(_CONTROLE.sub("", texto).strip()[:MAX_TEXTO_PAGINA])
        return paginas
    except PyPdfError:
        raise PdfRecusado("o arquivo está danificado ou não é um PDF") from None


def ler(dados: bytes) -> Leitura:
    """Confere o arquivo e devolve o texto por página. Levanta `PdfRecusado` com a orientação para o usuário."""
    if not dados:
        raise PdfRecusado("o arquivo está vazio")
    if len(dados) > TETO_PDF:
        raise PdfRecusado(f"o arquivo passa de {TETO_PDF // (1024 * 1024)} MB. Divida o arquivo")
    if b"%PDF-" not in dados[:1024]:
        raise PdfRecusado("o arquivo não é um PDF")
    comando = [sys.executable, "-m", "app.autos", str(MAX_PAGINAS)]
    with _vagas:
        try:
            filho = subprocess.run(comando, input=dados, capture_output=True, timeout=TEMPO,  # noqa: S603
                                   cwd=Path(__file__).parent.parent, env={"PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            raise PdfRecusado("a leitura demorou demais. Divida o arquivo") from None
    try:
        resultado = json.loads(filho.stdout) if filho.returncode == 0 else {}
    except ValueError:
        resultado = {}
    if "recusa" in resultado:
        raise PdfRecusado(str(resultado["recusa"]))
    paginas = resultado.get("paginas")
    if not isinstance(paginas, list) or not paginas or not all(isinstance(p, str) for p in paginas):
        raise PdfRecusado("o arquivo está danificado ou não é um PDF")
    return Leitura(hashlib.sha256(dados).hexdigest(), len(dados), paginas)


def _filho(argv: list[str]) -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORIA, MEMORIA))
        resource.setrlimit(resource.RLIMIT_CPU, (TEMPO, TEMPO))
    except (ImportError, ValueError, OSError):
        pass   # sistema sem esses limites: fica o teto de tempo do processo pai
    import logging
    logging.disable(logging.CRITICAL)
    try:
        saida = {"paginas": extrair(sys.stdin.buffer.read(), int(argv[0]))}
    except PdfRecusado as e:
        saida = {"recusa": str(e)}
    json.dump(saida, sys.stdout)


if __name__ == "__main__":
    _filho(sys.argv[1:])
