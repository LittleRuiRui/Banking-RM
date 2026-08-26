from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

MODULES = [
    ("1. 申报概要", ["客户", "集团", "注册", "监管", "额度", "币种", "期限", "用途", "定价", "还款", "担保", "客户号", "评级", "KYC"]),
    ("2. 申报理由与经营策略", ["合作背景", "战略意义", "风险策略", "总体评价", "主要风险"]),
    ("3. 客户与集团概况", ["股东", "控制", "子公司", "董事会", "管理层", "战略", "并购"]),
    ("4. 宏观与行业环境", ["GDP", "利率", "通胀", "财政", "主权评级", "银行业", "监管", "地缘", "战争", "能源", "航运"]),
    ("5. 主营业务与市场地位", ["CIB", "Capital Markets", "Financing", "Transaction Banking", "收入结构", "市场份额", "排名", "同业"]),
    ("6. 风险管理", ["三道防线", "风险偏好", "信用风险", "Stage 1", "Stage 2", "Stage 3", "ECL", "LCR", "NSFR", "VaR", "AML", "制裁", "网络安全"]),
    ("7. 资本分析", ["CET1", "Tier 1", "Total Capital", "Leverage Ratio", "RWA", "资本充足"]),
    ("8. 资产质量", ["NPL", "NPE", "Stage 1", "Stage 2", "Stage 3", "ECL", "覆盖率", "行业分布", "地区分布"]),
    ("9. 资产负债表", ["总资产", "Total Assets", "Loans to customers", "客户贷款", "金融资产", "客户存款", "债券", "Equity"]),
    ("10. 盈利能力", ["Revenue", "NBI", "Operating expenses", "Gross Operating Income", "Cost of Risk", "Net income", "ROE", "ROTE", "cost-income"]),
    ("11. 负债与流动性", ["存款", "交易负债", "债券", "同业融资", "期限结构", "LCR", "NSFR", "Liquidity Reserve"]),
    ("12. 现金流分析", ["经营现金流", "投资现金流", "融资现金流", "cash flow", "CFO"]),
    ("13. 财务预测与压力测试", ["Base Case", "Stress Case", "NIM", "融资成本", "RWA", "CET1", "压力测试"]),
    ("14. 银企合作", ["现有合作", "已批", "已用", "未用", "到期", "收益", "手续费", "Pipeline"]),
    ("15. 客户综合价值", ["Cross-sell", "FX", "Trade", "DCM", "Deposit", "Cash", "Custody", "EVA", "RAROC", "战略价值"]),
    ("16. 政策与准入", ["信用政策", "集中度", "国别风险", "审批权限", "CET1", "NPL", "Leverage", "LCR", "NSFR", "黑名单", "准入"]),
    ("17. ESG与合规", ["ESG", "AML", "KYC", "制裁", "产品政策", "监管处罚"]),
    ("18. 最终授信结论", ["风险判断", "授信建议", "额度", "期限", "审批条件", "风险缓释", "待补"]),
]

INTERNAL_FIELDS = {
    "内部评级", "客户号", "KYC", "AML", "现有敞口", "国别限额", "集中度", "审批权限", "RAROC", "EVA", "FTP", "客户综合贡献", "Pipeline"
}

CRITICAL_TERMS = [
    "CET1", "Tier 1", "Total Capital", "RWA", "Leverage Ratio", "LCR", "NSFR", "NPL", "NPE", "Stage 2", "Stage 3",
    "Revenue", "NBI", "Net income", "总资产", "贷款", "存款", "评级", "管理层", "战略", "监管处罚", "Stress Case"
]


def _contains(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def _years_near_term(text: str, term: str, radius: int = 180) -> list[int]:
    out = []
    for m in re.finditer(re.escape(term), text, re.I):
        window = text[max(0, m.start() - radius):m.end() + radius]
        out.extend(int(y) for y in re.findall(r"\b(20\d{2})\b", window))
    return out


def _latest_year(text: str) -> int | None:
    ys = [int(y) for y in re.findall(r"\b(20\d{2})\b", text)]
    return max(ys) if ys else None


def check_credit_application(text: str, current_year: int | None = None) -> dict:
    current_year = current_year or datetime.utcnow().year
    latest_doc_year = _latest_year(text)
    rows = []
    blocking = []
    should_update = []
    nice = []

    for module, terms in MODULES:
        hits = [t for t in terms if _contains(text, t)]
        coverage = len(hits) / max(len(terms), 1)
        if coverage >= 0.45:
            status = "已覆盖"
        elif coverage >= 0.18:
            status = "部分覆盖"
        else:
            status = "缺失"
        internal_hits = sorted([f for f in INTERNAL_FIELDS if _contains(text, f)])
        row_years = []
        for t in hits:
            row_years.extend(_years_near_term(text, t))
        data_year = max(row_years) if row_years else latest_doc_year
        stale = bool(data_year and data_year <= current_year - 2)
        update_flag = "是" if stale or status != "已覆盖" else "否"
        missing = [t for t in terms if t not in hits][:8]
        action_bits = []
        if missing:
            action_bits.append("补充: " + "、".join(missing))
        if stale:
            action_bits.append(f"数据可能过期（最新识别年份 {data_year}）")
        if internal_hits:
            action_bits.append("INTERNAL REQUIRED: " + "、".join(internal_hits))
        rows.append({
            "项目": module,
            "当前是否覆盖": status,
            "当前数据日期": str(data_year) if data_year else "未识别",
            "是否需要更新": update_flag,
            "缺失内容/建议动作": "；".join(action_bits) if action_bits else "无明显缺口",
        })
        if status == "缺失" and module.startswith(("1.", "7.", "8.", "13.", "16.", "18.")):
            blocking.append(f"{module}: 核心模块缺失")
        elif stale or status == "部分覆盖":
            should_update.append(f"{module}: {'数据过期' if stale else '覆盖不完整'}")
        elif missing:
            nice.append(f"{module}: 可补充 {', '.join(missing[:3])}")

    outdated_metrics = []
    for term in CRITICAL_TERMS:
        if not _contains(text, term):
            continue
        years = _years_near_term(text, term)
        if years and max(years) <= current_year - 2:
            outdated_metrics.append({"field": term, "latest_year_seen": max(years), "status": "需要更新"})

    internal_required = sorted([f for f in INTERNAL_FIELDS if not _contains(text, f)])
    entity_warning = None
    entities = [x for x in ["CASA", "CACIB", "Crédit Agricole S.A.", "Credit Agricole S.A.", "Crédit Agricole CIB", "Credit Agricole CIB"] if _contains(text, x)]
    if len(entities) >= 2:
        entity_warning = "检测到多个集团/法人主体名称，请核对集团口径与申报主体是否混用: " + ", ".join(entities)

    for f in internal_required:
        blocking.append(f"INTERNAL REQUIRED: {f}")

    return {
        "rows": rows,
        "gap_list": {
            "Blocking before submission": blocking,
            "Should update": should_update + [f"{x['field']} latest year {x['latest_year_seen']}" for x in outdated_metrics],
            "Nice to improve": nice,
        },
        "outdated_critical_fields": outdated_metrics,
        "entity_scope_warning": entity_warning,
        "latest_year_detected": latest_doc_year,
        "internal_required_missing": internal_required,
        "note": "Keyword-based first-pass checker. It identifies likely gaps and stale fields but does not replace credit judgement or internal-system validation.",
    }
