# Último update — 1.3.0.0

- Permitida a edição inline do nome de cards ativos, com salvamento por `Enter`
  ou ao sair do campo e cancelamento por `Esc`.
- Adicionada reordenação de tarefas da mesma prioridade por drag and drop, com animação dos cards e persistência da nova ordem.
- Exibida a data atual ao lado de `Hoje`, no formato `DD/MM`.
- Refinados os botões superiores de tarefas ativas, concluídas e configurações, com novos contornos, estados visuais, profundidade e cantos de `14px`.
- Atualizado o seletor de prioridade com melhor acabamento, menu mais destacado e indicadores coloridos na criação de tarefas; os indicadores foram removidos da versão compacta exibida nos cards.

## Otimizações de desempenho

- Removidos fallbacks impossíveis, conversões e validações repetidas de dados já
  normalizados, além de código de retrocompatibilidade em tempo de execução.
  A leitura e a migração dos JSON antigos foram preservadas.
- Otimizados a conclusão e o cronômetro, eliminando releituras redundantes e a
  espera por atualizações das outras janelas após salvar. O JSON passou a ser
  compacto, mantendo a gravação atômica e as edições pendentes do checklist.
- Otimizada a sincronização entre lista principal, inclusão rápida e bandeja,
  com notificações agrupadas e revisões que impedem atualizações atrasadas.
  O histórico atualiza em segundo plano apenas quando necessário; a bandeja
  reaproveita os dados recebidos, e a reordenação evita cálculos repetidos.
