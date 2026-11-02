"""可獨立測試的規則引擎：各類一次計分，LLM 不修改分數。"""
import re
import unicodedata
from urllib.parse import urlsplit

MAX_LENGTH = 5000
CHECKS = {
    "transfer": "對方是否要求先匯款",
    "line": "是否要求加私人 LINE",
    "urgency": "是否使用限時壓力",
    "isolation": "是否要求保密",
    "sensitive": "是否要求 OTP、信用卡或個資",
    "greed": "是否承諾高報酬",
    "url": "是否提供非官方網址或短網址",
}
RULES = {
    "url": ("未查證 / 短網址 / 示範黑名單", 30),
    "urgency": ("限時壓力", 15),
    "greed": ("利益誘惑", 20),
    "line": ("轉往私人 LINE", 15),
    "transfer": ("要求先匯款", 25),
    "isolation": ("要求保密", 20),
    "sensitive": ("索取驗證碼或敏感資料", 30),
    "authority": ("自稱官方或權威身分（尚未驗證）", 20),
}
PATTERNS = {
    "urgency": r"24\s*小時內|立即|限時|馬上|名額有限|只保留\s*\d+\s*分鐘",
    "greed": r"免費|日賺|高報酬|穩賺|保證.{0,8}(?:獲利|收益)|低價轉讓",
    "line": r"(?:加|加入|添加).{0,8}(?:私人\s*)?LINE|私[下人].{0,8}LINE",
    "transfer": r"先\s*(?:匯款|轉帳|付款)|(?:匯款|轉帳).{0,10}(?:保證金|指定帳戶)|(?:支付|繳交).{0,6}保證金",
    "isolation": r"保密|不要告訴.{0,8}(?:家長|老師|家人)|別告訴.{0,8}(?:家長|老師|家人)",
    "sensitive": r"(?:輸入|提供|傳送|回傳|填寫|告知|交出).{0,24}(?:OTP|驗證碼|信用卡|個資|個人資料|身分證|身份證|密碼)",
    "authority": r"(?:政府|銀行|物流|平台|中華郵政|郵局|警察|警政署|國稅局|客服).{0,8}(?:官方|通知|認證)|官方.{0,8}(?:通知|客服)|(?:我是|我們是|本公司是).{0,8}(?:銀行|警察|客服)",
}
TACTICS = {
    "urgency": ("急迫感 Urgency", "用時間壓力減少查證與思考。"),
    "greed": ("利益誘惑 Greed", "用獲利或優惠吸引你採取行動。"),
    "authority": ("權威偽造 Authority", "借用官方身分增加信任，身分仍需查證。"),
    "isolation": ("孤立保密 Isolation", "要求保密，阻止家長或老師協助查證。"),
}
# 僅少數人工維護的已知網域；不是完整官方資料庫。
KNOWN_DOMAINS = {"post.gov.tw", "165.npa.gov.tw", "npa.gov.tw"}
SHORT_DOMAINS = {"bit.ly", "tinyurl.com", "reurl.cc", "t.co", "is.gd"}
DEMO_BLOCKLIST = {"post-redelivery.example", "fake-bank.example"}
URL_PATTERN = re.compile(
    r"(?:https?://|www\.)[^\s<>\u3000，。；、！？\"'【】]+"
    r"|(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}(?![\w.-])(?:/[^\s<>，。；、！？\"']*)?",
    re.I,
)


def normalize(text):
    return unicodedata.normalize("NFKC", text).strip()


def level_for(score):
    return "高" if score >= 70 else "中" if score >= 40 else "低"


def clauses(text):
    return [s.strip() for s in re.split(r"[。！？!?；;\n，,]", text) if s.strip()]


def is_negated(clause, start, key):
    """有限的否定處理：僅看匹配前綴，避免防詐提醒反向加分。"""
    prefix = clause[max(0, start - 18):start]
    if key == "isolation" and clause[start:].startswith(("不要告訴", "別告訴")):
        return False  # 「不要告訴家長」本身就是保密要求。
    return bool(re.search(r"(?:不要|請勿|切勿|不需|無需|不必|不得|不會|不應|避免|毋須|不能|勿|別).{0,10}$", prefix))


