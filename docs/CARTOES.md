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

### C16 · Com integração oficial, o NewMPSC pode deixar a minuta no SIG como rascunho?
- **Por que é sua:** regras do projeto. O limite 2 diz que nada aqui escreve no SIG.
- **Hoje:** o protótipo (0.5.0) mostra o botão "Enviar ao SIG", mas só contra um SIG simulado, com dados fictícios. Nada chega ao SIG de verdade. A integração oficial não existe; a pergunta define o que se pede à TI.
- **Opções:**
  - **A. Sim, só rascunho.** Por ato do usuário, sem assinatura, só pela integração oficial. Assinar e protocolar continuam no SIG, pela pessoa.
    **Depois da decisão:** o coordenador ajusta o texto do limite 2 no `CLAUDE.md` ("não assina nem protocola; deixa rascunho só por ato do usuário e só pela integração oficial") e leva à TI o pedido de duas operações: ler a fila e depositar rascunho.
  - **B. Não.** A integração oficial só lê a fila; a peça segue saindo por arquivo ou cópia.
    **Depois da decisão:** o coordenador troca, no protótipo, "Enviar ao SIG" por "Copiar para o SIG", ajusta a apresentação e o plano do piloto, e leva à TI só o pedido de leitura.
  - **C. Decidir depois de ouvir a TI.**
    **Depois da decisão:** o protótipo fica como está, marcado como demonstração; o coordenador leva as duas possibilidades à TI e traz a resposta em cartão novo.
- **Recomendo:** A. Tira a cópia manual, que é onde se perde tempo e se cola texto errado, sem tirar da pessoa a assinatura nem o protocolo.
- **O que espera:** a pauta da conversa com a TI. Nada no código espera.

### C17 · O piloto: quais promotorias, e quando o plano vai à Administração?
- **Por que é sua:** rumo do produto e dado real.
- **Contexto:** o plano está em `docs/PILOTO.md`: três promotorias criminais, quatro fases com portão, dado real só depois de hospedagem, parecer e contrato. A Fase 1 usa só dados fictícios e pode começar já.
- **Opções:**
  - **A. Aprovar o plano com três promotorias.** A sua e duas convidadas por você.
    **Depois da decisão:** o coordenador prepara o roteiro e o guia de uma página da Fase 1, um servidor de ensaio com dados fictícios para os convidados, e passa a construir os itens de produto da Fase 2 na ordem do plano.
  - **B. Começar só pela sua promotoria.** Um piloto de um, e ampliar depois da Fase 2.
    **Depois da decisão:** o mesmo da opção A, com um participante; o plano é reescrito com as outras duas entrando na Fase 3.
  - **C. Ainda não.** Terminar antes a verificação de fontes (etapa 3) e só então falar em piloto.
    **Depois da decisão:** o plano fica guardado; o coordenador segue na etapa 3.
- **Recomendo:** A. A Fase 1 não depende de ninguém de fora e é a evidência que sustenta a conversa com a Administração.
- **O que espera:** as Fases 0 e 1 do piloto.
- **O que você faz:** convidar as duas promotorias; apresentar o projeto à Administração, à TI e ao encarregado de dados.

### C18 · Promotor e assessor da mesma promotoria veem os mesmos processos?
- **Por que é sua:** regras do projeto. O limite 3 diz que cada usuário vê só o que é seu.
- **Hoje:** cada conta tem a sua mesa. Um assessor não consegue preparar a minuta que o promotor vai conferir, a não ser usando a conta dele, o que não se deve fazer.
- **Opções:**
  - **A. Espaço da promotoria.** Quem é da mesma promotoria vê a mesma mesa; ninguém de fora vê. Só o promotor envia ao SIG.
    **Depois da decisão:** o coordenador ajusta o limite 3 no `CLAUDE.md` ("cada promotoria vê só o que é seu") e constrói o espaço com teste de isolamento entre promotorias e os três revisores, antes da Fase 2.
  - **B. Manter como está.** No piloto, só o promotor usa.
    **Depois da decisão:** o plano do piloto passa a contar só promotores, e a medição de tempo fica restrita ao trabalho deles.
- **Recomendo:** A. Sem isso o piloto mede um jeito de trabalhar que não é o das promotorias com assessor.
- **O que espera:** o início da Fase 2 nas promotorias com assessor.

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
| C9 · O que fazer quando o modelo declina um pedido, e onde ele processa | B: troca de modelo só para uma lista aprovada | 14/11/2026 | PR #11, com a reserva escolhida no C14 |
| C10 · Os "pequenos testes sem contrato" usam dado real | A: testes com autos fictícios feitos para parecer reais | 14/11/2026 | autos em `dados_ficticios/teste-api/`, neste PR |
| C11 · Para quais modelos o pedido pode passar quando o primeiro declina | A, com observação: só `claude-sonnet-5-5`; pediu as opções de lista | 14/11/2026 | a API não aceita esse modelo como reserva; virou o C14 |
| C12 · Em que condições a aplicação usa o JuriBase | C, com observação: procurar outra fonte de jurisprudência | 14/11/2026 | pesquisa feita; virou o C15 |
| C13 · Por quanto tempo fica a minuta escrita pela IA a partir dos autos | A: a minuta fica | 14/11/2026 | nada a executar |
| C14 · Para qual modelo o pedido passa quando o modelo atual declina | A: só `claude-opus-5`, pela troca do próprio serviço | 14/11/2026 | PR #11; falta confirmar com a chave (C8) que a API aceita essa reserva |
| C15 · De onde a aplicação tira a jurisprudência, no lugar do JuriBase | A: base própria com os dados abertos do STJ | 14/11/2026 | avaliação dos arquivos em curso; volta como cartão com o plano da base |
