from flask import Flask, request, abort
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    TemplateMessage,
    ConfirmTemplate,
    MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent
)
from linebot.exceptions import InvalidSignatureError
import requests
import json
import os
import re
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# 檢查環境變數
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
app_id = os.getenv('TDX_APP_ID')
app_key = os.getenv('TDX_APP_KEY')

# 確保環境變數存在
if not all([channel_access_token, channel_secret, app_id, app_key]):
    raise ValueError(
        "環境變數未設定完整。請確保以下環境變數都已設定：\n"
        "LINE_CHANNEL_ACCESS_TOKEN\n"
        "LINE_CHANNEL_SECRET\n"
        "TDX_APP_ID\n"
        "TDX_APP_KEY"
    )

# 設定 LINE Bot API
configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# TDX 認證 URL
auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"


class Auth:
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key

    def get_auth_header(self):
        return {
            'content-type': 'application/x-www-form-urlencoded',
            'grant_type': 'client_credentials',
            'client_id': self.app_id,
            'client_secret': self.app_key
        }


class BusData:
    def __init__(self, app_id, app_key, auth_response):
        self.app_id = app_id
        self.app_key = app_key
        self.auth_response = auth_response

    def get_data_header(self):
        auth_JSON = json.loads(self.auth_response.text)
        access_token = auth_JSON.get('access_token')
        return {
            'authorization': 'Bearer ' + access_token,
            'Accept-Encoding': 'gzip'
        }

    def get_route_info(self, route_number):
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Route/City/Taichung/{route_number}?$format=JSON"
        try:
            response = requests.get(url, headers=self.get_data_header())
            if response.status_code == 200:
                routes = response.json()
                if routes:
                    return {
                        'start': routes[0].get('DepartureStopNameZh', '未知起點'),
                        'end': routes[0].get('DestinationStopNameZh', '未知終點')
                    }
            return None
        except Exception as e:
            print(f"獲取路線資訊時發生錯誤: {str(e)}")
            return None

    def get_bus_info(self, route_number, direction):
        route_info = self.get_route_info(route_number)
        if not route_info:
            return "無法獲取路線資訊"

        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/Taichung?$filter=RouteName/Zh_tw eq '{route_number}'&$format=JSON"

        try:
            response = requests.get(url, headers=self.get_data_header())
            if response.status_code == 200:
                return self.process_bus_data(response.json(), route_info, direction)
            return "無法獲取資料"
        except Exception as e:
            print(f"獲取公車資訊時發生錯誤: {str(e)}")
            return f"錯誤: {str(e)}"

    def process_bus_data(self, data, route_info, direction):
        if not data:
            return "查無此路線資料"

        stops_info = []
        for stop in data:
            if (stop.get('EstimateTime') is not None and
                    stop.get('Direction') == direction):
                stop_name = stop.get('StopName', {}).get('Zh_tw', '未知站名')
                estimate_time = stop.get('EstimateTime', 0)

                # 將秒數轉換為分鐘，並判斷是否小於 1.5 分鐘
                if estimate_time < 90:  # 90秒 = 1.5分鐘
                    arrival_info = "即將到站"
                else:
                    estimate_minutes = estimate_time // 60
                    arrival_info = f"{estimate_minutes}分鐘"

                stops_info.append(f"站名: {stop_name}\n預估到站時間: {arrival_info}\n")

        direction_name = route_info['end'] if direction == 0 else route_info['start']

        if stops_info:
            return f"往{direction_name}方向的公車：\n\n" + "\n".join(stops_info)
        else:
            return f"目前往{direction_name}方向無公車即將到站"


@app.route('/')
def home():
    return 'LINE Bot is running!'


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(FollowEvent)
def handle_follow(event):
    print("處理新用戶關注事件")
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        message = TextMessage(text="歡迎使用公車查詢機器人！\n請直接輸入公車號碼來查詢到站時間。\n範例：51")
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[message]
            )
        )


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        user_input = event.message.text.strip()
        print(f"收到使用者輸入: {user_input}")

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            if user_input == "說明":
                print("處理說明請求")
                message = TextMessage(text="請輸入公車號碼來查詢到站時間")
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[message]
                    )
                )
                return

            direction_match = re.match(r'往(.*?)方向(\d+)號公車', user_input)
            if direction_match:
                print("處理方向選擇")
                direction_name = direction_match.group(1)
                route_number = direction_match.group(2)
                print(f"方向: {direction_name}, 路線: {route_number}")

                auth = Auth(app_id, app_key)
                auth_response = requests.post(auth_url, auth.get_auth_header())
                bus_data = BusData(app_id, app_key, auth_response)
                route_info = bus_data.get_route_info(route_number)

                if route_info:
                    direction = 0 if direction_name == route_info['end'] else 1
                    print(f"路線資訊: {route_info}, 方向值: {direction}")
                    result = bus_data.get_bus_info(route_number, direction)
                    result += "\n\n請重新輸入公車號碼以查詢最新資訊"
                    message = TextMessage(text=result)
                else:
                    print("無法獲取路線資訊")
                    message = TextMessage(text="無法獲取路線資訊\n請重新輸入公車號碼")

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[message]
                    )
                )
                return

            if user_input.isdigit():
                print(f"處理公車號碼查詢: {user_input}")
                auth = Auth(app_id, app_key)
                auth_response = requests.post(auth_url, auth.get_auth_header())
                bus_data = BusData(app_id, app_key, auth_response)
                route_info = bus_data.get_route_info(user_input)

                if route_info:
                    print(f"獲取到路線資訊: {route_info}")
                    template_message = TemplateMessage(
                        alt_text='請選擇方向',
                        template=ConfirmTemplate(
                            text=f'請選擇{user_input}號公車方向',
                            actions=[
                                MessageAction(
                                    label=f'往{route_info["end"]}',
                                    text=f'往{route_info["end"]}方向{user_input}號公車'
                                ),
                                MessageAction(
                                    label=f'往{route_info["start"]}',
                                    text=f'往{route_info["start"]}方向{user_input}號公車'
                                )
                            ]
                        )
                    )
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[template_message]
                        )
                    )
                else:
                    print("無法獲取路線資訊")
                    message = TextMessage(text="無法獲取路線資訊\n請重新輸入公車號碼")
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[message]
                        )
                    )
            else:
                print("輸入格式錯誤")
                message = TextMessage(text="請輸入正確的公車號碼")
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[message]
                    )
                )

    except Exception as e:
        print(f"發生錯誤: {str(e)}")
        message = TextMessage(text="發生錯誤，請稍後再試\n請重新輸入公車號碼")
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[message]
                )
            )


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)