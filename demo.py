"""展示用輸出與可重現的教學案例。無網路、沒有API呼叫。"""
import html

from engine import actions_for, evaluate
from samples import SAMPLES

VERSION = "2.0"

VERIFICATION_CASES = [
    {**sample, "expected_score": score, "group": "內建範例"}
    for sample, score in zip(SAMPLES, [95, 95, 95, 95, 85, 0])
] + [
    {"name": "待查證的網購交易", "scenario": "網購交易", "text": "請先匯款，再加私人 LINE 聯絡交貨。", "expected": "中", "expected_score": 40, "group": "邊界情境"},
    {"name": "正常限時活動", "scenario": "其他", "text": "社團限時免費體驗，請到校內攤位現場報名。", "expected": "低", "expected_score": 35, "group": "正常對照"},
    {"name": "防詐提醒", "scenario": "其他", "text": "請勿先匯款。不要加私人 LINE。不要提供 OTP。", "expected": "低", "expected_score": 0, "group": "正常對照"},
    {"name": "官方網域仍須查證", "scenario": "假包裹 / 假官方通知", "text": "【中華郵政官方通知】包裹已送達，請在營業時間領取。詳情 https://post.gov.tw/", "expected": "低", "expected_score": 20, "group": "正常對照"},
    {"name": "未收錄的新網址", "scenario": "網購交易", "text": "請立即前往 https://account-check.example.shop 並輸入 OTP 驗證碼。", "expected": "高", "expected_score": 75, "group": "網址檢查"},
    {"name": "重複催款不重複計分", "scenario": "其他", "text": "立即立即，限時先匯款，先匯款。", "expected": "中", "expected_score": 40, "group": "計分檢查"},
]


def verify_examples():
    rows = []
    for case in VERIFICATION_CASES:
        result = evaluate(case["text"])
        passed = result["score"] == case["expected_score"] and result["level"] == case["expected"]
        rows.append({"案例": case["name"], "類別": case["group"], "預期分數": case["expected_score"],
                     "實際分數": result["score"], "風險": result["level"], "檢查結果": "符合預期" if passed else "需檢查"})
    return rows


def highlight_message(text, quotes):
    """先以字元位置合併證據範圍，再escape每段；輸入永遠不能注入HTML。"""
    intervals = []
    for quote in dict.fromkeys(quotes):
        if not quote:
            continue
        start = 0
        while (found := text.find(quote, start)) != -1:
            intervals.append((found, found + len(quote)))
            start = found + len(quote)
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    output, cursor = [], 0
    for start, end in merged:
        output.extend([html.escape(text[cursor:start]), "<mark>", html.escape(text[start:end]), "</mark>"])
        cursor = end
    output.append(html.escape(text[cursor:]))
    return '<div class="message-evidence">' + "".join(output).replace("\n", "<br>") + "</div>"


def diagnosis_report(result, semantic, scenario):
    lines = [f"話術透視鏡 ScamLens v{VERSION}｜診斷摘要", f"情境：{scenario}",
             f"風險指數：{result['score']}/100；{result['level']}風險（非詐騙機率）",
             f"分析來源：{semantic['mode']}", f"可能類型：{semantic['possible_type']}",
             f"心理戰術：{'、'.join(semantic['tactics']) or '未偵測到四大心理戰術'}",
             f"判斷理由：{semantic['reason']}", f"分析信心值：{semantic['confidence']:.0%}（未校準）",
             semantic["notice"], "", "規則依據："]
    lines += [f"+{f['points']} {f['label']}（{'、'.join(f['sources'])}）" for f in result["findings"]]
    lines += [f"原始加總 {result['raw_score']}，上限100。", "", "建議行動："]
    lines += [f"{i}. {action}" for i, action in enumerate(actions_for(result["level"]), 1)]
    lines += ["", "查證入口：https://165.npa.gov.tw/", "本摘要供查證參考，低風險也不能保證安全。"]
    return "\n".join(lines)
