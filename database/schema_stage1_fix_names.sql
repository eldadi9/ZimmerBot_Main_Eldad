{\rtf1}BEGIN;

ALTER TABLE bookings
  DROP CONSTRAINT IF EXISTS status,
  DROP CONSTRAINT IF EXISTS check_dates;

ALTER TABLE bookings
  ADD CONSTRAINT check_dates CHECK (check_out > check_in),
  ADD CONSTRAINT status CHECK (status IN ('hold','confirmed','cancelled'));

ALTER TABLE transactions
  DROP CONSTRAINT IF EXISTS status;

ALTER TABLE transactions
  ADD CONSTRAINT status CHECK (status IN ('pending','paid','failed','refunded'));

ALTER TABLE notifications
  DROP CONSTRAINT IF EXISTS channel,
  DROP CONSTRAINT IF EXISTS status;

ALTER TABLE notifications
  ADD CONSTRAINT channel CHECK (channel IN ('email','sms','whatsapp','telegram')),
  ADD CONSTRAINT status CHECK (status IN ('pending','sent','failed'));

ALTER TABLE audit_log
  DROP CONSTRAINT IF EXISTS action;

ALTER TABLE audit_log
  ADD CONSTRAINT action CHECK (length(trim(action)) > 0);

COMMIT;
