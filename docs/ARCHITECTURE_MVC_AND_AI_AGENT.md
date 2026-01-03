# 🏗️ ארכיטקטורה: MVC + סוכן AI חכם

## 📋 תוכן עניינים

1. [סקירת הארכיטקטורה הנוכחית](#סקירת-הארכיטקטורה-הנוכחית)
2. [מבנה MVC מומלץ](#מבנה-mvc-מומלץ)
3. [שילוב עם Loveable (VIEW)](#שילוב-עם-loveable-view)
4. [סוכן AI חכם - ארכיטקטורה](#סוכן-ai-חכם---ארכיטקטורה)
5. [מודולריות - Addon לכל פלטפורמה](#מודולריות---addon-לכל-פלטפורמה)
6. [תכנית יישום](#תכנית-יישום)

---

## 🔍 סקירת הארכיטקטורה הנוכחית

### מבנה נוכחי (לפני MVC)

```
ZimmerBot_Main_Eldad/
├── src/
│   ├── api_server.py      # FastAPI - Controller + Routes
│   ├── main.py            # Calendar/Sheets Logic
│   ├── db.py              # Database - Model Layer
│   ├── pricing.py         # Pricing Logic
│   ├── hold.py           # Hold Manager
│   ├── payment.py        # Payment Manager
│   └── email_service.py  # Email Service
├── tools/
│   └── features_picker.html  # Frontend (VIEW) - לא מופרד
├── database/
│   └── schema.sql        # Database Schema
└── docs/
```

**בעיות:**
- ❌ אין הפרדה ברורה בין Model, View, Controller
- ❌ ה-View (HTML) מעורב עם Logic
- ❌ אין שכבת AI Agent נפרדת
- ❌ לא מודולרי - קשה להטמיע באתרים אחרים

---

## 🎯 מבנה MVC מומלץ

### ארכיטקטורה מוצעת

```
ZimmerBot/
├── backend/                    # Backend API (FastAPI)
│   ├── models/                # MODEL - Data Layer
│   │   ├── cabin.py           # Cabin Model
│   │   ├── booking.py         # Booking Model
│   │   ├── customer.py        # Customer Model
│   │   ├── transaction.py    # Transaction Model
│   │   └── pricing_rule.py    # Pricing Rule Model
│   │
│   ├── controllers/           # CONTROLLER - Business Logic
│   │   ├── booking_controller.py
│   │   ├── availability_controller.py
│   │   ├── pricing_controller.py
│   │   ├── payment_controller.py
│   │   └── hold_controller.py
│   │
│   ├── services/             # Services Layer
│   │   ├── calendar_service.py
│   │   ├── email_service.py
│   │   ├── payment_service.py
│   │   └── notification_service.py
│   │
│   ├── ai_agent/              # 🧠 AI Agent Layer (חדש!)
│   │   ├── agent_core.py      # Core AI Agent
│   │   ├── intent_classifier.py  # זיהוי כוונות
│   │   ├── context_manager.py    # ניהול הקשר
│   │   ├── response_generator.py # יצירת תגובות
│   │   ├── knowledge_base.py      # בסיס ידע
│   │   └── conversation_flow.py  # זרימת שיחה
│   │
│   ├── api/                   # API Routes
│   │   ├── routes/
│   │   │   ├── booking_routes.py
│   │   │   ├── availability_routes.py
│   │   │   ├── chat_routes.py      # AI Chat API
│   │   │   └── admin_routes.py
│   │   └── main.py           # FastAPI App
│   │
│   └── database/              # Database Layer
│       ├── connection.py
│       ├── repositories/      # Repository Pattern
│       │   ├── cabin_repository.py
│       │   ├── booking_repository.py
│       │   └── customer_repository.py
│       └── migrations/
│
├── frontend/                  # VIEW - Loveable/React/Vue
│   ├── web/                   # Web Widget
│   │   ├── components/
│   │   │   ├── ChatWidget.tsx
│   │   │   ├── BookingForm.tsx
│   │   │   ├── AvailabilityCalendar.tsx
│   │   │   └── PaymentModal.tsx
│   │   ├── hooks/
│   │   │   └── useChat.ts
│   │   └── index.ts          # Entry point
│   │
│   ├── facebook/             # Facebook Messenger Bot
│   │   └── messenger_bot.ts
│   │
│   ├── instagram/             # Instagram Bot
│   │   └── instagram_bot.ts
│   │
│   └── whatsapp/              # WhatsApp Business API
│       └── whatsapp_bot.ts
│
├── shared/                    # Shared Code
│   ├── types/                 # TypeScript Types
│   ├── constants/             # Constants
│   └── utils/                 # Utilities
│
└── plugins/                   # 🎯 Addon/Plugin System
    ├── wordpress/
    │   └── zimmerbot-plugin.php
    ├── shopify/
    │   └── zimmerbot-app/
    └── wix/
        └── zimmerbot-widget/
```

---

## 🎨 שילוב עם Loveable (VIEW)

### איפה נכנס ה-VIEW?

**Loveable = VIEW Layer בלבד**

```
┌─────────────────────────────────────────────────┐
│              VIEW (Loveable)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Web     │  │ Facebook │  │ Instagram│      │
│  │  Widget  │  │ Messenger│  │   Bot    │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
└───────┼─────────────┼─────────────┼────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   API Gateway (FastAPI)   │
        │      CONTROLLER Layer      │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   AI Agent + Services      │
        │    Business Logic          │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   Database (PostgreSQL)   │
        │      MODEL Layer           │
        └───────────────────────────┘
```

### זרימת נתונים

```typescript
// VIEW (Loveable) - רק UI, אין Logic
// frontend/web/components/ChatWidget.tsx

import { useChat } from '../hooks/useChat';

export function ChatWidget() {
  const { messages, sendMessage, isLoading } = useChat();
  
  return (
    <div className="chat-widget">
      {messages.map(msg => (
        <Message key={msg.id} message={msg} />
      ))}
      <Input 
        onSend={sendMessage} 
        disabled={isLoading}
      />
    </div>
  );
}

// Hook - תקשורת עם API
// frontend/web/hooks/useChat.ts

export function useChat() {
  const [messages, setMessages] = useState([]);
  
  const sendMessage = async (text: string) => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message: text })
    });
    const data = await response.json();
    setMessages(prev => [...prev, data]);
  };
  
  return { messages, sendMessage, isLoading };
}
```

```python
# CONTROLLER (FastAPI) - Business Logic
# backend/api/routes/chat_routes.py

from backend.ai_agent.agent_core import AIAgent

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # AI Agent מטפל בהודעה
    agent = AIAgent()
    response = await agent.process_message(
        message=request.message,
        session_id=request.session_id,
        context=request.context
    )
    
    return ChatResponse(
        message=response.text,
        intent=response.intent,
        actions=response.actions
    )
```

---

## 🧠 סוכן AI חכם - ארכיטקטורה

### מבנה הסוכן החכם

```python
# backend/ai_agent/agent_core.py

class AIAgent:
    """
    סוכן AI חכם שמטפל בכל השלבים:
    1. לפני ההזמנה - חיפוש, שאלות, המלצות
    2. ההזמנה - תהליך הזמנה מודרך
    3. הגעה - הוראות, פרטים
    4. שהות - תוספות, שאלות, בעיות
    5. עזיבה - משוב, תודה
    6. לקוח חוזר - הנחות, המלצות
    """
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.context_manager = ContextManager()
        self.response_generator = ResponseGenerator()
        self.knowledge_base = KnowledgeBase()
        self.conversation_flow = ConversationFlow()
    
    async def process_message(
        self, 
        message: str, 
        session_id: str,
        context: Optional[Dict] = None
    ) -> AgentResponse:
        """
        עיבוד הודעה - זיהוי כוונה, הקשר, ותגובה
        """
        # 1. זיהוי כוונה
        intent = await self.intent_classifier.classify(message)
        
        # 2. ניהול הקשר
        context = await self.context_manager.update(
            session_id=session_id,
            intent=intent,
            message=message,
            previous_context=context
        )
        
        # 3. קבלת מידע מבסיס הידע
        knowledge = await self.knowledge_base.get_relevant_info(
            intent=intent,
            context=context
        )
        
        # 4. יצירת תגובה
        response = await self.response_generator.generate(
            intent=intent,
            context=context,
            knowledge=knowledge,
            message=message
        )
        
        # 5. זרימת שיחה (state machine)
        next_actions = await self.conversation_flow.get_next_actions(
            current_state=context.state,
            intent=intent
        )
        
        return AgentResponse(
            text=response.text,
            intent=intent,
            actions=next_actions,
            context=context,
            metadata=response.metadata
        )
```

### זרימת שיחה - State Machine

```python
# backend/ai_agent/conversation_flow.py

class ConversationFlow:
    """
    ניהול זרימת שיחה - State Machine
    """
    
    STATES = {
        'GREETING': 'ברכה ראשונית',
        'SEARCHING': 'חיפוש צימר',
        'VIEWING_OPTIONS': 'צפייה באופציות',
        'BOOKING': 'תהליך הזמנה',
        'PAYMENT': 'תשלום',
        'CONFIRMED': 'הזמנה מאושרת',
        'PRE_ARRIVAL': 'לפני הגעה',
        'DURING_STAY': 'במהלך שהות',
        'POST_STAY': 'אחרי עזיבה',
        'RETURNING_CUSTOMER': 'לקוח חוזר'
    }
    
    TRANSITIONS = {
        'GREETING': ['SEARCHING', 'VIEWING_OPTIONS'],
        'SEARCHING': ['VIEWING_OPTIONS', 'BOOKING'],
        'VIEWING_OPTIONS': ['BOOKING', 'SEARCHING'],
        'BOOKING': ['PAYMENT', 'CONFIRMED'],
        'PAYMENT': ['CONFIRMED'],
        'CONFIRMED': ['PRE_ARRIVAL'],
        'PRE_ARRIVAL': ['DURING_STAY'],
        'DURING_STAY': ['POST_STAY'],
        'POST_STAY': ['RETURNING_CUSTOMER'],
        'RETURNING_CUSTOMER': ['SEARCHING', 'BOOKING']
    }
    
    async def get_next_actions(
        self, 
        current_state: str, 
        intent: str
    ) -> List[Action]:
        """
        קבלת פעולות הבאות לפי State ו-Intent
        """
        # Logic לזיהוי פעולות הבאות
        ...
```

### זיהוי כוונות (Intent Classification)

```python
# backend/ai_agent/intent_classifier.py

class IntentClassifier:
    """
    זיהוי כוונות - מה הלקוח רוצה?
    """
    
    INTENTS = {
        # לפני הזמנה
        'SEARCH_AVAILABILITY': 'חיפוש זמינות',
        'ASK_ABOUT_CABIN': 'שאלה על צימר',
        'COMPARE_CABINS': 'השוואה בין צימרים',
        'GET_PRICING': 'בקשת מחיר',
        'ASK_FEATURES': 'שאלה על תכונות',
        
        # תהליך הזמנה
        'START_BOOKING': 'התחלת הזמנה',
        'PROVIDE_DETAILS': 'מסירת פרטים',
        'ASK_BOOKING_STATUS': 'בדיקת סטטוס הזמנה',
        
        # במהלך שהות
        'REQUEST_SERVICE': 'בקשת שירות',
        'REPORT_ISSUE': 'דיווח על בעיה',
        'ASK_LOCAL_INFO': 'שאלה על האזור',
        'ORDER_ADDON': 'הזמנת תוספת',
        
        # אחרי עזיבה
        'LEAVE_REVIEW': 'השארת ביקורת',
        'ASK_RECOMMENDATION': 'בקשת המלצה',
        
        # כללי
        'GREETING': 'ברכה',
        'GOODBYE': 'פרידה',
        'THANK_YOU': 'תודה',
        'HELP': 'בקשת עזרה'
    }
    
    async def classify(self, message: str) -> str:
        """
        זיהוי כוונה מהודעה
        """
        # שימוש ב-LLM (OpenAI/Anthropic) או ML Model
        # או rule-based + embeddings
        ...
```

---

## 🎯 מודולריות - Addon לכל פלטפורמה

### ארכיטקטורת Plugin

```typescript
// shared/types/plugin.ts

export interface ZimmerBotPlugin {
  // זיהוי פלטפורמה
  platform: 'web' | 'facebook' | 'instagram' | 'whatsapp' | 'wordpress' | 'shopify';
  
  // אתחול
  init(config: PluginConfig): Promise<void>;
  
  // טיפול בהודעות
  handleMessage(message: IncomingMessage): Promise<OutgoingMessage>;
  
  // UI Components (רק ל-Web)
  getUIComponents?(): React.ComponentType[];
  
  // Webhooks (ל-Facebook/Instagram)
  handleWebhook?(payload: any): Promise<any>;
}

// frontend/web/index.ts
export class WebPlugin implements ZimmerBotPlugin {
  platform = 'web' as const;
  
  async init(config: PluginConfig) {
    // טעינת Widget
    this.renderWidget(config.containerId);
  }
  
  renderWidget(containerId: string) {
    const root = ReactDOM.createRoot(
      document.getElementById(containerId)!
    );
    root.render(<ChatWidget />);
  }
}

// frontend/facebook/messenger_bot.ts
export class FacebookPlugin implements ZimmerBotPlugin {
  platform = 'facebook' as const;
  
  async handleWebhook(payload: any) {
    // טיפול בהודעות מ-Facebook
    const message = payload.entry[0].messaging[0];
    const response = await this.sendToBackend(message);
    return this.sendToFacebook(response);
  }
}
```

### שימוש ב-Plugin

```html
<!-- WordPress -->
<div id="zimmerbot-widget"></div>
<script src="https://cdn.zimmerbot.com/widget.js"></script>
<script>
  ZimmerBot.init({
    containerId: 'zimmerbot-widget',
    apiUrl: 'https://api.zimmerbot.com',
    platform: 'wordpress'
  });
</script>
```

---

## 📊 תכנית יישום

### שלב 1: הפרדת MVC (2-3 ימים)

**משימות:**
1. יצירת מבנה תיקיות חדש
2. העברת קוד ל-Models, Controllers, Services
3. הפרדת View (HTML) ל-React/Vue component
4. יצירת API Gateway

**קבצים:**
```
backend/
├── models/
│   ├── cabin.py
│   ├── booking.py
│   └── customer.py
├── controllers/
│   ├── booking_controller.py
│   └── availability_controller.py
└── api/
    └── main.py
```

### שלב 2: AI Agent Core (5-7 ימים)

**משימות:**
1. יצירת `AIAgent` class
2. יצירת `IntentClassifier`
3. יצירת `ContextManager`
4. יצירת `ResponseGenerator`
5. יצירת `ConversationFlow`

**קבצים:**
```
backend/ai_agent/
├── agent_core.py
├── intent_classifier.py
├── context_manager.py
├── response_generator.py
└── conversation_flow.py
```

### שלב 3: View Layer (Loveable) (3-5 ימים)

**משימות:**
1. יצירת React Components ב-Loveable
2. יצירת Chat Widget
3. יצירת Booking Form
4. יצירת Availability Calendar
5. אינטגרציה עם Backend API

**קבצים:**
```
frontend/web/
├── components/
│   ├── ChatWidget.tsx
│   ├── BookingForm.tsx
│   └── AvailabilityCalendar.tsx
└── hooks/
    └── useChat.ts
```

### שלב 4: Plugin System (4-6 ימים)

**משימות:**
1. יצירת Plugin Interface
2. יצירת Web Plugin
3. יצירת Facebook Plugin
4. יצירת WordPress Plugin
5. יצירת Shopify App

**קבצים:**
```
plugins/
├── web/
│   └── index.ts
├── facebook/
│   └── messenger_bot.ts
├── wordpress/
│   └── zimmerbot-plugin.php
└── shopify/
    └── zimmerbot-app/
```

---

## 🔄 זרימת עבודה מלאה

### דוגמה: לקוח מחפש צימר

```
1. VIEW (Loveable)
   └─> משתמש כותב: "אני מחפש צימר לסופ"ש"
   
2. API Gateway (FastAPI)
   └─> POST /api/chat
       {
         "message": "אני מחפש צימר לסופ"ש",
         "session_id": "abc123"
       }
   
3. CONTROLLER
   └─> ChatController.handle_message()
   
4. AI Agent
   ├─> IntentClassifier: "SEARCH_AVAILABILITY"
   ├─> ContextManager: State = "SEARCHING"
   ├─> KnowledgeBase: קבלת צימרים זמינים
   └─> ResponseGenerator: "מצאתי 3 צימרים זמינים..."
   
5. Services
   └─> AvailabilityService.check_availability()
   
6. Models
   └─> CabinRepository.get_available_cabins()
   
7. Database
   └─> SELECT * FROM cabins WHERE ...
   
8. Response Chain (הפוך)
   └─> VIEW מציג: "מצאתי 3 צימרים זמינים..."
```

---

## ✅ Definition of Done

### שלב 1: MVC Separation
- [ ] כל הקוד מאורגן ב-Models, Controllers, Views
- [ ] אין Logic ב-View
- [ ] API Gateway עובד
- [ ] בדיקות עוברות

### שלב 2: AI Agent
- [ ] AI Agent מזהה כוונות
- [ ] ניהול הקשר עובד
- [ ] תגובות חכמות
- [ ] זרימת שיחה עובדת

### שלב 3: View Layer
- [ ] React Components ב-Loveable
- [ ] Chat Widget עובד
- [ ] אינטגרציה עם Backend
- [ ] UI/UX מעולה

### שלב 4: Plugin System
- [ ] Web Plugin עובד
- [ ] Facebook Plugin עובד
- [ ] WordPress Plugin עובד
- [ ] תיעוד מלא

---

## 📚 משאבים

- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [React Component Patterns](https://reactpatterns.com/)
- [Plugin Architecture](https://martinfowler.com/articles/pluginArchitecture.html)
- [AI Agent Design Patterns](https://www.patterns.dev/posts/ai-agent-patterns/)

