#!/usr/bin/env python3
"""
Interactive Time Entry Problem Fixer - COMPLETE VERSION WITH WHITELIST
Fixes all API communication issues and includes local whitelist functionality
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
import urllib3
from dataclasses import dataclass

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class Problem:
    entry_id: int
    employee_id: int
    employee_name: str
    timestamp: str
    clock_type: str
    problem_type: str
    description: str
    suggested_action: str

def get_current_pay_period():
    """Calculate current pay period dates (1st-15th or 16th-end of month)"""
    today = datetime.now()
    year = today.year
    month = today.month
    day = today.day
    
    if day <= 15:
        # First half of month: 1st-15th
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, 15)
    else:
        # Second half of month: 16th-end of month
        start_date = datetime(year, month, 16)
        # Get last day of month
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        end_date = next_month - timedelta(days=1)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

class WhitelistManager:
    """Manages local whitelist of validated entry IDs"""
    
    def __init__(self, whitelist_file: str = "validated_entries.json"):
        self.whitelist_file = whitelist_file
        self._whitelist: Set[int] = set()
        self.load_whitelist()
    
    def load_whitelist(self):
        """Load whitelist from file"""
        try:
            if os.path.exists(self.whitelist_file):
                with open(self.whitelist_file, 'r') as f:
                    data = json.load(f)
                    self._whitelist = set(data.get('validated_entry_ids', []))
                    print(f"📋 Loaded {len(self._whitelist)} validated entries from whitelist")
            else:
                print("📋 No existing whitelist found, starting fresh")
        except Exception as e:
            print(f"⚠️  Error loading whitelist: {e}")
            self._whitelist = set()
    
    def save_whitelist(self):
        """Save whitelist to file"""
        try:
            data = {
                'validated_entry_ids': list(self._whitelist),
                'last_updated': datetime.now().isoformat(),
                'total_validated': len(self._whitelist)
            }
            with open(self.whitelist_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"💾 Saved {len(self._whitelist)} validated entries to whitelist")
        except Exception as e:
            print(f"❌ Error saving whitelist: {e}")
    
    def add_entries(self, entry_ids: List[int], reason: str = "Validated as safe"):
        """Add entry IDs to whitelist"""
        before_count = len(self._whitelist)
        self._whitelist.update(entry_ids)
        after_count = len(self._whitelist)
        new_count = after_count - before_count
        
        print(f"✅ Added {new_count} new entries to whitelist (Total: {after_count})")
        print(f"📝 Reason: {reason}")
        
        # Log the validation
        self._log_validation(entry_ids, reason)
        self.save_whitelist()
    
    def remove_entries(self, entry_ids: List[int]):
        """Remove entry IDs from whitelist"""
        before_count = len(self._whitelist)
        self._whitelist.difference_update(entry_ids)
        after_count = len(self._whitelist)
        removed_count = before_count - after_count
        
        print(f"🗑️  Removed {removed_count} entries from whitelist (Total: {after_count})")
        self.save_whitelist()
    
    def is_validated(self, entry_id: int) -> bool:
        """Check if entry ID is in whitelist"""
        return entry_id in self._whitelist
    
    def filter_problems(self, problems: List[Problem]) -> tuple[List[Problem], List[Problem]]:
        """Filter problems into shown and suppressed lists"""
        shown = []
        suppressed = []
        
        for problem in problems:
            if self.is_validated(problem.entry_id):
                suppressed.append(problem)
            else:
                shown.append(problem)
        
        return shown, suppressed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get whitelist statistics"""
        return {
            'total_validated': len(self._whitelist),
            'whitelist_file': self.whitelist_file,
            'file_exists': os.path.exists(self.whitelist_file)
        }
    
    def _log_validation(self, entry_ids: List[int], reason: str):
        """Log validation action to a separate log file"""
        log_file = "validation_log.json"
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'entry_ids': entry_ids,
            'reason': reason,
            'count': len(entry_ids)
        }
        
        try:
            # Load existing log
            log_data = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    log_data = json.load(f)
            
            # Add new entry
            log_data.append(log_entry)
            
            # Keep only last 1000 entries
            if len(log_data) > 1000:
                log_data = log_data[-1000:]
            
            # Save log
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
                
        except Exception as e:
            print(f"⚠️  Warning: Could not log validation: {e}")
    
    def show_recent_validations(self, count: int = 10):
        """Show recent validation actions"""
        log_file = "validation_log.json"
        
        try:
            if not os.path.exists(log_file):
                print("📝 No validation history found")
                return
            
            with open(log_file, 'r') as f:
                log_data = json.load(f)
            
            if not log_data:
                print("📝 No validation history found")
                return
            
            print(f"\n📚 Recent Validations (last {min(count, len(log_data))}):")
            print("=" * 60)
            
            for entry in log_data[-count:]:
                timestamp = datetime.fromisoformat(entry['timestamp'])
                formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                entry_ids = entry['entry_ids']
                reason = entry['reason']
                
                if len(entry_ids) == 1:
                    print(f"• {formatted_time}: Entry {entry_ids[0]} - {reason}")
                else:
                    print(f"• {formatted_time}: {len(entry_ids)} entries ({entry_ids[0]}...{entry_ids[-1]}) - {reason}")
                    
        except Exception as e:
            print(f"❌ Error reading validation history: {e}")

