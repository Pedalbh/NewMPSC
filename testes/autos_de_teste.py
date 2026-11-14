"""Autos FICTÍCIOS para o primeiro teste com a API do Claude (cartão C10, opção A).

Três casos de tipos comuns, escritos para parecer autos de verdade, sem nenhum dado real: pessoas, lugares,
datas e números são inventados, e os números de processo têm dígito verificador inválido (-00). Não trazem
citação de lei nem de julgado: só fatos, como os autos que o motor vai ler.

`python -m testes.autos_de_teste` regrava os PDFs em `dados_ficticios/teste-api/`.
"""
from pathlib import Path

from testes.fabrica_pdf import pdf

PASTA = Path(__file__).parent.parent / "dados_ficticios" / "teste-api"
AVISO = "AUTOS FICTÍCIOS (teste da aplicação; nenhum dado real)"

FURTO = ("0000102-00.2026.8.24.0000", [
    f"{AVISO}\nProcesso 0000102-00.2026.8.24.0000\nAção Penal - Procedimento Ordinário\n\n"
    "Evento 1: denúncia.\n"
    "O Ministério Público oferece denúncia contra Pessoa C, porque, na madrugada\n"
    "de 3 de agosto de 2026, por volta das 2h30, na Rua das Acácias, n. 100,\n"
    "Bairro Centro, na cidade fictícia de Vila Exemplo, a pessoa denunciada\n"
    "rompeu o cadeado do portão da garagem da residência de Pessoa D e subtraiu\n"
    "uma bicicleta aro 29, cor azul, avaliada em R$ 2.400,00.\n"
    "A bicicleta foi encontrada no dia seguinte na casa da pessoa denunciada.\n"
    "Rol de testemunhas: Pessoa D (vítima); Policial E; Policial F.",
    "Evento 4: boletim de ocorrência.\n"
    "Comunicante: Pessoa D. Relata que, ao acordar, encontrou o cadeado do\n"
    "portão cortado e notou a falta da bicicleta. Uma câmera do vizinho, Pessoa G,\n"
    "gravou uma pessoa de moletom cinza empurrando uma bicicleta às 2h41.",
    "Evento 6: termo de reconhecimento e apreensão.\n"
    "Em 4 de agosto de 2026, os policiais E e F, com autorização de entrada dada\n"
    "por Pessoa H, que mora com a pessoa denunciada, encontraram no quintal uma\n"
    "bicicleta aro 29 azul. A vítima reconheceu a bicicleta pelo número de série.\n"
    "Também foi apreendido um alicate corta-vergalhão.",
    "Evento 9: laudo pericial.\n"
    "O cadeado examinado apresenta corte compatível com alicate corta-vergalhão.\n"
    "A bicicleta foi avaliada em R$ 2.400,00 e devolvida à vítima.",
    "Evento 15: interrogatório policial.\n"
    "A pessoa denunciada disse que comprou a bicicleta de um desconhecido por\n"
    "R$ 300,00, numa praça, sem recibo. Disse que o alicate é do trabalho.\n"
    "Não soube dizer onde estava na madrugada de 3 de agosto.",
    "Evento 22: decisão.\n"
    "Recebo a denúncia. Cite-se a pessoa acusada para resposta escrita em 10 dias.",
    "Evento 30: resposta à acusação.\n"
    "A defesa diz que não há prova de que a pessoa acusada estava no local e\n"
    "que a gravação não mostra o rosto. Pede a absolvição sumária e, se não for\n"
    "o caso, a oitiva da testemunha Pessoa J, que comprou peças da mesma praça.",
    "Evento 41: termo de audiência de instrução.\n"
    "Ouvidas a vítima, os policiais E e F e a testemunha de defesa Pessoa J.\n"
    "A vítima confirmou o reconhecimento pelo número de série.\n"
    "Pessoa J disse que viu a pessoa acusada comprar uma bicicleta na praça,\n"
    "mas não lembra a data nem a cor.\n"
    "Interrogada, a pessoa acusada manteve a versão da compra.\n"
    "Encerrada a instrução. Vista às partes para alegações finais por memoriais.",
])