def extract_urls(text):
    urls = []
    for match in URL_PATTERN.finditer(text):
        value = match.group().rstrip(".)]}")
        try:
            parsed = urlsplit(value if "://" in value else "https://" + value)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port  # 無效port／不完整IPv6不可讓整段分析中斷。
        except ValueError:
            urls.append({"url": value, "host": "格式異常的網址", "status": "網址格式異常，請勿直接開啟", "risky": True})
            continue
        if not host:
            urls.append({"url": value, "host": "缺少主機名稱", "status": "網址不完整，需查證", "risky": True})
            continue
        if parsed.username is not None or parsed.password is not None:
            status = "網址含使用者資訊，需另行查證真實目的地"
            risky = True
        elif parsed.scheme != "https" or port not in (None, 443):
            status = "非HTTPS或使用特殊連接埠，需查證"
            risky = True
        elif host in DEMO_BLOCKLIST:
            status = "示範黑名單（人工教學資料）"
            risky = True
        elif host in SHORT_DOMAINS:
            status = "短網址，目的地尚未查證"
            risky = True
        elif any(host == domain or host.endswith("." + domain) for domain in KNOWN_DOMAINS):
            status = "符合有限已知網域清單；仍需確認訊息來源"
            risky = False
        else:
            status = "未列入已知清單，需從官方管道查證"
            risky = True
        if not any(u["url"] == value for u in urls):
            urls.append({"url": value, "host": host, "status": status, "risky": risky})
    return urls


def evaluate(text, checked=()):
    text = normalize(text)
    if not text:
        raise ValueError("請先貼上要分析的訊息。")
    if len(text) > MAX_LENGTH:
        raise ValueError(f"請將訊息縮短到 {MAX_LENGTH} 字以內。")
    checked = set(checked) & CHECKS.keys()
    urls = extract_urls(text)
    findings = []
    for key, (label, points) in RULES.items():
        evidence = []
        if key == "url":
            evidence = [u["url"] for u in urls if u["risky"]]
        else:
            for clause in clauses(text):
                for match in re.finditer(PATTERNS[key], clause, re.I):
                    if not is_negated(clause, match.start(), key):
                        evidence.append(clause)
                        break
        sources = []
        if evidence:
            sources.append("訊息文字")
        if key in checked:
            sources.append("使用者勾選")
        if sources:
            findings.append({"key": key, "label": label, "points": points,
                             "evidence": list(dict.fromkeys(evidence)), "sources": sources})
    raw_score = sum(f["points"] for f in findings)
    score = min(100, raw_score)
    return {"text": text, "score": score, "raw_score": raw_score,
            "level": level_for(score), "findings": findings, "urls": urls}


def actions_for(level):
    if level == "高":
        return ["不要點擊訊息中的連結。", "不要轉帳或先付保證金。",
                "不要輸入或提供 OTP、信用卡或個資。", "從官方 App／官網查證，或撥打 165。",
                "找家長或老師一起確認，保留訊息紀錄。"]
    if level == "中":
        return ["先不要操作、付款或回傳資料。", "自行開啟官方 App 或官網查證。",
                "詢問家長、老師或撥打 165。"]
    return ["仍建議透過官方管道確認。", "不要只依賴單一訊息或系統分數判斷。"]


def help_message(result, scenario):
    priority = ["sensitive", "transfer", "url", "isolation", "line", "urgency", "greed", "authority"]
    ordered = sorted(result["findings"], key=lambda f: priority.index(f["key"]))
    labels = "、".join(f["label"] for f in ordered[:3]) or "尚未偵測到明顯風險特徵"
    return (f"我收到一則「{scenario}」的訊息，話術透視鏡標示為{result['level']}風險"
            f"（規則分數 {result['score']}/100，不代表詐騙機率）。"
            f"檢查項目：{labels}。我想先暫停操作，可以幫我一起透過官方管道確認嗎？")
