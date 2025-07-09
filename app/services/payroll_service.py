from datetime import datetime
from typing import List, Dict, Any, Optional
import calendar
import csv
import io

from app.models.payroll import WorkSession, DailySummary, PayrollSummary, PayrollConfig

def calculate_work_sessions(time_entries: List[Dict]) -> List[WorkSession]:
    """Convert time entries into work sessions (IN/OUT pairs)"""
    sessions = []
    current_session = None
    
    for entry in time_entries:
        if entry['clock_type'] == 'IN':
            # Start new session
            current_session = {
                'employee_id': entry['employee_id'],
                'clock_in': datetime.fromisoformat(entry['timestamp']),
                'clock_out': None,
                'wifi_network_in': entry.get('wifi_network'),
                'wifi_network_out': None,
                'is_complete': False
            }
        elif entry['clock_type'] == 'OUT' and current_session:
            # Complete the session
            current_session['clock_out'] = datetime.fromisoformat(entry['timestamp'])
            current_session['wifi_network_out'] = entry.get('wifi_network')
            current_session['is_complete'] = True
            
            # Calculate duration
            duration = current_session['clock_out'] - current_session['clock_in']
            current_session['duration_minutes'] = int(duration.total_seconds() / 60)
            current_session['duration_hours'] = round(duration.total_seconds() / 3600, 2)
            
            sessions.append(current_session)
            current_session = None
    
    # Handle incomplete session (clocked in but not out)
    if current_session:
        sessions.append(current_session)
    
    # Convert to WorkSession objects
    work_sessions = []
    for i, session in enumerate(sessions):
        work_sessions.append(WorkSession(
            session_id=f"{session['employee_id']}_{session['clock_in'].strftime('%Y%m%d_%H%M%S')}",
            employee_id=session['employee_id'],
            employee_name="",  # Will be filled by caller
            clock_in=session['clock_in'],
            clock_out=session['clock_out'],
            duration_minutes=session.get('duration_minutes'),
            duration_hours=session.get('duration_hours'),
            is_complete=session['is_complete'],
            wifi_network_in=session['wifi_network_in'],
            wifi_network_out=session['wifi_network_out'],
            date=session['clock_in'].strftime('%Y-%m-%d')
        ))
    
    return work_sessions

def calculate_daily_summary(sessions: List[WorkSession], date: str) -> DailySummary:
    """Calculate daily summary from sessions"""
    if not sessions:
        return None
    
    employee_id = sessions[0].employee_id
    employee_name = sessions[0].employee_name
    
    # Filter sessions for this date
    date_sessions = [s for s in sessions if s.date == date]
    
    total_hours = sum(s.duration_hours or 0 for s in date_sessions if s.is_complete)
    has_incomplete = any(not s.is_complete for s in date_sessions)
    
    # Simple overtime calculation (over 8 hours/day)
    regular_hours = min(total_hours, 8.0)
    overtime_hours = max(0, total_hours - 8.0)
    
    return DailySummary(
        employee_id=employee_id,
        employee_name=employee_name,
        date=date,
        total_hours=round(total_hours, 2),
        sessions=date_sessions,
        has_incomplete_session=has_incomplete,
        overtime_hours=round(overtime_hours, 2),
        regular_hours=round(regular_hours, 2)
    )

def calculate_payroll_summary(sessions: List[WorkSession], start_date: str, end_date: str) -> PayrollSummary:
    """Calculate payroll summary for a period"""
    if not sessions:
        return None
    
    employee_id = sessions[0].employee_id
    employee_name = sessions[0].employee_name
    
    # Get unique dates
    dates = sorted(set(s.date for s in sessions))
    daily_summaries = []
    
    for date in dates:
        daily = calculate_daily_summary(sessions, date)
        if daily:
            daily_summaries.append(daily)
    
    total_hours = sum(d.total_hours for d in daily_summaries)
    regular_hours = sum(d.regular_hours for d in daily_summaries)
    overtime_hours = sum(d.overtime_hours for d in daily_summaries)
    
    return PayrollSummary(
        employee_id=employee_id,
        employee_name=employee_name,
        start_date=start_date,
        end_date=end_date,
        total_hours=round(total_hours, 2),
        regular_hours=round(regular_hours, 2),
        overtime_hours=round(overtime_hours, 2),
        total_days_worked=len(daily_summaries),
        sessions=sessions,
        daily_summaries=daily_summaries
    )

def generate_payroll_csv(reports: List[PayrollSummary]) -> str:
    """Generate CSV format for payroll export"""
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Employee ID', 'Employee Name', 'Start Date', 'End Date',
        'Total Hours', 'Regular Hours', 'Overtime Hours', 'Days Worked'
    ])
    
    # Data rows
    for report in reports:
        writer.writerow([
            report.employee_id,
            report.employee_name,
            report.start_date,
            report.end_date,
            report.total_hours,
            report.regular_hours,
            report.overtime_hours,
            report.total_days_worked
        ])
    
    return output.getvalue()
