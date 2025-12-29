-- Migration: Add event_id and event_link to bookings table
-- Also create quotes table if it doesn't exist

-- Add event_id and event_link to bookings
ALTER TABLE bookings 
ADD COLUMN IF NOT EXISTS event_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS event_link TEXT;

-- Create quotes table if it doesn't exist
CREATE TABLE IF NOT EXISTS quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabin_id UUID REFERENCES cabins(id) ON DELETE CASCADE,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    adults INT,
    kids INT,
    total_price DECIMAL(10,2),
    quote_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add index for quotes
CREATE INDEX IF NOT EXISTS idx_quotes_cabin_id ON quotes(cabin_id);
CREATE INDEX IF NOT EXISTS idx_quotes_dates ON quotes(check_in, check_out);
CREATE INDEX IF NOT EXISTS idx_quotes_created_at ON quotes(created_at);

