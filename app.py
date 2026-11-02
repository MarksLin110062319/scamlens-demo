"""ScamLens 展示版：規則評分、話術說明與查證流程。"""
import html
import os
from pathlib import Path

import streamlit as st

from analysis import SYSTEM_PROMPT, analyze
from demo import VERSION, VERIFICATION_CASES, diagnosis_report, highlight_message, verify_examples
from engine import CHECKS, MAX_LENGTH, RULES, TACTICS, actions_for, evaluate, help_message
from samples import SAMPLES, SCENARIOS

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="ScamLens 話術透視鏡", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed")
st.markdown((ROOT / "styles.css").read_text(encoding="utf-8"), unsafe_allow_html=True)


def clear_result():
    for key in ("diagnosis", "help_text"):
        st.session_state.pop(key, None)


def load_sample(index):
    sample = SAMPLES[index]
    st.session_state["message"] = sample["text"]
    st.session_state["scenario"] = sample["scenario"]
    for key in CHECKS:
        st.session_state["check_" + key] = False
    clear_result()


def reset_input():
    st.session_state["message"] = ""
    st.session_state["scenario"] = SCENARIOS[0]
    for key in CHECKS:
        st.session_state["check_" + key] = False
    clear_result()


st.session_state.setdefault("message", "")
st.session_state.setdefault("scenario", SCENARIOS[0])

with st.sidebar:
    st.subheader("分析設定")
    mode_label = st.radio("分析方式", ["Mock 示範（免 API key）", "OpenAI LLM"], key="mode_label")
    mode = "api" if mode_label == "OpenAI LLM" else "mock"
    key_ready = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    consent = False
    if mode == "api":
        if key_ready:
            st.success("已設定 API key")
        else:
            st.warning("沒有 API key，分析時會改用 Mock。")
        st.caption("文字與情境會送到 OpenAI。請先移除真實個資；目前尚未自動去識別化。")
        consent = st.checkbox("我已移除真實個資，同意送出分析", key="api_consent")
    else:
        st.info("本機關鍵字模擬，不會呼叫 AI 服務。")
    st.divider()
    st.caption("規則決定風險分數，LLM 解釋心理話術。Mock 讓相同操作流程可以離線展示。")
    st.button("清除輸入與結果", on_click=reset_input, width="stretch")
    st.link_button("165 全民防騙網", "https://165.npa.gov.tw/", width="stretch")
    st.caption(f"ScamLens v{VERSION} · 高中職組展示原型")

st.markdown('<div class="brand-line"><span class="brand-symbol">◎</span> SCAMLENS <span>話術透視鏡</span></div>', unsafe_allow_html=True)
st.title("先看懂話術，再決定下一步。")
st.write("把可疑訊息貼在這裡，一起找出催促付款、索取資料或要求保密的訊號。")
st.caption(f"{'選用 LLM 分析' if mode == 'api' else 'Mock 展示模式 · 免 API key'}　／　文字分析　／　風險分數可追溯")

diagnose_tab, verify_tab, design_tab = st.tabs(["開始診斷", "範例驗證", "系統設計"])

