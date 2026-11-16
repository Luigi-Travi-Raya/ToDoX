---
name: todox-regression-testing
description: "Investigue bugs e valide alterações no ToDoX da pasta new com testes Python isolados, verificação do frontend Vue e cenários desktop; use ao corrigir regressões ou preparar um executável Windows."
---

# Diagnóstico e regressão do ToDoX

Considere somente a aplicação da pasta `new`; todos os caminhos abaixo são relativos a ela. Identifique a ação que falha, o resultado esperado e a evidência disponível. Relacione a falha ao fluxo entre interface, ponte, regras e arquivo persistido antes de escolher o teste. Não execute uma bateria de testes ou um empacotamento por uma mudança restrita a documentação ou configuração de agentes.

## Dados e efeitos isolados

Siga os exemplos de `tests/`: `unittest`, `TemporaryDirectory` e mocks para dependências externas. Construa fixtures mínimas no temporário e, quando relevante, verifique tanto o retorno quanto o JSON salvo. Não leia os JSON reais para reproduzir migrações: os carregadores podem regravá-los. Consulte `backend/data_paths.py` ao isolar os caminhos, pois os dados usados pela aplicação podem estar fora de `new`.

Controle o relógio para testar cronômetros sem esperas reais. Simule pywebview, bandeja, atalhos e APIs nativas em testes de lógica; importar o módulo de teste não deve abrir janelas nem registrar listeners. Use testes nativos somente para comportamento que esses doubles não comprovem.

Escolha os cenários afetados, sem transformar cada edição em uma auditoria completa:

- Persistência: arquivo antigo, dado inválido, salvamento e manutenção de registros históricos.
- Cronômetros: iniciar, pausar, retomar e concluir; tarefa pausada em zero; cálculo após reabertura.
- Listas: prioridades, ordenação manual, filtros por tags e histórico somente leitura.
- Ponte e janelas: argumentos e erros, notificação após mutações e atualização da janela principal e da bandeja.
- Traduções: mesmas chaves e placeholders, identificadores persistidos independentes do idioma.

Para um bug de lógica, acrescente um teste do comportamento observado quando isso proteger a correção. Prefira critérios externos a asserts sobre nomes internos, estrutura de componentes ou texto do código. Não adicione frameworks apenas para acompanhar uma edição pequena.

## Comandos existentes

Os comandos seguintes são executados **na pasta `new`**, com o ambiente local já preparado. Para um diagnóstico restrito, selecione primeiro o módulo de teste correspondente; para a suíte Python existente:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para verificar o bundle do frontend alterado:

```powershell
npm run build --prefix frontend
```

Consulte `frontend/package.json` antes de escolher comandos adicionais. Atualmente o build executa Vite; não equivale a uma suíte de testes ou à verificação completa de tipos dos componentes Vue. Não declare `npm test` ou lint aprovados sem scripts correspondentes.

## Limites da validação

Inspecione os scripts de build antes de empacotar e gere apenas o formato pedido. Um build aprovado confirma a geração do artefato, não atalhos globais, bandeja, foco, WebView2 ou persistência na instalação. Para esses pontos, execute uma verificação nativa com dados de teste isolados, se o ambiente e o pedido permitirem; caso contrário, registre precisamente o que ficou sem verificar.

Relate o teste que reproduzia a falha, a correção observada, os comandos executados e as limitações restantes. Após as verificações pertinentes passarem, não repita nem amplie os testes sem uma nova falha, mudança ou preocupação concreta.
