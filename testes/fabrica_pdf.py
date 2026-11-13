"""Fabrica PDFs FICTÍCIOS para os testes, sem biblioteca: um texto por página, fonte Helvetica.
`python -m testes.fabrica_pdf` regrava `dados_ficticios/autos-ficticios.pdf`."""
from pathlib import Path

AUTOS_FICTICIOS = [
    "AUTOS FICTÍCIOS (demonstração)\nProcesso 0000101-00.2026.8.24.0000\nEvento 1: denúncia.\n"
    "Pessoa A é acusada de subtrair um objeto de Pessoa B.",
    "Evento 2: decisão de recebimento da denúncia.\nCite-se a pessoa acusada.",
    "Evento 3: resposta à acusação.\nA defesa pede a absolvição.",
]


def _conteudo(texto: str) -> bytes:
    linhas = ["BT", "/F1 12 Tf", "72 760 Td", "16 TL"]
    for linha in texto.split("\n"):
        escapada = linha.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        linhas.append(f"({escapada}) Tj T*")
    linhas.append("ET")
    return "\n".join(linhas).encode("cp1252")


def pdf(paginas: list[str]) -> bytes:
    """Um PDF válido com uma página por item. Texto vazio vira página sem texto, como a de um documento digitalizado."""
    n = len(paginas)
    objetos = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Count {n} /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] >>".encode(),
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    for i, texto in enumerate(paginas):
        fluxo = _conteudo(texto) if texto else b""
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {5 + 2 * i} 0 R "
                       f"/Resources << /Font << /F1 3 0 R >> >> >>".encode())
        objetos.append(f"<< /Length {len(fluxo)} >>\nstream\n".encode() + fluxo + b"\nendstream")
    saida, posicoes = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for numero, corpo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n".encode() + corpo + b"\nendobj\n"
    inicio_tabela = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for p in posicoes:
        saida += f"{p:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_tabela}\n%%EOF\n".encode()
    return bytes(saida)


if __name__ == "__main__":
    destino = Path(__file__).parent.parent / "dados_ficticios" / "autos-ficticios.pdf"
    destino.write_bytes(pdf(AUTOS_FICTICIOS))
    print(destino)
