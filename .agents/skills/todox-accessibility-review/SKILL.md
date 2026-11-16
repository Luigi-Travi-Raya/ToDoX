---
name: todox-accessibility-review
description: "Revise acessibilidade e usabilidade da interface Vue/TypeScript do ToDoX na pasta new: teclado, foco, contraste, legibilidade, nomes acessíveis e menus ou diálogos no pywebview. Use para uma revisão solicitada ou uma mudança que afete essas interações."
---

# Revisão de acessibilidade do ToDoX

Examine a superfície solicitada e entregue problemas reproduzíveis ou correções verificáveis. O escopo é somente a pasta `new`; todos os caminhos desta habilidade são relativos a ela. Diferencie inspeção de código, medição e uso real da interface.

## Definir o alcance

Leia `README.md` e os controles envolvidos em `frontend/src/`, implementados em Vue dentro do pywebview. Inclua formulário rápido e bandeja apenas quando compartilharem o componente ou fluxo afetado.

Use os controles reais e os estados do produto. Uma prévia no navegador ajuda a testar HTML e CSS, mas não comprova integração com foco de janelas nativas, atalho global ou tecnologia assistiva no aplicativo distribuído.

## Verificar os caminhos relevantes

- **Teclado e foco:** percorra a ação com Tab e Shift+Tab; confira ativação por Enter ou Espaço conforme o controle, foco visível, ordem lógica e retorno do foco após fechar um menu ou diálogo. Verifique Escape nos popups que o suportam e evite conflitar edição de texto com atalhos.
- **Menus e seletores:** verifique rótulo, estado aberto, opção selecionada, navegação por teclado e comportamento ao fechar. Em `PrioritySelect.vue`, examine em conjunto a semântica de listbox, as opções e a gestão de foco; atributos ARIA sozinhos não demonstram funcionamento correto.
- **Diálogos:** confira título identificável, foco inicial útil e restauração do foco. Diálogos modais devem impedir interação acidental com o conteúdo de fundo; um popover não modal pode exigir comportamento diferente. Respeite as regras atuais de perda de foco da bandeja.
- **Nomes e feedback:** botões apenas com ícones precisam ter propósito identificável. Prefira elementos HTML nativos e rótulos associados; use nomes acessíveis localizados e esconda ícones decorativos da árvore de acessibilidade. Confira se erro, salvamento ou mudança de estado podem ser percebidos sem depender apenas da cor.
- **Leitura e contraste:** examine texto principal, metadados, foco, prioridades e estados desabilitados nos dois temas. Meça as combinações usadas, incluindo fundos de tags personalizados quando relevantes. Use texto, forma ou ícone para complementar estados coloridos; registre a combinação e o método de medição quando relatar contraste.
- **Espaço e movimento:** confira truncamento, múltiplas linhas, áreas de clique, rolagem e ampliação do Windows. Examine também zoom CSS e preferência por movimento reduzido quando houver animações. Verifique textos longos e localidades suportadas antes de fixar larguras.

O suporte a leitores de tela no pywebview depende da plataforma e dos componentes e precisa de teste real quando fizer parte do pedido.

## Registrar ou corrigir

Para cada problema relevante, indique localização, ação para reproduzir, impacto na tarefa e correção sugerida. Priorize bloqueios que impeçam criar, editar, iniciar, pausar ou concluir uma tarefa. Não preencha o relatório com recomendações sem evidência no escopo examinado.

Quando o pedido autorizar correções, implemente-as e repita o caminho afetado. Use dados fictícios em ambiente isolado; não altere arquivos pessoais para testar. Informe claramente as verificações que dependem de execução em Windows ou de tecnologia assistiva não disponível. Não declare conformidade integral com uma norma a partir de uma revisão parcial.
