import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.core.database import get_db # Import get_db
from app.models.admin import ProblemTimeEntry # Import ProblemTimeEntry

logger = logging.getLogger(__name__)

def detect_time_entry_problems(employee_id: int, start_date: str, end_date: str) -> List[ProblemTimeEntry]:
    """Detect common time entry problems"""
    problems = []
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get employee info
        cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            return problems
        
        employee_name = employee['name']
        
        # Get all entries for the period
        cursor.execute('''
            SELECT entry_id, employee_id, clock_type, timestamp, wifi_network
            FROM time_entries 
            WHERE employee_id = ? 
            AND date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp ASC
        ''', (employee_id, start_date, end_date))
        
        entries = cursor.fetchall()
        
        for i, entry in enumerate(entries):
            entry_time = datetime.fromisoformat(entry['timestamp'])
            
            # Problem 1: Double punch (same type within 5 minutes)
            if i > 0:
                prev_entry = entries[i-1]
                prev_time = datetime.fromisoformat(prev_entry['timestamp'])
                time_diff = (entry_time - prev_time).total_seconds() / 60  # minutes
                
                if entry['clock_type'] == prev_entry['clock_type'] and time_diff < 5:
                    problems.append(ProblemTimeEntry(
                        entry_id=entry['entry_id'],
                        employee_id=employee_id,
                        employee_name=employee_name,
                        timestamp=entry_time,
                        clock_type=entry['clock_type'],
                        problem_type="DOUBLE_PUNCH",
                        problem_description=f"Duplicate {entry['clock_type']} punch within {time_diff:.1f} minutes",
                        suggested_action="Delete this entry or edit the time"
                    ))
            
            # Problem 2: Very long session (>12 hours between IN and OUT)
            if i > 0 and entry['clock_type'] == 'OUT':
                prev_entry = entries[i-1]
                if prev_entry['clock_type'] == 'IN':
                    prev_time = datetime.fromisoformat(prev_entry['timestamp'])
                    session_hours = (entry_time - prev_time).total_seconds() / 3600
                    
                    if session_hours > 12:
                        problems.append(ProblemTimeEntry(
                            entry_id=entry['entry_id'],
                            employee_id=employee_id,
                            employee_name=employee_name,
                            timestamp=entry_time,
                            clock_type=entry['clock_type'],
                            problem_type="LONG_SESSION",
                            problem_description=f"Work session of {session_hours:.1f} hours",
                            suggested_action="Check if employee forgot to clock out/in"
                        ))
            
            # Problem 3: Unusual hours (before 4 AM or after 11 PM)
            hour = entry_time.hour
            if hour < 4 or hour > 23:
                problems.append(ProblemTimeEntry(
                    entry_id=entry['entry_id'],
                    employee_id=employee_id,
                    employee_name=employee_name,
                    timestamp=entry_time,
                    clock_type=entry['clock_type'],
                    problem_type="UNUSUAL_HOURS",
                    problem_description=f"Clock punch at {entry_time.strftime('%I:%M %p')}",
                    suggested_action="Verify this is correct or edit time"
                ))
        
        # Problem 4: Missing punch (ends with IN or starts with OUT)
        # This check is better performed on a daily basis after sessions are calculated
        # For now, we'll keep the logic from your original code if needed for quick reports
        if entries:
            first_entry = entries[0]
            last_entry = entries[-1]
            
            if first_entry['clock_type'] == 'OUT' and first_entry['timestamp'].split('T')[0] == start_date:
                problems.append(ProblemTimeEntry(
                    entry_id=first_entry['entry_id'],
                    employee_id=employee_id,
                    employee_name=employee_name,
                    timestamp=datetime.fromisoformat(first_entry['timestamp']),
                    clock_type=first_entry['clock_type'],
                    problem_type="MISSING_CLOCK_IN_START_OF_PERIOD",
                    problem_description="Period starts with clock OUT, suggesting a missing initial clock IN.",
                    suggested_action="Add missing clock IN entry before this"
                ))
            
            if last_entry['clock_type'] == 'IN' and last_entry['timestamp'].split('T')[0] == end_date:
                problems.append(ProblemTimeEntry(
                    entry_id=last_entry['entry_id'],
                    employee_id=employee_id,
                    employee_name=employee_name,
                    timestamp=datetime.fromisoformat(last_entry['timestamp']),
                    clock_type=last_entry['clock_type'],
                    problem_type="MISSING_CLOCK_OUT_END_OF_PERIOD",
                    problem_description="Period ends with clock IN, suggesting a missing final clock OUT.",
                    suggested_action="Add missing clock OUT entry after this"
                ))
    
    return problems
