# Central de cartões

Cada decisão que é do titular vira um cartão aqui. O resto o coordenador decide e segue, deixando registrado no PR. A régua está no `CLAUDE.md`.

Como responder: diga na conversa o número do cartão e a opção (por exemplo, "C1: A"). A resposta já é a ordem de execução: o coordenador registra a decisão aqui, com a data, e executa na hora o que está em **Depois da decisão** da opção escolhida, sem nova pergunta. O caminho é o de sempre: ramo, PR com testes, revisores do nível da tarefa, CI verde, merge.

O coordenador só volta a perguntar se, durante a execução, aparecer fato novo que mude o efeito descrito na opção (isso vira cartão novo, e o resto da execução segue). Passo que só o titular pode dar (chave de API, contrato, conversa institucional) fica listado em **O que você faz**; o coordenador executa tudo o que não depende dele.

## Estrutura de cada cartão
- **Título:** a pergunta numa frase.
- **Por que é sua:** qual item da régua do `CLAUDE.md` o traz para cá.
- **Hoje** ou **Contexto:** como está agora e o que se sabe.
- **Opções:** cada uma com o efeito e, logo abaixo, **Depois da decisão:** o que o coordenador executa sozinho se ela for escolhida.
- **Recomendo:** a opção e o porquê, numa linha.
- **O que espera:** o que fica parado sem resposta.
- **O que você faz** (só quando há): passo que só o titular pode dar.

## Abertos

### C1 · Por quanto tempo o texto dos autos fica guardado?
- **Por que é sua:** prazo de guarda de dado de processo criminal (LGPD).
- **Hoje:** fica até alguém remover à mão.
- **Opções**
  - **A.** Apagar sozinho 30 dias depois de o processo ser marcado como concluído. Se o processo voltar à fila antes disso, o prazo zera.
    - **Depois da decisão:** regra de apagamento automático, com teste (apaga no 31º dia; volta à fila zera o prazo; outro usuário não é afetado); revisor de qualidade e de segurança.
  - **B.** Apagar sozinho N dias depois do envio, com o processo concluído ou não.
    - **Depois da decisão:** mesma construção e mesmos testes de A, contando do envio. Precisa de N na resposta (por exemplo, "C1: B, 90 dias").
  - **C.** Manter como está, só remoção à mão.
    - **Depois da decisão:** só o registro aqui. Volta como cartão antes da etapa 6.
- **Recomendo:** A. O texto existe enquanto serve ao trabalho e some sem depender de alguém lembrar.
- **O que espera:** nada agora. Precisa estar decidido antes de dado real (etapa 6).

### C2 · A impressão digital do arquivo original continua guardada?
- **Por que é sua:** dado e LGPD. A impressão digital (`sha256`) permite provar que alguém teve um documento específico.
- **Hoje:** ela só serve para avisar que o arquivo já foi enviado.
- **Opções**
  - **A.** Manter como está. O risco de prova continua.
    - **Depois da decisão:** só o registro aqui.
  - **B.** Trocar por uma impressão que só o servidor consegue refazer (com chave do servidor). Continua avisando arquivo repetido, mas não serve de prova fora do servidor.
    - **Depois da decisão:** troca do `sha256` pela impressão com chave do servidor (HMAC), conversão dos registros existentes, teste de arquivo repetido; revisor de segurança.
  - **C.** Não guardar nada. Arquivo repetido entra duas vezes e ocupa o limite de texto em dobro.
    - **Depois da decisão:** apaga a coluna, tira o aviso de arquivo repetido da tela e do teste da jornada; revisor de qualidade e designer.
- **Recomendo:** B. Mantém a utilidade e tira o risco.
- **O que espera:** nada agora. Mudança pequena, feita em qualquer etapa depois da decisão.

### C3 · Quanto texto de autos cada usuário pode guardar?
- **Por que é sua:** define o quanto de dado cada pessoa acumula no servidor.
- **Hoje (provisório):** 200 milhões de caracteres por usuário, perto de 80 mil páginas cheias; 50 MB e 2.000 páginas por arquivo; 30 arquivos por processo.
- **Opções**
  - **A.** Manter os números provisórios e rever com autos reais, quando houver.
    - **Depois da decisão:** só o registro aqui. Volta como cartão quando houver autos reais.
  - **B.** Definir agora outros números. Valem já, para todos os usuários.
    - **Depois da decisão:** troca dos números em `app/servicos.py` e `app/autos.py`, com os testes de limite ajustados. Precisa dos números na resposta (por exemplo, "C3: B, 100 milhões").
- **Recomendo:** A. Sem autos reais, qualquer número novo seria chute.
- **O que espera:** nada.

