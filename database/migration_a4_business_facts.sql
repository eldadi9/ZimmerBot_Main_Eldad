-- ============================================
-- שלב A4: טבלת Business Facts
-- ============================================
-- יצירת טבלה לשמירת עובדות עסקיות (Business Facts)
-- Agent עונה מתוך facts אלה בלי להמציא מידע

-- טבלה: business_facts (עובדות עסקיות)
CREATE TABLE IF NOT EXISTS business_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fact_key VARCHAR(100) NOT NULL UNIQUE, -- מפתח ייחודי (לדוגמה: "check_in_time", "check_out_time")
    fact_value TEXT NOT NULL, -- הערך (לדוגמה: "15:00", "11:00")
    category VARCHAR(50), -- קטגוריה (לדוגמה: "hours", "policies", "amenities")
    description TEXT, -- תיאור (אופציונלי)
    is_active BOOLEAN NOT NULL DEFAULT TRUE, -- האם העובדה פעילה
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- יצירת index לחיפוש מהיר
CREATE INDEX IF NOT EXISTS idx_business_facts_key ON business_facts(fact_key);
CREATE INDEX IF NOT EXISTS idx_business_facts_category ON business_facts(category);
CREATE INDEX IF NOT EXISTS idx_business_facts_active ON business_facts(is_active);

-- הכנסת עובדות בסיסיות
INSERT INTO business_facts (fact_key, fact_value, category, description) VALUES
    ('check_in_time', '15:00', 'hours', 'שעת צ''ק אין'),
    ('check_out_time', '11:00', 'hours', 'שעת צ''ק אאוט'),
    ('cancellation_policy', '24 שעות מראש', 'policies', 'מדיניות ביטול'),
    ('parking', 'כן, חניה פרטית', 'amenities', 'חניה'),
    ('pets_allowed', 'לא מותרות', 'policies', 'חיות מחמד'),
    ('kosher', 'לא', 'policies', 'כשרות'),
    ('wifi', 'כן, חינם', 'amenities', 'WiFi')
ON CONFLICT (fact_key) DO NOTHING;

-- עדכון טבלת FAQ - הוספת שדה לסמן תשובות מוצעות
ALTER TABLE faq ADD COLUMN IF NOT EXISTS suggested_answer TEXT; -- תשובה שהסוכן הציע (לפני אישור)
ALTER TABLE faq ADD COLUMN IF NOT EXISTS suggested_at TIMESTAMP; -- מתי הוצעה התשובה

-- יצירת index לחיפוש FAQ מאושר בלבד
CREATE INDEX IF NOT EXISTS idx_faq_approved_active ON faq(approved) WHERE approved = TRUE;

COMMENT ON TABLE business_facts IS 'עובדות עסקיות - Agent עונה מתוך facts אלה בלבד';
COMMENT ON COLUMN business_facts.fact_key IS 'מפתח ייחודי לעובדה (לדוגמה: check_in_time)';
COMMENT ON COLUMN business_facts.fact_value IS 'הערך של העובדה';
COMMENT ON COLUMN faq.approved IS 'רק FAQ מאושר משמש את ה-Agent';

