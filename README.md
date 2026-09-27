# Avaliação de Riscos e Controles

Aplicação desktop (Python + Tkinter) para conduzir a avaliação de riscos de uma área:
o avaliador seleciona área, riscos e controles em campos de seleção com escala de 1 a 5,
vê o risco inerente e o residual calculados na hora e, ao final, exporta a **matriz de
riscos em Excel** para revisão do analista.

## Instalação (No meu caso, estou usando Omarchy / Arch), no windows, basta criar o mesmo arquivo com final .bd

```bash
chmod +x instalar.sh
./instalar.sh
```

O script instala o `tk` via pacman se faltar, cria o `.venv`, instala as dependências,
roda os testes e cria o atalho **Avaliação de Riscos** no launcher.

Para rodar manualmente: `.venv/bin/python app.py`

> **Hyprland:** se a janela de cadastro de controle abrir em modo tile em vez de flutuar,
> crie uma regra de janela flutuante para a classe `AvaliacaoRiscos` no seu `hyprland.conf`
> (a sintaxe de `windowrule` varia conforme a versão do Hyprland).

## Fluxo de uso

1. **Avaliações** → escolha a área, o período e o avaliador → *Iniciar avaliação*.
   Há um botão para carregar uma avaliação de exemplo.
2. **Riscos e controles** → para cada risco: processo, categoria, descrição, causa,
   consequência, e as notas de **probabilidade** e **impacto** (cada nota mostra seu
   significado). *Salvar risco*, depois *+ Adicionar controle*:
   - tipo (preventivo/detectivo, manual/automático), frequência, dono e evidência;
   - notas de **desenho** e **operação**;
   - opcional: amostra e falhas do teste → a aplicação **sugere a nota de operação**.
   O painel à direita recalcula inerente, efetividade e residual a cada seleção e
   mostra a trajetória do risco na matriz 5×5.
3. **Matriz de riscos** → mapas de calor inerente × residual, indicadores e ranking.
4. **Exportar Excel** (`Ctrl+E`) → arquivo para o analista revisar.

Atalhos: `Ctrl+N` novo risco · `Ctrl+S` salvar risco · `Ctrl+E` exportar.

## Metodologia (padrão, ajustável)

Tudo fica em [`config/metodologia.yaml`](config/metodologia.yaml): descrições das notas,
fatores, pesos por tipo de controle, faixas de risco, método do residual e listas de
áreas/categorias/frequências. Depois de editar, clique em **Metodologia → Recarregar**.

| Cálculo | Fórmula |
|---|---|
| Risco inerente | P × I (1 a 25) |
| Efetividade do controle | fator do desenho × fator da operação × peso do tipo |
| Efetividade combinada | 1 − Π(1 − efetividade de cada controle), limitada ao teto (95%) |
| P e I residuais | 1 + (nota − 1) × (1 − efetividade) |
| Risco residual | P residual × I residual |

`metodo_residual: proporcional` aplica a efetividade combinada em P e I;
`natureza` faz os preventivos reduzirem P e os detectivos reduzirem I.

## O Excel exportado

| Aba | Conteúdo |
|---|---|
| Resumo | Indicadores, mapas de calor inerente e residual, distribuição por nível, gráfico e parecer geral |
| Matriz de Riscos | Um risco por linha, com cálculos em fórmulas e colunas de parecer do analista |
| Controles | Um controle por linha, com efetividade, classificação e parecer |
| Parâmetros | Espelho da metodologia; alterar aqui recalcula tudo (útil para simulação) |
| Instruções | Legenda e passo a passo de revisão |

Texto **azul** = nota lançada (ajustável) · texto **preto** = fórmula · fundo **amarelo** =
campo do analista. Os cálculos são fórmulas vivas: se o analista mudar uma nota, a matriz,
os níveis e os mapas de calor se atualizam.

## Estrutura

```
avaliacao-riscos/
├── app.py                    # ponto de entrada
├── config/metodologia.yaml   # metodologia (ponto de refino)
├── riscos/
│   ├── config.py             # leitura e validação da metodologia
│   ├── calculo.py            # motor de cálculo (funções puras)
│   ├── db.py                 # SQLite: avaliação → riscos → controles
│   ├── servico.py            # junta banco + cálculo
│   ├── excel.py              # exportação da matriz
│   └── ui/                   # interface (Tkinter + tema sv-ttk)
├── scripts/exemplo.py        # avaliação de demonstração
├── tests/                    # pytest
└── data/                     # banco e preferências (criado na 1ª execução, fora do Git)
```

O banco fica em `data/avaliacoes.db` (pode ser trocado pela variável `RISCOS_DB`).
