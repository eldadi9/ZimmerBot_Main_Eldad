-- ============================================
-- שלב A1: טבלאות Agent Chat
-- ============================================
-- יצירת טבלאות לשיחות, הודעות, FAQ ו-escalations

-- טבלה: conversations (שיחות)
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('web', 'whatsapp', 'voice', 'sms')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'escalated')),
    metadata JSONB, -- מידע נוסף על השיחה (context, session data, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: messages (הודעות בשיחה)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB, -- מידע נוסף (intent, confidence, actions, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: faq (שאלות מאושרות)
CREATE TABLE IF NOT EXISTS faq (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    approved BOOLEAN NOT NULL DEFAULT FALSE, -- רק FAQ מאושר משמש את ה-Agent
    suggested_by UUID REFERENCES customers(id) ON DELETE SET NULL, -- מי הציע (אם רלוונטי)
    approved_by UUID, -- מי אישר (Host/Admin)
    approved_at TIMESTAMP,
    usage_count INT DEFAULT 0, -- כמה פעמים השתמשו ב-FAQ זה
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: escalations (דורש בעלים)
CREATE TABLE IF NOT EXISTS escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    reason TEXT NOT NULL, -- למה צריך escalation
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'resolved', 'closed')),
    assigned_to UUID, -- מי מטפל (Host/Admin)
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Indexes על שדות חיפוש
-- ============================================

-- Indexes לטבלת conversations
CREATE INDEX IF NOT EXISTS idx_conversations_customer_id ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(channel);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);

-- Indexes לטבלת messages
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Indexes לטבלת faq
CREATE INDEX IF NOT EXISTS idx_faq_approved ON faq(approved);
CREATE INDEX IF NOT EXISTS idx_faq_usage_count ON faq(usage_count);
CREATE INDEX IF NOT EXISTS idx_faq_created_at ON faq(created_at);

-- Indexes לטבלת escalations
CREATE INDEX IF NOT EXISTS idx_escalations_conversation_id ON escalations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_created_at ON escalations(created_at);

-- ============================================
-- Triggers לעדכון updated_at אוטומטית
-- ============================================

-- Trigger לטבלת conversations
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger לטבלת faq
CREATE TRIGGER update_faq_updated_at BEFORE UPDATE ON faq
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger לטבלת escalations
CREATE TRIGGER update_escalations_updated_at BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- הערות
-- ============================================
-- טבלאות אלה תומכות במערכת Agent Chat:
-- 1. conversations - כל שיחה עם לקוח
-- 2. messages - כל הודעה בשיחה (user/assistant/system)
-- 3. faq - שאלות מאושרות (רק approved=true משמש את ה-Agent)
-- 4. escalations - מקרים שדורשים התערבות אנושית

