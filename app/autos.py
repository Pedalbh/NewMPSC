"""Leitura dos autos em PDF. O arquivo vem de fora, então é aberto num processo filho, sem os segredos da aplicação
e com teto de tempo e de memória; só o texto de cada página volta. O arquivo original não é guardado.

O filho roda `_filho` em modo isolado (`python -I`), lê o PDF da entrada padrão e escreve o resultado em JSON."""
import hashlib
import hmac
import io
import json
import re
import subprocess  # noqa: S404 (o filho é este mesmo módulo, com argumentos fixos)
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

TETO_PDF = 50 * 1024 * 1024
MAX_PAGINAS = 2000
MAX_TEXTO_PAGINA = 20_000
MAX_TEXTO_ARQUIVO = 8_000_000   # caracteres somados; autos de 2.000 páginas cheias ficam abaixo disso
TEMPO = 60                      # segundos para ler um arquivo
MEMORIA = 1024 * 1024 * 1024    # teto de memória do processo filho
ESPERA_VAGA = 3                 # segundos; depois disso o servidor diz que está ocupado, em vez de enfileirar
_vagas = threading.BoundedSemaphore(2)   # leituras ao mesmo tempo, somando todos os usuários
_lendo: set[int] = set()                 # usuários com envio em leitura
_tranca = threading.Lock()
# O modo isolado ignora a pasta atual; o filho recebe onde está o pacote, instalado ou não. A pasta vai para o
# fim do caminho de importação, para que nada nela tome o lugar de um módulo da biblioteca padrão.
_ACHAR = "import sys; sys.path.append(sys.argv.pop(1)); from app.autos import _filho"
_PARTIDA = _ACHAR + "; _filho(sys.argv[1:])"
_RAIZ = str(Path(__file__).resolve().parent.parent)
_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁠-⁩﻿]")   # controles e invisíveis


class PdfRecusado(Exception):
    """A mensagem é a orientação mostrada ao usuário."""


class Ocupado(PdfRecusado):
    pass


@dataclass(frozen=True)
class Leitura:
    sha256: str
    tamanho: int
    paginas: list[str]

    @property
    def sem_texto(self) -> int:
        return sum(1 for p in self.paginas if not p)

    @property
    def caracteres(self) -> int:
        return sum(len(p) for p in self.paginas)


def limpar(texto: str) -> str:
    """Tira o que o banco não grava ou a tela não deve mostrar: surrogates soltos, controles e marcas de direção."""
    return _CONTROLE.sub("", texto.encode("utf-8", "ignore").decode("utf-8")).strip()


def resumo(dados: bytes) -> str:
    """O sha256 do arquivo. Só vive na memória: o que se guarda é a `impressao`."""
    return hashlib.sha256(dados).hexdigest()


def impressao(resumo_do_arquivo: str, chave: bytes) -> str:
    """Cartão C2: impressão que só o servidor refaz (HMAC com chave dele). Fora daqui não prova que alguém
    teve um documento, porque sem a chave não dá para calcular a impressão de um arquivo conhecido."""
    return hmac.new(chave, resumo_do_arquivo.encode(), hashlib.sha256).hexdigest()


@contextmanager
def vez_do_usuario(usuario_id: int):
    """Um envio em leitura por usuário: ninguém ocupa sozinho as vagas de leitura."""
    with _tranca:
        if usuario_id in _lendo:
            raise Ocupado("já há um envio seu em leitura; espere terminar")
        _lendo.add(usuario_id)
    try:
        yield
    finally:
        with _tranca:
            _lendo.discard(usuario_id)


