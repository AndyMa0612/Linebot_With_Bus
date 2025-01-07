

### 公車查詢 LINE Bot

---

### 環境安裝套件

#### Web 框架  
```bash
pip install flask
```

#### LINE Bot SDK  
```bash
pip install line-bot-sdk
```

#### HTTP 請求  
```bash
pip install requests
```

#### 環境變數管理  
```bash
pip install python-dotenv
```

---

1. 先創建 LINE OA 一個帳號。  
2. 打開 API，進到 LINE Developers 找自己的 **ACCESS_TOKEN** 和 **SECRET**。  
3. 登入 TDX 運輸資料流通服務，查詢自己要的路線 API。  
4. 創建一個 `.env` 檔，將以下資訊打進去：  
   ```env
   LINE_CHANNEL_ACCESS_TOKEN=你的 LINE 頻道存取權杖  
   LINE_CHANNEL_SECRET=你的 LINE 頻道密鑰  
   TDX_APP_ID=你的 TDX 應用程式 ID  
   TDX_APP_KEY=你的 TDX 應用程式金鑰  
   ```  
5. 連接 `ngrok`：  
   ```bash
   ngrok http 5000
   ```  
6. 將 **Webhook URL** 貼上並加上 `/callback`。  
7. 執行 `app.py`，就可以使用 LINE Bot。  