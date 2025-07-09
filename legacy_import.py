#!/usr/bin/env python3
"""
Legacy Time Clock Data Import Script

This script imports legacy punch time data into the timeclock system via the admin API.
It converts paired daily entries (clock in/out times) into individual time entries.

Usage:
    python legacy_import.py

Requirements:
    - requests library: pip install requests
    - Server running at https://localhost:8443
    - Admin secret: correct-horse-battery-staples

Data File Format:
    Tab-separated values with columns: Date, Clock In, Clock Out, Total Hours, Hours Less Break
    Example: 3/1/2025	9:16	17:37	8.35	7.85
"""

import requests
import json
from datetime import datetime
import time
import urllib3
import os
import sys

# Disable SSL warnings for localhost
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
BASE_URL = "https://localhost:8443"
ADMIN_SECRET = "correct-horse-battery-staples"

# Headers for admin authentication
HEADERS = {
    "Content-Type": "application/json",
    "X-Admin-Secret": ADMIN_SECRET
}

def get_user_inputs():
    """Get employee ID and data file from user input"""
    print("🕐 Legacy Time Clock Data Import Tool")
    print("=" * 50)
    
    # Get employee ID
    while True:
        try:
            employee_id = input("\n📋 Enter Employee ID: ").strip()
            employee_id = int(employee_id)
            if employee_id > 0:
                break
            else:
                print("❌ Employee ID must be a positive number")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Get data file
    while True:
        filename = input("\n📁 Enter data filename (or 'sample' for built-in sample): ").strip()
        
        if filename.lower() == 'sample':
            print("✅ Using built-in sample data")
            return employee_id, None
        elif os.path.isfile(filename):
            print(f"✅ Found file: {filename}")
            return employee_id, filename
        else:
            print(f"❌ File '{filename}' not found. Please check the path.")

def read_data_from_file(filename):
    """Read time clock data from file"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

def get_sample_data():
    """Return the built-in sample data"""
    return """3/1/2025	9:16	17:37	8.35	7.85
