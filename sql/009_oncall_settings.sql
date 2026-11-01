CREATE TABLE IF NOT EXISTS oncall_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value JSONB NOT NULL,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO oncall_settings (setting_key, setting_value)
VALUES
    ('show_copy', 'true'::jsonb),
    ('show_call', 'false'::jsonb)
ON CONFLICT (setting_key) DO NOTHING;
