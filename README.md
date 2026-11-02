# ScamLens：Streamlit Community Cloud 部署版

此資料夾內容可直接上傳至獨立的 GitHub repository。將 app.py 放在 repository 根目錄，入口填 app.py。不要把 ZIP 檔本身上傳，也不要多包一層 ScamLens_Cloud 資料夾。

## 部署設定

- Repository：你的帳號／scamlens-demo（名稱可自行決定）
- Branch：repository 實際分支，例如 main
- Main file path：app.py
- Python：3.12
- Secrets：第一次部署Mock版時留白

先在GitHub建立repository，再把本資料夾「裡面的檔案與.streamlit資料夾」上傳。若選Public，程式碼也會公開。接著在 https://share.streamlit.io/ 建立應用程式，選repository、分支與app.py後部署。

## 預期結構

```
app.py
analysis.py
engine.py
demo.py
samples.py
styles.css
requirements.txt
.gitignore
README.md
.streamlit/
    config.toml
```

## 上線後檢查

1. 網頁使用Mock模式，沒有API key也能執行。
2. 正常學校通知：0分、低風險。
3. 演唱會票券案例：95分、高風險。
4. 範例驗證頁：12/12符合開發者預期，不代表真實準確率。
5. 使用無痕視窗及手機行動網路開啟部署網址，確認學生可以存取。

若學生看到登入／存取限制，可到App settings的Sharing設定確認誰能查看此應用程式。公開程式碼與公開應用程式是不同設定，請依課堂需求選擇。

## 雲端資料處理

部署後，學生輸入的訊息會送到網站伺服器執行Python程式，並非完全在學生瀏覽器內運算。Mock不會呼叫外部AI服務。本版沒有建立訊息資料庫。請先使用內建範例或移除真實個資的文字。

本次部署包沒有API key，也沒有開啟真實LLM功能的付費呼叫。之後如需LLM，應在平台Secrets設定並實測，再評估課堂使用的存取與用量限制。不要將key上傳至GitHub。

## 常見錯誤

- 找不到app.py：檢查入口與repository檔案層級是否一致。
- 找不到styles.css或demo.py：確認必要檔案都上傳，並保留檔名大小寫。
- 依賴安裝失敗：確認根目錄有requirements.txt，Python選3.12。
- 網頁可開但外觀不同：確認.streamlit/config.toml位於repository根目錄下的.streamlit資料夾。

官方部署文件：https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
