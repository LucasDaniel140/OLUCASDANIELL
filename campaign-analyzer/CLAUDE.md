# Campaign Analyzer — CLAUDE.md

## Objetivo do projeto

Sistema pessoal de análise de campanhas de tráfego pago (**Meta Ads** e **Google Ads**).
O usuário exporta um relatório CSV da plataforma, faz upload via interface web, e o sistema
normaliza os dados, calcula métricas derivadas e gera um diagnóstico de performance.

---

## Estrutura de pastas

```
campaign-analyzer/
├── app.py               # Entrypoint Flask (rotas: / e /upload)
├── config.py            # Configurações (pastas, limites, chave secreta)
├── requirements.txt
├── CLAUDE.md            # Este arquivo
├── uploads/             # CSVs enviados pelo usuário (gerados em runtime)
├── reports/             # Relatórios JSON gerados (gerados em runtime)
├── modules/
│   ├── __init__.py
│   ├── meta_parser.py   # Leitura e normalização de CSV do Meta Ads
│   ├── google_parser.py # Leitura e normalização de CSV do Google Ads
│   ├── analyzer.py      # KPIs agregados e rankings
│   ├── report_builder.py# Montagem e persistência do relatório JSON
│   └── utils.py         # Helpers (safe_float, safe_int, geração de filename)
└── templates/
    ├── base.html        # Layout Bootstrap 5 dark
    ├── index.html       # Formulário de upload
    └── analysis.html    # Resultado da análise
```

---

## Schema padrão de dados

Todo DataFrame produzido pelos parsers deve conter **exatamente estas colunas**, nesta ordem:

| Campo           | Tipo    | Descrição                               |
|-----------------|---------|-----------------------------------------|
| `campaign_name` | `str`   | Nome da campanha                        |
| `adset_name`    | `str`   | Nome do conjunto / grupo de anúncios    |
| `ad_name`       | `str`   | Nome do anúncio                         |
| `impressions`   | `int`   | Total de impressões                     |
| `clicks`        | `int`   | Total de cliques                        |
| `spend`         | `float` | Valor investido em BRL                  |
| `conversions`   | `int`   | Total de conversões                     |
| `revenue`       | `float` | Receita gerada em BRL (0 se indisponível) |
| `ctr`           | `float` | Taxa de cliques em % (calculado se ausente) |
| `cpc`           | `float` | Custo por clique em BRL (calculado)     |
| `cpm`           | `float` | Custo por 1 000 impressões em BRL (calculado) |
| `cpa`           | `float` | Custo por aquisição em BRL (calculado)  |
| `roas`          | `float` | Receita / Gasto (calculado se revenue > 0) |
| `date`          | `date`  | Data do registro (None se não disponível) |

### Regras de cálculo

- `ctr  = clicks / impressions * 100`
- `cpc  = spend / clicks`
- `cpm  = spend / impressions * 1000`
- `cpa  = spend / conversions`
- `roas = revenue / spend`

Métricas já presentes no CSV exportado **não são sobrescritas** (apenas preenchidas quando `== 0`).

---

## Instruções para alterar o schema

> **IMPORTANTE:** O schema acima é o contrato entre todos os módulos.
> Qualquer alteração deve ser propagada simultaneamente para:
>
> 1. `modules/meta_parser.py` — `_SCHEMA_DEFAULTS` e `_ensure_schema`
> 2. `modules/google_parser.py` — `_SCHEMA_DEFAULTS` e `_ensure_schema`
> 3. `modules/analyzer.py` — referências às colunas
> 4. `modules/report_builder.py` — se a nova métrica precisar de relatório
> 5. `templates/analysis.html` — tabela de referência de colunas
> 6. Este arquivo (`CLAUDE.md`) — tabela de schema acima

Nunca adicione ou renomeie uma coluna em apenas um módulo.

---

## Configuração e execução

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar em modo de desenvolvimento
python app.py
# ou
flask --app app run --debug
```

A aplicação sobe em `http://127.0.0.1:5000` por padrão.

---

## Plataformas suportadas

| Plataforma  | Parser                  | Encoding esperado |
|-------------|-------------------------|-------------------|
| Meta Ads    | `modules/meta_parser.py` | UTF-8 com BOM     |
| Google Ads  | `modules/google_parser.py` | UTF-8 com BOM   |

Os parsers usam `sep=None, engine='python'` para detectar automaticamente
o separador (`,` ou `;` ou `\t`).
