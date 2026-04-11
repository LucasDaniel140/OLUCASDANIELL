"""
Campaign analyzer — motor de análise de performance.

Receives a normalized DataFrame (standard schema defined in CLAUDE.md) and
returns a complete analysis dict with: summary KPIs, per-campaign metrics +
score/status/diagnosis, automatic alerts, and prioritized recommendations.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze(
    df: pd.DataFrame,
    platform: str,
    client_name: str,
    period: str,
    goals: dict | None = None,
) -> dict:
    """
    Main analysis function.

    Parameters
    ----------
    df          : Normalized DataFrame (standard schema).
    platform    : 'meta' or 'google'.
    client_name : Client identifier string.
    period      : Human-readable period string, e.g. '01/01/2024 → 31/01/2024'.
    goals       : Optional client goals dict from goals.py (target_cpa, min_roas, etc.).

    Returns
    -------
    dict with keys: client, platform, period, summary, campaigns, alerts,
    recommendations, goal_comparison.
    """
    summary         = _build_summary(df)
    campaigns       = _build_campaigns(df, summary)
    summary         = _enrich_summary(summary, campaigns)
    adsets          = _build_adsets(df, summary)
    ads             = _build_ads(df, summary)
    alerts          = _build_alerts(campaigns, summary, goals)
    recommendations = _build_recommendations(campaigns, alerts, summary)
    goal_comparison = _compare_goals(summary, goals) if goals else None

    return {
        "client":          client_name,
        "platform":        platform,
        "period":          period,
        "summary":         summary,
        "campaigns":       campaigns,
        "adsets":          adsets,
        "ads":             ads,
        "alerts":          alerts,
        "recommendations": recommendations,
        "goal_comparison": goal_comparison,
    }


# ---------------------------------------------------------------------------
# 1. Summary
# ---------------------------------------------------------------------------

def _build_summary(df: pd.DataFrame) -> dict:
    total_impressions = int(df["impressions"].sum())
    total_clicks = int(df["clicks"].sum())
    total_spend = round(float(df["spend"].sum()), 2)
    total_conversions = int(df["conversions"].sum())
    total_revenue = round(float(df["revenue"].sum()), 2)

    avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0.0
    avg_cpc = round(total_spend / total_clicks, 2) if total_clicks else 0.0
    avg_cpm = round(total_spend / total_impressions * 1000, 2) if total_impressions else 0.0
    avg_cpa = round(total_spend / total_conversions, 2) if total_conversions else 0.0
    avg_roas = round(total_revenue / total_spend, 2) if total_spend and total_revenue else 0.0
    has_revenue = total_revenue > 0

    return {
        "total_spend": total_spend,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "total_revenue": total_revenue,
        "avg_ctr": avg_ctr,
        "avg_cpc": avg_cpc,
        "avg_cpm": avg_cpm,
        "avg_cpa": avg_cpa,
        "avg_roas": avg_roas,
        "has_revenue": has_revenue,
        "best_campaign": None,
        "worst_campaign": None,
    }


def _enrich_summary(summary: dict, campaigns: list[dict]) -> dict:
    """Populate best/worst campaign fields after the campaign list is built."""
    if not campaigns:
        return summary

    if summary["has_revenue"]:
        with_roas = [c for c in campaigns if c["roas"] > 0]
        if with_roas:
            summary["best_campaign"] = max(with_roas, key=lambda c: c["roas"])["campaign_name"]
            summary["worst_campaign"] = min(with_roas, key=lambda c: c["roas"])["campaign_name"]
    else:
        with_cpa = [c for c in campaigns if c["cpa"] > 0]
        if with_cpa:
            summary["best_campaign"] = min(with_cpa, key=lambda c: c["cpa"])["campaign_name"]
        # Worst = lowest overall score
        summary["worst_campaign"] = min(campaigns, key=lambda c: c["score"])["campaign_name"]

    return summary


# ---------------------------------------------------------------------------
# 2. Campaigns
# ---------------------------------------------------------------------------

def _build_campaigns(df: pd.DataFrame, summary: dict) -> list[dict]:
    avg_cpc = summary["avg_cpc"]
    avg_cpa = summary["avg_cpa"]
    has_revenue = summary["has_revenue"]
    total_spend = summary["total_spend"]

    campaigns: list[dict] = []
    for camp_name, group in df.groupby("campaign_name", dropna=False):
        camp_name = str(camp_name).strip() if camp_name else "—"
        kpis = _compute_kpis(group)
        score = _compute_score(kpis, avg_cpc, avg_cpa, has_revenue)
        status = _status_label(score)
        diagnosis = _diagnosis_text(kpis, avg_cpc, avg_cpa, has_revenue)
        spend_pct = round(kpis["spend"] / total_spend * 100, 1) if total_spend else 0.0

        campaigns.append({
            "campaign_name": camp_name,
            **kpis,
            "score": score,
            "status": status,
            "diagnosis": diagnosis,
            "spend_pct": spend_pct,
        })

    # Sort by spend descending
    campaigns.sort(key=lambda c: c["spend"], reverse=True)
    return campaigns


def _build_adsets(df: pd.DataFrame, summary: dict) -> list[dict]:
    """Return per-adset KPIs grouped by (campaign_name, adset_name)."""
    col = "adset_name"
    if col not in df.columns:
        return []
    if df[col].fillna("").str.strip().eq("").all():
        return []

    avg_cpc     = summary["avg_cpc"]
    avg_cpa     = summary["avg_cpa"]
    has_revenue = summary["has_revenue"]
    total_spend = summary["total_spend"]

    rows: list[dict] = []
    for (camp, adset), group in df.groupby(["campaign_name", col], dropna=False):
        adset_clean = str(adset).strip() if adset and str(adset).strip() not in ("", "nan") else None
        if not adset_clean:
            continue
        kpis      = _compute_kpis(group)
        score     = _compute_score(kpis, avg_cpc, avg_cpa, has_revenue)
        spend_pct = round(kpis["spend"] / total_spend * 100, 1) if total_spend else 0.0
        rows.append({
            "campaign_name": str(camp).strip() if camp else "—",
            "adset_name":    adset_clean,
            **kpis,
            "score":         score,
            "status":        _status_label(score),
            "spend_pct":     spend_pct,
        })

    rows.sort(key=lambda r: r["spend"], reverse=True)
    return rows


def _build_ads(df: pd.DataFrame, summary: dict) -> list[dict]:
    """Return per-ad KPIs grouped by (campaign_name, adset_name, ad_name)."""
    col = "ad_name"
    if col not in df.columns:
        return []
    if df[col].fillna("").str.strip().eq("").all():
        return []

    avg_cpc     = summary["avg_cpc"]
    avg_cpa     = summary["avg_cpa"]
    has_revenue = summary["has_revenue"]
    total_spend = summary["total_spend"]

    rows: list[dict] = []
    for (camp, adset, ad), group in df.groupby(
        ["campaign_name", "adset_name", col], dropna=False
    ):
        ad_clean = str(ad).strip() if ad and str(ad).strip() not in ("", "nan") else None
        if not ad_clean:
            continue
        kpis      = _compute_kpis(group)
        score     = _compute_score(kpis, avg_cpc, avg_cpa, has_revenue)
        spend_pct = round(kpis["spend"] / total_spend * 100, 1) if total_spend else 0.0
        rows.append({
            "campaign_name": str(camp).strip() if camp else "—",
            "adset_name":    str(adset).strip() if adset and str(adset).strip() not in ("", "nan") else "—",
            "ad_name":       ad_clean,
            **kpis,
            "score":         score,
            "status":        _status_label(score),
            "spend_pct":     spend_pct,
        })

    rows.sort(key=lambda r: r["spend"], reverse=True)
    return rows


def _compute_kpis(group: pd.DataFrame) -> dict:
    impressions = int(group["impressions"].sum())
    clicks = int(group["clicks"].sum())
    spend = round(float(group["spend"].sum()), 2)
    conversions = int(group["conversions"].sum())
    revenue = round(float(group["revenue"].sum()), 2)

    ctr = round(clicks / impressions * 100, 2) if impressions else 0.0
    cpc = round(spend / clicks, 2) if clicks else 0.0
    cpm = round(spend / impressions * 1000, 2) if impressions else 0.0
    cpa = round(spend / conversions, 2) if conversions else 0.0
    roas = round(revenue / spend, 2) if spend and revenue else 0.0

    return {
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "conversions": conversions,
        "revenue": revenue,
        "ctr": ctr,
        "cpc": cpc,
        "cpm": cpm,
        "cpa": cpa,
        "roas": roas,
    }


def _compute_score(
    kpis: dict, avg_cpc: float, avg_cpa: float, has_revenue: bool
) -> int:
    score = 0
    ctr = kpis["ctr"]
    cpc = kpis["cpc"]
    cpa = kpis["cpa"]
    roas = kpis["roas"]
    conversions = kpis["conversions"]

    # CTR — max 20 pts
    if ctr > 2.0:
        score += 20
    elif ctr >= 1.0:
        score += 10

    # CPC below account average — 20 pts
    if avg_cpc > 0 and cpc > 0 and cpc < avg_cpc:
        score += 20

    # CPA below account average — 25 pts
    if avg_cpa > 0 and cpa > 0 and cpa < avg_cpa:
        score += 25

    # ROAS — max 25 pts
    if has_revenue and roas > 0:
        if roas > 3.0:
            score += 25
        elif roas >= 1.5:
            score += 10

    # At least one conversion — 10 pts
    if conversions > 0:
        score += 10

    return min(100, max(0, score))


def _status_label(score: int) -> str:
    if score >= 80:
        return "Escalar"
    if score >= 60:
        return "Manter"
    if score >= 40:
        return "Otimizar"
    return "Pausar"


def _diagnosis_text(
    kpis: dict, avg_cpc: float, avg_cpa: float, has_revenue: bool
) -> str:
    parts: list[str] = []
    ctr = kpis["ctr"]
    cpc = kpis["cpc"]
    cpa = kpis["cpa"]
    roas = kpis["roas"]
    conversions = kpis["conversions"]

    # CTR assessment
    if ctr < 0.5:
        parts.append(
            f"CTR crítico ({ctr:.2f}%) — criativo ou público provavelmente inadequado"
        )
    elif ctr < 1.0:
        parts.append(f"CTR abaixo de 1% ({ctr:.2f}%) — espaço para melhorar o criativo")
    elif ctr >= 2.0:
        parts.append(f"CTR forte ({ctr:.2f}%)")
    else:
        parts.append(f"CTR razoável ({ctr:.2f}%)")

    # CPA vs average
    if conversions == 0:
        parts.append("sem conversões no período")
    elif avg_cpa > 0 and cpa > 0:
        diff_pct = (cpa - avg_cpa) / avg_cpa * 100
        if diff_pct > 50:
            parts.append(
                f"CPA R${cpa:.2f} está {diff_pct:.0f}% acima da média"
                " — revisar segmentação ou oferta"
            )
        elif diff_pct > 10:
            parts.append(f"CPA R${cpa:.2f} ligeiramente acima da média")
        elif diff_pct < -20:
            parts.append(
                f"CPA R${cpa:.2f} está {abs(diff_pct):.0f}% abaixo da média — boa eficiência"
            )
        else:
            parts.append(f"CPA R${cpa:.2f} dentro da média")

    # ROAS
    if has_revenue and roas > 0:
        if roas >= 4.0:
            parts.append(f"ROAS excelente ({roas:.2f}x)")
        elif roas >= 3.0:
            parts.append(f"ROAS muito bom ({roas:.2f}x)")
        elif roas >= 1.5:
            parts.append(f"ROAS positivo ({roas:.2f}x)")
        elif roas >= 1.0:
            parts.append(f"ROAS baixo ({roas:.2f}x) — margem apertada")
        else:
            parts.append(f"ROAS negativo ({roas:.2f}x) — campanha operando com prejuízo")

    # CTR ok but CPA high → landing page signal
    if ctr >= 1.0 and avg_cpa > 0 and cpa > avg_cpa * 1.5 and conversions > 0:
        parts.append("cliques não estão convertendo — revisar landing page ou funil")

    if not parts:
        return "Dados insuficientes para diagnóstico."

    sentence = ". ".join(parts)
    return sentence[0].upper() + sentence[1:] + "."


# ---------------------------------------------------------------------------
# 3. Alerts
# ---------------------------------------------------------------------------

def _build_alerts(
    campaigns: list[dict], summary: dict, goals: dict | None = None
) -> list[dict]:
    alerts: list[dict] = []
    avg_cpa = summary["avg_cpa"]
    has_revenue = summary["has_revenue"]

    for c in campaigns:
        name = c["campaign_name"]
        ctr = c["ctr"]
        cpa = c["cpa"]
        roas = c["roas"]
        spend_pct = c["spend_pct"]
        conversions = c["conversions"]

        # CTR crítico
        if c["impressions"] > 0 and ctr < 0.5:
            alerts.append({
                "type": "ctr_critical",
                "level": "critical",
                "campaign": name,
                "message": (
                    f'CTR crítico ({ctr:.2f}%) em "{name}"'
                    " — possível problema de criativo ou público."
                ),
            })

        # CPA muito acima da média
        if avg_cpa > 0 and cpa > avg_cpa * 2 and conversions > 0:
            alerts.append({
                "type": "cpa_high",
                "level": "critical",
                "campaign": name,
                "message": (
                    f'CPA muito alto (R${cpa:.2f}) em "{name}"'
                    f" — {cpa / avg_cpa:.1f}x acima da média."
                    " Revisar segmentação."
                ),
            })

        # Alto gasto sem nenhuma conversão
        if spend_pct > 30 and conversions == 0:
            alerts.append({
                "type": "no_conversion",
                "level": "warning",
                "campaign": name,
                "message": (
                    f'"{name}" consumiu {spend_pct:.1f}% do orçamento'
                    f" (R${c['spend']:.2f}) sem gerar nenhuma conversão."
                ),
            })

        # ROAS negativo
        if has_revenue and roas > 0 and roas < 1.0:
            alerts.append({
                "type": "roas_negative",
                "level": "critical",
                "campaign": name,
                "message": (
                    f'ROAS negativo ({roas:.2f}x) em "{name}"'
                    " — cada real investido retorna menos de R$1,00."
                ),
            })

        # CTR alto + CPA alto → landing page
        if ctr >= 1.0 and avg_cpa > 0 and cpa > avg_cpa * 1.5 and conversions > 0:
            alerts.append({
                "type": "landing_page",
                "level": "warning",
                "campaign": name,
                "message": (
                    f'Cliques sem conversão eficiente em "{name}"'
                    f" (CTR {ctr:.2f}%, CPA {cpa / avg_cpa:.1f}x acima da média)"
                    " — verificar landing page ou oferta."
                ),
            })

    # Budget overspend alert (prepend — highest priority)
    if goals and goals.get("monthly_budget"):
        budget = float(goals["monthly_budget"])
        actual_spend = summary["total_spend"]
        if budget > 0 and actual_spend > budget * 1.05:
            overspend_pct = (actual_spend - budget) / budget * 100
            alerts.insert(0, {
                "type": "budget_overspend",
                "level": "critical",
                "campaign": "geral",
                "message": (
                    f"Orçamento mensal excedido em {overspend_pct:.1f}% — "
                    f"investido R${actual_spend:,.2f} de um orçamento de"
                    f" R${budget:,.2f}."
                ),
            })

    # Critical first, then warning
    alerts.sort(key=lambda a: 0 if a["level"] == "critical" else 1)
    return alerts


# ---------------------------------------------------------------------------
# 5. Goal comparison
# ---------------------------------------------------------------------------

def _compare_goals(summary: dict, goals: dict) -> list[dict]:
    """Compare summary KPIs against defined client goals."""
    rows: list[dict] = []

    def _status(actual: float, target: float, higher_is_better: bool) -> str:
        if target == 0:
            return "não atingida"
        diff_pct = (actual - target) / abs(target) * 100
        if higher_is_better:
            if diff_pct >= 0:
                return "atingida"
            if diff_pct >= -10:
                return "próxima"
            return "não atingida"
        else:
            if diff_pct <= 0:
                return "atingida"
            if diff_pct <= 10:
                return "próxima"
            return "não atingida"

    if goals.get("target_cpa") and summary.get("avg_cpa", 0) > 0:
        target = float(goals["target_cpa"])
        actual = float(summary["avg_cpa"])
        rows.append({
            "label": "CPA alvo",
            "target": target,
            "actual": actual,
            "fmt": "brl",
            "status": _status(actual, target, False),
            "higher_is_better": False,
        })

    if goals.get("min_roas") and summary.get("avg_roas", 0) > 0:
        target = float(goals["min_roas"])
        actual = float(summary["avg_roas"])
        rows.append({
            "label": "ROAS mínimo",
            "target": target,
            "actual": actual,
            "fmt": "x",
            "status": _status(actual, target, True),
            "higher_is_better": True,
        })

    if goals.get("min_ctr") and summary.get("avg_ctr", 0) > 0:
        target = float(goals["min_ctr"])
        actual = float(summary["avg_ctr"])
        rows.append({
            "label": "CTR mínimo",
            "target": target,
            "actual": actual,
            "fmt": "pct",
            "status": _status(actual, target, True),
            "higher_is_better": True,
        })

    if goals.get("max_cpc") and summary.get("avg_cpc", 0) > 0:
        target = float(goals["max_cpc"])
        actual = float(summary["avg_cpc"])
        rows.append({
            "label": "CPC máximo",
            "target": target,
            "actual": actual,
            "fmt": "brl",
            "status": _status(actual, target, False),
            "higher_is_better": False,
        })

    return rows


# ---------------------------------------------------------------------------
# 4. Recommendations
# ---------------------------------------------------------------------------

def _build_recommendations(
    campaigns: list[dict], alerts: list[dict], summary: dict
) -> list[dict]:
    recs: list[dict] = []
    avg_ctr = summary["avg_ctr"]
    avg_roas = summary["avg_roas"]
    avg_cpa = summary["avg_cpa"]
    has_revenue = summary["has_revenue"]

    to_scale = [c for c in campaigns if c["status"] == "Escalar"]
    to_pause = [c for c in campaigns if c["status"] == "Pausar"]
    to_optimize = [c for c in campaigns if c["status"] == "Otimizar"]

    # Priority 1 — pause worst campaigns
    if to_pause:
        names = ", ".join(f'"{c["campaign_name"]}"' for c in to_pause[:2])
        suffix = f" e mais {len(to_pause) - 2}" if len(to_pause) > 2 else ""
        recs.append({
            "priority": 1,
            "action": (
                f"Pausar {names}{suffix} imediatamente e redirecionar o budget"
                " para as campanhas de melhor performance."
            ),
            "impact": "Elimina desperdício de orçamento e melhora o CPA geral da conta.",
            "campaign": to_pause[0]["campaign_name"] if len(to_pause) == 1 else "Múltiplas",
        })

    # Priority 2 — scale best campaigns
    if to_scale:
        names = ", ".join(f'"{c["campaign_name"]}"' for c in to_scale[:2])
        suffix = f" e mais {len(to_scale) - 2}" if len(to_scale) > 2 else ""
        recs.append({
            "priority": 2,
            "action": (
                f"Aumentar o orçamento de {names}{suffix} em 20–30%"
                " para aproveitar a performance positiva."
            ),
            "impact": "Aumenta conversões e receita mantendo ou melhorando o CPA atual.",
            "campaign": to_scale[0]["campaign_name"] if len(to_scale) == 1 else "Múltiplas",
        })

    # Priority 3 — low CTR → new creatives
    if avg_ctr < 1.5:
        recs.append({
            "priority": 3,
            "action": (
                "Testar 2–3 novos criativos (vídeo curto, UGC ou carrossel)"
                f" para elevar o CTR médio, atualmente em {avg_ctr:.2f}%."
            ),
            "impact": "Melhorar o CTR reduz o CPM efetivo e gera mais cliques com o mesmo orçamento.",
            "campaign": "geral",
        })

    # Priority 4 — CTR ok but CPA high → landing page
    lp_issue = [
        c for c in campaigns
        if c["ctr"] >= 1.0
        and avg_cpa > 0
        and c["cpa"] > avg_cpa * 1.5
        and c["conversions"] > 0
    ]
    if lp_issue:
        recs.append({
            "priority": 4,
            "action": (
                "Revisar landing page e funil de conversão das campanhas com CTR"
                " bom mas CPA acima da média."
            ),
            "impact": "Melhorar a taxa de conversão da página reduz o CPA sem alterar o investimento.",
            "campaign": lp_issue[0]["campaign_name"] if len(lp_issue) == 1 else "Múltiplas",
        })

    # Priority 5 — low ROAS or optimize campaigns
    if has_revenue and avg_roas > 0 and avg_roas < 1.5:
        recs.append({
            "priority": 5,
            "action": (
                f"Revisar oferta, precificação ou ticket médio — ROAS médio está em {avg_roas:.2f}x,"
                " abaixo do mínimo saudável de 1.5x."
            ),
            "impact": "Aumentar o valor por conversão melhora o ROAS sem precisar reduzir o investimento.",
            "campaign": "geral",
        })
    elif to_optimize:
        recs.append({
            "priority": 5,
            "action": (
                "Revisar segmentação, fase de aprendizado e lances das campanhas em status 'Otimizar'."
            ),
            "impact": "Ajustes de público e estratégia de lance podem melhorar o CPA e elevar o score.",
            "campaign": "geral",
        })

    recs.sort(key=lambda r: r["priority"])
    return recs[:5]
