# Campaign Analyzer — CLAUDE.md

## Objetivo do projeto

Sistema pessoal de análise de campanhas de tráfego pago (**Meta Ads** e **Google Ads**).
O usuário exporta um relatório CSV da plataforma, faz upload via interface web, e o sistema
normaliza os dados, calcula métricas derivadas, gera diagnóstico de performance e compara
períodos. Inclui sistema de metas por cliente e geração de PDF via WeasyPrint.

---

## Estrutura de pastas

```
campaign-analyzer/
├── app.py                  # Entrypoint Flask (todas as rotas)
├── config.py               # Configurações (pastas, limites, chave secreta)
├── requirements.txt
├── CLAUDE.md               # Este arquivo
├── uploads/                # CSVs enviados pelo usuário (gerados em runtime)
├── reports/                # Análises JSON persistidas (geradas em runtime)
├── data/
│   └── client_goals.json   # Metas por cliente (chave = slug do cliente)
├── modules/
│   ├── __init__.py
│   ├── meta_parser.py      # Leitura e normalização de CSV do Meta Ads
│   ├── google_parser.py    # Leitura e normalização de CSV do Google Ads
│   ├── analyzer.py         # KPIs, scoring, alertas, recomendações, comparação de metas
│   ├── comparator.py       # Comparação entre dois períodos de análise
│   ├── report_builder.py   # Relatório HTML standalone para entrega ao cliente
│   ├── goals.py            # Persistência de metas por cliente (JSON)
│   └── utils.py            # Helpers: safe_float, allowed_file, normalize_slug, etc.
└── templates/
    ├── base.html           # Layout Bootstrap 5 dark (navbar: Nova análise · Histórico · Metas)
    ├── index.html          # Formulário de upload + lista de análises recentes
    ├── analysis.html       # Dashboard de análise com metas + botões HTML/PDF
    ├── history.html        # Histórico agrupado por cliente + comparação
    ├── compare.html        # Comparação lado a lado de dois períodos
    ├── goals.html          # Listagem global de metas por cliente
    └── goals_form.html     # Formulário de criação/edição de metas por cliente
```

---

## Rotas Flask

| Método | Rota                        | Função           | Descrição                                          |
|--------|-----------------------------|------------------|----------------------------------------------------|
| GET    | `/`                         | `index`          | Formulário de upload + histórico recente           |
| POST   | `/upload`                   | `upload`         | Processa CSV → análise → persiste JSON             |
| GET    | `/report/<analysis_id>`     | `report`         | Relatório HTML standalone para o cliente           |
| GET    | `/report/<analysis_id>/pdf` | `report_pdf`     | Download PDF via WeasyPrint (fallback: Ctrl+P)     |
| GET    | `/history`                  | `history`        | Histórico agrupado por cliente (acordeão)          |
| GET    | `/compare?a=<id>&b=<id>`    | `compare`        | Comparação de dois períodos com deltas             |
| GET    | `/goals`                    | `goals`          | Listagem global de metas por cliente               |
| GET    | `/goals/<client_slug>`      | `goals_form`     | Formulário de metas (pré-preenchido se existir)    |
| POST   | `/goals/<client_slug>`      | `goals_form`     | Salva metas em `data/client_goals.json`            |

### Segurança de rotas
- `analysis_id` validado com `re.match(r"^[A-Za-z0-9_-]+$", ...)` — proteção path traversal
- `client_slug` validado com `re.match(r"^[a-z0-9-]+$", ...)` — apenas slugs normalizados

---

## Schema padrão de dados (DataFrame)

Todo DataFrame produzido pelos parsers deve conter **exatamente estas colunas**:

| Campo           | Tipo    | Descrição                                         |
|-----------------|---------|---------------------------------------------------|
| `campaign_name` | `str`   | Nome da campanha                                  |
| `adset_name`    | `str`   | Nome do conjunto / grupo de anúncios              |
| `ad_name`       | `str`   | Nome do anúncio                                   |
| `impressions`   | `int`   | Total de impressões                               |
| `clicks`        | `int`   | Total de cliques                                  |
| `spend`         | `float` | Valor investido em BRL                            |
| `conversions`   | `int`   | Total de conversões                               |
| `revenue`       | `float` | Receita gerada em BRL (0 se indisponível)         |
| `ctr`           | `float` | Taxa de cliques em % (calculado se ausente)       |
| `cpc`           | `float` | Custo por clique em BRL (calculado)               |
| `cpm`           | `float` | Custo por 1.000 impressões em BRL (calculado)     |
| `cpa`           | `float` | Custo por aquisição em BRL (calculado)            |
| `roas`          | `float` | Receita / Gasto (calculado se revenue > 0)        |
| `date`          | `date`  | Data do registro (None se não disponível)         |

