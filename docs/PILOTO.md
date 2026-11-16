# Plano do piloto: NewMPSC em promotorias criminais

Proposta de 15/11/2026, aprovada pelo titular em 16/11/2026 (cartões C16, C17 e C18: opção A nos três), para a conversa com a Administração, a TI e o encarregado de dados. Materiais da Fase 1 em `docs/piloto/`; pedido de integração em `docs/PEDIDO-TI.md`. Pontos jurídicos aparecem como **CONFERIR**: não foram verificados em fonte oficial. Os números de meta são propostas do coordenador, a confirmar com a medição inicial.

## Em uma frase
Três promotorias criminais usam o NewMPSC por cerca de quatro meses, em quatro fases com portão entre elas, para responder com dados se a mesa única com o SIG por baixo poupa tempo sem perder segurança, e se vale ampliar.

## O que o piloto precisa responder

| Pergunta | Como se mede | Meta proposta |
| --- | --- | --- |
| Poupa tempo? | Tempo entre a entrada do processo na fila e a minuta pronta para assinar; arquivos e telas manuseados por processo | Tempo mediano 30% menor que o medido antes |
| As pessoas usam? | Parte da fila da promotoria que passou pela mesa; dias de uso por semana | 70% da fila pela mesa nas duas últimas semanas de cada fase |
| O relatório por IA merece confiança? | Parágrafos do relatório que o promotor corrigiu por erro de fato, numa amostra conferida por uma segunda pessoa | Até 1 em cada 10 parágrafos com correção de fato; nenhum erro de fato chegando à peça assinada |
| É seguro? | Incidentes com dado; acesso indevido; peça enviada com trecho a completar | Zero |
| Quanto custa? | Gasto com a API por processo; horas de suporte por semana | Medir; ainda não há número |
| Vale ampliar? | Nota dos participantes e a resposta deles a "voltaria ao jeito antigo?" | Maioria não voltaria |

Sem medição inicial não há comparação. Por isso a Fase 0 inclui duas semanas medindo o jeito de hoje nas mesmas promotorias. A medição registra tempos de trabalho de pessoas identificáveis: fica só com o coordenador, sem nome no relatório, e é apagada ao fim da Fase 4.

A "segunda pessoa" que confere a amostra dos relatórios por IA é sempre da mesma promotoria (o promotor ou um assessor dele). Ninguém de fora abre autos de outra mesa.

## Quem participa
- **Três promotorias criminais**, voluntárias. Proposta de perfil, para cobrir casos diferentes: a do titular; uma de comarca maior, com vara criminal de volume alto; uma de comarca menor, com atribuição criminal misturada a outras. A escolha é do titular (cartão C17).
- **Em cada uma:** o promotor e quem prepara minutas com ele. O piloto começa com até 3 promotores e 6 assessores.
- **Espaço da promotoria:** hoje cada usuário só vê o que é seu. Para o assessor preparar e o promotor conferir a mesma minuta, a aplicação ganha um espaço da promotoria (cartão C18, aprovado; em construção). É condição para a Fase 2 funcionar onde há assessor.

## Fases e portões
Só se passa de fase quando o portão é cumprido. Qualquer participante pode pedir pausa.

### Fase 0 · Preparação (4 a 6 semanas; depende da instituição)
- Apresentar o projeto à Administração, à TI e ao encarregado de dados, com o protótipo e o resumo de `docs/RESUMO-C4.md`.
- Definir a hospedagem institucional e quem conduz contrato e parecer.
- Medir o jeito de hoje nas três promotorias, por duas semanas.
- Decidir, com o encarregado, se processos em segredo de justiça, com vítima de violência sexual, com criança ou adolescente, ou com medida protetiva entram no piloto. Até essa decisão, ficam de fora. CONFERIR: ECA; Lei 11.340/2006; Lei 14.245/2021; normas do CNMP e do MPSC sobre processo sigiloso.
- Definir o que acontece com os dados ao fim do piloto, em cada desfecho: prazo e forma de apagar minutas, registros de pedidos à IA, registros de acesso e cópias de segurança.
- **Portão 0:** autorização escrita para o piloto; hospedagem definida; parecer do encarregado sobre dado real na aplicação; relatório de impacto à proteção de dados, se o encarregado pedir; plano de resposta a incidente, com quem avisa quem e em que prazo. CONFERIR: LGPD, art. 4º, III, "d", e, se ele não afastar a lei, arts. 7º, 11 e 23; arts. 38 e 48 e a regulamentação da ANPD sobre incidentes; normas do CNMP e do MPSC sobre uso de IA; Resolução CNJ 615/2025, se e como se aplica ao Ministério Público.