class InteractiveTimeFixer:
    def __init__(self, base_url: str, admin_secret: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-Admin-Secret': admin_secret,
            'Content-Type': 'application/json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.verify = False
        self.whitelist = WhitelistManager()
        
        print(f"🔗 Connected to: {self.base_url}")
        print("🔒 SSL verification disabled for self-signed certificates")
        
        # Show whitelist stats on startup
        stats = self.whitelist.get_stats()
        if stats['total_validated'] > 0:
            print(f"📋 Whitelist active: {stats['total_validated']} validated entries will be suppressed")
    
    def check_connection(self) -> bool:
        """Test connection to the server"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                print("✅ Server connection successful!")
                data = response.json()
                print(f"📱 Server: {data.get('message', 'Unknown')}")
                print(f"🔢 Version: {data.get('version', 'Unknown')}")
                return True
            else:
                print(f"❌ Server responded with status {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("💡 Make sure the server is running and the URL/port are correct")
            return False
    
    def test_admin_auth(self) -> bool:
        """Test admin authentication specifically"""
        try:
            print("🔐 Testing admin authentication...")
            response = self.session.get(f"{self.base_url}/admin/admin/time-entries?limit=1")
            
            if response.status_code == 200:
                print("✅ Admin authentication successful!")
                return True
            elif response.status_code == 403:
                print("❌ Admin authentication failed - check your admin secret")
                return False
            elif response.status_code == 404:
                print("❌ Admin endpoints not found - check if admin router is properly mounted")
                return False
            else:
                print(f"❌ Admin test failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Admin auth test failed: {e}")
            return False
    
    def get_problems(self, employee_id: int = None, start_date: str = None, 
                    end_date: str = None) -> List[Problem]:
        """Get all problems in the date range"""
        
        # Use current pay period if no dates provided
        if not start_date or not end_date:
            start_date, end_date = get_current_pay_period()
            print(f"📅 Using current pay period: {start_date} to {end_date}")
        
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if employee_id:
            params['employee_id'] = employee_id
        
        url = f"{self.base_url}/admin/admin/time-entries/problems"
        
        print(f"🔍 Searching for problems: {url}")
        print(f"📋 Parameters: {params}")
        
        try:
            response = self.session.get(url, params=params)
            print(f"📡 API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"📊 API returned {data.get('total_problems', 0)} problems")
                
                problems = []
                for p in data.get('problems', []):
                    problems.append(Problem(
                        entry_id=p['entry_id'],
                        employee_id=p['employee_id'],
                        employee_name=p['employee_name'],
                        timestamp=p['timestamp'],
                        clock_type=p['clock_type'],
                        problem_type=p['problem_type'],
                        description=p['problem_description'],
                        suggested_action=p['suggested_action']
                    ))
                return problems
            elif response.status_code == 403:
                print("❌ Authentication failed - check your admin secret")
                return []
            elif response.status_code == 404:
                print("❌ Problems endpoint not found - check API structure")
                return []
            else:
                print(f"❌ Failed to get problems: {response.status_code}")
                print(f"Response: {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error getting problems: {e}")
            return []
    
    def get_raw_entries(self, employee_id: int, start_date: str, end_date: str) -> List[Dict]:
        """Get raw time entries for debugging using the correct endpoint"""
        params = {
            'employee_id': employee_id,
            'start_date': start_date,
            'end_date': end_date,
            'limit': 100
        }
        
        url = f"{self.base_url}/admin/admin/time-entries"
        
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('entries', [])
            else:
                print(f"❌ Failed to get raw entries: {response.status_code}")
                print(f"Response: {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error getting raw entries: {e}")
            return []
    
    def get_employee_raw_entries(self, employee_id: int, start_date: str, end_date: str) -> Dict:
        """Get employee raw entries using the specific endpoint"""
        url = f"{self.base_url}/admin/admin/time-entries/employee/{employee_id}/raw"
        params = {
            'start_date': start_date,
            'end_date': end_date
        }
        
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get employee raw entries: {response.status_code}")
                print(f"Response: {response.text}")
                return {}
        except Exception as e:
            print(f"❌ Error getting employee raw entries: {e}")
            return {}
    
    def check_employee_exists(self, employee_id: int) -> bool:
        """Check if an employee exists in the system"""
        try:
            response = self.session.get(f"{self.base_url}/admin/admin/time-entries", 
                                      params={'employee_id': employee_id, 'limit': 1})
            if response.status_code == 200:
                data = response.json()
                if data.get('entries'):
                    print(f"✅ Employee {employee_id} found in system")
                    return True
                else:
                    print(f"⚠️  Employee {employee_id} exists but has no time entries")
                    return True
            elif response.status_code == 404:
                print(f"❌ Employee {employee_id} not found")
                return False
            else:
                print(f"❌ Error checking employee: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error checking employee: {e}")
            return False
    
    def display_problems(self, problems: List[Problem], show_suppressed: bool = False):
        """Display problems in a readable format with enhanced context"""
        if not problems:
            print("🎉 No problems found!")
            return
        
        # Filter problems based on whitelist
        shown_problems, suppressed_problems = self.whitelist.filter_problems(problems)
        
        # Display suppression summary if there are suppressed problems
        if suppressed_problems:
            print(f"\n🔇 {len(suppressed_problems)} validated entries suppressed from display")
            if show_suppressed:
                print("   (Showing them below because show_suppressed=True)")
            else:
                print("   (Use 'Show validated entries' option to see them)")
        
        # Choose which problems to display
        display_problems = shown_problems if not show_suppressed else problems
        
        if not display_problems:
            print("🎉 No unvalidated problems found!")
            if suppressed_problems:
                print(f"💡 ({len(suppressed_problems)} validated entries are hidden)")
            return
        
        print(f"\n📋 Found {len(display_problems)} problem(s):")
        if show_suppressed:
            print("   (Including validated entries)")
        print("=" * 80)
        
        for i, problem in enumerate(display_problems, 1):
            # Mark validated entries
            validation_marker = ""
            if self.whitelist.is_validated(problem.entry_id):
                validation_marker = " [✅ VALIDATED]"
            
            print(f"\n{i}. Entry ID: {problem.entry_id}{validation_marker}")
            print(f"   Employee: {problem.employee_name} (ID: {problem.employee_id})")
            print(f"   Time: {problem.timestamp} ({problem.clock_type})")
            print(f"   Problem: {problem.problem_type}")
            print(f"   Description: {problem.description}")
            
            # Add context for LONG_SESSION problems
            if problem.problem_type == "LONG_SESSION":
                self._show_session_context(problem)
            
            print(f"   💡 Suggested: {problem.suggested_action}")
        
        # Show summary of what's displayed vs suppressed
        if suppressed_problems and not show_suppressed:
            print(f"\n📊 Summary: {len(shown_problems)} shown, {len(suppressed_problems)} validated (hidden)")
    
    def _show_session_context(self, problem: Problem):
        """Show additional context for long session problems"""
        try:
            # Get the employee's entries around this time to show broader context
            problem_time = datetime.fromisoformat(problem.timestamp)
            # Look back 3 days and forward 1 day for full context
            start_date = (problem_time - timedelta(days=3)).strftime('%Y-%m-%d')
            end_date = (problem_time + timedelta(days=1)).strftime('%Y-%m-%d')
            
            entries = self.get_raw_entries(problem.employee_id, start_date, end_date)
            
            if entries:
                # Sort entries by timestamp
                entries_sorted = sorted(entries, key=lambda x: x['timestamp'])
                
                # Find the problem entry index
                problem_entry_idx = None
                for idx, entry in enumerate(entries_sorted):
                    if entry['entry_id'] == problem.entry_id:
                        problem_entry_idx = idx
                        break
                
                if problem_entry_idx is not None:
                    print(f"   📅 Timeline Context (Entry {problem.entry_id} marked with >>>):")
                    
                    # Show entries with context around the problem
                    start_idx = max(0, problem_entry_idx - 3)
                    end_idx = min(len(entries_sorted), problem_entry_idx + 3)
                    
                    for idx in range(start_idx, end_idx):
                        entry = entries_sorted[idx]
                        entry_time = datetime.fromisoformat(entry['timestamp'])
                        
                        # Format the timestamp nicely
                        date_str = entry_time.strftime('%m-%d')
                        time_str = entry_time.strftime('%H:%M')
                        
                        # Mark the problem entry
                        marker = ">>> " if entry['entry_id'] == problem.entry_id else "    "
                        
                        # Calculate duration if this is an OUT following an IN
                        duration_info = ""
                        if entry['clock_type'] == 'OUT' and idx > 0:
                            prev_entry = entries_sorted[idx - 1]
                            if prev_entry['clock_type'] == 'IN':
                                prev_time = datetime.fromisoformat(prev_entry['timestamp'])
                                duration = entry_time - prev_time
                                hours = duration.total_seconds() / 3600
                                if hours > 12:
                                    duration_info = f" [{hours:.1f}h - LONG!]"
                                else:
                                    duration_info = f" [{hours:.1f}h]"
                        
                        print(f"      {marker}{date_str} {time_str} {entry['clock_type']:<3} (ID:{entry['entry_id']:>3}){duration_info}")
                    
                    print(f"   🔍 Analysis:")
                    
                    # Find the matching IN for this OUT
                    if problem.clock_type == 'OUT':
                        matching_in = None
                        for idx in range(problem_entry_idx - 1, -1, -1):
                            if entries_sorted[idx]['clock_type'] == 'IN':
                                matching_in = entries_sorted[idx]
                                break
                        
                        if matching_in:
                            in_time = datetime.fromisoformat(matching_in['timestamp'])
                            duration = problem_time - in_time
                            hours = duration.total_seconds() / 3600
                            days_apart = (problem_time.date() - in_time.date()).days
                            
                            print(f"      • This OUT pairs with IN from Entry {matching_in['entry_id']}")
                            print(f"      • Session duration: {hours:.1f} hours across {days_apart} day(s)")
                            
                            if days_apart > 0:
                                print(f"      • 🚨 Likely missing clock-out on {in_time.strftime('%m-%d')} or clock-in on {problem_time.strftime('%m-%d')}")
        except Exception as e:
            print(f"   ⚠️  Could not load session context: {e}")
    
    def debug_employee_entries(self, employee_id: int, start_date: str, end_date: str):
        """Debug function to show what entries exist for an employee"""
        print(f"\n🔍 Debug: Looking for entries for employee {employee_id}")
        print(f"📅 Date range: {start_date} to {end_date}")
        
        if not self.check_employee_exists(employee_id):
            return
        
        print("\n🎯 Trying specific employee endpoint...")
        employee_data = self.get_employee_raw_entries(employee_id, start_date, end_date)
        
        if employee_data:
            entries = employee_data.get('entries', [])
            employee_name = employee_data.get('employee_name', 'Unknown')
            print(f"📊 Found {len(entries)} entries for {employee_name}:")
            for entry in entries:
                print(f"   {entry['timestamp']} - {entry['clock_type']} (ID: {entry['entry_id']})")
        else:
            print("\n🔄 Fallback: Trying general time entries endpoint...")
            entries = self.get_raw_entries(employee_id, start_date, end_date)
            
            if entries:
                print(f"📊 Found {len(entries)} entries:")
                for entry in entries:
                    print(f"   {entry['timestamp']} - {entry['clock_type']} (ID: {entry['entry_id']})")
            else:
                print("❌ No entries found for this employee/date range")
    
    def quick_fix_missing_punch(self, employee_id: int, missing_type: str, 
                               estimated_time: str, reason: str) -> bool:
        """Fix missing punch"""
        params = {
            'employee_id': employee_id,
            'missing_type': missing_type,
            'estimated_time': estimated_time,
            'reason': reason
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/admin/admin/time-entries/quick-fix/missing-punch", 
                params=params
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ {result.get('message', 'Fix applied successfully')}")
                return True
            else:
                print(f"❌ Fix failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error applying fix: {e}")
            return False
    
    def delete_entry(self, entry_id: int, reason: str) -> bool:
        """Delete a single entry"""
        try:
            response = self.session.delete(
                f"{self.base_url}/admin/admin/time-entries/{entry_id}",
                params={'reason': reason}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Deleted entry {entry_id}: {reason}")
                return True
            else:
                print(f"❌ Delete failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error deleting entry: {e}")
            return False
    
    def bulk_delete_entries(self, entry_ids: List[int], reason: str) -> bool:
        """Delete multiple entries"""
        data = {
            'entry_ids': entry_ids, 
            'reason': reason
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/admin/admin/time-entries/bulk-delete", 
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Deleted {len(entry_ids)} entries: {reason}")
                return True
            else:
                print(f"❌ Bulk delete failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error bulk deleting entries: {e}")
            return False
    
    def edit_entry(self, entry_id: int, new_timestamp: str, new_clock_type: str, 
                   admin_notes: str) -> bool:
        """Edit an existing entry"""
        data = {
            'entry_id': entry_id,
            'new_timestamp': new_timestamp,
            'new_clock_type': new_clock_type,
            'admin_notes': admin_notes
        }
        
        try:
            response = self.session.put(
                f"{self.base_url}/admin/admin/time-entries/{entry_id}", 
                json=data
            )
            if response.status_code == 200:
                print(f"✅ Entry {entry_id} updated successfully")
                return True
            else:
                print(f"❌ Edit failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error editing entry: {e}")
            return False
    
    def create_manual_entry(self, employee_id: int, clock_type: str, 
                           timestamp: str, admin_notes: str) -> bool:
        """Create a new manual entry"""
        data = {
            'employee_id': employee_id,
            'clock_type': clock_type,
            'timestamp': timestamp,
            'admin_notes': admin_notes,
            'wifi_network': 'ADMIN_CREATED'
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/admin/admin/time-entries", 
                json=data
            )
            if response.status_code == 200:
                print(f"✅ Created manual {clock_type} entry")
                return True
            else:
                print(f"❌ Creation failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error creating entry: {e}")
            return False

def get_user_input(prompt: str, valid_options: List[str] = None) -> str:
    """Get user input with validation"""
    while True:
        response = input(f"{prompt}: ").strip()
        if valid_options and response.lower() not in [opt.lower() for opt in valid_options]:
            print(f"Please enter one of: {', '.join(valid_options)}")
            continue
        return response

def get_employee_id() -> int:
    """Get employee ID from user"""
    while True:
        try:
            emp_id = int(input("Enter employee ID (or 0 for all employees): "))
            return emp_id if emp_id > 0 else None
        except ValueError:
            print("Please enter a valid number")

def get_datetime_input(prompt: str, default: str = None) -> str:
    """Get datetime input from user"""
    if default:
        prompt += f" (default: {default})"
    
    while True:
        response = input(f"{prompt}: ").strip()
        if not response and default:
            return default
        
        try:
            datetime.fromisoformat(response)
            return response
        except ValueError:
            print("Please enter datetime in format: YYYY-MM-DDTHH:MM:SS (e.g., 2024-06-26T08:00:00)")

def handle_whitelist_management(fixer: InteractiveTimeFixer):
    """Handle whitelist management submenu"""
    while True:
        print("\n" + "=" * 40)
        print("WHITELIST MANAGEMENT")
        print("=" * 40)
        
        stats = fixer.whitelist.get_stats()
        print(f"📊 Current Status: {stats['total_validated']} validated entries")
        
        print("\n1. 📊 Show whitelist statistics")
        print("2. 📚 Show recent validations")
        print("3. 🗑️  Remove entries from whitelist")
        print("4. 📄 Export whitelist")
        print("5. 📥 Import whitelist")
        print("6. ⬅️  Back to main menu")
        
        choice = get_user_input("Select option", ["1", "2", "3", "4", "5", "6"])
        
        if choice == "6":
            break
        elif choice == "1":
            print(f"\n📊 Whitelist Statistics:")
            print(f"   Total validated entries: {stats['total_validated']}")
            print(f"   Whitelist file: {stats['whitelist_file']}")
            print(f"   File exists: {'Yes' if stats['file_exists'] else 'No'}")
            
        elif choice == "2":
            count = input("Number of recent validations to show (default: 10): ").strip()
            try:
                count = int(count) if count else 10
                fixer.whitelist.show_recent_validations(count)
            except ValueError:
                print("❌ Invalid number, showing last 10")
                fixer.whitelist.show_recent_validations(10)
                
        elif choice == "3":
            print("Enter entry IDs to remove from whitelist (comma-separated):")
            ids_input = input("Entry IDs: ").strip()
            try:
                entry_ids = [int(x.strip()) for x in ids_input.split(",")]
                fixer.whitelist.remove_entries(entry_ids)
            except ValueError:
                print("❌ Please enter valid entry IDs")
                
        elif choice == "4":
            export_whitelist(fixer.whitelist)
            
        elif choice == "5":
            import_whitelist(fixer.whitelist)

def handle_validation_workflow(fixer: InteractiveTimeFixer, shown_problems: List[Problem], 
                              employee_id: int, search_start: str, search_end: str):
    """Handle the validation workflow for marking problems as safe"""
    if not shown_problems:
        print("❌ No unvalidated problems to validate")
        return
    
    print(f"\n✅ Validation Workflow - {len(shown_problems)} problems available")
    print("=" * 50)
    
    print("1. ✅ Validate all current problems")
    print("2. 🎯 Validate specific problems")
    print("3. 🏷️  Validate by problem type")
    print("4. 👤 Validate by employee")
    print("5. ⬅️  Cancel")
    
    choice = get_user_input("Select validation option", ["1", "2", "3", "4", "5"])
    
    if choice == "5":
        return
    
    print(f"\n📝 Validation Reason (examples: 'Weekend overtime approved', 'Emergency shift', 'Reviewed with supervisor')")
    reason = input("Reason: ").strip()
    if not reason:
        reason = "Validated as acceptable by admin"
    
    entry_ids_to_validate = []
    
    if choice == "1":
        entry_ids_to_validate = [p.entry_id for p in shown_problems]
        print(f"📋 Validating all {len(entry_ids_to_validate)} problems")
        
    elif choice == "2":
        print(f"\nCurrent problems:")
        for i, problem in enumerate(shown_problems, 1):
            print(f"{i}. Entry {problem.entry_id}: {problem.employee_name} - {problem.problem_type}")
        
        selection = input("Enter problem numbers to validate (comma-separated, e.g., 1,3,5): ").strip()
        try:
            selected_nums = [int(x.strip()) for x in selection.split(",")]
            for num in selected_nums:
                if 1 <= num <= len(shown_problems):
                    entry_ids_to_validate.append(shown_problems[num - 1].entry_id)
                else:
                    print(f"⚠️  Skipping invalid problem number: {num}")
        except ValueError:
            print("❌ Invalid input format")
            return
            
    elif choice == "3":
        problem_types = list(set(p.problem_type for p in shown_problems))
        print(f"\nAvailable problem types:")
        for i, ptype in enumerate(problem_types, 1):
            count = sum(1 for p in shown_problems if p.problem_type == ptype)
            print(f"{i}. {ptype} ({count} entries)")
        
        try:
            type_choice = int(input("Select problem type to validate (number): ")) - 1
            if 0 <= type_choice < len(problem_types):
                selected_type = problem_types[type_choice]
                entry_ids_to_validate = [p.entry_id for p in shown_problems if p.problem_type == selected_type]
                print(f"📋 Validating {len(entry_ids_to_validate)} entries of type '{selected_type}'")
            else:
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Please enter a valid number")
            return
            
    elif choice == "4":
        employees = list(set((p.employee_id, p.employee_name) for p in shown_problems))
        print(f"\nEmployees with problems:")
        for i, (emp_id, emp_name) in enumerate(employees, 1):
            count = sum(1 for p in shown_problems if p.employee_id == emp_id)
            print(f"{i}. {emp_name} (ID: {emp_id}) - {count} entries")
        
        try:
            emp_choice = int(input("Select employee to validate (number): ")) - 1
            if 0 <= emp_choice < len(employees):
                selected_emp_id = employees[emp_choice][0]
                selected_emp_name = employees[emp_choice][1]
                entry_ids_to_validate = [p.entry_id for p in shown_problems if p.employee_id == selected_emp_id]
                print(f"📋 Validating {len(entry_ids_to_validate)} entries for {selected_emp_name}")
            else:
                print("❌ Invalid selection")
                return
        except ValueError:
            print("❌ Please enter a valid number")
            return
    
    if entry_ids_to_validate:
        print(f"\n⚠️  About to validate {len(entry_ids_to_validate)} entries:")
        print(f"   Entry IDs: {entry_ids_to_validate}")
        print(f"   Reason: {reason}")
        print(f"   These entries will be suppressed from future problem displays")
        
        confirm = get_user_input("Proceed with validation?", ["y", "n"])
        if confirm.lower() == "y":
            fixer.whitelist.add_entries(entry_ids_to_validate, reason)
            print(f"✅ Successfully validated {len(entry_ids_to_validate)} entries")
        else:
            print("❌ Validation cancelled")
    else:
        print("❌ No entries selected for validation")

def export_whitelist(whitelist: WhitelistManager):
    """Export whitelist to a different format or location"""
    try:
        export_file = input("Export filename (default: whitelist_export.json): ").strip()
        if not export_file:
            export_file = "whitelist_export.json"
            
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'total_entries': len(whitelist._whitelist),
            'validated_entry_ids': list(whitelist._whitelist),
            'source_file': whitelist.whitelist_file
        }
        
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        print(f"✅ Exported {len(whitelist._whitelist)} entries to {export_file}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")

def import_whitelist(whitelist: WhitelistManager):
    """Import whitelist from another file"""
    try:
        import_file = input("Import filename: ").strip()
        if not import_file or not os.path.exists(import_file):
            print("❌ File not found")
            return
            
        with open(import_file, 'r') as f:
            import_data = json.load(f)
            
        if 'validated_entry_ids' in import_data:
            new_entries = import_data['validated_entry_ids']
        elif isinstance(import_data, list):
            new_entries = import_data
        else:
            print("❌ Unrecognized file format")
            return
            
        try:
            new_entries = [int(x) for x in new_entries]
        except (ValueError, TypeError):
            print("❌ Invalid entry ID format in import file")
            return
            
        current_count = len(whitelist._whitelist)
        overlap = set(new_entries) & whitelist._whitelist
        new_count = len(set(new_entries) - whitelist._whitelist)
        
        print(f"📊 Import Summary:")
        print(f"   Current whitelist: {current_count} entries")
        print(f"   Import file: {len(new_entries)} entries")
        print(f"   Already validated: {len(overlap)} entries")
        print(f"   New entries: {new_count} entries")
        
        if new_count > 0:
            confirm = get_user_input(f"Import {new_count} new entries?", ["y", "n"])
            if confirm.lower() == "y":
                reason = input("Reason for import: ").strip() or f"Imported from {import_file}"
                whitelist.add_entries(list(set(new_entries) - whitelist._whitelist), reason)
                print(f"✅ Successfully imported {new_count} new entries")
            else:
                print("❌ Import cancelled")
        else:
            print("💡 No new entries to import")
            
    except Exception as e:
        print(f"❌ Import failed: {e}")

def interactive_problem_fixer():
    """Main interactive loop"""
    print("🚀 Interactive Time Entry Problem Fixer - COMPLETE VERSION WITH WHITELIST")
    print("=" * 75)
    
    # Configuration
    base_url = input("Enter server URL (default: https://localhost:8443): ").strip() or "https://localhost:8443"
    admin_secret = input("Enter admin secret: ").strip()
    
    if not admin_secret:
        print("❌ Admin secret is required!")
        return
    
    # Initialize fixer
    fixer = InteractiveTimeFixer(base_url, admin_secret)
    
    # Test connection
    if not fixer.check_connection():
        return
    
    # Test admin authentication
    if not fixer.test_admin_auth():
        return
    
    # Show current pay period
    start_date, end_date = get_current_pay_period()
    print(f"\n📅 Current pay period: {start_date} to {end_date}")
    
    # Main loop
    while True:
        print("\n" + "=" * 50)
        print("MAIN MENU")
        print("=" * 50)
        print("1. 🔍 Find problems (current pay period)")
        print("2. 🔍 Find problems (custom date range)")
        print("3. 🏥 Quick health check")
        print("4. 🐛 Debug employee entries")
        print("5. 🔐 Test admin authentication")
        print("6. 📋 Whitelist management")
        print("7. 🚪 Exit")
        
        choice = get_user_input("Select option", ["1", "2", "3", "4", "5", "6", "7"])
        
        if choice == "7":
            print("👋 Goodbye!")
            break
        elif choice == "3":
            fixer.check_connection()
            continue
        elif choice == "5":
            fixer.test_admin_auth()
            continue
        elif choice == "6":
            handle_whitelist_management(fixer)
            continue
        elif choice == "4":
            employee_id = get_employee_id()
            if employee_id:
                debug_start = input(f"Start date (default: {start_date}): ").strip() or start_date
                debug_end = input(f"End date (default: {end_date}): ").strip() or end_date
                fixer.debug_employee_entries(employee_id, debug_start, debug_end)
            continue
        elif choice in ["1", "2"]:
            # Problem detection workflow
            if choice == "2":
                print("\n📅 Custom Date Range Setup")
                search_start = input(f"Start date (YYYY-MM-DD, default: {start_date}): ").strip() or start_date
                search_end = input(f"End date (YYYY-MM-DD, default: {end_date}): ").strip() or end_date
            else:
                search_start, search_end = start_date, end_date
                print(f"\n📅 Using current pay period: {search_start} to {search_end}")
            
            employee_id = get_employee_id()
            
            print("🔍 Searching for problems...")
            all_problems = fixer.get_problems(employee_id, search_start, search_end)
            shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
            
            if not all_problems:
                print("🎉 No problems found in the specified range!")
                
                if employee_id:
                    debug_choice = get_user_input("Would you like to see raw entries for debugging?", ["y", "n"])
                    if debug_choice.lower() == "y":
                        fixer.debug_employee_entries(employee_id, search_start, search_end)
                continue
            
            # Display problems and offer fixes
            fixer.display_problems(all_problems)
            
            # Problem-by-problem fixing
            while shown_problems or suppressed_problems:
                print(f"\n🛠️  Problem Fixing Menu ({len(shown_problems)} active, {len(suppressed_problems)} validated)")
                print("1. 🔧 Fix specific problem")
                print("2. 🗑️  Delete single entry")
                print("3. 🗑️  Bulk delete entries")
                print("4. ➕ Add missing punch")
                print("5. ✏️  Edit entry manually")
                print("6. ✅ Validate problems as safe")
                print("7. 👁️  Show validated entries")
                print("8. 🔄 Refresh problem list")
                print("9. ⬅️  Back to main menu")
                
                fix_choice = get_user_input("Select fix option", ["1", "2", "3", "4", "5", "6", "7", "8", "9"])
                
                if fix_choice == "9":
                    break
                elif fix_choice == "8":
                    all_problems = fixer.get_problems(employee_id, search_start, search_end)
                    shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                    fixer.display_problems(all_problems)
                elif fix_choice == "7":
                    if suppressed_problems:
                        print(f"\n📋 Validated Entries ({len(suppressed_problems)}):")
                        print("=" * 50)
                        for i, problem in enumerate(suppressed_problems, 1):
                            print(f"{i}. Entry {problem.entry_id}: {problem.employee_name} - {problem.problem_type}")
                            print(f"   {problem.timestamp} ({problem.clock_type}) - {problem.description}")
                    else:
                        print("📋 No validated entries in current search")
                elif fix_choice == "6":
                    handle_validation_workflow(fixer, shown_problems, employee_id, search_start, search_end)
                    all_problems = fixer.get_problems(employee_id, search_start, search_end)
                    shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                elif fix_choice == "1":
                    if not shown_problems:
                        print("❌ No unvalidated problems to fix. Use option 7 to see validated entries.")
                        continue
                        
                    try:
                        prob_num = int(input(f"Which problem to fix (1-{len(shown_problems)}): ")) - 1
                        if 0 <= prob_num < len(shown_problems):
                            problem = shown_problems[prob_num]
                            
                            if "MISSING" in problem.problem_type and "IN" in problem.problem_type:
                                estimated_time = get_datetime_input("Estimated clock-in time", f"{problem.timestamp.split('T')[0]}T08:00:00")
                                reason = input("Reason for missing punch: ").strip() or "Missing clock-in estimated by admin"
                                if fixer.quick_fix_missing_punch(problem.employee_id, "IN", estimated_time, reason):
                                    all_problems = fixer.get_problems(employee_id, search_start, search_end)
                                    shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                            
                            elif "MISSING" in problem.problem_type and "OUT" in problem.problem_type:
                                estimated_time = get_datetime_input("Estimated clock-out time", f"{problem.timestamp.split('T')[0]}T17:00:00")
                                reason = input("Reason for missing punch: ").strip() or "Missing clock-out estimated by admin"
                                if fixer.quick_fix_missing_punch(problem.employee_id, "OUT", estimated_time, reason):
                                    all_problems = fixer.get_problems(employee_id, search_start, search_end)
                                    shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                            
                            elif "DOUBLE_PUNCH" in problem.problem_type:
                                confirm = get_user_input(f"Delete duplicate entry {problem.entry_id}?", ["y", "n"])
                                if confirm.lower() == "y":
                                    reason = input("Reason for deletion: ").strip() or "Removing duplicate punch"
                                    if fixer.delete_entry(problem.entry_id, reason):
                                        all_problems = fixer.get_problems(employee_id, search_start, search_end)
                                        shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                            
                            else:
                                print(f"💡 Manual fix needed for {problem.problem_type}")
                                print(f"   Suggestion: {problem.suggested_action}")
                        else:
                            print("❌ Invalid problem number")
                    except ValueError:
                        print("❌ Please enter a valid number")
                
                elif fix_choice == "2":
                    try:
                        entry_id = int(input("Entry ID to delete: "))
                        reason = input("Reason for deletion: ").strip() or "Manual deletion"
                        if fixer.delete_entry(entry_id, reason):
                            all_problems = fixer.get_problems(employee_id, search_start, search_end)
                            shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                    except ValueError:
                        print("❌ Please enter a valid entry ID")
                
                elif fix_choice == "3":
                    print("Enter entry IDs to delete (comma-separated):")
                    ids_input = input("Entry IDs: ").strip()
                    try:
                        entry_ids = [int(x.strip()) for x in ids_input.split(",")]
                        reason = input("Reason for deletion: ").strip() or "Bulk deletion of entries"
                        if fixer.bulk_delete_entries(entry_ids, reason):
                            all_problems = fixer.get_problems(employee_id, search_start, search_end)
                            shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                    except ValueError:
                        print("❌ Please enter valid entry IDs")
                
                elif fix_choice == "4":
                    try:
                        emp_id = int(input("Employee ID: "))
                        punch_type = get_user_input("Punch type", ["IN", "OUT"])
                        timestamp = get_datetime_input("Timestamp")
                        reason = input("Reason: ").strip() or "Manual addition of missing punch"
                        if fixer.quick_fix_missing_punch(emp_id, punch_type, timestamp, reason):
                            all_problems = fixer.get_problems(employee_id, search_start, search_end)
                            shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                    except ValueError:
                        print("❌ Please enter a valid employee ID")
                
                elif fix_choice == "5":
                    try:
                        entry_id = int(input("Entry ID to edit: "))
                        new_timestamp = get_datetime_input("New timestamp")
                        new_type = get_user_input("New clock type", ["IN", "OUT"])
                        notes = input("Admin notes: ").strip() or "Manual correction by admin"
                        if fixer.edit_entry(entry_id, new_timestamp, new_type, notes):
                            all_problems = fixer.get_problems(employee_id, search_start, search_end)
                            shown_problems, suppressed_problems = fixer.whitelist.filter_problems(all_problems)
                    except ValueError:
                        print("❌ Please enter a valid entry ID")
                
                # Refresh display after any changes
                if shown_problems or suppressed_problems:
                    fixer.display_problems(all_problems)

if __name__ == "__main__":
    interactive_problem_fixer()