TRAFICO = ("0000105-00.2026.8.24.0000", [
    f"{AVISO}\nProcesso 0000105-00.2026.8.24.0000\nAuto de Prisão em Flagrante\n\n"
    "Evento 1: auto de prisão em flagrante.\n"
    "Em 11 de novembro de 2026, às 19h10, na Praça do Coreto, cidade fictícia de\n"
    "Vila Exemplo, a guarnição dos policiais K e L abordou Pessoa M, que estava\n"
    "sentada num banco com uma mochila. Na mochila foram encontradas 18 porções\n"
    "de substância esverdeada e R$ 340,00 em notas trocadas.",
    "Evento 1, continuação: depoimentos.\n"
    "Policial K: a guarnição fazia ronda e viu Pessoa M entregar algo a um\n"
    "rapaz que fugiu de bicicleta. Na abordagem, encontrou a mochila.\n"
    "Policial L: confirmou a ronda e a abordagem; não viu a entrega.\n"
    "Pessoa M, ouvida, ficou em silêncio.",
    "Evento 3: laudo de constatação provisório.\n"
    "As 18 porções somam 41 gramas. O teste preliminar deu resultado positivo\n"
    "para a substância investigada. O laudo definitivo será juntado depois.",
    "Evento 5: certidão de antecedentes.\n"
    "Nada consta contra Pessoa M.",
    "Evento 8: pedido da defesa.\n"
    "A defesa diz que Pessoa M tem 19 anos, estuda e trabalha como entregador,\n"
    "com endereço fixo, e junta comprovante de matrícula e de residência.\n"
    "Diz que a droga era para consumo próprio e pede a liberdade provisória.",
    "Evento 10: termo de audiência de custódia.\n"
    "Pessoa M disse que não sofreu agressão. Disse que a mochila era sua e que\n"
    "o dinheiro era das entregas da semana.\n"
    "Decisão: a análise da prisão ficou para depois da manifestação do\n"
    "Ministério Público, com vista imediata.",
])

VIOLENCIA = ("0000106-00.2026.8.24.0000", [
    f"{AVISO}\nProcesso 0000106-00.2026.8.24.0000\nMedidas Protetivas de Urgência\n\n"
    "Evento 1: requerimento da vítima, na delegacia.\n"
    "Pessoa N relata que viveu com Pessoa O por cinco anos e que se separaram\n"
    "em setembro de 2026. Diz que, desde então, Pessoa O manda mensagens com\n"
    "ameaças e aparece na porta do trabalho dela. Pede que ele fique longe dela,\n"
    "de casa e do trabalho, e que não a procure por nenhum meio.",
    "Evento 1, continuação: termo de declarações.\n"
    "Em 2 de novembro de 2026, Pessoa O mandou mensagem dizendo que ela\n"
    "\"ia se arrepender\" se não voltasse. Em 4 de novembro, ele esperou na saída\n"
    "do trabalho dela e gritou com ela na frente de colegas.\n"
    "Pessoa N tem um filho de 6 anos com Pessoa O. Diz que tem medo.",
    "Evento 2: capturas de tela das mensagens.\n"
    "Doze mensagens de 1 a 5 de novembro. Entre elas: \"você vai ver\",\n"
    "\"não adianta fugir\", \"eu sei onde você trabalha\".",
    "Evento 3: formulário de avaliação de risco.\n"
    "Respostas da vítima: ameaça recente, sim; separação recente, sim;\n"
    "perseguição, sim; arma em casa, não sabe; agressão física antes, não.",
    "Evento 5: decisão.\n"
    "Defiro as medidas protetivas de afastamento de 300 metros da vítima, de\n"
    "casa e do trabalho dela, e de proibição de contato por qualquer meio.\n"
    "Intime-se Pessoa O. Vista ao Ministério Público.",
    "Evento 9: certidão do oficial de justiça.\n"
    "Pessoa O foi intimado em 8 de novembro de 2026.\n"
    "Evento 12: informação da vítima.\n"
    "Pessoa N diz que, em 12 de novembro, Pessoa O mandou nova mensagem\n"
    "por um perfil com outro nome: \"isso não vai ficar assim\".\n"
    "Ela também pergunta como ficam as visitas ao filho.",
])

CASOS = {"furto": FURTO, "trafico": TRAFICO, "violencia-domestica": VIOLENCIA}


def gravar(pasta: Path = PASTA) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    feitos = []
    for nome, (_, paginas) in CASOS.items():
        destino = pasta / f"{nome}.pdf"
        destino.write_bytes(pdf(paginas))
        feitos.append(destino)
    return feitos


if __name__ == "__main__":
    for caminho in gravar():
        print(caminho)
