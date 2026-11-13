"""A minuta como lista de blocos {texto, estilo} e a exportação para Word no padrão do Manual de Redação do MPSC
(Arial 12, entrelinha 1,5, corpo justificado com recuo de 3 cm, margens 3/2 cm). Sem biblioteca externa.
Adaptado de modulos/minuta/elaborador.py do repositório Gabinete (ver ORIGEM.md)."""
import re
import zipfile
from io import BytesIO

ESTILOS = ("endereco", "esquerda", "titulo", "secao", "corpo", "item", "centro", "direita")
MAX_BLOCOS = 400
MAX_TEXTO = 6000


def folha(m: dict) -> list[dict]:
    """Minuta estruturada (endereçamento, autos, parágrafos, pedidos, fecho) -> blocos na ordem do Manual."""
    b = [{"texto": m["enderecamento"], "estilo": "endereco"}, {"texto": f"Autos n. {m['autos']}", "estilo": "esquerda"}]
    for p in m["paragrafos"]:
        if p.get("secao"):
            b.append({"texto": p["secao"], "estilo": "secao"})
        b.append({"texto": p["texto"], "estilo": "corpo"})
    abre = f"Diante do exposto, o Ministério Público {m.get('verbo') or 'requer'}"
    itens = [x.rstrip(" .;") for x in m["pedidos"]]
    if len(itens) == 1:
        b.append({"texto": f"{abre} {itens[0]}.", "estilo": "corpo"})
    elif itens:
        b.append({"texto": f"{abre}:", "estilo": "corpo"})
        for i, x in enumerate(itens, 1):
            fim = "." if i == len(itens) else ("; e" if i == len(itens) - 1 else ";")
            b.append({"texto": f"{chr(96 + i)}) {x}{fim}", "estilo": "corpo"})
    b.append({"texto": m["fecho"], "estilo": "centro"})
    return b


def normalizar(blocos) -> list[dict]:
    """Blocos vindos da tela: só estilos conhecidos, texto limpo e dentro dos tetos. Levanta ValueError."""
    if not isinstance(blocos, list) or not blocos:
        raise ValueError("a minuta precisa de ao menos um parágrafo")
    if len(blocos) > MAX_BLOCOS:
        raise ValueError(f"a minuta passou de {MAX_BLOCOS} parágrafos")
    saida = []
    for b in blocos:
        if not isinstance(b, dict) or b.get("estilo") not in ESTILOS or not isinstance(b.get("texto"), str):
            raise ValueError("parágrafo em formato inesperado")
        texto = _limpo(b["texto"]).replace("\r\n", "\n").strip()
        if len(texto) > MAX_TEXTO:
            raise ValueError(f"parágrafo com mais de {MAX_TEXTO} caracteres")
        if texto:
            saida.append({"texto": texto, "estilo": b["estilo"]})
    if not saida:
        raise ValueError("a minuta precisa de ao menos um parágrafo")
    return saida


def texto_simples(blocos: list[dict]) -> str:
    return "\n\n".join(b["texto"] for b in blocos).strip() + "\n"


_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _limpo(s) -> str:
    # só caracteres válidos em XML 1.0
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]", "", str(s))


def docx(blocos: list[dict]) -> bytes:
    pars = []
    for b in blocos:
        est = b.get("estilo") or "corpo"
        jc = {"titulo": "center", "centro": "center", "direita": "right", "endereco": "left", "esquerda": "left",
              "secao": "left", "item": "left"}.get(est, "both")
        ind = '<w:ind w:firstLine="1701"/>' if est == "corpo" else ""
        negrito = "<w:b/>" if est in ("titulo", "endereco", "secao", "esquerda") else ""
        depois = "240" if est in ("endereco", "esquerda") else "120" if est == "secao" else "0"
        for linha in _limpo(b.get("texto") or "").split("\n") or [""]:
            pars.append(f'<w:p><w:pPr><w:spacing w:after="{depois}" w:line="360" w:lineRule="auto"/>{ind}'
                        f'<w:jc w:val="{jc}"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" '
                        f'w:cs="Arial"/>{negrito}<w:sz w:val="24"/></w:rPr><w:t xml:space="preserve">{_esc(linha)}'
                        '</w:t></w:r></w:p>')
    corpo = ("".join(pars) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1701" w:right="1134" '
             'w:bottom="1134" w:left="1701" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>')
    pacote = "http://schemas.openxmlformats.org/package/2006"
    arquivos = {
        "[Content_Types].xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="{pacote}/'
                               'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
                               'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                               '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                               'officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{pacote}/'
                       'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
                       '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W}><w:body>'
                             f'{corpo}</w:body></w:document>',
    }
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return buf.getvalue()
