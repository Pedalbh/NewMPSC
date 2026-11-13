"""DADOS FICTÍCIOS nos testes. Leitor da tabela exportada do SIG (fila de processos), pelo formato de
nucleo/contratos/SIG-TABELA.md. Só lê: nada aqui grava no SIG nem no eproc.

Entrada: os bytes do arquivo que o SIG grava com extensão .xls: Excel 97-2003 (BIFF), HTML, XML do Excel 2003,
.xlsx ou texto separado por ponto e vírgula ou tabulação (o formato é reconhecido pelo conteúdo). Saída: dicionário no contrato sig-tabela v1.0
(nucleo/contratos/sig-tabela.schema.json). Roda igual no ambiente e no Pyodide (xlrd 2.0.2, Python puro).

Regras (SIG-TABELA.md): cabeçalho achado pelo nome; coluna desconhecida guardada em `extras`; falta de Nº Judiciário
ou Entrada no cabeçalho recusa o arquivo; número com dígito verificador inválido, Entrada malformada ou número
repetido vão para `conferir`, nunca são descartados em silêncio. As Observações são lidas para a tela e não vão ao
Claude (minimização; `SO_TELA`)."""
import hashlib
import io
import re
from datetime import datetime

VERSAO = "1.0"
TETO_LINHAS = 5000
MAX_COLUNAS = 500                # a fila do SIG tem 18; acima disso o arquivo não é uma fila
TETO_BYTES = 20 * 1024 * 1024   # uma fila de 5000 linhas fica bem abaixo; acima disso, recusa antes de abrir
CODIFICACAO = "cp1252"   # o SIG não grava a página de código; cp1252 cobre o latin-1 e as aspas do Windows
SO_TELA = ("observacoes",)   # campos que só aparecem na tela e nunca entram em pedido ao Claude

OBRIGATORIAS = ("Nº Judiciário", "Entrada")
CONHECIDAS = {
    "Sel.": None, "Atividade realizada": None, "Fluxo paralelo": None, "Tipo de processo": None,
    "Pendência": "pendencia", "Dependentes": "dependentes", "Réu preso": "reu_preso",
    "Nº Judiciário": "judiciario", "Nº SIG": "sig", "Tarjas TJ": "tarjas", "Sistema": "sistema",
    "Entrada": "entrada", "Alocado para o usuário": "alocado", "Observação da fila": "obs_fila",
    "Observação do processo": "obs_processo", "Classe TJ": "classe", "Assunto Principal": "assunto", "Vista": "vista",
}
CNJ = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")
ASSINATURA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class TabelaRecusada(ValueError):
    """O arquivo não serve como tabela do SIG; a mensagem diz o que fazer."""


def dv_ok(numero):
    m = CNJ.match(numero or "")
    if not m:
        return False
    seq, dv, ano, j, tr, origem = m.groups()
    return 98 - (int(seq + ano + j + tr + origem) * 100) % 97 == int(dv)


