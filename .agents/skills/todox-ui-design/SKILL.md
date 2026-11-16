---
name: todox-ui-design
description: "Crie ou ajuste o design de fluxos, layouts, componentes e temas do ToDoX em Vue/TypeScript e pywebview na pasta new, incluindo especificações para implementação. Use para trabalho visual e de usabilidade; correções isoladas de lógica não exigem esta habilidade."
---

# Design de interface do ToDoX

Transforme o pedido em uma interface coerente com o produto e em decisões implementáveis. O escopo é somente a pasta `new`; todos os caminhos desta habilidade são relativos a ela.

## Entender a superfície

- Consulte `README.md`, os componentes relevantes em `frontend/src/`, `frontend/src/style.css`, `frontend/src/theme.ts` e os recursos em `frontend/public/`. `App.vue`, `QuickAdd.vue` e `TrayMenu.vue` representam superfícies diferentes; `PrioritySelect.vue` é compartilhado.
- Use o pedido e os componentes citados para delimitar a mudança. Trate documentação como contexto e confirme o comportamento no código atual.

## Projetar a mudança

Parta da ação que a pessoa precisa realizar e do estado que precisa compreender. Preserve a hierarquia entre nome da tarefa, prioridade, tags, tempo e ações. Evite aumentar a densidade visual a ponto de prejudicar leitura e seleção de controles.

Reutilize cores, tipografia, espaçamentos, raios e ícones existentes. Ao introduzir um padrão recorrente, indique onde centralizá-lo na implementação atual; não imponha uma reestruturação geral de estilos para uma mudança pequena. Mantenha representações consistentes da mesma prioridade e do mesmo estado entre as superfícies afetadas.

Especifique os estados que a mudança realmente utiliza: padrão, hover, foco, pressionado, desabilitado, vazio, erro e processamento. Para tarefas, diferencie em andamento, pausada e concluída por sinais compreensíveis além da cor. O histórico possui restrições próprias de interação.

Considere tema claro e escuro, dimensões reais da janela, rolagem, nomes longos, múltiplas tags e escalonamento do Windows. Examine largura mínima, zoom CSS e contêineres antes de ajustar medidas; um valor em CSS pode não corresponder ao tamanho percebido na tela.

Use o sistema de tradução em `frontend/src/i18n/`. O inglês é o idioma padrão e fallback atual; não substitua esse comportamento pelo idioma da conversa. Considere expansão de texto em alemão e espanhol e a renderização de japonês. Novos textos da interface precisam acompanhar as localidades suportadas quando forem implementados.

## Entregar e conferir

Para uma proposta, apresente a solução principal com componentes afetados, estados e critérios de aceitação concretos. Inclua medidas e cores quando forem necessárias para reproduzir a solução. Um esboço ou imagem ajuda quando resolve uma dúvida espacial; não é uma exigência para alterações simples.

Para uma implementação visual, altere os arquivos da superfície escolhida e confira os estados afetados no tamanho real disponível. Use dados fictícios para estados vazios, textos longos e variação de prioridades. Não use os arquivos pessoais `tarefas.json` e `configuracoes.json` como massa de teste.

Informe o que foi verificado visualmente e o que permaneceu sem execução. Se desenvolvimento assumir a implementação, repasse componentes, comportamento, recursos reutilizados e critérios de aceitação, sem prescrever mudanças de lógica fora do pedido.
