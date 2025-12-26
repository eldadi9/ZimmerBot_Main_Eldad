-- ============================================
-- שלב 1: מודל נתונים (Database Schema)
-- ============================================

-- טבלה: cabins (צימרים)
CREATE TABLE IF NOT EXISTS cabins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    area VARCHAR(50),
    max_adults INT,
    max_kids INT,
    features JSONB,
    base_price_night DECIMAL(10,2),
    weekend_price DECIMAL(10,2),
    images_urls TEXT[],
    calendar_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: customers (לקוחות) - חייבת להיות לפני bookings
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: bookings (הזמנות)
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabin_id UUID REFERENCES cabins(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    adults INT,
    kids INT,
    status VARCHAR(20) CHECK (status IN ('hold', 'confirmed', 'cancelled')),
    total_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_dates CHECK (check_out > check_in)
);

-- טבלה: pricing_rules (כללי תמחור)
CREATE TABLE IF NOT EXISTS pricing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabin_id UUID REFERENCES cabins(id) ON DELETE CASCADE,
    rule_type VARCHAR(50) NOT NULL, -- 'weekend', 'holiday', 'season', 'discount'
    start_date DATE,
    end_date DATE,
    multiplier DECIMAL(5,2) DEFAULT 1.0, -- מכפיל מחיר
    fixed_amount DECIMAL(10,2), -- סכום קבוע
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: transactions (תשלומים)
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID REFERENCES bookings(id) ON DELETE CASCADE,
    payment_id VARCHAR(255) UNIQUE, -- ID מספק הסליקה
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ILS',
    status VARCHAR(20) CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    payment_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: notifications (הודעות)
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID REFERENCES bookings(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    notification_type VARCHAR(50), -- 'confirmation', 'reminder', 'cancellation'
    channel VARCHAR(20) CHECK (channel IN ('email', 'sms', 'whatsapp', 'push')),
    status VARCHAR(20) CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- טבלה: audit_log (לוג פעולות)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values JSONB,
    new_values JSONB,
    user_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Indexes על שדות חיפוש
-- ============================================

-- Indexes לטבלת cabins
CREATE INDEX IF NOT EXISTS idx_cabins_area ON cabins(area);
CREATE INDEX IF NOT EXISTS idx_cabins_calendar_id ON cabins(calendar_id);
CREATE INDEX IF NOT EXISTS idx_cabins_created_at ON cabins(created_at);

-- Indexes לטבלת bookings
CREATE INDEX IF NOT EXISTS idx_bookings_cabin_id ON bookings(cabin_id);
CREATE INDEX IF NOT EXISTS idx_bookings_customer_id ON bookings(customer_id);
CREATE INDEX IF NOT EXISTS idx_bookings_check_in ON bookings(check_in);
CREATE INDEX IF NOT EXISTS idx_bookings_check_out ON bookings(check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_dates ON bookings(check_in, check_out);

-- Indexes לטבלת customers
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

-- Indexes לטבלת pricing_rules
CREATE INDEX IF NOT EXISTS idx_pricing_rules_cabin_id ON pricing_rules(cabin_id);
CREATE INDEX IF NOT EXISTS idx_pricing_rules_dates ON pricing_rules(start_date, end_date);

-- Indexes לטבלת transactions
CREATE INDEX IF NOT EXISTS idx_transactions_booking_id ON transactions(booking_id);
CREATE INDEX IF NOT EXISTS idx_transactions_payment_id ON transactions(payment_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);

-- Indexes לטבלת notifications
CREATE INDEX IF NOT EXISTS idx_notifications_booking_id ON notifications(booking_id);
CREATE INDEX IF NOT EXISTS idx_notifications_customer_id ON notifications(customer_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);

-- Indexes לטבלת audit_log
CREATE INDEX IF NOT EXISTS idx_audit_log_table_record ON audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

-- ============================================
-- Triggers לעדכון updated_at אוטומטית
-- ============================================

-- Function לעדכון updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers
CREATE TRIGGER update_cabins_updated_at BEFORE UPDATE ON cabins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bookings_updated_at BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