def _texto(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip() if v is not None else ""


def _sim(v):
    return _texto(v).upper() == "S"


def _entrada(v, data_excel=None):
    """Texto DD/MM/AAAA HH:MM:SS (como o SIG exporta) ou célula de data do Excel (`data_excel` = datetime)."""
    if data_excel is not None:
        return data_excel.replace(microsecond=0).isoformat()
    try:
        return datetime.strptime(_texto(v), "%d/%m/%Y %H:%M:%S").isoformat()
    except ValueError:
        return None


def _tarjas(v):
    return [t for t in re.findall(r"#([^#;]+)#", _texto(v)) if t]


# ------------------------------------------------------------------ formatos de arquivo (todos viram uma grade)
def _limitar(grade, linha):
    """Teto durante a leitura, antes de a grade crescer: nenhum formato passa de TETO_LINHAS+100 linhas nem de
    MAX_COLUNAS colunas, nem com células mescladas."""
    if len(grade) > TETO_LINHAS + 100:
        raise TabelaRecusada(f"a tabela tem mais de {TETO_LINHAS} linhas; exporte só a fila de trabalho")
    if len(linha) > MAX_COLUNAS:
        raise TabelaRecusada(f"planilha com mais de {MAX_COLUNAS} colunas; exporte só a fila de trabalho")


# O SIG grava com extensão .xls arquivos que por dentro podem ser Excel 97-2003 (BIFF), HTML, XML do Excel 2003,
# .xlsx ou texto separado. Cada leitor devolve uma grade (lista de linhas de valores); data do Excel vem como
# datetime. Só biblioteca padrão, salvo o xlrd para o BIFF. A mensagem de recusa nunca traz conteúdo do arquivo.

def _decodificar(dados, padrao=CODIFICACAO):
    if dados.startswith(b"\xff\xfe") or dados.startswith(b"\xfe\xff"):
        return dados.decode("utf-16")
    if dados.startswith(b"\xef\xbb\xbf"):
        return dados[3:].decode("utf-8")
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode(padrao, errors="replace")


# Excel sem o envelope OLE (o SIG grava assim, em BIFF4): o arquivo começa direto no registro BOF da planilha.
BOF_BIFF_CRU = (b"\x09\x00", b"\x09\x02", b"\x09\x04", b"\x09\x08")   # BIFF2, 3, 4 e 5/8


def _formato(dados):
    if dados.startswith(ASSINATURA_OLE) or dados[:2] in BOF_BIFF_CRU:
        return "xls"
    if dados.startswith(b"PK\x03\x04"):
        return "xlsx"
    inicio = _decodificar(dados[:4096]).lstrip("\ufeff \t\r\n").lower()
    if inicio.startswith("<?xml") and "urn:schemas-microsoft-com:office:spreadsheet" in _decodificar(dados[:20000]).lower():
        return "xml2003"
    if inicio.startswith("<") and re.search(r"<(html|table|tr)\b", _decodificar(dados[:200000]).lower()):
        return "html"
    if not inicio.startswith("<") and "\x00" not in inicio and (";" in inicio or "\t" in inicio):
        return "texto"
    return None


def _grade_xls(dados):
    import xlrd   # importado aqui: o resto do núcleo roda sem ele
    try:
        livro = xlrd.open_workbook(file_contents=dados, encoding_override=CODIFICACAO,
                                   on_demand=dados.startswith(ASSINATURA_OLE), logfile=io.StringIO())
        aba = livro.sheet_by_index(0)
    except Exception as e:   # xlrd levanta vários tipos; para quem usa, a mensagem é a mesma
        raise TabelaRecusada(f"não foi possível ler a planilha ({type(e).__name__}); exporte a fila do SIG de novo")
    grade = []
    for r in range(aba.nrows):
        linha = []
        for c in range(aba.ncols):
            v = aba.cell_value(r, c)
            if aba.cell_type(r, c) == xlrd.XL_CELL_DATE:
                try:
                    v = xlrd.xldate_as_datetime(v, livro.datemode)
                except Exception:
                    pass
            linha.append(v)
        grade.append(linha)
    return grade


def _grade_html(dados):
    from html.parser import HTMLParser
    texto = _decodificar(dados)
    m = re.search(r"charset\s*=\s*[\"']?([\w-]+)", texto[:4096], re.I)
    if m and m.group(1).lower() not in ("utf-8", "utf8"):
        try:
            texto = dados.decode(m.group(1), errors="replace")
        except LookupError:
            pass

    class Leitor(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.grade, self.linha, self.celula, self.span = [], None, None, 1

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.linha = []
            elif tag in ("td", "th") and self.linha is not None:
                self.celula = []
                span = dict(attrs).get("colspan") or "1"
                self.span = min(int(span), MAX_COLUNAS) if span.isdigit() and int(span) > 1 else 1
            elif tag == "br" and self.celula is not None:
                self.celula.append("\n")

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.celula is not None:
                self.linha.append("".join(self.celula).strip())
                self.linha.extend([""] * (self.span - 1))     # célula mesclada ocupa as colunas que cobre
                self.celula = None
                _limitar(self.grade, self.linha)
            elif tag == "tr" and self.linha is not None:
                _limitar(self.grade, self.linha)
                self.grade.append(self.linha)
                self.linha = None

        def handle_data(self, data):
            if self.celula is not None:
                self.celula.append(data)

    leitor = Leitor()
    leitor.feed(texto)
    if not leitor.grade:
        raise TabelaRecusada("o arquivo é uma página HTML sem tabela; exporte a fila do SIG de novo")
    return leitor.grade


def _grade_xml2003(dados):
    import xml.etree.ElementTree as ET
    ns = "{urn:schemas-microsoft-com:office:spreadsheet}"
    try:
        raiz = ET.fromstring(dados)
    except ET.ParseError:
        raise TabelaRecusada("o XML da planilha está corrompido; exporte a fila do SIG de novo")
    tabela = raiz.find(f"{ns}Worksheet/{ns}Table")
    if tabela is None:
        raise TabelaRecusada("o XML não tem planilha; exporte a fila do SIG de novo")
    grade = []
    for row in tabela.findall(f"{ns}Row"):
        linha = []
        for cel in row.findall(f"{ns}Cell"):
            idx = cel.get(f"{ns}Index")
            if idx and idx.isdigit():
                if int(idx) > MAX_COLUNAS:
                    raise TabelaRecusada(f"planilha com mais de {MAX_COLUNAS} colunas; exporte só a fila de trabalho")
                linha.extend([""] * (int(idx) - 1 - len(linha)))
            d = cel.find(f"{ns}Data")
            linha.append("".join(d.itertext()) if d is not None else "")
            junta = cel.get(f"{ns}MergeAcross")
            if junta and junta.isdigit():
                linha.extend([""] * min(int(junta), MAX_COLUNAS))
            _limitar(grade, linha)
        _limitar(grade, linha)
        grade.append(linha)
    return grade


def _grade_xlsx(dados):
    import zipfile
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
        nomes = z.namelist()
        folha = "xl/worksheets/sheet1.xml" if "xl/worksheets/sheet1.xml" in nomes else \
            sorted(n for n in nomes if n.startswith("xl/worksheets/") and n.endswith(".xml"))[0]
        if z.getinfo(folha).file_size > TETO_BYTES * 5:
            raise TabelaRecusada("planilha grande demais depois de descompactada; exporte só a fila de trabalho")
        compartilhadas = []
        if "xl/sharedStrings.xml" in nomes and z.getinfo("xl/sharedStrings.xml").file_size > TETO_BYTES * 5:
            raise TabelaRecusada("planilha grande demais depois de descompactada; exporte só a fila de trabalho")
        if "xl/sharedStrings.xml" in nomes:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{ns}si"):
                compartilhadas.append("".join(t.text or "" for t in si.iter(f"{ns}t")))
        raiz = ET.fromstring(z.read(folha))
    except TabelaRecusada:
        raise
    except Exception as e:
        raise TabelaRecusada(f"não foi possível ler a planilha .xlsx ({type(e).__name__}); exporte a fila do SIG de novo")

    def col(ref, atual):
        m = re.match(r"([A-Z]{1,3})\d*$", ref or "")
        if not m:
            return atual
        n = 0
        for ch in m.group(1):
            n = n * 26 + ord(ch) - 64
        return n - 1
    grade = []
    for row in raiz.iter(f"{ns}row"):
        linha = {}
        prox = 0
        for c in row.findall(f"{ns}c"):
            t = c.get("t")
            if t == "inlineStr":
                v = "".join(x.text or "" for x in c.iter(f"{ns}t"))
            else:
                ve = c.find(f"{ns}v")
                v = ve.text if ve is not None else ""
                if t == "s" and v.isdigit() and int(v) < len(compartilhadas):
                    v = compartilhadas[int(v)]
            i = col(c.get("r"), prox)
            if i >= MAX_COLUNAS:
                raise TabelaRecusada(f"planilha com mais de {MAX_COLUNAS} colunas; exporte só a fila de trabalho")
            linha[i] = v or ""
            prox = i + 1
        rr = row.get("r")
        r = int(rr) - 1 if rr and rr.isdigit() else len(grade)
        if r > TETO_LINHAS + 100:
            raise TabelaRecusada(f"a tabela tem mais de {TETO_LINHAS} linhas; exporte só a fila de trabalho")
        while len(grade) < r:
            grade.append([])
        grade.append([linha.get(i, "") for i in range(max(linha) + 1)] if linha else [])
    return grade


def _grade_texto(dados):
    import csv
    texto = _decodificar(dados)
    amostra = "\n".join(texto.splitlines()[:20])
    sep = max(";\t,", key=lambda c: amostra.count(c))
    grade = []
    for r in csv.reader(io.StringIO(texto), delimiter=sep):
        _limitar(grade, r)
        grade.append(list(r))
    return grade


LEITORES = {"xls": _grade_xls, "html": _grade_html, "xml2003": _grade_xml2003, "xlsx": _grade_xlsx, "texto": _grade_texto}


def _abrir(dados):
    if not dados:
        raise TabelaRecusada("arquivo vazio: exporte a fila do SIG de novo")
    if len(dados) > TETO_BYTES:
        raise TabelaRecusada("arquivo grande demais para uma fila do SIG (mais de 20 MB); exporte só a fila de trabalho")
    formato = _formato(dados)
    if formato is None:
        raise TabelaRecusada("formato não reconhecido (esperado: Excel, HTML, XML do Excel ou texto separado); "
                             "exporte a fila do SIG de novo")
    try:
        grade = LEITORES[formato](dados)
    except TabelaRecusada:
        raise
    except Exception as e:   # qualquer outro erro de leitura vira recusa clara, nunca derruba a página
        raise TabelaRecusada(f"não foi possível ler o arquivo ({formato}, {type(e).__name__}); "
                             "exporte a fila do SIG de novo")
    larg = max((len(r) for r in grade), default=0)
    if larg > MAX_COLUNAS:
        raise TabelaRecusada(f"planilha com mais de {MAX_COLUNAS} colunas; exporte só a fila de trabalho")
    return formato, [list(r) + [""] * (larg - len(r)) for r in grade]


def _achar_cabecalho(grade):
    """A linha que tem as duas colunas obrigatórias; sem ela, a primeira que tenha uma (para a recusa dizer o que
    falta). Um título igual a "Entrada" não engana: a linha com as duas vence."""
    parcial = (None, [])
    for r, linha in enumerate(grade[:30]):
        nomes = [_texto(v) for v in linha]
        if all(o in nomes for o in OBRIGATORIAS):
            return r, nomes
        if parcial[0] is None and any(o in nomes for o in OBRIGATORIAS):
            parcial = (r, nomes)
    return parcial


def ler(dados, nome=None, modificado=None):
    formato, grade = _abrir(dados)
    r0, nomes = _achar_cabecalho(grade)
    faltam = [c for c in OBRIGATORIAS if c not in nomes]
    if r0 is None or faltam:
        raise TabelaRecusada("faltam colunas obrigatórias no cabeçalho: " + ", ".join(faltam or OBRIGATORIAS))
    if len(grade) - r0 - 1 > TETO_LINHAS:
        raise TabelaRecusada(f"a tabela tem mais de {TETO_LINHAS} linhas; exporte só a fila de trabalho")

    linhas, conferir, vistos = [], [], set()
    # coluna sem nome vira "Coluna N"; nome repetido ganha sufixo e vai para conferir (nada some em silêncio)
    rotulos, contagem = [], {}
    for c, col in enumerate(nomes):
        col = col or f"Coluna {c + 1}"
        if col in contagem:
            contagem[col] += 1
            conferir.append({"linha": r0 + 1, "motivo": f"coluna repetida no cabeçalho: {col}"})
            col = f"{col} ({contagem[col]})"
        else:
            contagem[col] = 1
        rotulos.append(col)
    for r in range(r0 + 1, len(grade)):
        bruto = dict(zip(rotulos, grade[r]))
        if not any(_texto(v) for v in bruto.values()):
            continue
        n = _texto(bruto.get("Nº Judiciário"))
        if not n:
            conferir.append({"linha": r + 1, "motivo": "linha sem Nº Judiciário"})
            continue
        if n in vistos:
            conferir.append({"linha": r + 1, "numero": n, "motivo": "número repetido na tabela"})
            continue
        vistos.add(n)
        ok = dv_ok(n)
        if not ok:
            conferir.append({"linha": r + 1, "numero": n, "motivo": "número com dígito verificador inválido"})
        v_entrada = bruto.get("Entrada")
        entrada = _entrada(v_entrada, v_entrada if isinstance(v_entrada, datetime) else None)
        if entrada is None:
            conferir.append({"linha": r + 1, "numero": n, "motivo": "Entrada fora do formato DD/MM/AAAA HH:MM:SS"})
        linhas.append({
            "judiciario": n,
            "dv_ok": ok,
            "sig": _texto(bruto.get("Nº SIG")),
            "reu_preso": _sim(bruto.get("Réu preso")),
            "vista": _texto(bruto.get("Vista")),
            "entrada_iso": entrada,
            "pendencia": _texto(bruto.get("Pendência")),
            "dependentes": _sim(bruto.get("Dependentes")),
            "tarjas": _tarjas(bruto.get("Tarjas TJ")),
            "classe": _texto(bruto.get("Classe TJ")),
            "assunto": _texto(bruto.get("Assunto Principal")),
            "sistema": _texto(bruto.get("Sistema")),
            "alocado": _texto(bruto.get("Alocado para o usuário")),
            "observacoes": {"fila": _texto(bruto.get("Observação da fila")),
                            "processo": _texto(bruto.get("Observação do processo"))},
            "extras": {k: _texto(v) for k, v in bruto.items() if k not in CONHECIDAS and _texto(v)},
        })
    return {
        "versao": VERSAO,
        "formato": formato,
        "lida_em": datetime.now().replace(microsecond=0).isoformat(),
        "arquivo": {"nome": nome, "sha256": hashlib.sha256(dados).hexdigest(), "modificado": modificado},
        "linhas": linhas,
        "conferir": conferir,
    }
