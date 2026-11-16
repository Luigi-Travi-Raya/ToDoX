# Nova interface

Reescrita da interface em Vue e TypeScript, mantendo regras, persistência e
integrações nativas em Python com pywebview.

## Preparação

Na pasta `new`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install --prefix frontend
```

## Desenvolvimento

No primeiro terminal:

```powershell
cd frontend
npm run dev
```

No segundo terminal:

```powershell
.\.venv\Scripts\python.exe -m backend.main --dev
```

O backend usa o `tarefas.json` existente na raiz do projeto.

Para executar usando o frontend já compilado:

```powershell
npm run build --prefix frontend
.\.venv\Scripts\python.exe -m backend.main
```

## Tags e cores

Tags novas recebem uma cor RGB totalmente aleatória. A associação é salva em
`tarefas.json`, portanto a mesma tag reutiliza sua cor nas demais tarefas e
depois de reiniciar o aplicativo.

Clique em uma tag de uma tarefa ativa para abrir o editor. Nele é possível
renomear ou remover tags e escolher qualquer cor pelo seletor ao lado de cada
uma. A troca de cor é aplicada a todas as tarefas que possuam a mesma tag.

## Edição do nome

Clique no nome de uma tarefa ativa para editá-lo diretamente no card. Pressione
`Enter` para salvar ou `Esc` para cancelar; ao sair do campo, a alteração também
é salva. O nome é obrigatório, aceita até 120 caracteres e as tags continuam
sendo alteradas no editor próprio.

## Idiomas

O ToDoX oferece inglês, japonês, alemão, português brasileiro e espanhol. O
inglês é o idioma padrão e também o fallback usado quando uma tradução não está
disponível. A escolha pode ser alterada em `Configurações > Idioma` e é salva
em `configuracoes.json`.

As prioridades são persistidas com identificadores independentes do idioma
(`urgent`, `high`, `medium`, `low` e `very_low`). Arquivos antigos que ainda
usam os rótulos em português são migrados automaticamente na primeira leitura.

A compatibilidade com dados antigos fica na leitura dos JSON de tarefas e
configurações. Depois dessa leitura, a ponte e a interface usam o esquema atual:
as ações recebem os identificadores de prioridade acima, e o salvamento de
configurações recebe também `tema` e `locale`.

## Atualização das tarefas

Após salvar uma alteração, a ponte retorna a lista atualizada de tarefas ativas.
As outras janelas recebem essa mesma lista em segundo plano, com revisões que
impedem uma resposta atrasada de substituir dados mais recentes. Notificações
pendentes são agrupadas, e a bandeja reaproveita os dados recebidos para calcular
se precisa mudar de tamanho.

O histórico é atualizado em segundo plano quando uma alteração o afeta, sem
bloquear os botões da tarefa. A abertura inicial da lista carrega tarefas ativas
e histórico numa única leitura. Os arquivos continuam sendo salvos por
substituição atômica, em JSON compacto, preservando a leitura de bases antigas.

## Popover da bandeja

O ícone do ToDoX permanece na bandeja do Windows enquanto o aplicativo está em
execução:

- o clique esquerdo abre e foca a lista principal;
- o clique direito abre ou fecha um popover próprio de `340 px`, posicionado
  próximo ao cursor e adaptado ao tema claro ou escuro selecionado.

O popover mostra as atividades cujo cronômetro já foi iniciado ao menos uma vez,
incluindo as que estão em execução e as que estão pausadas. Cada item apresenta
a cor da prioridade, nome, tempo em `HH:MM:SS`, estado e botões somente com
ícones para pausar/continuar e concluir.

Abaixo das atividades ficam `Nova tarefa` (com o atalho atual), `Abrir lista` e
`Sair`; não há ação de configurações nesse popover. Ele pode ser fechado pelo
botão `X`, por `Esc`, por um novo clique direito no ícone ou ao perder o foco.

O campo persistido `atividade_iniciada` diferencia uma tarefa nunca iniciada de
uma tarefa pausada mesmo quando o tempo acumulado ainda é zero. Ele começa como
`false`, passa para `true` no primeiro início do cronômetro e não volta para
`false` enquanto a tarefa estiver ativa. Arquivos antigos recebem esse campo na
leitura com base na existência de uma sessão ativa ou de tempo acumulado.

## Checklist por tarefa

Na lista principal, use `Add checklist` (ou a tradução do idioma selecionado)
para abrir os passos dentro do card. O painel segue a primeira versão do mockup,
começando sob o cronômetro. A fração mostra passos concluídos/total.

Adicione pelo campo e `Enter` ou `+`; clique no texto de um passo para editá-lo.
`Enter` salva, `Esc` cancela e sair do campo também salva uma edição válida.
Os nomes aceitam até 120 caracteres; `#texto` é conteúdo literal. A caixa marca
ou desmarca, e a lixeira exclui o passo sem opção de desfazer.
Recolher preserva o rascunho durante a sessão.

Passos não têm cronômetro próprio e não concluem a tarefa automaticamente.
Ao passar de nenhum passo concluído para um, o cronômetro da tarefa começa
ou retoma, se estiver parado, preservando o tempo acumulado. Pode ser qualquer
linha do checklist. Marcações posteriores não retomam um cronômetro pausado
enquanto já houver passos concluídos; desmarcar não altera o relógio.
Concluir a tarefa mantém as marcações, inclusive passos pendentes; o histórico
permite apenas consultar o checklist. Inclusão rápida e bandeja mantêm seus
fluxos atuais. Checklists são persistidos junto de cada tarefa; registros
antigos recebem uma lista vazia.

Para uma prévia isolada com dados fictícios e ponte Python real, após compilar
o frontend:

```powershell
.\.venv\Scripts\python.exe -m tools.preview_checklist
```

A prévia usa diretório temporário e não abre os JSON pessoais. Consulte
`--help` para opções de tema, idioma, dimensões e textos de teste.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O empacotamento final será feito somente depois da validação funcional e dos
ajustes visuais.
