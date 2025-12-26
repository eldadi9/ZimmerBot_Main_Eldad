BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS cabins (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  area TEXT,
  calendar_id TEXT,
  max_adults INT DEFAULT 0,
  max_kids INT DEFAULT 0,
  base_price_night NUMERIC(12,2) DEFAULT 0,
  weekend_price NUMERIC(12,2) DEFAULT 0,
  features JSONB DEFAULT '{}'::jsonb,
  images_urls TEXT[] DEFAULT ARRAY[]::TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customers (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bookings (
  id UUID PRIMARY KEY,
  cabin_id UUID NOT NULL,
  customer_id UUID NOT NULL,
  check_in TIMESTAMPTZ NOT NULL,
  check_out TIMESTAMPTZ NOT NULL,
  adults INT DEFAULT 0,
  kids INT DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'hold',
  total_price NUMERIC(12,2) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT check_dates CHECK (check_out > check_in),
  CONSTRAINT status CHECK (status IN ('hold','confirmed','cancelled'))
);

CREATE TABLE IF NOT EXISTS pricing_rules (
  id UUID PRIMARY KEY,
  cabin_id UUID NOT NULL,
  rule_type TEXT,
  value NUMERIC(12,2) DEFAULT 0,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY,
  booking_id UUID NOT NULL,
  payment_id TEXT,
  amount NUMERIC(12,2) DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT status CHECK (status IN ('pending','paid','failed','refunded'))
);

CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY,
  booking_id UUID,
  customer_id UUID,
  channel TEXT NOT NULL DEFAULT 'email',
  status TEXT NOT NULL DEFAULT 'pending',
  message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT channel CHECK (channel IN ('email','sms','whatsapp','telegram')),
  CONSTRAINT status CHECK (status IN ('pending','sent','failed'))
);

CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT action CHECK (length(trim(action)) > 0)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='bookings' AND constraint_type='FOREIGN KEY'
      AND constraint_name='bookings_cabin_id_fkey'
  ) THEN
    ALTER TABLE bookings
      ADD CONSTRAINT bookings_cabin_id_fkey FOREIGN KEY (cabin_id) REFERENCES cabins(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='bookings' AND constraint_type='FOREIGN KEY'
      AND constraint_name='bookings_customer_id_fkey'
  ) THEN
    ALTER TABLE bookings
      ADD CONSTRAINT bookings_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='pricing_rules' AND constraint_type='FOREIGN KEY'
      AND constraint_name='pricing_rules_cabin_id_fkey'
  ) THEN
    ALTER TABLE pricing_rules
      ADD CONSTRAINT pricing_rules_cabin_id_fkey FOREIGN KEY (cabin_id) REFERENCES cabins(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='transactions' AND constraint_type='FOREIGN KEY'
      AND constraint_name='transactions_booking_id_fkey'
  ) THEN
    ALTER TABLE transactions
      ADD CONSTRAINT transactions_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES bookings(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='notifications' AND constraint_type='FOREIGN KEY'
      AND constraint_name='notifications_booking_id_fkey'
  ) THEN
    ALTER TABLE notifications
      ADD CONSTRAINT notifications_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES bookings(id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='notifications' AND constraint_type='FOREIGN KEY'
      AND constraint_name='notifications_customer_id_fkey'
  ) THEN
    ALTER TABLE notifications
      ADD CONSTRAINT notifications_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES customers(id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_cabins_calendar_id ON cabins(calendar_id);

CREATE INDEX IF NOT EXISTS idx_bookings_cabin_id ON bookings(cabin_id);
CREATE INDEX IF NOT EXISTS idx_bookings_customer_id ON bookings(customer_id);
CREATE INDEX IF NOT EXISTS idx_bookings_check_in ON bookings(check_in);
CREATE INDEX IF NOT EXISTS idx_bookings_check_out ON bookings(check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);

CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);

CREATE INDEX IF NOT EXISTS idx_transactions_booking_id ON transactions(booking_id);
CREATE INDEX IF NOT EXISTS idx_transactions_payment_id ON transactions(payment_id);

COMMIT;
