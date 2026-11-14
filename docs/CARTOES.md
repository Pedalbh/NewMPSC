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

### C10 · Os "pequenos testes sem contrato" usam dado real?
- **Por que é sua:** dado real (limite 1 do `CLAUDE.md`). No C4 você escreveu: "podemos fazer pequenos testes sem o contrato institucional, para validar a proposta".
- **Hoje:** a aplicação recusa ligar o motor de IA com dado real, por qualquer configuração.
- **Opções**
  - **A.** Os testes usam autos fictícios, feitos para parecer reais, o que o limite 1 já permite.
    - **Depois da decisão:** o coordenador monta 2 ou 3 autos fictícios de tipos comuns (furto, tráfico, violência doméstica) para o teste com a API.
  - **B.** Os testes usam alguns autos reais, anonimizados à mão por você, sem contrato. Exige mudar o limite 1 e assumir o que o C4 deixou como CONFERIR.
    - **Depois da decisão:** cartão novo com o texto do limite 1 alterado e as condições do teste (quantos autos, quem anonimiza, onde roda, quando apaga).
- **Recomendo:** A. Valida a proposta sem tirar dado real do MPSC antes do parecer.
- **O que espera:** o primeiro teste com a API, que também espera a chave (C8).

### C11 · Para quais modelos o pedido pode passar quando o primeiro declina?
- **Por que é sua:** no C9 você escolheu B ("só para uma lista que você aprovar"), e a resposta não trouxe a lista.
- **Opções**
  - **A.** Só `claude-sonnet-5-5`.
    - **Depois da decisão:** troca ligada só para ele, com teste e revisão de segurança.
  - **B.** `claude-sonnet-5-5` e `claude-haiku-5-5`.
    - **Depois da decisão:** troca ligada para os dois, nessa ordem, com teste e revisão de segurança.
  - **C.** Outra lista, dita na resposta.
    - **Depois da decisão:** a mesma construção, com a lista dada.
- **Recomendo:** A. Um modelo reserva só, e não está confirmado se a troca é compatível com retenção zero (o que só pesa com dado real).
- **O que espera:** a troca de modelo do C9.

### C12 · Em que condições a aplicação usa o JuriBase?
- **Por que é sua:** contrato, custo e destino novo de dado (o texto das buscas sai para um terceiro). Vem do levantamento do C6.
- **O que está publicado** (lido nos trechos de busca em 14/11/2026; as páginas inteiras estão bloqueadas pela rede desta sessão):
  - acesso por chave gerada no site, sem cartão, com uma "URL do conector" (servidor MCP); não achei API própria para aplicações;
  - plano grátis com 100 consultas por mês; plano Pro pago, sem preço publicado nos trechos;
  - privacidade: dados guardados por "até 180 dias", base legal citada é o legítimo interesse; o serviço se diz "produto da PreviusIA" (CNPJ 42.130.949/0001-56, não conferido na Receita).
- **O que não está publicado:** se a chave pode ser usada por aplicação no servidor; o que acontece com o texto das buscas; país do servidor; termos de uso; uso por órgão público; contato comercial e encarregado.
- **Opções**
  - **A.** Você (ou a TI do MPSC) faz o contato com o JuriBase com as perguntas acima e traz as respostas.
    - **Depois da decisão:** o coordenador escreve as perguntas numa lista curta, pronta para enviar, em `docs/`.
  - **B.** Liberar `juribase.com.br` na rede desta sessão para o coordenador ler as páginas inteiras (planos, termos, conector) antes do contato.
    - **Depois da decisão:** o coordenador pede a liberação, lê as páginas e atualiza este cartão; o contato continua com você.
  - **C.** Desistir do JuriBase como fonte da aplicação e procurar outra.
    - **Depois da decisão:** levantamento de alternativas, trazido como cartão novo.
- **Recomendo:** B e depois A. Ler o que já está publicado encurta a conversa.
- **O que espera:** a etapa 3.
- **O que você faz:** o contato com o JuriBase.

## Decididos

Cada linha diz também como ficou a execução: o PR que a cumpriu, "nada a executar" ou o que ainda falta.

| Cartão | Decisão | Quando | Execução |
| --- | --- | --- | --- |
| Motor de IA | API do Claude direta | 13/11/2026 | PR #5 |
| Fonte de jurisprudência | JuriBase | 13/11/2026 | falta o acesso da aplicação (C6) |
| Merge | Com os revisores aprovando e o CI verde, o coordenador faz o merge sem perguntar | 13/11/2026 | nada a executar |
| Onde vivem os cartões | Neste arquivo; o coordenador traz cada cartão aberto na conversa | 13/11/2026 | PR #4 |
| Execução depois da decisão | A resposta ao cartão já é a ordem: o coordenador executa sem nova pergunta | 14/11/2026 | PR #6 |
| C1 · Por quanto tempo o texto dos autos fica guardado | A: apaga sozinho o texto dos autos 30 dias depois de o processo ser concluído | 14/11/2026 | em construção, junto com o C2 |
| C2 · A impressão digital do arquivo original continua guardada | B: impressão do arquivo com chave do servidor | 14/11/2026 | em construção, junto com o C1 |
| C3 · Quanto texto de autos cada usuário pode guardar | A: números provisórios mantidos; revisão com autos reais | 14/11/2026 | nada a executar agora |
| C4 · O que precisa existir antes de texto real ir para a API do Claude | A, com observação: etapa 2 só com dados fictícios; dado real barrado até o contrato; resumo para TI e encarregado | 14/11/2026 | resumo em `docs/RESUMO-C4.md`; a observação virou o C10 |
| C5 · Qual fonte de legislação vigente a aplicação consulta | A: na etapa 3 só jurisprudência é conferida; citação de lei sai "não conferida" | 14/11/2026 | entra na etapa 3, com a avaliação de Planalto e LexML trazida em cartão |
| C6 · Como a aplicação passa a acessar o JuriBase | B: o coordenador levanta o que o JuriBase publica | 14/11/2026 | levantamento feito; virou o C12 |
| C7 · O que o motor de IA escreve antes de existir a verificação de fontes | A: o motor escreve só o relatório até existir a verificação de fontes | 14/11/2026 | nada a executar: já está assim |
| C8 · Qual modelo o motor usa, e com que teto de gasto | A: modelo padrão mantido; custo medido nos primeiros testes | 14/11/2026 | no primeiro teste com a API, que espera a chave |
| C9 · O que fazer quando o modelo declina um pedido, e onde ele processa | B: troca de modelo só para uma lista aprovada | 14/11/2026 | parado: falta a lista (C11) |
