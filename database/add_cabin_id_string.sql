-- Add cabin_id_string column to cabins table to store original IDs like ZB01, ZB02, ZB03
-- This allows booking by original cabin ID instead of UUID

ALTER TABLE cabins 
ADD COLUMN IF NOT EXISTS cabin_id_string VARCHAR(20);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_cabins_cabin_id_string ON cabins(cabin_id_string);

-- Update existing cabins if we can match them
-- This is a one-time migration - you may need to run import_cabins_to_db.py after this