3/2/2025	9:14	17:58	8.73	8.23
3/3/2025	9:16	17:51	8.58	8.08
3/4/2025	9:12	18:07	8.92	8.42
3/6/2025	9:12	18:00	8.8	8.3
3/7/2025	9:17	18:05	8.8	8.3
3/8/2025	9:14	17:56	8.7	8.2
3/9/2025	8:07	17:07	9	8.5
3/11/2025	8:10	17:07	8.95	8.45
3/13/2025	8:29	17:21	8.87	8.37
3/14/2025	8:12	17:07	8.92	8.42
3/15/2025	8:19	16:58	8.65	8.15
3/16/2025	8:18	17:08	8.83	8.33
3/18/2025	8:14	16:57	8.72	8.22
3/20/2025	8:11	17:08	8.95	8.45
3/21/2025	8:13	16:34	8.35	7.85
3/22/2025	8:20	17:22	9.03	8.53
3/23/2025	8:13	17:19	9.1	8.6
3/25/2025	8:15	17:10	8.92	8.42
3/27/2025	8:16	16:41	8.42	7.92
3/28/2025	8:13	16:29	8.27	7.77
3/29/2025	8:13	17:18	9.08	8.58
3/30/2025	8:20	17:02	8.7	8.2
4/1/2025	8:14	17:13	8.98	8.48
4/3/2025	8:11	16:57	8.77	8.27
4/5/2025	8:14	16:33	8.32	7.82
4/6/2025	8:26	16:49	8.38	7.88
4/7/2025	8:19	16:52	8.55	8.05
4/8/2025	8:15	17:32	9.28	8.78
4/10/2025	9:30	16:45	7.25	6.75
4/12/2025	8:14	16:43	8.48	7.98
4/13/2025	8:13	17:44	9.52	9.02
4/14/2025	8:14	16:55	8.68	8.18
4/15/2025	8:13	17:04	8.85	8.35
4/17/2025	8:00	17:04	9.07	8.57
4/19/2025	8:09	17:16	9.12	8.62
4/20/2025	8:11	17:19	9.13	8.63
4/21/2025	8:09	16:46	8.62	8.12
4/22/2025	8:06	17:12	9.1	8.6
4/24/2025	8:06	16:58	8.87	8.37
4/26/2025	8:07	15:55	7.8	7.3
4/27/2025	8:09	16:57	8.8	8.3
4/29/2025	8:05	17:12	9.12	8.62
5/1/2025	8:09	16:53	8.73	8.23
5/2/2025	8:08	16:41	8.55	8.05
5/3/2025	8:18	17:15	8.95	8.45
5/4/2025	8:17	17:18	9.02	8.52
5/5/2025	8:13	17:22	9.15	8.65
5/6/2025	7:59	17:14	9.25	8.75
5/8/2025	8:08	17:40	9.53	9.03
5/10/2025	8:06	16:49	8.72	8.22
5/11/2025	8:05	17:40	9.58	9.08
5/13/2025	8:06	17:45	9.65	9.15
5/15/2025	8:16	17:55	9.65	9.15
5/16/2025	8:00	17:30	9.5	9
5/17/2025	8:07	17:50	9.72	9.22
5/18/2025	8:16	17:22	9.1	8.6
5/20/2025	7:59	17:24	9.42	8.92
5/22/2025	8:45	16:56	8.18	7.68
5/23/2025	8:04	17:09	9.08	8.58
5/24/2025	8:07	17:26	9.32	8.82
5/25/2025	8:08	17:20	9.2	8.7
5/26/2025	8:02	17:34	9.53	9.03
5/27/2025	8:03	17:43	9.67	9.17
5/29/2025	7:59	17:25	9.43	8.93
5/31/2025	8:05	17:28	9.38	8.88"""

def parse_legacy_data(data_content, employee_id):
    """Parse the legacy data into structured entries"""
    entries = []
    
    for line in data_content.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) >= 3:
            date_str = parts[0].strip()
            clock_in_str = parts[1].strip()
            clock_out_str = parts[2].strip()
            
            # Parse date (M/D/YYYY format)
            try:
                date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                date_formatted = date_obj.strftime('%Y-%m-%d')
                
                # Create clock IN entry
                clock_in_time = f"{date_formatted}T{clock_in_str.zfill(5)}:00"
                entries.append({
                    "employee_id": employee_id,
                    "clock_type": "IN",
                    "timestamp": clock_in_time,
                    "wifi_network": "LEGACY_IMPORT",
                    "admin_notes": f"Legacy data import from {date_str} - Clock IN"
                })
                
                # Create clock OUT entry
                clock_out_time = f"{date_formatted}T{clock_out_str.zfill(5)}:00"
                entries.append({
                    "employee_id": employee_id,
                    "clock_type": "OUT", 
                    "timestamp": clock_out_time,
                    "wifi_network": "LEGACY_IMPORT",
                    "admin_notes": f"Legacy data import from {date_str} - Clock OUT"
                })
                
            except ValueError as e:
                print(f"⚠️  Error parsing date '{date_str}': {e}")
                continue
    
    return entries

def verify_employee_exists(employee_id):
    """Verify that the specified employee exists in the system"""
    url = f"{BASE_URL}/employees/by_id/{employee_id}"
    
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            employee_data = response.json()
            print(f"✅ Employee verified: {employee_data.get('name', 'Unknown')} (ID: {employee_id})")
            return True
        else:
            print(f"❌ Employee ID {employee_id} not found (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error verifying employee: {e}")
        return False

def create_time_entry(entry_data):
    """Create a single time entry via the admin API"""
    url = f"{BASE_URL}/admin/admin/time-entries"
    
    try:
        response = requests.post(
            url, 
            headers=HEADERS,
            json=entry_data,
            verify=False,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            return True, response.json()
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Request error: {e}"

def main():
    """Main import process"""
    
    # Step 1: Get user inputs
    employee_id, filename = get_user_inputs()
    
    # Step 2: Get data content
    if filename:
        print(f"\n📋 Step 1: Reading data from {filename}...")
        data_content = read_data_from_file(filename)
        if not data_content:
            print("❌ Import aborted - could not read file")
            return
    else:
        print("\n📋 Step 1: Using built-in sample data...")
        data_content = get_sample_data()
    
    # Step 3: Verify employee exists
    print(f"\n📋 Step 2: Verifying employee {employee_id}...")
    if not verify_employee_exists(employee_id):
        print("❌ Import aborted - employee not found")
        return
    
    # Step 4: Parse legacy data
    print("\n📋 Step 3: Parsing legacy data...")
    entries = parse_legacy_data(data_content, employee_id)
    print(f"✅ Parsed {len(entries)} time entries ({len(entries)//2} days)")
    
    if len(entries) == 0:
        print("❌ No valid entries found in data")
        return
    
    # Step 5: Confirm import
    print(f"\n⚠️  About to import {len(entries)} entries for employee {employee_id}")
    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Import cancelled by user")
        return
    
    # Step 6: Import entries
    print("\n📋 Step 4: Importing entries...")
    successful_imports = 0
    failed_imports = 0
    
    for i, entry in enumerate(entries, 1):
        print(f"⏳ Importing entry {i}/{len(entries)}: {entry['clock_type']} at {entry['timestamp']}")
        
        success, result = create_time_entry(entry)
        
        if success:
            successful_imports += 1
            print(f"   ✅ Success")
        else:
            failed_imports += 1
            print(f"   ❌ Failed: {result}")
        
        # Brief pause between requests to avoid overwhelming the server
        time.sleep(0.05)  # 50ms delay
    
    # Step 7: Summary
    print("\n" + "=" * 50)
    print("📊 Import Summary:")
    print(f"   Employee ID: {employee_id}")
    print(f"   Data source: {'File: ' + filename if filename else 'Built-in sample'}")
    print(f"   Total entries processed: {len(entries)}")
    print(f"   Successful imports: {successful_imports}")
    print(f"   Failed imports: {failed_imports}")
    print(f"   Success rate: {(successful_imports/len(entries)*100):.1f}%")
    
    if failed_imports == 0:
        print("🎉 All entries imported successfully!")
    else:
        print(f"⚠️  {failed_imports} entries failed to import")

if __name__ == "__main__":
    main()
