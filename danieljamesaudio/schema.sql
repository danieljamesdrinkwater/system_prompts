-- DanielJamesAudio Database Schema
-- SQLite database for equipment management, hire, repairs, and invoicing

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Business settings (key-value store)
CREATE TABLE IF NOT EXISTS business_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Default business settings
INSERT OR IGNORE INTO business_settings (key, value) VALUES
    ('business_name', 'Daniel James Audio'),
    ('address', ''),
    ('phone', ''),
    ('email', ''),
    ('bank_details', ''),
    ('vat_number', ''),
    ('vat_registered', 'false'),
    ('vat_rate', '20.0'),
    ('invoice_prefix', 'DJA'),
    ('next_invoice_number', '1'),
    ('payment_terms_days', '30'),
    ('currency', 'GBP');

-- Users (supports future multi-user growth)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'staff' CHECK (role IN ('owner', 'staff')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Equipment categories
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

INSERT OR IGNORE INTO categories (name, description) VALUES
    ('PA Systems', 'Speakers, amplifiers, subwoofers, crossovers, signal processors'),
    ('Backline', 'Guitar amps, bass amps, drum kits, keyboards, DI boxes'),
    ('Mixing & Recording', 'Mixing desks, audio interfaces, outboard gear, microphones'),
    ('Cabling & Accessories', 'XLR, TRS, speakON, power cables, stands, cases, racks');

-- Equipment inventory
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    serial_number TEXT,
    category_id INTEGER REFERENCES categories(id),
    subcategory TEXT,
    purchase_date DATE,
    purchase_price REAL,
    current_value REAL,
    condition TEXT DEFAULT 'good' CHECK (condition IN ('excellent', 'good', 'fair', 'poor', 'non-functional')),
    status TEXT DEFAULT 'available' CHECK (status IN ('available', 'on_hire', 'in_repair', 'retired')),
    location TEXT DEFAULT 'warehouse',
    day_rate REAL,
    week_rate REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status);
CREATE INDEX IF NOT EXISTS idx_equipment_category ON equipment(category_id);
CREATE INDEX IF NOT EXISTS idx_equipment_make_model ON equipment(make, model);

-- Equipment photos
CREATE TABLE IF NOT EXISTS equipment_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    caption TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Defects / faults logged against equipment
CREATE TABLE IF NOT EXISTS defects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    photo_path TEXT,
    reported_date DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'in_repair', 'resolved')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Repairs
CREATE TABLE IF NOT EXISTS repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    defect_id INTEGER REFERENCES defects(id),
    diagnosis TEXT,
    repair_type TEXT DEFAULT 'diy' CHECK (repair_type IN ('diy', 'outsourced')),
    repair_steps TEXT,  -- JSON array of step objects
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    assigned_to TEXT,  -- repair contact name or 'self'
    labour_cost REAL DEFAULT 0,
    parts_cost REAL DEFAULT 0,
    started_at DATE,
    completed_at DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trusted repair contacts
CREATE TABLE IF NOT EXISTS repair_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    speciality TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    website TEXT,
    notes TEXT,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Spare parts inventory
CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    part_number TEXT,
    quantity_in_stock INTEGER DEFAULT 0,
    reorder_level INTEGER DEFAULT 0,
    unit_cost REAL,
    supplier TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Service and user manuals
CREATE TABLE IF NOT EXISTS manuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_make TEXT NOT NULL,
    equipment_model TEXT NOT NULL,
    manual_type TEXT DEFAULT 'user' CHECK (manual_type IN ('service', 'user', 'quick_start', 'schematic')),
    file_path TEXT,
    external_url TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Join table: equipment <-> manuals (many-to-many)
CREATE TABLE IF NOT EXISTS equipment_manuals (
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    manual_id INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
    PRIMARY KEY (equipment_id, manual_id)
);

-- Hire bookings
CREATE TABLE IF NOT EXISTS hire_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    client_email TEXT,
    client_phone TEXT,
    client_address TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT DEFAULT 'enquiry' CHECK (status IN ('enquiry', 'confirmed', 'active', 'returned', 'cancelled')),
    subtotal REAL DEFAULT 0,
    vat_amount REAL DEFAULT 0,
    total_price REAL DEFAULT 0,
    deposit_amount REAL DEFAULT 0,
    deposit_paid INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Items within a hire booking
CREATE TABLE IF NOT EXISTS hire_booking_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES hire_bookings(id) ON DELETE CASCADE,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    day_rate REAL,
    agreed_price REAL,
    return_condition TEXT,
    return_notes TEXT
);

-- Pre-built hire packages
CREATE TABLE IF NOT EXISTS hire_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    day_rate REAL,
    week_rate REAL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Items within a hire package
CREATE TABLE IF NOT EXISTS hire_package_items (
    package_id INTEGER NOT NULL REFERENCES hire_packages(id) ON DELETE CASCADE,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id),
    PRIMARY KEY (package_id, equipment_id)
);

-- Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    booking_id INTEGER REFERENCES hire_bookings(id),
    client_name TEXT NOT NULL,
    client_email TEXT,
    client_address TEXT,
    issue_date DATE DEFAULT CURRENT_DATE,
    due_date DATE,
    subtotal REAL DEFAULT 0,
    vat_rate REAL DEFAULT 0,
    vat_amount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'sent', 'paid', 'overdue', 'cancelled')),
    paid_date DATE,
    payment_method TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Invoice line items
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    quantity REAL DEFAULT 1,
    unit_price REAL NOT NULL,
    total REAL NOT NULL
);

-- Business plan versions
CREATE TABLE IF NOT EXISTS business_plan_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    version INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email templates
CREATE TABLE IF NOT EXISTS email_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default email templates
INSERT OR IGNORE INTO email_templates (name, subject_template, body_template) VALUES
    ('hire_quote', 'Quote from Daniel James Audio - {booking_ref}',
     'Hi {client_name},\n\nThank you for your enquiry. Please find below our quote for equipment hire:\n\n{equipment_list}\n\nDates: {start_date} to {end_date}\nTotal: £{total}\n\nPayment terms: {payment_terms}\n\nPlease let me know if you have any questions.\n\nBest regards,\nDaniel James\nDaniel James Audio'),
    ('hire_confirmation', 'Booking Confirmed - Daniel James Audio - {booking_ref}',
     'Hi {client_name},\n\nThis is to confirm your equipment hire booking:\n\n{equipment_list}\n\nDates: {start_date} to {end_date}\nTotal: £{total}\n\nCollection/delivery details will be confirmed shortly.\n\nBest regards,\nDaniel James\nDaniel James Audio'),
    ('invoice_email', 'Invoice {invoice_number} - Daniel James Audio',
     'Hi {client_name},\n\nPlease find attached invoice {invoice_number} for £{total}.\n\nPayment is due by {due_date}.\n\nBank details:\n{bank_details}\n\nThank you for your business.\n\nBest regards,\nDaniel James\nDaniel James Audio');

-- Correspondence log
CREATE TABLE IF NOT EXISTS correspondence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER REFERENCES hire_bookings(id),
    invoice_id INTEGER REFERENCES invoices(id),
    recipient_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'sent')),
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
