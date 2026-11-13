# Central de cartões

Cada decisão que é do titular vira um cartão aqui. O resto o coordenador decide e segue, deixando registrado no PR. A régua está no `CLAUDE.md`.

Como responder: diga na conversa o número do cartão e a opção (por exemplo, "C1: A"). O coordenador registra a decisão aqui, com a data, e segue.

## Abertos

### C1 · Por quanto tempo o texto dos autos fica guardado
- **Por que é sua:** prazo de guarda de dado de processo criminal (LGPD).
- **Hoje:** fica até alguém remover à mão.
- **Opções**
  - **A.** Apagar sozinho 30 dias depois de o processo ser marcado como concluído. Se o processo voltar à fila antes disso, o prazo zera.
  - **B.** Apagar sozinho N dias depois do envio, com o processo concluído ou não.
  - **C.** Manter como está, só remoção à mão.
- **Recomendo:** A. O texto existe enquanto serve ao trabalho e some sem depender de alguém lembrar.
- **O que espera:** nada agora. Precisa estar decidido antes de dado real (etapa 6).

### C2 · Guardar ou não a impressão digital do arquivo original
- **Por que é sua:** a impressão digital (`sha256`) permite provar que alguém teve um documento específico. Hoje ela só serve para avisar que o arquivo já foi enviado.
- **Opções**
  - **A.** Manter como está.
  - **B.** Trocar por uma impressão que só o servidor consegue refazer (com chave do servidor). Continua avisando arquivo repetido, mas não serve de prova fora do servidor.
  - **C.** Não guardar nada. Arquivo repetido entra duas vezes.
- **Recomendo:** B. Mantém a utilidade e tira o risco.
- **O que espera:** nada agora. Mudança pequena, feita em qualquer etapa depois da decisão.

### C3 · Quanto texto de autos cada usuário pode guardar
- **Por que é sua:** define o quanto de dado cada pessoa acumula no servidor.
- **Hoje (provisório):** 200 milhões de caracteres por usuário, perto de 80 mil páginas cheias; 50 MB e 2.000 páginas por arquivo; 30 arquivos por processo.
- **Opções**
  - **A.** Manter os números provisórios e rever com autos reais, quando houver.
  - **B.** Definir agora outros números.
- **Recomendo:** A. Sem autos reais, qualquer número novo seria chute.
- **O que espera:** nada.

### C4 · Contrato e base legal antes de texto real ir para a API do Claude
- **Por que é sua:** destino novo de dado, fora do MPSC e fora do país, e contrato.
- **Contexto:** a etapa 2 liga a aplicação à API do Claude, direta (decisão sua de 13/11/2026). O processamento é nos Estados Unidos, salvo contrato com outra região. O parecer de segurança marcou como CONFERIR, em fonte oficial: enquadramento na LGPD, regime de transferência internacional e normas do CNMP e do MPSC.
- **Opções**
  - **A.** A etapa 2 é construída e testada só com dados fictícios. Dado real fica barrado até haver contrato institucional e parecer do encarregado de dados do MPSC. Em paralelo, o coordenador prepara um resumo de uma página para você levar à área de TI e ao encarregado.
  - **B.** Igual a A, sem o resumo: você conduz a conversa institucional por conta própria.
  - **C.** Segurar a etapa 2 até o contrato existir.
- **Recomendo:** A. O trabalho técnico não depende do contrato, e o resumo adianta a conversa.
- **O que espera:** o uso com dado real. A construção da etapa 2 não espera.

### C5 · Qual fonte de legislação vigente a aplicação consulta
- **Por que é sua:** define o que vale como fonte oficial de conteúdo jurídico (limite 5 do `CLAUDE.md`) e pode ter custo.
- **Contexto:** a busca no diretório de conectores não achou nenhum de legislação brasileira (a busca cobre só parte do diretório).
- **Opções**
  - **A.** Na etapa 3, a aplicação confere só jurisprudência (JuriBase). Toda citação de lei aparece marcada como "não conferida", para você conferir à mão.
  - **B.** A aplicação consulta direto as fontes oficiais abertas (Planalto, LexML). Depende de avaliação técnica do que cada uma oferece; essa avaliação ainda não foi feita.
  - **C.** Contratar um serviço pago de legislação.
- **Recomendo:** A agora, com a avaliação de B feita no começo da etapa 3 e trazida num cartão novo.
- **O que espera:** a etapa 3.

### C6 · Como a aplicação acessa o JuriBase
- **Por que é sua:** contrato e possível custo com um terceiro.
- **Contexto:** você definiu o JuriBase para a jurisprudência. Hoje ele está ligado à sua conta do Claude como conector. A aplicação no servidor precisa de um acesso próprio, e não sei em que condições o JuriBase oferece isso (acesso para aplicações, preço, termos).
- **Opções**
  - **A.** Você consulta o JuriBase sobre acesso para aplicações e traz as condições.
  - **B.** O coordenador levanta o que estiver publicado e traz um cartão novo com as condições e o custo.
- **Recomendo:** B.
- **O que espera:** a etapa 3.

## Decididos

| Cartão | Decisão | Quando |
| --- | --- | --- |
| Motor de IA | API do Claude direta | 13/11/2026 |
| Fonte de jurisprudência | JuriBase | 13/11/2026 |
| Merge | Com os revisores aprovando e o CI verde, o coordenador faz o merge sem perguntar | 13/11/2026 |
| Onde vivem os cartões | Neste arquivo; o coordenador traz cada cartão aberto na conversa | 13/11/2026 |