with diagnose_tab:
    with st.expander("沒有訊息？先載入一則範例", expanded=not bool(st.session_state["message"])):
        sample_columns = st.columns(3)
        for i, sample in enumerate(SAMPLES):
            sample_columns[i % 3].button(sample["name"], key=f"sample_{i}",
                                         on_click=load_sample, args=(i,), width="stretch")
        st.caption("人工編寫的教學訊息，含正常通知對照；載入後按「開始分析」。")

    with st.container(key="workspace"):
        left, right = st.columns([1, 1.08], gap="large")
        with left:
            with st.container(border=True, key="input_panel"):
                st.subheader("01　貼上與檢查")
                scenario = st.selectbox("這則訊息涉及哪種情境？", SCENARIOS, key="scenario")
                text = st.text_area("可疑簡訊、LINE 訊息或社群私訊", key="message", height=170,
                                    max_chars=MAX_LENGTH, placeholder="貼上訊息；請先移除姓名、電話、帳號等真實個資。")
                st.caption(f"{len(text)} / {MAX_LENGTH} 字")
                st.markdown("**交易前檢查表**")
                st.caption("勾選對話中出現的要求。同一項目只計分一次。")
                checked = []
                check_columns = st.columns(2)
                for i, (key, label) in enumerate(CHECKS.items()):
                    if check_columns[i % 2].checkbox(label, key="check_" + key):
                        checked.append(key)
                submitted = st.button("🔎 開始分析", type="primary", width="stretch")

        fingerprint = (text, scenario, tuple(checked), mode, consent, key_ready)
        if st.session_state.get("diagnosis", {}).get("fingerprint") != fingerprint:
            clear_result()
        if submitted:
            clear_result()
            if mode == "api" and key_ready and not consent:
                with left:
                    st.error("請先移除個資並勾選同意，或切換到 Mock 模式。")
            else:
                try:
                    result = evaluate(text, checked)
                    with st.spinner("計算規則分數，拆解訊息話術…"):
                        semantic = analyze(result, scenario, mode)
                    st.session_state["diagnosis"] = {"fingerprint": fingerprint, "rules": result, "semantic": semantic}
                except ValueError as error:
                    with left:
                        st.error(str(error))

        with right:
            with st.container(border=True, key="result_panel"):
                st.subheader("02　風險診斷卡")
                diagnosis = st.session_state.get("diagnosis")
                if not diagnosis:
                    st.markdown('<div class="empty-result"><div class="empty-symbol">◎</div><h3>先停一下，讓訊息有跡可循。</h3><p>貼上文字，或從範例開始。分析後會顯示風險指數、可疑句子與下一步。</p></div>', unsafe_allow_html=True)
                    st.markdown("**這張卡會幫你回答**")
                    st.write("對方要我做什麼？用什麼話術催促我？我該怎麼查證？")
                else:
                    result, semantic = diagnosis["rules"], diagnosis["semantic"]
                    score, level = result["score"], result["level"]
                    banner = {"高": st.error, "中": st.warning, "低": st.success}[level]
                    banner(f"{level}風險 · " + {"高": "先停止操作，找人一起查證", "中": "先暫停，從官方管道確認", "低": "明顯風險特徵較少，仍需確認來源"}[level])
                    score_col, count_col = st.columns(2)
                    score_col.metric("風險指數", f"{score} / 100")
                    count_col.metric("命中風險項目", f"{len(result['findings'])} 項")
                    st.progress(score / 100)
                    st.caption("規則點數，非詐騙機率。0–39 低／40–69 中／70–100 高。")
                    st.caption(f"分析來源：{semantic['mode']}")
                    if semantic.get("warning"):
                        st.warning(semantic["warning"])
                    st.markdown("**可能類型**")
                    st.text(semantic["possible_type"])
                    st.markdown("**心理戰術**")
                    if semantic["tactics"]:
                        for tactic in semantic["tactics"]:
                            explanation = next((desc for label, desc in TACTICS.values() if label == tactic), "")
                            st.markdown(f'<div class="tactic-row"><b>{html.escape(tactic)}</b><span>{html.escape(explanation)}</span></div>', unsafe_allow_html=True)
                    else:
                        st.caption("未偵測到四大心理戰術，仍需查看規則依據。")
                    st.markdown("**判斷理由**")
                    st.text(semantic["reason"])
                    with st.expander("分析信心值與模式說明"):
                        st.write(f"話術分析信心值：{semantic['confidence']:.0%}")
                        st.caption(semantic["notice"])

    if diagnosis := st.session_state.get("diagnosis"):
        result, semantic = diagnosis["rules"], diagnosis["semantic"]
        quotes = list(dict.fromkeys(semantic["quotes"] + [q for f in result["findings"] for q in f["evidence"]]))
        st.subheader("03　看懂依據，完成查證")
        evidence_col, action_col = st.columns([1, 1.08], gap="large")
        with evidence_col:
            with st.container(border=True):
                st.markdown("**訊息中的風險線索**")
                st.caption("黃色標示為命中的文字片段。顯示經全形／半形正規化的分析文字。")
                st.markdown(highlight_message(result["text"], quotes), unsafe_allow_html=True)
                if not quotes:
                    st.caption("沒有命中原文片段；勾選的要求會列在下方規則明細。")
                with st.expander("查看規則計分明細", expanded=True):
                    if result["findings"]:
                        st.dataframe([{"風險項目": f["label"], "加分": f["points"], "依據來源": "＋".join(f["sources"])} for f in result["findings"]], hide_index=True, width="stretch")
                    else:
                        st.write("未命中規則，0 分。")
                    st.caption(f"原始合計 {result['raw_score']}，上限 100，最終 {result['score']} 分。文字與勾選不重複計分。")
                if result["urls"]:
                    with st.expander("網址檢查結果"):
                        for url in result["urls"]:
                            st.text(f"{url['host']}\n{url['status']}")
                        st.caption("只比對本機有限清單，未連線開啟網址或查詢真實黑名單。符合已知網域也不保證整段訊息安全。")
        with action_col:
            with st.container(border=True):
                st.markdown("**建議行動**")
                for i, action in enumerate(actions_for(result["level"]), 1):
                    st.write(f"{i}. {action}")
                with st.expander("查看查證指南"):
                    st.write("離開對方的連結與電話，自己開啟原本使用的官方 App、官網或交易平台，核對訂單與公告。仍有疑慮時，找家長、老師或 165 協助。")
                    st.link_button("前往 165 全民防騙網", "https://165.npa.gov.tw/")
                if st.button("✉ 一鍵產生家長 / 老師求助訊息", width="stretch"):
                    st.session_state["help_text"] = help_message(result, scenario)
                if "help_text" in st.session_state:
                    st.text_area("可複製、修改後傳給家長或老師", key="help_text", height=140)
                    st.download_button("下載求助文字", st.session_state["help_text"], "scamlens-help.txt", "text/plain; charset=utf-8")
                    st.caption("只產生文字，不會自動傳送。")
                st.download_button("下載本次診斷摘要", diagnosis_report(result, semantic, scenario),
                                   "scamlens-diagnosis.txt", "text/plain; charset=utf-8", width="stretch")