### C4 · O que precisa existir antes de texto real ir para a API do Claude?
- **Por que é sua:** destino novo de dado, fora do MPSC e fora do país, e contrato.
- **Contexto:** a etapa 2 liga a aplicação à API do Claude, direta (decisão sua de 13/11/2026). A aplicação pede que o processamento seja nos Estados Unidos (sem esse pedido, o padrão do serviço é qualquer região). O parecer de segurança marcou como CONFERIR, em fonte oficial: enquadramento na LGPD (art. 4º, III, "d", e art. 33), a Resolução CD/ANPD nº 19/2024 sobre transferência internacional, as normas do CNMP e do MPSC sobre uso de IA, e o prazo de retenção do lado da Anthropic. Segundo a documentação da Anthropic, conteúdo retido não treina modelo sem permissão, e a retenção zero é um acordo comercial, não uma opção de painel.
- **Opções**
  - **A.** A etapa 2 é construída e testada só com dados fictícios. Dado real fica barrado até haver contrato institucional e parecer do encarregado de dados do MPSC. Em paralelo, o coordenador prepara um resumo de uma página para você levar à área de TI e ao encarregado.
    - **Depois da decisão:** trava de dado real mantida como está; o coordenador escreve o resumo de uma página em `docs/` e o entrega na conversa.
  - **B.** Igual a A, sem o resumo: você conduz a conversa institucional por conta própria.
    - **Depois da decisão:** só o registro aqui; trava mantida.
  - **C.** Segurar a etapa 2 até o contrato existir.
    - **Depois da decisão:** a opção `NEWMPSC_MOTOR=claude` passa a ser recusada em todos os ambientes, com teste, até o contrato; a etapa 2 fica pronta, sem uso.
- **Recomendo:** A. O trabalho técnico não depende do contrato, e o resumo adianta a conversa.
- **O que espera:** o uso com dado real. A construção da etapa 2 não espera.
- **O que você faz:** levar o resumo (ou conduzir a conversa) à TI e ao encarregado de dados do MPSC.

### C5 · Qual fonte de legislação vigente a aplicação consulta?
- **Por que é sua:** define o que vale como fonte oficial de conteúdo jurídico (limite 5 do `CLAUDE.md`) e pode ter custo.
- **Contexto:** a busca no diretório de conectores não achou nenhum de legislação brasileira (a busca cobre só parte do diretório).
- **Opções**
  - **A.** Na etapa 3, a aplicação confere só jurisprudência (JuriBase). Toda citação de lei aparece marcada como "não conferida", para você conferir à mão.
    - **Depois da decisão:** na etapa 3, toda citação de lei sai marcada "não conferida"; a avaliação de B entra no começo da etapa 3 e volta como cartão novo.
  - **B.** A aplicação consulta direto as fontes oficiais abertas (Planalto, LexML). Depende de avaliação técnica do que cada uma oferece; essa avaliação ainda não foi feita.
    - **Depois da decisão:** avaliação técnica de Planalto e LexML, trazida como cartão novo antes de ligar qualquer uma (destino novo de dado).
  - **C.** Contratar um serviço pago de legislação.
    - **Depois da decisão:** levantamento de serviços e preços, trazido como cartão novo para escolher (contrato).
- **Recomendo:** A agora, com a avaliação de B feita no começo da etapa 3 e trazida num cartão novo.
- **O que espera:** a etapa 3.

### C6 · Como a aplicação passa a acessar o JuriBase?
- **Por que é sua:** contrato e possível custo com um terceiro.
- **Contexto:** você definiu o JuriBase para a jurisprudência. Hoje ele está ligado à sua conta do Claude como conector. A aplicação no servidor precisa de um acesso próprio, e não sei em que condições o JuriBase oferece isso (acesso para aplicações, preço, termos).
- **Opções**
  - **A.** Você consulta o JuriBase sobre acesso para aplicações e traz as condições. A etapa 3 espera a sua consulta.
    - **Depois da decisão:** nada até as condições chegarem; com elas, cartão novo.
  - **B.** O coordenador levanta o que estiver publicado. Nenhum contato com o JuriBase em seu nome.
    - **Depois da decisão:** levantamento do que o JuriBase publica sobre acesso para aplicações, preço e termos, trazido como cartão novo.
- **Recomendo:** B.
- **O que espera:** a etapa 3.
- **O que você faz:** na opção A, consultar o JuriBase.

