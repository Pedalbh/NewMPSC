# NewMPSC e a API do Claude: resumo para a TI e o encarregado de dados

Uma página para abrir a conversa institucional (cartão C4, decisão de 14/11/2026). Pontos jurídicos aparecem como **CONFERIR**: não foram verificados em fonte oficial.

## O que é
Aplicação web de apoio ao promotor: fila de processos, minutas e pauta de audiências. A aplicação **sugere**; quem decide, assina e protocola é o promotor. Ela não escreve no SIG nem no eproc.

Desde a etapa 2, ela pode pedir a um modelo de IA (API do Claude, da Anthropic, Estados Unidos) o **relatório dos fatos** de um processo, a partir do texto dos autos em PDF. O modelo não escreve fundamentação nem pedido.

## Situação hoje
- Só **dados fictícios**. A aplicação recusa ligar a IA com dado real, por qualquer configuração, até haver contrato institucional e parecer do encarregado.
- Não há servidor institucional. Nenhum dado do MPSC saiu para a IA.

## O que sairia do MPSC, com dado real
- **Sai:** a classe, o assunto e o texto das páginas dos autos daquele processo.
- **Não sai:** o número do processo, o nome dos arquivos, dados do usuário.
- **Para onde:** API da Anthropic, com processamento pedido nos Estados Unidos.
- **Registro local:** cada pedido fica registrado (quem, qual processo, quando, qual modelo), sem conteúdo.
- **Guarda local:** o texto dos autos é apagado sozinho 30 dias depois de o processo ser concluído (cartão C1).

## O que precisa ser decidido pela instituição
1. **Base legal** para o envio. CONFERIR: LGPD, art. 4º, III, "d", e art. 33.
2. **Transferência internacional.** CONFERIR: Resolução CD/ANPD nº 19/2024.
3. **Normas de uso de IA** do CNMP e do MPSC. CONFERIR quais estão vigentes.
4. **Contrato com a Anthropic:** retenção dos dados do lado deles. Pela documentação da Anthropic, conteúdo não treina modelo sem permissão; retenção zero é acordo comercial, não opção de configuração. CONFERIR no contrato.
5. **Hospedagem** da aplicação dentro do MPSC ou em nuvem contratada.

## O que se pede à TI e ao encarregado
- Dizer se o uso é possível e em que condições.
- Indicar quem conduz o contrato e o parecer.
- Até lá, a aplicação segue só com dados fictícios.