def extrair(dados: bytes, max_paginas: int = MAX_PAGINAS) -> list[str]:
    """Texto de cada página, na ordem. Roda dentro do processo filho."""
    from pypdf import PdfReader
    from pypdf.errors import DependencyError, PyPdfError

    try:
        leitor = PdfReader(io.BytesIO(dados))
        # PDF só com restrição de impressão ou edição é cifrado, mas abre com a senha vazia
        if leitor.is_encrypted and not leitor.decrypt(""):
            raise PdfRecusado("o arquivo está protegido por senha")
        total = len(leitor.pages)
        if total == 0:
            raise PdfRecusado("o arquivo não tem páginas")
        if total > max_paginas:
            raise PdfRecusado(f"o arquivo tem {total} páginas; o limite é {max_paginas}. Divida o arquivo")
        paginas, soma = [], 0
        for pagina in leitor.pages:
            try:
                texto = limpar(pagina.extract_text() or "")[:MAX_TEXTO_PAGINA]
            except (MemoryError, DependencyError):
                raise
            except Exception:   # noqa: BLE001 (página que não se deixa ler conta como página sem texto)
                texto = ""
            soma += len(texto)
            if soma > MAX_TEXTO_ARQUIVO:
                raise PdfRecusado("o arquivo tem texto demais para um só envio. Divida o arquivo")
            paginas.append(texto)
        return paginas
    except DependencyError:
        raise PdfRecusado("o arquivo usa uma proteção que este servidor não abre") from None
    except (PyPdfError, RecursionError, ValueError, KeyError, TypeError, AttributeError, IndexError, ArithmeticError):
        raise PdfRecusado("o arquivo está danificado ou não é um PDF") from None


def conferir(dados: bytes) -> None:
    """Conferência barata, antes de gastar uma vaga de leitura."""
    if not dados:
        raise PdfRecusado("o arquivo está vazio")
    if len(dados) > TETO_PDF:
        raise PdfRecusado(f"o arquivo passa de {TETO_PDF // (1024 * 1024)} MB. Divida o arquivo")
    if b"%PDF-" not in dados[:1024]:
        raise PdfRecusado("o arquivo não é um PDF")


def ler(dados: bytes, tempo: float | None = None, exigir_limites: bool = False) -> Leitura:
    """Confere o arquivo e devolve o texto por página. Levanta `PdfRecusado` com a orientação para o usuário.
    Com `exigir_limites` (produção), não lê se o sistema não aplicar os tetos de memória e de processador."""
    conferir(dados)
    tempo = TEMPO if tempo is None else min(tempo, TEMPO)
    if tempo <= 0:
        raise PdfRecusado("o envio demorou demais. Envie este arquivo de novo, sozinho")
    comando = [sys.executable, "-I", "-c", _PARTIDA, _RAIZ, str(MAX_PAGINAS)] + (["exigir"] if exigir_limites else [])
    if not _vagas.acquire(timeout=ESPERA_VAGA):
        raise Ocupado("o servidor está lendo outros arquivos; tente de novo em instantes")
    try:
        filho = subprocess.run(comando, input=dados, capture_output=True, timeout=tempo,  # noqa: S603
                               env={"PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        raise PdfRecusado("a leitura demorou demais. Divida o arquivo") from None
    finally:
        _vagas.release()
    try:
        resultado = json.loads(filho.stdout) if filho.returncode == 0 else {}
    except ValueError:
        resultado = {}
    if "recusa" in resultado:
        raise PdfRecusado(str(resultado["recusa"]))
    paginas = resultado.get("paginas")
    if not isinstance(paginas, list) or not paginas or not all(isinstance(p, str) for p in paginas):
        raise PdfRecusado("o arquivo está danificado ou não é um PDF")
    return Leitura(resumo(dados), len(dados), paginas)


def limitar() -> bool:
    """Aplica ao processo atual os tetos de memória e de processador, um a um. Diz se os dois valeram."""
    try:
        import resource
    except ImportError:
        return False
    aplicados = True
    for recurso, teto in ((resource.RLIMIT_AS, MEMORIA), (resource.RLIMIT_CPU, TEMPO)):
        try:
            rigido = resource.getrlimit(recurso)[1]
            teto = teto if rigido == resource.RLIM_INFINITY else min(teto, rigido)
            resource.setrlimit(recurso, (teto, teto))
        except (ValueError, OSError):
            aplicados = False
    return aplicados


def _filho(argv: list[str]) -> None:
    import logging
    logging.disable(logging.CRITICAL)
    if not limitar() and "exigir" in argv[1:]:
        saida = {"recusa": "este servidor não está preparado para ler PDF com segurança. Avise o responsável"}
    else:
        try:
            saida = {"paginas": extrair(sys.stdin.buffer.read(), int(argv[0]))}
        except PdfRecusado as e:
            saida = {"recusa": str(e)}
    sys.stdout.buffer.write(json.dumps(saida, ensure_ascii=False).encode("utf-8"))