### C7 · O que o motor de IA escreve antes de existir a verificação de fontes?
- **Por que é sua:** conteúdo jurídico (limite 5 do `CLAUDE.md`).
- **Hoje (como a etapa 2 foi construída):** o motor escreve só o relatório dos fatos, com a página de cada parágrafo, e a lista de pontos a enfrentar. Fundamentação e pedido ficam em branco, marcados para você.
- **Opções**
  - **A.** Manter assim até a verificação de fontes (etapa 3) existir.
    - **Depois da decisão:** só o registro aqui; a etapa 2 já está assim.
  - **B.** Deixar o motor rascunhar também a fundamentação, com toda citação de lei e de julgado marcada como "não conferida". Exige mudar o limite 5.
    - **Depois da decisão:** cartão novo com o texto do limite 5 alterado (mudança de regra do projeto); só depois dele o motor passa a rascunhar a fundamentação.
- **Recomendo:** A. É o que o limite 5 já manda, e o relatório é a parte que mais poupa leitura.
- **O que espera:** nada. A etapa 2 já segue a opção A.

### C8 · Qual modelo o motor usa, e com que teto de gasto?
- **Por que é sua:** dinheiro.
- **Hoje:** `claude-opus-5-5`, o padrão recomendado pela Anthropic. Preço de tabela em 03/11/2026: US$ 4 por milhão de tokens de entrada e US$ 20 por milhão de saída. Estimativa minha, sem medição: autos de 500 páginas dão algo como 400 mil tokens de entrada, perto de US$ 2 por relatório; autos de 50 páginas, perto de US$ 0,20. Limites atuais por usuário: 20 pedidos por hora e 60 por dia. No pior caso (autos no tamanho máximo), o parecer de segurança calculou cerca de US$ 2,70 por pedido.
- **Opções**
  - **A.** Manter o modelo padrão e medir o custo real nos primeiros testes com dados fictícios, antes de fixar um teto.
    - **Depois da decisão:** no primeiro teste com a API de verdade, o coordenador mede o custo por relatório e traz o resultado num cartão novo de teto.
  - **B.** Trocar já por um modelo mais barato (`claude-sonnet-5-5`, metade do preço), aceitando relatório possivelmente pior.
    - **Depois da decisão:** troca do modelo padrão em `app/motor_claude.py`, com teste.
  - **C.** Fixar agora um teto mensal em dólares.
    - **Depois da decisão:** trava de gasto mensal por servidor, com teste; precisa do valor na resposta (por exemplo, "C8: C, US$ 50").
- **Recomendo:** A.
- **O que espera:** o primeiro teste com a API de verdade.
- **O que você faz:** criar a chave da API; o coordenador a pede por formulário seguro, nunca na conversa.

### C9 · O que fazer quando o modelo declina um pedido, e onde ele processa?
- **Por que é sua:** destino do dado (qual modelo e em que região o texto é processado) e custo.
- **Contexto:** a API da Anthropic oferece passar o pedido a outro modelo quando o primeiro declina. A rota dessa troca não é publicada por modelo, e o parecer de segurança não conseguiu confirmar se ela é compatível com retenção zero. Sobre a região: restringir aos Estados Unidos custa 10% a mais; o padrão do serviço é qualquer região.
- **Hoje (como a etapa 2 foi construída):** sem troca de modelo (se o modelo declina, a tela avisa e você escreve à mão) e processamento pedido para os Estados Unidos.
- **Opções**
  - **A.** Manter assim.
    - **Depois da decisão:** só o registro aqui; a etapa 2 já está assim.
  - **B.** Ligar a troca de modelo, só para uma lista de modelos que você aprovar.
    - **Depois da decisão:** troca de modelo ligada só para a lista dada na resposta, com teste; revisor de segurança.
  - **C.** Deixar o processamento em qualquer região, 10% mais barato.
    - **Depois da decisão:** tira o pedido de região dos Estados Unidos, com teste; revisor de segurança.
- **Recomendo:** A, até haver contrato e a questão da retenção estar conferida.
- **O que espera:** nada.

## Decididos

Cada linha diz também como ficou a execução: o PR que a cumpriu, "nada a executar" ou o que ainda falta.

| Cartão | Decisão | Quando | Execução |
| --- | --- | --- | --- |
| Motor de IA | API do Claude direta | 13/11/2026 | PR #5 |
| Fonte de jurisprudência | JuriBase | 13/11/2026 | falta o acesso da aplicação (C6) |
| Merge | Com os revisores aprovando e o CI verde, o coordenador faz o merge sem perguntar | 13/11/2026 | nada a executar |
| Onde vivem os cartões | Neste arquivo; o coordenador traz cada cartão aberto na conversa | 13/11/2026 | PR #4 |
| Execução depois da decisão | A resposta ao cartão já é a ordem: o coordenador executa sem nova pergunta | 14/11/2026 | este PR |
