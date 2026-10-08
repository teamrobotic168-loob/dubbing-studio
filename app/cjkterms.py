"""Built-in technical terms for Chinese and Korean sources → the English form that stays in the Khmer text.

A Chinese or Korean video says "服务器" / "서버" – the Khmer dub should say "server" (Latin script, read by
an English voice), exactly like an English video does.  The English glossary cannot catch that, because the
source text does not contain the English word.  Korean also writes brand and product names phonetically in
Hangul ("유튜브", "파이썬"), Chinese writes them with characters ("谷歌", "微软").

Format of the tables:   source | variant | variant = English output
Only unambiguous NOUNS and names are listed: a wrong substitution is worse than a missing one (a missing
term is simply translated into Khmer).  Verbs are left out on purpose – a placeholder in the place of a verb
("部署", "디버깅", "암호화") makes Google Translate lose the grammar of the whole sentence (measured:
"... ដាក់លេខកូដរបស់អ្នកទៅ debugging ហើយបន្ទាប់មកទៅ server" instead of a correct sentence).
Users can add more with   源词 => English   lines in the Technical terms page.
"""
from __future__ import annotations

from typing import Dict

ZH_TERMS_TEXT = """
# ── AI & Data ──
人工智能 | 人工智慧 = AI
机器学习 | 機器學習 = machine learning
深度学习 | 深度學習 = deep learning
强化学习 | 強化學習 = reinforcement learning
神经网络 | 神經網絡 | 神經網路 = neural network
大语言模型 | 大語言模型 = large language model
大模型 = LLM
提示词 | 提示詞 = prompt
提示工程 = prompt engineering
数据集 | 數據集 | 資料集 = dataset
训练数据 | 训练集 | 訓練數據 | 訓練資料 = training data
算法 | 演算法 = algorithm
聊天机器人 | 聊天機器人 = chatbot
计算机视觉 | 計算機視覺 | 電腦視覺 = computer vision
自然语言处理 | 自然語言處理 = natural language processing
数据科学家 | 數據科學家 | 資料科學家 = data scientist
数据科学 | 數據科學 | 資料科學 = data science
数据分析师 | 數據分析師 | 資料分析師 = data analyst
数据分析 | 數據分析 | 資料分析 = analytics
大数据 | 大數據 = big data
向量数据库 | 向量資料庫 | 向量數據庫 = vector database
语音识别 | 語音識別 = speech-to-text
语音合成 | 語音合成 = text-to-speech
检索增强生成 | 檢索增強生成 = RAG

# ── Software & Web ──
应用程序接口 | 應用程式介面 | 应用程序编程接口 = API
前端 = front-end
后端 | 後端 = back-end
全栈 | 全端 = full-stack
框架 = framework
插件 | 外掛 = plugin
仪表盘 | 仪表板 | 儀表板 | 儀表盤 = dashboard
服务器 | 伺服器 | 服務器 = server
数据库 | 數據庫 | 資料庫 = database
微服务 | 微服務 = microservices
命令行 | 命令列 = command line
脚本 | 腳本 = script
编译器 | 編譯器 = compiler
开源 | 開源 = open source
源代码 | 源代碼 | 源碼 | 原始碼 = source code
版本控制 = version control
云计算 | 雲計算 | 雲端運算 = cloud computing
云端 | 雲端 = cloud
无服务器 | 無伺服器 | 無服務器 = serverless
负载均衡 | 負載均衡 = load balancer
带宽 | 頻寬 | 帶寬 = bandwidth
浏览器 | 瀏覽器 = browser
缓存 | 緩存 | 快取 = cache
用户名 | 使用者名稱 | 用戶名 = username
域名 | 網域名稱 = domain name
低代码 | 低代碼 = low-code
无代码 | 無代碼 = no-code
软件即服务 | 軟體即服務 = SaaS

# ── Security ──
网络安全 | 網絡安全 | 網路安全 = cybersecurity
身份验证 | 身份驗證 = authentication
双因素认证 | 雙因素認證 | 两步验证 | 兩步驟驗證 = two-factor authentication
密码 | 密碼 = password
防火墙 | 防火牆 = firewall
网络钓鱼 | 網路釣魚 | 網絡釣魚 = phishing
恶意软件 | 惡意軟體 | 惡意軟件 = malware
勒索软件 | 勒索軟體 | 勒索軟件 = ransomware
黑客 | 駭客 = hacker
虚拟专用网络 | 虛擬私人網路 = VPN

# ── Hardware ──
软件 | 軟體 | 軟件 = software
硬件 | 硬體 = hardware
固件 | 韌體 = firmware
中央处理器 | 中央處理器 = CPU
图形处理器 | 圖形處理器 = GPU
显卡 | 顯卡 | 顯示卡 = GPU
内存 | 記憶體 = RAM
固态硬盘 | 固態硬碟 | 固態硬盤 = SSD
机械硬盘 | 機械硬碟 = HDD
蓝牙 | 藍牙 = Bluetooth
物联网 | 物聯網 = IoT
树莓派 | 樹莓派 = Raspberry Pi

# ── Business & Marketing ──
搜索引擎优化 | 搜尋引擎優化 | 搜索引擎優化 | 搜尋引擎最佳化 = SEO
用户体验 | 用戶體驗 | 使用者體驗 = UX
用户界面 | 用戶界面 | 使用者介面 = UI
创业公司 | 初创公司 | 新创公司 | 創業公司 | 初創公司 | 新創公司 = startup
转化率 | 轉化率 | 轉換率 = conversion rate
落地页 | 着陆页 | 落地頁 | 著陸頁 = landing page
产品经理 | 產品經理 = product manager
项目管理 | 項目管理 | 專案管理 = project management
敏捷开发 | 敏捷開發 = Agile
工作流 = workflow
电子商务 | 電子商務 | 电商 | 電商 = e-commerce
网红 | 網紅 = influencer
风险投资 | 風險投資 | 創投 = venture capital
首席执行官 | 首席執行官 | 執行長 = CEO
首席技术官 | 首席技術官 | 技術長 = CTO
首席财务官 | 首席財務官 | 財務長 = CFO
点击率 | 點擊率 = CTR
投资回报率 | 投資報酬率 | 投資回報率 = ROI
关键绩效指标 | 關鍵績效指標 = KPI

# ── Finance & Crypto ──
区块链 | 區塊鏈 = blockchain
加密货币 | 加密貨幣 | 虚拟货币 | 虛擬貨幣 = cryptocurrency
比特币 | 比特幣 = Bitcoin
以太坊 = Ethereum
金融科技 = fintech
去中心化金融 = DeFi
非同质化代币 | 非同質化代幣 = NFT

# ── Social & Media ──
油管 = YouTube
谷歌浏览器 | 谷歌瀏覽器 = Chrome
谷歌 = Google
微软 | 微軟 = Microsoft
脸书 | 臉書 = Facebook
推特 = Twitter
领英 | 領英 = LinkedIn
微信 = WeChat
网飞 | 奈飞 | 網飛 = Netflix
订阅者 | 訂閱者 | 订阅用户 = subscribers
订阅 | 訂閱 = subscribe
缩略图 | 縮圖 | 縮略圖 = thumbnail
播放列表 | 播放清單 = playlist
播客 = podcast
直播 = livestream
博客 = blog
亚马逊 | 亞馬遜 = Amazon
特斯拉 = Tesla
英伟达 | 輝達 | 英偉達 = NVIDIA
英特尔 | 英特爾 = Intel
华为 | 華為 = Huawei
腾讯 | 騰訊 = Tencent
阿里巴巴 = Alibaba
百度 = Baidu
淘宝 | 淘寶 = Taobao
支付宝 | 支付寶 = Alipay
字节跳动 | 字節跳動 = ByteDance
"""