with verify_tab:
    st.subheader("用相同規則，重新檢查範例")
    st.write("用來確認功能是否符合設計，包含明顯風險、正常通知、限時活動與防詐提醒。")
    st.info("以下是開發者自編的教學案例，與規則共同設計。符合預期不代表真實詐騙辨識準確率。此頁只執行本機規則，沒有呼叫 LLM。")
    if st.button("執行 12 則範例驗證", type="primary", key="run_verification"):
        st.session_state["verification"] = verify_examples()
    if rows := st.session_state.get("verification"):
        passed = sum(row["檢查結果"] == "符合預期" for row in rows)
        if passed == len(rows):
            st.success(f"{passed} / {len(rows)} 則符合預期")
        else:
            st.warning(f"{passed} / {len(rows)} 則符合預期，請檢查差異")
        st.dataframe(rows, hide_index=True, width="stretch")
        case_name = st.selectbox("查看案例文字與設定依據", [case["name"] for case in VERIFICATION_CASES], key="verification_case")
        case = next(case for case in VERIFICATION_CASES if case["name"] == case_name)
        st.text(case["text"])
        st.caption(f"開發者預期：{case['expected_score']}/100、{case['expected']}風險。情境：{case['scenario']}。")
    st.markdown("**尚未驗證的效果**")
    st.write("真實 LLM 分析品質、真實訊息資料集的召回率與誤判率，以及使用者是否更能查證，仍需要另外研究。")

with design_tab:
    st.subheader("AI 工具的設計與範圍")
    st.write("目標使用者是面對票券、遊戲交易、打工與網購訊息的高中生，並讓家長與老師容易一起查證。")
    st.markdown("**處理流程**")
    st.code("文字＋情境＋檢查表\n    ↓\n正規化與連結擷取\n    ↓\n規則引擎：固定點數、每類一次\n    ↓\nLLM 或 Mock：心理戰術、原文、類型與簡短理由\n    ↓\n風險診斷卡、官方查證、求助文字", language="text")
    st.markdown("**分數與 AI 分工**")
    st.write("最終分數 = min(100, 規則點數加總)。LLM 負責解釋，不修改總分；沒有 key 或輸出失敗時改用 Mock，頁面會標明實際分析來源。")
    st.dataframe([{"規則": label, "分數": score} for label, score in RULES.values()], hide_index=True, width="stretch")
    with st.expander("四大心理戰術與分析指令"):
        for label, description in TACTICS.values():
            st.write(f"**{label}**：{description}")
        st.code(SYSTEM_PROMPT, language="text")
    st.markdown("**已完成的展示流程**")
    st.write("文字輸入、七種情境、檢查表、規則明細、話術片段標示、Mock／選配 LLM、求助與摘要下載、範例驗證。")
    st.markdown("**後續規劃**")
    st.write("截圖 OCR、LINE Bot、165 資料串接、去識別化，以及以獨立真實資料集評估辨識效果。")
    st.caption("使用 Python 與 Streamlit，沒有自行訓練模型。API 模式需環境變數 OPENAI_API_KEY；沒有 key 仍可完整展示 Mock 流程。")

st.divider()
st.caption(f"ScamLens v{VERSION}｜供查證參考，低風險也不保證安全。輸入變更後請重新分析。")