### Fase 1 · Ensaio com dados fictícios (2 semanas; pode começar já)
- Os participantes usam o protótipo de hoje: SIG simulado e autos fictícios, com o motor de demonstração. O relatório por IA sobre os autos fictícios só entra no ensaio se o cartão do servidor de ensaio decidir que sim.
- Uma hora de treinamento por promotoria e um roteiro de tarefas: buscar a fila, corrigir uma minuta, enviar, marcar audiência.
- Não depende de contrato com fornecedor de IA nem de hospedagem institucional, porque nenhum dado real entra. Para isso valer na prática, e não só como promessa:
  - cada participante assina um termo curto: no ensaio, só dados fictícios;
  - a aplicação só aceita número de processo claramente fictício na planilha, na colagem, na pauta, nos autos, no pedido à IA e no envio ao SIG (desde a 0.5.1). Não examina o texto livre da minuta e não reconhece nome nem documento;
  - o servidor de ensaio é hospedagem nova: onde fica, quem opera e se o motor de IA liga nele são decisão do titular (cartão C19). Até lá, o ensaio roda com o motor de demonstração, sem IA;
  - o banco do ensaio é apagado ao fim da fase.
- **Portão 1:** cada participante faz o roteiro inteiro sem ajuda; os defeitos achados foram corrigidos; nenhum dado real entrou.

### Fase 2 · Dado real, sem IA (4 semanas)
- A fila real entra pela planilha exportada do SIG; a peça sai em .docx ou por cópia, como hoje. O ganho medido aqui é o da mesa: prioridade, minuta num lugar só, pauta.
- O motor de IA fica desligado. Nenhum texto de processo sai do servidor.
- Exige: hospedagem institucional, parecer, e os itens de produto da lista abaixo.
- **Portão 2:** zero incidente; meta de uso cumprida; nenhuma pendência de segurança aberta.

### Fase 3 · Dado real, com relatório por IA (6 semanas)
- O motor escreve só o relatório dos fatos, com a página de cada parágrafo. Fundamentação e pedido continuam do promotor.
- Toda semana, uma amostra dos relatórios é conferida por uma segunda pessoa contra os autos.
- Exige: contrato com o fornecedor de IA, com retenção e região definidas, cobrindo também o modelo de reserva (cartões C4 e C14); teto de gasto (C8). O processamento acontece fora do Brasil. CONFERIR: LGPD, arts. 33 a 36, e a resolução da ANPD sobre transferência internacional.
- **Portão 3:** metas de confiança e de segurança cumpridas.

### Fase 4 · Avaliação (2 semanas)
- Relatório com os números, os defeitos e a opinião dos participantes.
- Decisão do titular e da Administração: ampliar, ajustar e repetir, ou encerrar.

## O SIG durante o piloto
O protótipo mostra o destino: a fila chega com um clique e a minuta volta como rascunho. Isso depende de a TI abrir uma integração, que hoje não existe. Por isso:

- **No piloto**, o SIG entra pela planilha exportada e sai por arquivo. Nada escreve no SIG.
- **Em paralelo**, uma trilha com a TI: primeiro só leitura da fila; depois, se o titular decidir que sim (cartão C16), o depósito de rascunho sem assinatura.
- Assinar e protocolar ficam sempre no SIG, pela pessoa.

## O que precisa existir na aplicação antes de cada fase

