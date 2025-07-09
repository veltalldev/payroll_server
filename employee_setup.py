#!/usr/bin/env python3
"""
Timeclock Employee Setup Script
Run this to initialize the database and add employees with PINs and colors
"""

import sqlite3
import sys
import hashlib
import hmac
from datetime import datetime
from pathlib import Path

DATABASE_PATH = "timeclock.db"
ADMIN_SECRET = "correct-horse-battery-staples"  # Should match your server config

# Predefined brand colors for employees (same as Flutter app)
BRAND_COLORS = [
    "#2962FF",  # Blue
    "#00C853",  # Green  
    "#FF6D00",  # Orange
    "#9C27B0",  # Purple
    "#D32F2F",  # Red
    "#00ACC1",  # Cyan
    "#8BC34A",  # Light Green
    "#FF9800",  # Amber
]

def hash_pin(pin: str, salt: str) -> str:
    """Hash a PIN with salt using HMAC-SHA256"""
    return hmac.new(
        salt.encode('utf-8'),
        pin.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def generate_salt(employee_id: int) -> str:
    """Generate a consistent salt for an employee"""
    return hashlib.sha256(f"{employee_id}_{ADMIN_SECRET}".encode()).hexdigest()[:16]

def init_database():
    """Initialize the database with all required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
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
    
    # Add PIN and color fields if they don't exist
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN pin_hash TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN pin_set_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN brand_color TEXT DEFAULT '#2962FF'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN display_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
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
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def add_employee(name, employee_number, pin=None, employee_id=None):
    """Add a new employee to the database with PIN and color"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Get next available color
        cursor.execute('SELECT COUNT(*) FROM employees WHERE active = TRUE')
        employee_count = cursor.fetchone()[0]
        brand_color = BRAND_COLORS[employee_count % len(BRAND_COLORS)]
        
        # Add employee
        if employee_id:
            cursor.execute('''
                INSERT INTO employees (employee_id, name, employee_number, brand_color, display_order)
                VALUES (?, ?, ?, ?, ?)
            ''', (employee_id, name, employee_number, brand_color, employee_count))
        else:
            cursor.execute('''
                INSERT INTO employees (name, employee_number, brand_color, display_order)
                VALUES (?, ?, ?, ?)
            ''', (name, employee_number, brand_color, employee_count))
            employee_id = cursor.lastrowid
        
        # Set PIN if provided
        if pin:
            set_employee_pin(cursor, employee_id, pin)
        
        conn.commit()
        print(f"✅ Added employee: {name} (ID: {employee_id}, #: {employee_number}, Color: {brand_color})")
        if pin:
            print(f"   📱 PIN set: {pin}")
        else:
            print(f"   ⚠️  No PIN set - use option 6 to set PIN")
        
        return employee_id
        
    except sqlite3.IntegrityError as e:
        print(f"❌ Error adding employee {name}: {e}")
        return None
    finally:
        conn.close()

def set_employee_pin(cursor, employee_id, pin):
    """Set PIN for an employee (internal function)"""
    if not pin.isdigit() or len(pin) != 4:
        raise ValueError("PIN must be exactly 4 digits")
    
    salt = generate_salt(employee_id)
    pin_hash = hash_pin(pin, salt)
    
    cursor.execute('''
        UPDATE employees 
        SET pin_hash = ?, pin_set_at = ?
        WHERE employee_id = ?
    ''', (pin_hash, datetime.now(), employee_id))

def set_pin_for_employee(employee_id, pin):
    """Set or update PIN for an existing employee"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if employee exists
        cursor.execute('SELECT name FROM employees WHERE employee_id = ?', (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            print(f"❌ Employee {employee_id} not found")
            return False
        
        if not pin.isdigit() or len(pin) != 4:
            print("❌ PIN must be exactly 4 digits")
            return False
        
        set_employee_pin(cursor, employee_id, pin)
        conn.commit()
        
        print(f"✅ PIN set for {employee[0]} (ID: {employee_id})")
        return True
        
    except Exception as e:
        print(f"❌ Error setting PIN: {e}")
        return False
    finally:
        conn.close()

def list_employees():
    """List all employees in the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT employee_id, name, employee_number, created_at, active, 
               brand_color, pin_hash, display_order
        FROM employees 
        ORDER BY display_order, employee_id
    ''')
    
    employees = cursor.fetchall()
    conn.close()
    
    if not employees:
        print("No employees found in database")
        return
    
    print("\nCurrent Employees:")
    print("-" * 80)
    print(f"{'ID':<4} {'Name':<20} {'Emp #':<10} {'Active':<8} {'PIN':<6} {'Color':<10} {'Created'}")
    print("-" * 80)
    
    for emp in employees:
        active_status = "✅ Yes" if emp[4] else "❌ No"
        has_pin = "✅ Set" if emp[6] else "❌ None"
        created_date = emp[3][:10] if emp[3] else "Unknown"
        color = emp[5] if emp[5] else "#2962FF"
        print(f"{emp[0]:<4} {emp[1]:<20} {emp[2]:<10} {active_status:<8} {has_pin:<6} {color:<10} {created_date}")

def deactivate_employee(employee_id):
    """Deactivate an employee (don't delete, preserve history)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE employees SET active = FALSE WHERE employee_id = ?', (employee_id,))
    
    if cursor.rowcount > 0:
        conn.commit()
        print(f"✅ Employee {employee_id} deactivated")
    else:
        print(f"❌ Employee {employee_id} not found")
    
    conn.close()

def update_display_order():
    """Update display order for carousel based on current active employees"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT employee_id FROM employees 
        WHERE active = TRUE 
        ORDER BY employee_id
    ''')
    
    employees = cursor.fetchall()
    
    for i, (emp_id,) in enumerate(employees):
        cursor.execute('''
            UPDATE employees 
            SET display_order = ? 
            WHERE employee_id = ?
        ''', (i, emp_id))
    
    conn.commit()
    conn.close()
    print(f"✅ Updated display order for {len(employees)} employees")