### Regras de cálculo
- `ctr  = clicks / impressions * 100`
- `cpc  = spend / clicks`
- `cpm  = spend / impressions * 1000`
- `cpa  = spend / conversions`
- `roas = revenue / spend`

Métricas já presentes no CSV **não são sobrescritas** (apenas preenchidas quando `== 0`).

---

## Schema de análise (JSON persistido)

```json
{
  "client":          "Nome do cliente",
  "platform":        "meta | google",
  "period":          "01/01/2024 → 31/01/2024",
  "generated_at":    "2024-01-31T14:30:00",
  "analysis_id":     "20240131_143000_nome_cliente",
  "summary":         { ... },
  "campaigns":       [ ... ],
  "alerts":          [ ... ],
  "recommendations": [ ... ],
  "goal_comparison": [ ... ] | null
}
```

### summary
```json
{
  "total_spend": 5000.00, "total_impressions": 100000,
  "total_clicks": 2000, "total_conversions": 40,
  "total_revenue": 15000.00, "avg_ctr": 2.00,
  "avg_cpc": 2.50, "avg_cpm": 50.00,
  "avg_cpa": 125.00, "avg_roas": 3.00,
  "has_revenue": true,
  "best_campaign": "Nome da melhor", "worst_campaign": "Nome da pior"
}
```

### campaigns (por item)
```json
{
  "campaign_name": "...", "impressions": 0, "clicks": 0,
  "spend": 0.0, "conversions": 0, "revenue": 0.0,
  "ctr": 0.0, "cpc": 0.0, "cpm": 0.0, "cpa": 0.0, "roas": 0.0,
  "score": 75, "status": "Escalar | Manter | Otimizar | Pausar",
  "diagnosis": "Texto de diagnóstico.", "spend_pct": 25.0
}
```

### alerts (por item)
```json
{
  "type": "ctr_critical | cpa_high | no_conversion | roas_negative | landing_page | budget_overspend",
  "level": "critical | warning",
  "campaign": "nome da campanha ou 'geral'",
  "message": "Texto do alerta."
}
```

### goal_comparison (por item, null se sem metas)
```json
{
  "label": "CPA alvo",
  "target": 45.0, "actual": 38.5,
  "fmt": "brl | pct | x",
  "status": "atingida | próxima | não atingida",
  "higher_is_better": false
}
```

---

## Sistema de metas (`data/client_goals.json`)

```json
{
  "empresa-xyz": {
    "client_name": "Empresa XYZ",
    "slug": "empresa-xyz",
    "target_cpa": 45.0,
    "min_roas": 3.0,
    "min_ctr": 1.5,
    "max_cpc": 2.5,
    "monthly_budget": 5000.0
  }
}
```

Todos os campos de meta são opcionais. Apenas os campos presentes são comparados.

---

## Scoring de campanhas

| Critério                        | Pontos |
|---------------------------------|--------|
| CTR > 2%                        | +20    |
| CTR ≥ 1%                        | +10    |
| CPC abaixo da média da conta    | +20    |
| CPA abaixo da média da conta    | +25    |
| ROAS > 3x                       | +25    |
| ROAS ≥ 1.5x                     | +10    |
| Pelo menos 1 conversão          | +10    |
| **Score máximo**                | 100    |

### Status por score
| Score    | Status   | Cor        |
|----------|----------|------------|
| ≥ 80     | Escalar  | Verde      |
| 60–79    | Manter   | Ciano      |
| 40–59    | Otimizar | Amarelo    |
| < 40     | Pausar   | Vermelho   |

---

## Jinja2 filters registrados

| Filtro           | Uso                          | Exemplo            |
|------------------|------------------------------|--------------------|
| `brl`            | `value\|brl`                 | `R$ 1.234,56`      |
| `pct`            | `value\|pct`                 | `1.23%`            |
| `num`            | `value\|num`                 | `1.234.567`        |
| `fmtdt`          | `iso_str\|fmtdt`             | `31/01/2024 14:30` |
| `fmtdate`        | `iso_str\|fmtdate`           | `31/01/2024`       |
| `normalize_slug` | `client_name\|normalize_slug`| `empresa-xyz`      |

