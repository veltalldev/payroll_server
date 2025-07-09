# app/services/biweekly_report_service.py
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import calendar
from app.models.payroll import WorkSession, DailySummary, PayrollSummary

logger = logging.getLogger(__name__)

class BiweeklyPeriod:
    """Represents a biweekly pay period"""
    def __init__(self, year: int, month: int, half: int):
        self.year = year
        self.month = month
        self.half = half  # 1 or 2
        self.month_name = calendar.month_name[month]
        
        # Calculate date range
        if half == 1:
            self.start_date = datetime(year, month, 1)
            self.end_date = datetime(year, month, 15)
        else:
            self.start_date = datetime(year, month, 16)
            # Get last day of month
            last_day = calendar.monthrange(year, month)[1]
            self.end_date = datetime(year, month, last_day)
    
    @property
    def period_string(self) -> str:
        """Return the period in format like 'July2'"""
        return f"{self.month_name}{self.half}"
    
    @property
    def date_range_string(self) -> str:
        """Return formatted date range"""
        return f"{self.start_date.strftime('%B %d')} - {self.end_date.strftime('%B %d, %Y')}"
    
    @property
    def start_date_str(self) -> str:
        return self.start_date.strftime('%Y-%m-%d')
    
    @property
    def end_date_str(self) -> str:
        return self.end_date.strftime('%Y-%m-%d')

def parse_period_string(period: str, year: Optional[int] = None) -> BiweeklyPeriod:
    """
    Parse period string like 'July2' into BiweeklyPeriod
    
    Args:
        period: Format like 'July2' or 'December1'
        year: Optional year, defaults to current year
    
    Returns:
        BiweeklyPeriod object
    """
    if year is None:
        year = datetime.now().year
    
    # Extract month name and half number
    period = period.strip()
    if not period:
        raise ValueError("Period string cannot be empty")
    
    # Find where the digit starts
    digit_pos = None
    for i, char in enumerate(period):
        if char.isdigit():
            digit_pos = i
            break
    
    if digit_pos is None:
        raise ValueError(f"No period number found in '{period}'. Expected format like 'July2'")
    
    month_name = period[:digit_pos].strip()
    half_str = period[digit_pos:].strip()
    
    # Parse half
    try:
        half = int(half_str)
        if half not in [1, 2]:
            raise ValueError(f"Period half must be 1 or 2, got {half}")
    except ValueError:
        raise ValueError(f"Invalid period number '{half_str}'. Must be 1 or 2")
    
    # Parse month name
    month_names = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    month_abbr = {name.lower()[:3]: i for i, name in enumerate(calendar.month_name) if name}
    
    month_key = month_name.lower()
    month = month_names.get(month_key) or month_abbr.get(month_key)
    
    if month is None:
        raise ValueError(f"Invalid month name '{month_name}'")
    
    return BiweeklyPeriod(year, month, half)

def calculate_biweekly_stats(sessions: List[WorkSession]) -> Dict:
    """Calculate statistics for biweekly period"""
    if not sessions:
        return {
            'total_hours': 0.0,
            'less_break_hours': 0.0,
            'days_worked': 0,
            'avg_hours_per_day': 0.0,
            'break_time': 0.0,
            'weekend_days': 0
        }
    
    total_hours = sum(s.duration_hours or 0 for s in sessions if s.is_complete)
    
    # Calculate "less break" hours - subtract 30 mins (0.5 hours) for sessions > 5 hours
    less_break_hours = sum(
        (s.duration_hours - 0.5) if (s.duration_hours and s.duration_hours > 5) else (s.duration_hours or 0)
        for s in sessions if s.is_complete
    )
    
    days_worked = len([s for s in sessions if s.is_complete])
    avg_hours_per_day = less_break_hours / days_worked if days_worked > 0 else 0
    break_time = total_hours - less_break_hours
    
    # Count weekend days (assuming date field exists)
    weekend_days = 0
    for session in sessions:
        try:
            session_date = datetime.strptime(session.date, '%Y-%m-%d')
            if session_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                weekend_days += 1
        except (ValueError, AttributeError):
            pass
    
    # Calculate wage payout
    wage_payout = less_break_hours * 13.0

    return {
        'total_hours': round(total_hours, 2),
        'less_break_hours': round(less_break_hours, 2),
        'days_worked': days_worked,
        'avg_hours_per_day': round(avg_hours_per_day, 1),
        'break_time': round(break_time, 1),
        'weekend_days': weekend_days,
        'wage_payout': wage_payout
    }

