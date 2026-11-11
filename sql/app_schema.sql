-- Extra tables for Sessions, Tickets, and Items (Neon PostgreSQL)

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    messages JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY, -- NIM-0001
    query TEXT NOT NULL,
    route TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id TEXT NOT NULL,
    transcript JSONB NOT NULL DEFAULT '[]',
    summary TEXT,
    notes JSONB NOT NULL DEFAULT '[]',
    retrieved_slugs TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    category TEXT,
    stock INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed mock items if empty
INSERT INTO items (name, description, price, category, stock)
SELECT 'Nimbus Cloud Pro', 'High-performance cloud compute instance', 49.99, 'Cloud', 100
WHERE NOT EXISTS (SELECT 1 FROM items LIMIT 1);

INSERT INTO items (name, description, price, category, stock)
SELECT 'Nimbus Storage 1TB', 'Secure redundant storage for your data', 19.99, 'Storage', 500
WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Nimbus Storage 1TB');

INSERT INTO items (name, description, price, category, stock)
SELECT 'Nimbus VPN Express', 'Ultra-fast global VPN access', 9.99, 'Security', 1000
WHERE NOT EXISTS (SELECT 1 FROM items WHERE name = 'Nimbus VPN Express');
