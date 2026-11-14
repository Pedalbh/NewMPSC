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

### C14 · Para qual modelo o pedido passa quando o modelo atual declina?
- **Por que é sua:** destino do dado e custo. Substitui o C11: você escolheu A (`claude-sonnet-5-5`) e pediu as opções de lista.
- **Fato novo:** pela documentação da Anthropic, a troca feita pelo próprio serviço só aceita, para o `claude-opus-5-5`, os modelos da lista que a Anthropic publica para ele, que deve ser `claude-opus-5` e `claude-opus-4-8`. O `claude-sonnet-5-5` não entra nessa troca. A lista exata só se confirma com a chave da API (C8). Recusa por pedido de "mostrar o raciocínio" nunca é trocada.
- **Opções**
  - **A.** Só `claude-opus-5`, pela troca do próprio serviço. Mesma família, preço um pouco maior (US$ 5 / US$ 25 por milhão de tokens).
    - **Depois da decisão:** troca ligada só para ele, com teste; o registro do pedido guarda qual modelo respondeu; revisor de segurança.
  - **B.** `claude-opus-5` e depois `claude-opus-4-8`, pela troca do próprio serviço.
    - **Depois da decisão:** a mesma construção de A, com os dois.
  - **C.** Deixar a Anthropic escolher por tipo de recusa (`fallbacks: "default"`). Sem lista para manter; o modelo pode mudar sem aviso.
    - **Depois da decisão:** a mesma construção, sem lista; o registro do pedido mostra o modelo que respondeu.
  - **D.** Como você escolheu no C11: nova tentativa feita pela aplicação no `claude-sonnet-5-5`. Funciona, mas é um segundo pedido inteiro, pago à parte, e a aplicação passa a decidir a troca.
    - **Depois da decisão:** nova tentativa no código, só em recusa, com teste e revisor de segurança.
- **Recomendo:** A. Um modelo reserva só, da mesma família, sem segundo pedido pago.
- **O que espera:** a troca de modelo do C9. Nada mais.

## Decididos

Cada linha diz também como ficou a execução: o PR que a cumpriu, "nada a executar" ou o que ainda falta.

| Cartão | Decisão | Quando | Execução |
| --- | --- | --- | --- |
| Motor de IA | API do Claude direta | 13/11/2026 | PR #5 |
| Fonte de jurisprudência | JuriBase | 13/11/2026 | falta o acesso da aplicação (C6) |
| Merge | Com os revisores aprovando e o CI verde, o coordenador faz o merge sem perguntar | 13/11/2026 | nada a executar |
| Onde vivem os cartões | Neste arquivo; o coordenador traz cada cartão aberto na conversa | 13/11/2026 | PR #4 |
| Execução depois da decisão | A resposta ao cartão já é a ordem: o coordenador executa sem nova pergunta | 14/11/2026 | PR #6 |
| C1 · Por quanto tempo o texto dos autos fica guardado | A: apaga sozinho o texto dos autos 30 dias depois de o processo ser concluído | 14/11/2026 | PR #8 |
| C2 · A impressão digital do arquivo original continua guardada | B: impressão do arquivo com chave do servidor | 14/11/2026 | PR #8 |
| C3 · Quanto texto de autos cada usuário pode guardar | A: números provisórios mantidos; revisão com autos reais | 14/11/2026 | nada a executar agora |
| C4 · O que precisa existir antes de texto real ir para a API do Claude | A, com observação: etapa 2 só com dados fictícios; dado real barrado até o contrato; resumo para TI e encarregado | 14/11/2026 | resumo em `docs/RESUMO-C4.md`; a observação virou o C10 |
| C5 · Qual fonte de legislação vigente a aplicação consulta | A: na etapa 3 só jurisprudência é conferida; citação de lei sai "não conferida" | 14/11/2026 | entra na etapa 3, com a avaliação de Planalto e LexML trazida em cartão |
| C6 · Como a aplicação passa a acessar o JuriBase | B: o coordenador levanta o que o JuriBase publica | 14/11/2026 | levantamento feito; virou o C12 |
| C7 · O que o motor de IA escreve antes de existir a verificação de fontes | A: o motor escreve só o relatório até existir a verificação de fontes | 14/11/2026 | nada a executar: já está assim |
| C8 · Qual modelo o motor usa, e com que teto de gasto | A: modelo padrão mantido; custo medido nos primeiros testes | 14/11/2026 | no primeiro teste com a API, que espera a chave |
| C9 · O que fazer quando o modelo declina um pedido, e onde ele processa | B: troca de modelo só para uma lista aprovada | 14/11/2026 | parado: falta a lista (C11) |
| C10 · Os "pequenos testes sem contrato" usam dado real | A: testes com autos fictícios feitos para parecer reais | 14/11/2026 | autos em `dados_ficticios/teste-api/`, neste PR |
| C11 · Para quais modelos o pedido pode passar quando o primeiro declina | A, com observação: só `claude-sonnet-5-5`; pediu as opções de lista | 14/11/2026 | a API não aceita esse modelo como reserva; virou o C14 |
| C12 · Em que condições a aplicação usa o JuriBase | C, com observação: procurar outra fonte de jurisprudência | 14/11/2026 | pesquisa em curso; volta como cartão |
| C13 · Por quanto tempo fica a minuta escrita pela IA a partir dos autos | A: a minuta fica | 14/11/2026 | nada a executar |
