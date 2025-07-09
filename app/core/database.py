import sqlite3
from contextlib import contextmanager
import logging
from app.core.config import ServerConfig # Import ServerConfig

logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    conn = sqlite3.connect(ServerConfig.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_database():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create employees table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                employee_number TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Add PIN fields to employees table if they don't exist
        try:
            cursor.execute("ALTER TABLE employees ADD COLUMN pin_hash TEXT")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        try:
            cursor.execute("ALTER TABLE employees ADD COLUMN pin_set_at TIMESTAMP")
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Create time_entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS time_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                clock_type TEXT NOT NULL CHECK(clock_type IN ('IN', 'OUT')),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                qr_code_used TEXT NOT NULL,
                synced_to_cloud BOOLEAN DEFAULT FALSE,
                work_date DATE GENERATED ALWAYS AS (DATE(timestamp)) STORED,
                wifi_network TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        ''')
        
        # Create index for efficient payroll queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_payroll_lookup 
            ON time_entries (employee_id, work_date, timestamp)
        ''')
        
        # Create qr_sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qr_sessions (
                session_id TEXT PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                qr_code TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                wifi_network TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        ''')
        
        # Create wifi verification log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wifi_verification_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                wifi_ssid TEXT,
                success BOOLEAN NOT NULL,
                message TEXT NOT NULL,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        ''')
        
        # Create index for wifi log queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_wifi_log_lookup 
            ON wifi_verification_log (employee_id, timestamp, success)
        ''')
        
        # Create PIN attempts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pin_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                success BOOLEAN NOT NULL,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        ''')
        
        # Create index for PIN attempts
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pin_attempts_lookup 
            ON pin_attempts (employee_id, timestamp, success)
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully with PIN authentication support")

def seed_test_data():
    """Add test employees for development/testing"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if we already have employees
        cursor.execute("SELECT COUNT(*) FROM employees")
        count = cursor.fetchone()[0]
        
        if count > 0:
            logger.info(f"Database already has {count} employees")
            return
        
        # Add test employees
        test_employees = [
            (1, "John Doe", "EMP001", True),
            (2, "Jane Smith", "EMP002", True),
            (3, "Bob Johnson", "EMP003", True),
        ]
        
        cursor.executemany('''
            INSERT INTO employees (employee_id, name, employee_number, active)
            VALUES (?, ?, ?, ?)
        ''', test_employees)
        
        conn.commit()
        logger.info(f"Added {len(test_employees)} test employees to database")

def seed_test_pins():
    """Add test PINs for development employees"""
    import hashlib
    import hmac
    from datetime import datetime
    
    def hash_pin(pin: str, salt: str) -> str:
        """Hash a PIN with salt using HMAC-SHA256"""
        return hmac.new(
            salt.encode('utf-8'),
            pin.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def generate_salt(employee_id: int) -> str:
        """Generate a consistent salt for an employee"""
        return hashlib.sha256(f"{employee_id}_{ServerConfig.ADMIN_SECRET}".encode()).hexdigest()[:16]
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Test PIN assignments
        test_pins = [
            (1, "1234"),  # John Doe
            (2, "5678"),  # Jane Smith  
            (3, "9012"),  # Bob Johnson
        ]
        
        for employee_id, pin in test_pins:
            salt = generate_salt(employee_id)
            pin_hash = hash_pin(pin, salt)
            
            cursor.execute('''
                UPDATE employees 
                SET pin_hash = ?, pin_set_at = ?
                WHERE employee_id = ? AND pin_hash IS NULL
            ''', (pin_hash, datetime.now(), employee_id))
        
        conn.commit()
        logger.info("Test PINs seeded for development")
