---
name: todox-desktop-development
description: "Implemente funcionalidades e correções no ToDoX da pasta new em Python e Vue/TypeScript com pywebview; use para contratos da ponte, persistência JSON e integrações desktop no Windows."
---

# Desenvolvimento desktop do ToDoX

Trabalhe somente na aplicação da pasta `new`. Todos os caminhos e comandos abaixo são relativos a ela:

- `backend/`: regras, persistência, ponte Python e integrações desktop.
- `frontend/src/`: interface Vue e TypeScript.
- `tests/` e `README.md`: testes existentes e comportamento documentado.

Use o código e os testes para resolver divergências de documentação. Não amplie alterações para código fora de `new`.

## Implementação

Localize a regra em `backend/tasks.py` ou `settings.py`, sua exposição em `api.py`, os tipos e wrappers em `frontend/src/api.ts` e o componente que usa o resultado. Uma mudança na ponte precisa manter nomes, argumentos, retornos e erros compatíveis nas duas pontas.

Use os wrappers existentes, que aguardam `pywebviewready` e traduzem os códigos de erro. O Vite sozinho não fornece a ponte Python; uma interface aberta apenas no navegador não demonstra que as ações desktop funcionam. Preserve a notificação `tasks-changed` às janelas afetadas após mutações e o tratamento de promessas na interface.

Mantenha identificadores de domínio independentes da tradução. Ao acrescentar texto, siga `frontend/src/i18n/` e mantenha chaves e placeholders compatíveis nos catálogos existentes. Reutilize componentes e tokens antes de criar variantes.

## Persistência e integrações nativas

Antes de modificar o esquema, leia o carregador e os testes de migração. Preserve registros históricos, IDs, tempo acumulado e a diferença entre tarefa concluída e removida. Considere uma tarefa iniciada e pausada em zero segundos: `atividade_iniciada` não equivale a tempo positivo.

Respeite a escrita temporária seguida de substituição em `tasks.py` e a serialização de mutações de `AppApi`. Teste arquivos antigos em `TemporaryDirectory`, nunca nos JSON reais do usuário. Consulte `backend/data_paths.py` para caminhos em desenvolvimento e executável: o aplicativo pode acessar dados fora de `new`. Preserve-os e não presuma que o diretório do `.exe` seja gravável.

Preserve o despacho para a thread da janela usado por `desktop.py`. Mudanças no ciclo de vida devem considerar janela principal, inclusão rápida, popover, fechamento e encerramento completo, sem deixar listeners duplicados.

## Verificação e entrega

Use `$todox-regression-testing` quando precisar diagnosticar ou validar uma mudança. Verifique a implementação contra os critérios do pedido e explique qualquer limitação que exija teste nativo.

Para recursos ou empacotamento, inspecione `build.ps1`, `build-msix.ps1` e `ListaDeTarefas.spec`. Execute apenas o formato necessário à entrega, depois de verificar os pré-requisitos. Não edite arquivos gerados em `build/` ou `dist/` como fonte e não publique o pacote por consequência do build.
