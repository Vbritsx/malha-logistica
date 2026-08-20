# Malha Logística — Versão 1

Esta pasta contém a **versão 1** (original) do dashboard de Malha Logística.

## Arquivos
- `index.html` — Página principal
- `css/style.css` — Estilos do dashboard
- `js/app.js` — Lógica de inicialização e controles do mapa
- `js/measurement.js` — Ferramenta de medição de rotas (OSRM)
- `processar_dados.py` — Script Python para processar o Excel e gerar `data.js`

## Funcionalidades
- Mapa interativo com 12 CDs da Sabesp
- Filtros por CD, Inbound/Outbound e Parceiro
- Medição de rota por estrada (OSRM)
- Rodapé com dados do parceiro (movimentações, volume, valor, material)
- Alternância de tema claro/escuro no mapa
- Efeito de foco visual ao filtrar CD ou medir rota

> **Nota:** O arquivo `js/data.js` é gerado automaticamente pelo `processar_dados.py` e não está duplicado aqui. Use o `data.js` da pasta raiz.