| Antes da | Item |
| --- | --- |
| Fase 1 | Recusa de número de processo real na importação e na colagem (feito, 0.5.1); termo dos participantes (`docs/piloto/TERMO-FASE1.md`); servidor de ensaio decidido em cartão (C19) |
| Fase 2 | Segundo fator no login e troca de senha pela pessoa (item 4); registro de acessos, com prazo de guarda próprio (item 2); Postgres com migrações, limpeza no lugar do `secure_delete` e cópia de segurança com prazo compatível com o C1 (itens 3 e 9); limite de tentativas de login em armazenamento comum (item 3); disco e pasta temporária cifrados, pasta da aplicação só de leitura e agendador da limpeza dos autos (item 9); conferência de dependências e versões fixadas por hash (item 10); registros de erro sem texto de processo; exclusão de processo e de usuário (item 8); prazo de guarda da minuta com dado real; espaço da promotoria (C18, aprovado); revisão de segurança independente antes do primeiro dado real |
| Fase 3 | Contrato e parecer (C4); retirada de dados pessoais de terceiros antes do envio à IA (item 6); teto de gasto (C8); prazo de guarda do registro de pedidos à IA (item 7) |

Os números de item são os da seção "O que falta para uso real" de `docs/ARQUITETURA.md`.

## Regras de parada
O piloto para na hora, na promotoria afetada ou em todas, se acontecer um destes:
- dado de processo visto por quem não devia, ou fora do servidor sem contrato;
- peça assinada com erro de fato que veio do relatório por IA e passou pela conferência;
- falha da aplicação que faça perder trabalho ou prazo.

Volta-se só depois de a causa estar corrigida, com teste, e de o titular autorizar.

## Papéis

| Quem | Faz |
| --- | --- |
| Titular | Patrocina, escolhe as promotorias, decide os cartões, leva à Administração |
| Promotores e assessores do piloto | Usam no trabalho de verdade, apontam defeitos, respondem à avaliação |
| TI | Hospedagem, acesso, trilha de integração com o SIG |
| Encarregado de dados | Parecer, condições de uso, acompanhamento de incidente |
| Coordenador técnico | Constrói e corrige, treina, mede, escreve o relatório de cada fase |

## Apoio aos participantes
- Uma hora de treinamento por promotoria, na Fase 1, e um guia de uma página.
- Um canal único para dúvida e defeito, com resposta no mesmo dia útil.
- Uma conversa de 20 minutos por semana com cada promotoria.

## Riscos

| Risco | Resposta |
| --- | --- |
| A instituição demora a autorizar | A Fase 1 não depende dela e já gera evidência para a conversa |
| A TI não abre integração | O piloto inteiro funciona com planilha e arquivo; o envelope completo fica como etapa seguinte |
| O relatório por IA erra um fato | Todo relatório é "a conferir", com a página ao lado; amostra semanal; regra de parada |
| Pouco uso por falta de tempo de quem testa | Promotorias voluntárias; roteiro curto; ganho já na Fase 2, sem IA |
| Custo da IA acima do esperado | Teto no painel do fornecedor; a Fase 3 só começa com o teto definido |
| Dependência de uma pessoa só | Código, decisões e testes ficam no repositório; a TI recebe a documentação na Fase 0 |

## Decisões que ainda vão virar cartão
Além do C16, do C17 e do C18, já decididos:
- onde fica o servidor de ensaio da Fase 1, quem opera e se a IA liga nele (já aberto: C19);
- por quanto tempo fica a minuta com dado real. O C13 ("a minuta fica") foi decidido com dado fictício;
- se processos sigilosos e com dados de vítimas entram na Fase 2;
- o que se apaga, e quando, ao fim do piloto.

## O que o piloto não faz
- Não escreve no SIG nem no eproc, não assina e não protocola.
- A IA não escreve fundamentação nem pedido, e nenhuma citação jurídica entra sem conferência em fonte oficial.
- Não dispensa a conferência do promotor em nenhuma peça.

## Custos a levantar
Ainda sem valores: hospedagem; API de IA por processo (a medir, C8); horas do coordenador técnico e da TI; tempo dos participantes em treinamento e avaliação.

## Calendário proposto
Contado a partir da decisão do titular. As Fases 0 e 1 correm juntas.

| Semanas | O que acontece |
| --- | --- |
| 1 a 2 | Fase 1 (ensaio com dados fictícios); apresentação à Administração |
| 1 a 6 | Fase 0 (autorização, hospedagem, parecer, medição inicial) |
| 7 a 10 | Fase 2 (dado real, sem IA) |
| 11 a 16 | Fase 3 (dado real, com relatório por IA) |
| 17 a 18 | Fase 4 (avaliação e decisão) |

Se a autorização ou o contrato atrasarem, as fases seguintes andam junto: nenhum portão é pulado.