KO_TERMS_TEXT = """
# ── AI & Data ──
인공 지능 = AI
머신 러닝 | 기계 학습 = machine learning
딥 러닝 | 심층 학습 = deep learning
강화 학습 = reinforcement learning
신경망 | 인공 신경망 | 뉴럴 네트워크 = neural network
거대 언어 모델 | 대규모 언어 모델 | 대형 언어 모델 = large language model
프롬프트 엔지니어링 = prompt engineering
프롬프트 = prompt
데이터 셋 | 데이터 세트 = dataset
학습 데이터 | 훈련 데이터 = training data
알고리즘 = algorithm
챗봇 = chatbot
컴퓨터 비전 = computer vision
자연어 처리 = natural language processing
데이터 과학자 | 데이터 사이언티스트 = data scientist
데이터 과학 | 데이터 사이언스 = data science
데이터 분석가 = data analyst
데이터 분석 = analytics
빅 데이터 = big data
벡터 데이터베이스 = vector database
음성 인식 = speech-to-text
음성 합성 = text-to-speech
검색 증강 생성 = RAG
챗 GPT | 챗 지피티 = ChatGPT
오픈 AI | 오픈 에이아이 = OpenAI
제미나이 = Gemini
클로드 = Claude
코파일럿 = Copilot
텐서플로 = TensorFlow
파이토치 = PyTorch
판다스 = pandas
넘파이 = NumPy
주피터 = Jupyter
허깅페이스 = Hugging Face
에이아이 = AI
엘엘엠 = LLM
지피티 = GPT

# ── Software & Web ──
에이피아이 = API
프론트 엔드 | 프런트 엔드 = front-end
백 엔드 = back-end
풀 스택 = full-stack
프레임워크 = framework
플러그인 = plugin
대시보드 = dashboard
서버 리스 = serverless
서버 = server
데이터베이스 = database
마이크로서비스 = microservices
명령 줄 | 커맨드 라인 = command line
터미널 = terminal
스크립트 = script
컴파일러 = compiler
오픈 소스 = open source
소스 코드 = source code
버전 관리 = version control
클라우드 = cloud
로드 밸런서 = load balancer
레이턴시 = latency
대역폭 = bandwidth
브라우저 = browser
쿠키 = cookie
캐시 = cache
로그인 = login
회원가입 = sign up
사용자 이름 | 유저 네임 = username
비밀번호 | 패스워드 = password
도메인 이름 | 도메인 = domain name
유아이 = UI
유엑스 = UX
파이썬 = Python
자바스크립트 = JavaScript
타입스크립트 = TypeScript
리액트 = React
앵귤러 = Angular
플라스크 = Flask
라라벨 = Laravel
워드프레스 = WordPress
도커 = Docker
쿠버네티스 = Kubernetes
깃 허브 | 깃 헙 = GitHub
깃랩 = GitLab
리눅스 = Linux
우분투 = Ubuntu
윈도우즈 | 윈도우 = Windows
안드로이드 = Android
아이폰 = iPhone
크롬 = Chrome
파이어폭스 = Firefox
엑셀 = Excel
파워포인트 = PowerPoint
노션 = Notion
슬랙 = Slack
피그마 = Figma
포토샵 = Photoshop
일러스트레이터 = Illustrator
캔바 = Canva
와이파이 = Wi-Fi
블루투스 = Bluetooth
유에스비 = USB
라즈베리 파이 = Raspberry Pi
아두이노 = Arduino

# ── Security ──
사이버 보안 = cybersecurity
이중 인증 | 2단계 인증 = two-factor authentication
방화벽 = firewall
피싱 = phishing
악성코드 = malware
랜섬웨어 = ransomware
해커 = hacker

# ── Hardware ──
소프트웨어 = software
하드웨어 = hardware
펌웨어 = firmware
사물 인터넷 = IoT
씨피유 = CPU
지피유 = GPU
에스에스디 = SSD

# ── Business & Marketing ──
검색 엔진 최적화 | 에스이오 = SEO
사용자 경험 = UX
사용자 인터페이스 | 유저 인터페이스 = UI
스타트업 = startup
전환율 = conversion rate
랜딩 페이지 = landing page
프로덕트 매니저 = product manager
프로젝트 관리 = project management
애자일 = Agile
스크럼 = Scrum
칸반 = Kanban
스프린트 = sprint
워크 플로우 | 워크 플로 = workflow
이커머스 | 전자 상거래 = e-commerce
인플루언서 = influencer
브랜딩 = branding
뉴스레터 = newsletter
벤처 캐피털 = venture capital

# ── Finance & Crypto ──
블록체인 = blockchain
암호화폐 | 가상화폐 = cryptocurrency
비트코인 = Bitcoin
이더리움 = Ethereum
핀테크 = fintech
디파이 = DeFi
엔에프티 = NFT

# ── Social & Media ──
유튜브 = YouTube
구글 = Google
페이스북 = Facebook
인스타그램 = Instagram
틱톡 = TikTok
텔레그램 = Telegram
트위터 = Twitter
링크드인 = LinkedIn
왓츠앱 = WhatsApp
위챗 = WeChat
넷플릭스 = Netflix
스포티파이 = Spotify
마이크로소프트 = Microsoft
애플 = Apple
아마존 = Amazon
테슬라 = Tesla
엔비디아 = NVIDIA
인텔 = Intel
삼성 = Samsung
네이버 = Naver
카카오톡 = KakaoTalk
구독자 = subscribers
구독 = subscribe
썸네일 = thumbnail
플레이리스트 = playlist
해시태그 = hashtag
브이로그 = vlog
팟캐스트 = podcast
"""


def _parse(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        left, _, right = line.rpartition("=")
        right = right.strip()
        for src in left.split("|"):
            src = src.strip()
            if src and right:
                out[src] = right
    return out


ZH_TERMS: Dict[str, str] = _parse(ZH_TERMS_TEXT)
KO_TERMS: Dict[str, str] = _parse(KO_TERMS_TEXT)


def builtin_terms(lang: str) -> Dict[str, str]:
    """Source word → English form, for a source language ('zh' | 'ko'); empty for English."""
    if lang == "zh":
        return ZH_TERMS
    if lang == "ko":
        return KO_TERMS
    return {}