---

## normalize_slug

Função em `modules/utils.py`. Converte nome de cliente em slug URL-safe:

- Remove acentos via `unicodedata.normalize("NFD")`
- Converte caracteres não-alfanuméricos em `-`
- Lowercase, remove hífens iniciais/finais
- Retorna `"cliente"` se o resultado for vazio

Exemplo: `"Empresa São João & Cia."` → `"empresa-sao-joao-cia"`

Registrada como filtro Jinja2 `normalize_slug` e usada em:
- `app.py`: `upload` (carregar metas), `_group_by_client` (campo `slug` nos grupos)
- `modules/goals.py`: chave do JSON de metas
- Templates: `{{ group.slug }}`, `{{ client_slug }}`, `{{ result.client | normalize_slug }}`

---

## WeasyPrint PDF

Rota `GET /report/<analysis_id>/pdf`:
1. Carrega o JSON da análise
2. Gera HTML via `build_report()`
3. Converte para PDF com `WeasyPrint.HTML(string=html).write_pdf()`
4. Retorna `Response` com `content_type="application/pdf"` e header `Content-Disposition: attachment`
5. Em caso de falha (ImportError ou runtime error): flash de aviso + redirect para a versão HTML

---

## Módulos

### `modules/meta_parser.py`
- `MetaParser(filepath).parse() -> pd.DataFrame`
- Auto-detecta separador (`sep=None, engine='python'`)
- Mapeia ~40 variantes de nomes de coluna PT-BR/EN para o schema padrão
- Trata UTF-8 BOM, calcula métricas derivadas quando ausentes

### `modules/google_parser.py`
- `GoogleParser(filepath).parse() -> pd.DataFrame`
- Pula linhas de metadados no topo do arquivo
- Remove linhas de totais ("Total")
- Mesma lógica de cálculo de métricas derivadas

### `modules/analyzer.py`
- `analyze(df, platform, client_name, period, goals=None) -> dict`
- Funções internas: `_build_summary`, `_build_campaigns`, `_enrich_summary`, `_build_alerts`, `_build_recommendations`, `_compare_goals`
- `_compare_goals(summary, goals)` retorna lista de dicts com `{label, target, actual, fmt, status, higher_is_better}`
- Status da meta: `"atingida"` / `"próxima"` (±10%) / `"não atingida"`
- Alerta `budget_overspend` gerado se `total_spend > monthly_budget * 1.05`

### `modules/comparator.py`
- `compare(analysis_a, analysis_b) -> dict`
- Retorna: `{client_a, client_b, same_client, period_a, period_b, platform_a, platform_b, summary_rows, camps_both, camps_only_a, camps_only_b, diagnosis, recommendations}`
- `_delta(a, b)`: variação percentual de b em relação a a; `None` se base == 0

### `modules/report_builder.py`
- `build_report(analysis) -> str` — HTML standalone com CSS embutido
- Seções: header, resumo executivo, **metas do período**, performance por campanha, pontos de atenção, próximos passos, footer
- Labels para o cliente: Destaque / Estável / Em ajuste / Em revisão (sem termos internos)
- Print button `onclick="window.print()"` para Ctrl+P / Cmd+P

### `modules/goals.py`
- `get_goals(client_slug) -> dict | None`
- `save_goals(client_slug, client_name, goals) -> None`
- `list_all_goals() -> list[dict]`
- Persiste em `data/client_goals.json`

### `modules/utils.py`
- `normalize_slug(name) -> str`
- `allowed_file(filename, extensions) -> bool`
- `generate_unique_filename(client_name, original) -> str`
- `safe_float(value) -> float`
- `safe_int(value) -> int`
- `platform_label(platform) -> str`

---

## Plataformas suportadas

| Plataforma  | Parser                   | Encoding       |
|-------------|--------------------------|----------------|
| Meta Ads    | `modules/meta_parser.py` | UTF-8 com BOM  |
| Google Ads  | `modules/google_parser.py` | UTF-8 com BOM |

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

> **Nota de deploy:** Esta é uma aplicação Flask com estado local (uploads/ e reports/).
> Requer um servidor que suporte filesystem persistente — Railway, Render ou VPS.
> Netlify (estático) e Vercel (serverless com filesystem efêmero) não são compatíveis.

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