def interactive_setup():
    """Interactive employee setup"""
    print("Timeclock System - Employee Setup")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Add new employee")
        print("2. List all employees") 
        print("3. Deactivate employee")
        print("4. Bulk add from list")
        print("5. Set/update employee PIN")
        print("6. Update display order")
        print("7. Quick demo setup")
        print("8. Exit")
        
        choice = input("\nSelect option (1-8): ").strip()
        
        if choice == '1':
            name = input("Employee name: ").strip()
            employee_number = input("Employee number/badge ID: ").strip()
            pin = input("4-digit PIN (or press Enter to skip): ").strip()
            
            if name and employee_number:
                if pin and (not pin.isdigit() or len(pin) != 4):
                    print("❌ PIN must be exactly 4 digits, skipping PIN")
                    pin = None
                add_employee(name, employee_number, pin)
                update_display_order()
            else:
                print("❌ Name and employee number are required")
        
        elif choice == '2':
            list_employees()
        
        elif choice == '3':
            try:
                emp_id = int(input("Employee ID to deactivate: "))
                deactivate_employee(emp_id)
                update_display_order()
            except ValueError:
                print("❌ Please enter a valid employee ID number")
        
        elif choice == '4':
            print("\nBulk Add Mode - Enter employees one per line")
            print("Format: Name, Employee Number, PIN (optional)")
            print("Enter empty line when done")
            print("Example: John Smith, 001, 1234")
            
            while True:
                line = input("Employee: ").strip()
                if not line:
                    break
                
                try:
                    parts = [x.strip() for x in line.split(',')]
                    if len(parts) >= 2:
                        name, emp_num = parts[0], parts[1]
                        pin = parts[2] if len(parts) > 2 and parts[2] else None
                        
                        if pin and (not pin.isdigit() or len(pin) != 4):
                            print(f"❌ Invalid PIN for {name}, skipping PIN")
                            pin = None
                        
                        if name and emp_num:
                            add_employee(name, emp_num, pin)
                        else:
                            print("❌ Invalid format, use: Name, Employee Number, PIN")
                    else:
                        print("❌ Invalid format, use: Name, Employee Number, PIN")
                except ValueError:
                    print("❌ Invalid format, use: Name, Employee Number, PIN")
            
            update_display_order()
        
        elif choice == '5':
            try:
                emp_id = int(input("Employee ID: "))
                pin = input("New 4-digit PIN: ").strip()
                set_pin_for_employee(emp_id, pin)
            except ValueError:
                print("❌ Please enter a valid employee ID number")
        
        elif choice == '6':
            update_display_order()
        
        elif choice == '7':
            quick_setup_demo()
        
        elif choice == '8':
            break
        
        else:
            print("❌ Invalid option")

def quick_setup_demo():
    """Add some demo employees for testing with PINs"""
    print("Adding demo employees for testing...")
    
    demo_employees = [
        ("Alice Johnson", "001", "1234"),
        ("Bob Smith", "002", "5678"), 
        ("Carol Davis", "003", "9012"),
        ("David Wilson", "004", "3456"),
        ("Eva Brown", "005", "7890")
    ]
    
    for name, emp_num, pin in demo_employees:
        add_employee(name, emp_num, pin)
    
    update_display_order()
    print("✅ Demo employees added with PINs")
    print("\nDemo PINs:")
    for name, emp_num, pin in demo_employees:
        print(f"  {name}: {pin}")

if __name__ == "__main__":
    print("Timeclock Employee Setup")
    print("=" * 30)
    
    # Initialize database first
    init_database()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            quick_setup_demo()
            list_employees()
        elif sys.argv[1] == "--list":
            list_employees()
        elif sys.argv[1] == "--set-pin":
            if len(sys.argv) != 4:
                print("Usage: python employee_setup.py --set-pin <employee_id> <pin>")
            else:
                try:
                    emp_id = int(sys.argv[2])
                    pin = sys.argv[3]
                    set_pin_for_employee(emp_id, pin)
                except ValueError:
                    print("❌ Employee ID must be a number")
        else:
            print("Usage:")
            print("  python employee_setup.py                    # Interactive setup")
            print("  python employee_setup.py --demo             # Add demo employees")
            print("  python employee_setup.py --list             # List current employees")
            print("  python employee_setup.py --set-pin ID PIN   # Set PIN for employee")
    else:
        interactive_setup()
    
    print("\n✅ Setup complete! You can now start the timeclock server.")
    print("📱 Remember to test the PINs in the tablet app!")