def generate_biweekly_html_report(
    employee_name: str,
    employee_id: int,
    period: BiweeklyPeriod,
    sessions: List[WorkSession],
    stats: Dict
) -> str:
    """Generate standalone HTML report for biweekly timesheet"""
    
    # Create a daily data structure for easy lookup
    daily_data = {}
    for session in sessions:
        if session.is_complete:
            session_date = datetime.strptime(session.date, '%Y-%m-%d')
            day_of_month = session_date.day
            
            # Calculate less-break hours for this session
            raw_hours = session.duration_hours or 0
            less_break = raw_hours - 0.5 if raw_hours > 5 else raw_hours
            
            daily_data[day_of_month] = {
                'clock_in': session.clock_in.strftime('%H:%M') if session.clock_in else '--:--',
                'clock_out': session.clock_out.strftime('%H:%M') if session.clock_out else '--:--',
                'raw_hours': f"{raw_hours:.2f}",
                'less_break_hours': f"{less_break:.2f}",
                'day_of_week': session_date.strftime('%a'),
                'is_weekend': session_date.weekday() >= 5
            }
    
    # Generate HTML
    html_content = f"""
 <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Biweekly Timesheet - {employee_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f9fafb;
            padding: 1rem;
            color: #374151;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        .content {{
            display: grid;
            grid-template-columns: 1fr 3fr;
            gap: 1.5rem;
            padding: 1.5rem;
        }}
        
        .stats-sidebar {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .stat-card {{
            padding: 1.2rem;
            border-radius: 10px;
            color: white;
            text-align: center;
        }}
        
        .stat-card.header {{
            background: linear-gradient(135deg, #374151, #1f2937);
        }}
        
        .stat-card.blue {{
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        }}
        
        .stat-card.green {{
            background: linear-gradient(135deg, #10b981, #047857);
        }}
        
        .stat-card .title {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .stat-card .employee-name {{
            font-size: 1.1rem;
            font-weight: bold;
            margin-bottom: 0.25rem;
        }}
        
        .stat-card .employee-id {{
            font-size: 0.8rem;
            opacity: 0.9;
            margin-bottom: 0.25rem;
        }}
        
        .stat-card .period {{
            font-size: 0.8rem;
            opacity: 0.8;
        }}
        
        .stat-card .value {{
            font-size: 1.8rem;
            font-weight: bold;
            margin-bottom: 0.25rem;
        }}
        
        .stat-card .label {{
            opacity: 0.9;
            font-size: 0.8rem;
        }}
        
        .stat-card.purple {{
            background: linear-gradient(135deg, #8b5cf6, #6d28d9);
        }}
        
        .stat-card .hours-breakdown {{
            display: flex;
            justify-content: space-between;
            margin-top: 0.5rem;
        }}
        
        .stat-card .hours-item {{
            text-align: center;
            flex: 1;
        }}
        
        .stat-card .hours-item .hours-value {{
            font-size: 1.4rem;
            font-weight: bold;
            margin-bottom: 0.1rem;
        }}
        
        .stat-card .hours-item .hours-label {{
            font-size: 0.7rem;
            opacity: 0.9;
        }}
        
        .timesheet-table {{
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .table th {{
            background: #f9fafb;
            padding: 1rem 0.95rem;
            text-align: left;
            font-weight: 600;
            color: #374151;
            font-size: 0.9rem;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        .table th.center {{
            text-align: center;
        }}
        
        .table th.payable {{
            background: #ecfdf5;
            color: #065f46;
        }}
        
        .table td {{
            padding: 0.75rem 0.95rem;
            border-bottom: 1px solid #f3f4f6;
            font-size: 0.9rem;
        }}
        
        .table td.center {{
            text-align: center;
        }}
        
        .table td.date {{
            font-weight: 500;
            color: #374151;
            width: 120px;
            min-width: 120px;
        }}
        
        .table td.weekend {{
            color: #2563eb;
            font-weight: 600;
        }}
        
        .table td.payable {{
            background: #ecfdf5;
            color: #065f46;
            font-weight: 600;
        }}
        
        .table tr:nth-child(even) {{
            background: #f8fafc;
        }}
        
        .table tr:nth-child(even) td.payable {{
            background: #dcfce7;
        }}
        
        .table tr:hover {{
            background: #f1f5f9;
        }}
        
        .table tr:hover td.payable {{
            background: #bbf7d0;
        }}
        
        .empty-cell {{
            color: #9ca3af;
        }}
        
        @media print {{
            body {{
                padding: 0;
                background: white;
            }}
            
            .container {{
                box-shadow: none;
                border-radius: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            <div class="stats-sidebar">
                <div class="stat-card header">
                    <div class="title">Biweekly Timesheet</div>
                    <div class="employee-name">{employee_name}</div>
                    <div class="employee-id">Employee ID: {employee_id}</div>
                    <div class="period">{period.date_range_string}</div>
                </div>
                
                <div class="stat-card blue">
                    <div class="label">Hours Breakdown</div>
                    <div class="hours-breakdown">
                        <div class="hours-item">
                            <div class="hours-value">{stats['total_hours']}</div>
                            <div class="hours-label">Total</div>
                        </div>
                        <div class="hours-item">
                            <div class="hours-value">{stats['less_break_hours']}</div>
                            <div class="hours-label">Payable</div>
                        </div>
                    </div>
                </div>
                
                <div class="stat-card purple">
                    <div class="value">${stats['wage_payout']:.2f}</div>
                    <div class="label">Wage Payout @ $13/hr</div>
                </div>
            </div>
            
            <div class="timesheet-table">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Day</th>
                            <th class="center">Clock In</th>
                            <th class="center">Clock Out</th>
                            <th class="center">Raw Hours</th>
                            <th class="center payable">Payable Hours</th>
                        </tr>
                    </thead>
                    <tbody>"""
    # Generate table rows for each day in the period
    current_date = period.start_date
    while current_date <= period.end_date:
        day_of_month = current_date.day
        day_data = daily_data.get(day_of_month, {})
        
        is_weekend = day_data.get('is_weekend', current_date.weekday() >= 5)
        day_of_week = day_data.get('day_of_week', current_date.strftime('%a'))
        
        clock_in = day_data.get('clock_in', '--:--')
        clock_out = day_data.get('clock_out', '--:--')
        raw_hours = day_data.get('raw_hours', '--')
        less_break_hours = day_data.get('less_break_hours', '--')
        
        weekend_class = ' weekend' if is_weekend else ''
        empty_class = ' empty-cell' if not day_data else ''
        
        html_content += f"""
                        <tr>
                            <td class="date">{current_date.strftime('%b %d')}</td>
                            <td class="{weekend_class.strip()}">{day_of_week}</td>
                            <td class="center{empty_class}">{clock_in}</td>
                            <td class="center{empty_class}">{clock_out}</td>
                            <td class="center{empty_class}">{raw_hours}</td>
                            <td class="center payable{empty_class}">{less_break_hours}</td>
                        </tr>"""
        
        current_date += timedelta(days=1)
    
    html_content += """
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    return html_content
