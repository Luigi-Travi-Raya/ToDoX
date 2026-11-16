# Agentes do ToDoX

Estas instruções se aplicam somente à pasta `new/`. Todos os caminhos abaixo
são relativos a ela. Trabalhe na aplicação Vue + TypeScript com backend
Python/pywebview, sem alterar a implementação antiga na pasta superior.

## Design

- Definição: `.codex/agents/design.toml`.
- Responsabilidade: UX/UI, componentes, temas, estados de interação e
  acessibilidade.
- Habilidades: `todox-ui-design` e `todox-accessibility-review`, em
  `.agents/skills/`.
- Entrega: solução implementável, com componentes afetados, comportamento
  esperado e critérios de verificação visual.

## Desenvolvimento

- Definição: `.codex/agents/desenvolvimento.toml`.
- Responsabilidade: Python, Vue/TypeScript, ponte pywebview, persistência,
  integrações Windows, testes e empacotamento.
- Habilidades: `todox-desktop-development` e `todox-regression-testing`, em
  `.agents/skills/`.
- Entrega: alteração concluída, verificações executadas e limitações relevantes.

Delegue a esses agentes quando a especialidade ajudar a cumprir o pedido.
Para tarefas pequenas, o agente principal pode aplicar diretamente a habilidade
correspondente. Se o cliente ainda não carregou os agentes personalizados, leia
o TOML do papel e forneça suas instruções ao subagente disponível.
Em trabalho paralelo, atribua arquivos distintos a cada agente; compartilhe as
decisões de design que condicionem a implementação antes da edição.

## Contexto e verificação

- Consulte `README.md`, `frontend/package.json`, o código e os testes atuais.
- A interface está em `frontend/src/`, as regras e integrações em `backend/`
  e os testes Python em `tests/`.
- Preserve os JSON reais do usuário durante testes. Use diretórios temporários
  e fixtures próprias; até a leitura pode migrar e salvar dados. Confirme os
  caminhos de execução e distribuição em `backend/data_paths.py`.
- Não edite saídas geradas em `build/`, `dist/`, `frontend/node_modules/` ou
  `.venv/` como código-fonte.
- Para testes Python, a partir desta pasta:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
- Para compilar o frontend: `npm run build --prefix frontend`.
  Esse comando usa Vite e não substitui testes funcionais, verificação completa
  dos tipos Vue ou revisão visual.
- Escolha as verificações conforme a mudança. Não execute testes ou builds do
  aplicativo apenas por uma edição de instruções de agentes.

Exemplos de uso: "Use o agente design para revisar a tela principal" ou
"Use o agente desenvolvimento para corrigir o cronômetro e validar a mudança".
