import logging
from datetime import datetime, timedelta
from typing import Optional, List
import calendar

from fastapi import APIRouter, HTTPException, Response
from app.core.database import get_db # Import get_db
from app.models.payroll import WorkSession, DailySummary, PayrollSummary # Import models
from app.services.payroll_service import calculate_work_sessions, calculate_daily_summary, calculate_payroll_summary, generate_payroll_csv # Import services
from app.services.biweekly_report_service import (
    parse_period_string, 
    calculate_biweekly_stats, 
    generate_biweekly_html_report,
    BiweeklyPeriod
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/payroll/employee/{employee_id}/timesheet", response_model=PayrollSummary)
async def get_employee_timesheet(
    employee_id: int,
    start_date: str,  # YYYY-MM-DD
    end_date: str,    # YYYY-MM-DD
):
    """Get detailed timesheet for an employee"""
    try:
        # Validate dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get employee info
            cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
            employee = cursor.fetchone()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            employee_name = employee['name']
            
            # Get time entries for the period
            cursor.execute('''
                SELECT employee_id, clock_type, timestamp, wifi_network
                FROM time_entries 
                WHERE employee_id = ? 
                AND date(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (employee_id, start_date, end_date))
            
            time_entries = [dict(row) for row in cursor.fetchall()]
            
            # Calculate work sessions
            sessions = calculate_work_sessions(time_entries)
            
            # Add employee name to sessions
            for session in sessions:
                session.employee_name = employee_name
            
            # Calculate payroll summary
            payroll_summary = calculate_payroll_summary(sessions, start_date, end_date)
            
            return payroll_summary
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error generating timesheet: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate timesheet")

@router.get("/payroll/daily-summary")
async def get_daily_summary(date: str):
    """Get daily summary for all employees"""
    try:
        # Validate date
        summary_date = datetime.strptime(date, '%Y-%m-%d')
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all employees who worked on this date
            cursor.execute('''
                SELECT DISTINCT e.employee_id, e.name
                FROM employees e
                JOIN time_entries te ON e.employee_id = te.employee_id
                WHERE date(te.timestamp) = ?
                ORDER BY e.name
            ''', (date,))
            
            employees = cursor.fetchall()
            daily_summaries = []
            
            for employee in employees:
                employee_id = employee['employee_id']
                employee_name = employee['name']
                
                # Get time entries for this employee on this date
                cursor.execute('''
                    SELECT employee_id, clock_type, timestamp, wifi_network
                    FROM time_entries 
                    WHERE employee_id = ? AND date(timestamp) = ?
                    ORDER BY timestamp ASC
                ''', (employee_id, date))
                
                time_entries = [dict(row) for row in cursor.fetchall()]
                sessions = calculate_work_sessions(time_entries)
                
                # Add employee name
                for session in sessions:
                    session.employee_name = employee_name
                
                daily_summary = calculate_daily_summary(sessions, date)
                if daily_summary:
                    daily_summaries.append(daily_summary)
            
            # Calculate totals
            total_employees = len(daily_summaries)
            total_hours = sum(d.total_hours for d in daily_summaries)
            total_overtime = sum(d.overtime_hours for d in daily_summaries)
            employees_with_incomplete = sum(1 for d in daily_summaries if d.has_incomplete_session)
            
            return {
                "date": date,
                "summary": {
                    "total_employees_worked": total_employees,
                    "total_hours": round(total_hours, 2),
                    "total_overtime_hours": round(total_overtime, 2),
                    "employees_with_incomplete_sessions": employees_with_incomplete
                },
                "employee_summaries": daily_summaries
            }
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error generating daily summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate daily summary")

@router.get("/payroll/weekly-report")
async def get_weekly_report(week_start: str):
    """Get weekly payroll report starting from given Monday"""
    try:
        start_date = datetime.strptime(week_start, '%Y-%m-%d')
        
        # Ensure it's a Monday
        if start_date.weekday() != 0:
            # Adjust to previous Monday
            days_since_monday = start_date.weekday()
            start_date = start_date - timedelta(days=days_since_monday)
        
        end_date = start_date + timedelta(days=6)  # Sunday
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all employees who worked this week
            cursor.execute('''
                SELECT DISTINCT e.employee_id, e.name
                FROM employees e
                JOIN time_entries te ON e.employee_id = te.employee_id
                WHERE date(te.timestamp) BETWEEN ? AND ?
                ORDER BY e.name
            ''', (start_str, end_str))
            
            employees = cursor.fetchall()
            weekly_reports = []
            employee_summaries = []
            
            for employee in employees:
                employee_id = employee['employee_id']
                employee_name = employee['name']
                
                # Get all time entries for this week
                cursor.execute('''
                    SELECT employee_id, clock_type, timestamp, wifi_network
                    FROM time_entries 
                    WHERE employee_id = ? 
                    AND date(timestamp) BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (employee_id, start_str, end_str))
                
                time_entries = [dict(row) for row in cursor.fetchall()]
                sessions = calculate_work_sessions(time_entries)
                employee_total_hours = 0
                # Add employee name
                for session in sessions:
                    session.employee_name = employee_name
                    if session.is_complete:
                       employee_total_hours += session.duration_hours
                payroll_summary = calculate_payroll_summary(sessions, start_str, end_str)
                if payroll_summary:
                    weekly_reports.append(payroll_summary)
                employee_summaries.append({
                    "name": employee_name,
                    "total hours": employee_total_hours
                })
            return {
                "week_start": start_str,
                "week_end": end_str,
                "summaries": employee_summaries,
                "employee_reports": weekly_reports
            }
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error generating weekly report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate weekly report")

@router.get("/payroll/monthly-report")
async def get_monthly_report(year: int, month: int):
    """Get monthly payroll report"""
    try:
        # Get first and last day of month
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, calendar.monthrange(year, month)[1])
        
        start_str = first_day.strftime('%Y-%m-%d')
        end_str = last_day.strftime('%Y-%m-%d')
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all employees who worked this month
            cursor.execute('''
                SELECT DISTINCT e.employee_id, e.name
                FROM employees e
                JOIN time_entries te ON e.employee_id = te.employee_id
                WHERE date(te.timestamp) BETWEEN ? AND ?
                ORDER BY e.name
            ''', (start_str, end_str))
            
            employees = cursor.fetchall()
            monthly_reports = []
            
            for employee in employees:
                employee_id = employee['employee_id']
                employee_name = employee['name']
                
                # Get all time entries for this month
                cursor.execute('''
                    SELECT employee_id, clock_type, timestamp, wifi_network
                    FROM time_entries 
                    WHERE employee_id = ? 
                    AND date(timestamp) BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (employee_id, start_str, end_str))
                
                time_entries = [dict(row) for row in cursor.fetchall()]
                sessions = calculate_work_sessions(time_entries)
                
                # Add employee name
                for session in sessions:
                    session.employee_name = employee_name
                
                payroll_summary = calculate_payroll_summary(sessions, start_str, end_str)
                if payroll_summary:
                    monthly_reports.append(payroll_summary)
            
            return {
                "year": year,
                "month": month,
                "month_name": calendar.month_name[month],
                "start_date": start_str,
                "end_date": end_str,
                "employee_reports": monthly_reports
            }
            
    except Exception as e:
        logger.error(f"Error generating monthly report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate monthly report")

@router.get("/payroll/all-employees")
async def get_all_employee_timesheets(
    start_date: str,
    end_date: str,
    format: str = "json"  # json or csv
):
    """Get timesheets for all employees in a date range"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all active employees
            cursor.execute("SELECT employee_id, name FROM employees WHERE active = TRUE")
            employees = cursor.fetchall()
            
            all_reports = []
            
            for employee in employees:
                employee_id = employee['employee_id']
                employee_name = employee['name']
                
                # Get time entries for this employee
                cursor.execute('''
                    SELECT employee_id, clock_type, timestamp, wifi_network
                    FROM time_entries 
                    WHERE employee_id = ? 
                    AND date(timestamp) BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (employee_id, start_date, end_date))
                
                time_entries = [dict(row) for row in cursor.fetchall()]
                
                if time_entries:  # Only include employees who worked
                    sessions = calculate_work_sessions(time_entries)
                    
                    # Add employee name
                    for session in sessions:
                        session.employee_name = employee_name
                    
                    payroll_summary = calculate_payroll_summary(sessions, start_date, end_date)
                    if payroll_summary:
                        all_reports.append(payroll_summary)
            
            if format.lower() == "csv":
                # Return CSV format for payroll systems
                return Response(
                    content=generate_payroll_csv(all_reports),
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=payroll_{start_date}_to_{end_date}.csv"}
                )
            
            return {
                "start_date": start_date,
                "end_date": end_date,
                "total_employees": len(all_reports),
                "employee_reports": all_reports
            }
            
    except Exception as e:
        logger.error(f"Error generating all employee timesheets: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate timesheets")

@router.get("/payroll/today")
async def get_today_summary():
    """Get today's summary - convenience endpoint"""
    today = datetime.now().strftime('%Y-%m-%d')
    return await get_daily_summary(today)

@router.get("/payroll/yesterday")
async def get_yesterday_summary():
    """Get yesterday's summary - convenience endpoint"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    return await get_daily_summary(yesterday)

@router.get("/payroll/this-week")
async def get_this_week_report():
    """Get this week's report - convenience endpoint"""
    today = datetime.now()
    # Get Monday of this week
    monday = today - timedelta(days=today.weekday())
    week_start = monday.strftime('%Y-%m-%d')
    return await get_weekly_report(week_start)

@router.get("/payroll/this-month")
async def get_this_month_report():
    """Get this month's report - convenience endpoint"""
    today = datetime.now()
    return await get_monthly_report(today.year, today.month)


@router.get("/payroll/employee/{employee_id}/biweekly-report/{period}")
async def get_employee_biweekly_report(
    employee_id: int,
    period: str,  # Format: "July2", "December1", etc.
    year: Optional[int] = None
):
    """
    Get biweekly timesheet report data for an employee
    
    Args:
        employee_id: Employee ID
        period: Period string like "July2" (July 16-31) or "March1" (March 1-15)
        year: Optional year, defaults to current year
    
    Returns:
        JSON with timesheet data and statistics
    """
    try:
        # Parse the period string
        biweekly_period = parse_period_string(period, year)
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get employee info
            cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
            employee = cursor.fetchone()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            employee_name = employee['name']
            
            # Get time entries for the biweekly period
            cursor.execute('''
                SELECT employee_id, clock_type, timestamp, wifi_network
                FROM time_entries 
                WHERE employee_id = ? 
                AND date(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (employee_id, biweekly_period.start_date_str, biweekly_period.end_date_str))
            
            time_entries = [dict(row) for row in cursor.fetchall()]
            
            # Calculate work sessions
            sessions = calculate_work_sessions(time_entries)
            
            # Add employee name to sessions
            for session in sessions:
                session.employee_name = employee_name
            
            # Calculate biweekly statistics
            stats = calculate_biweekly_stats(sessions)
            
            return {
                "employee_id": employee_id,
                "employee_name": employee_name,
                "period": biweekly_period.period_string,
                "date_range": biweekly_period.date_range_string,
                "start_date": biweekly_period.start_date_str,
                "end_date": biweekly_period.end_date_str,
                "statistics": stats,
                "sessions": [
                    {
                        "session_id": session.session_id,
                        "date": session.date,
                        "clock_in": session.clock_in.isoformat() if session.clock_in else None,
                        "clock_out": session.clock_out.isoformat() if session.clock_out else None,
                        "duration_hours": session.duration_hours,
                        "is_complete": session.is_complete,
                        "wifi_network_in": session.wifi_network_in,
                        "wifi_network_out": session.wifi_network_out
                    }
                    for session in sessions
                ]
            }
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating biweekly report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate biweekly report")

@router.get("/payroll/employee/{employee_id}/biweekly-report-html/{period}")
async def get_employee_biweekly_report_html(
    employee_id: int,
    period: str,  # Format: "July2", "December1", etc.
    year: Optional[int] = None,
    download: bool = False
):
    """
    Get biweekly timesheet report as standalone HTML file
    
    Args:
        employee_id: Employee ID
        period: Period string like "July2" (July 16-31) or "March1" (March 1-15)
        year: Optional year, defaults to current year
        download: If True, returns as downloadable file
    
    Returns:
        HTML content for the timesheet report
    """
    try:
        # Parse the period string
        biweekly_period = parse_period_string(period, year)
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get employee info
            cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
            employee = cursor.fetchone()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            employee_name = employee['name']
            
            # Get time entries for the biweekly period
            cursor.execute('''
                SELECT employee_id, clock_type, timestamp, wifi_network
                FROM time_entries 
                WHERE employee_id = ? 
                AND date(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (employee_id, biweekly_period.start_date_str, biweekly_period.end_date_str))
            
            time_entries = [dict(row) for row in cursor.fetchall()]
            
            # Calculate work sessions
            sessions = calculate_work_sessions(time_entries)
            
            # Add employee name to sessions
            for session in sessions:
                session.employee_name = employee_name
            
            # Calculate biweekly statistics
            stats = calculate_biweekly_stats(sessions)
            
            # Generate HTML report
            html_content = generate_biweekly_html_report(
                employee_name=employee_name,
                employee_id=employee_id,
                period=biweekly_period,
                sessions=sessions,
                stats=stats
            )
            
            # Set up response headers
            headers = {"Content-Type": "text/html; charset=utf-8"}
            
            if download:
                # Safe filename for download
                safe_name = employee_name.replace(" ", "_").replace("/", "-")
                filename = f"timesheet_{safe_name}_{biweekly_period.period_string}_{biweekly_period.year}.html"
                headers["Content-Disposition"] = f"attachment; filename={filename}"
            
            return Response(content=html_content, headers=headers)
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating biweekly HTML report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate biweekly HTML report")

# Convenience endpoints for current periods

@router.get("/payroll/employee/{employee_id}/current-biweekly-report")
async def get_current_biweekly_report(employee_id: int):
    """Get biweekly report for current pay period"""
    today = datetime.now()
    
    # Determine which half of the month we're in
    if today.day <= 15:
        period = f"{calendar.month_name[today.month]}1"
    else:
        period = f"{calendar.month_name[today.month]}2"
    
    return await get_employee_biweekly_report(employee_id, period, today.year)

@router.get("/payroll/employee/{employee_id}/current-biweekly-report-html")
async def get_current_biweekly_report_html(employee_id: int, download: bool = False):
    """Get HTML biweekly report for current pay period"""
    today = datetime.now()
    
    # Determine which half of the month we're in
    if today.day <= 15:
        period = f"{calendar.month_name[today.month]}1"
    else:
        period = f"{calendar.month_name[today.month]}2"
    
    return await get_employee_biweekly_report_html(employee_id, period, today.year, download)

@router.get("/payroll/employee/{employee_id}/previous-biweekly-report")
async def get_previous_biweekly_report(employee_id: int):
    """Get biweekly report for previous pay period"""
    today = datetime.now()
    
    # Determine previous period
    if today.day <= 15:
        # Current period is first half, previous is second half of last month
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        period = f"{calendar.month_name[prev_month]}2"
    else:
        # Current period is second half, previous is first half of this month
        period = f"{calendar.month_name[today.month]}1"
        prev_year = today.year
    
    return await get_employee_biweekly_report(employee_id, period, prev_year)

# Batch endpoints for multiple employees

@router.get("/payroll/all-employees/biweekly-reports/{period}")
async def get_all_employees_biweekly_reports(
    period: str,
    year: Optional[int] = None,
    active_only: bool = True
):
    """Get biweekly reports for all employees"""
    try:
        biweekly_period = parse_period_string(period, year)
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all employees
            active_filter = "AND active = TRUE" if active_only else ""
            cursor.execute(f"SELECT employee_id, name FROM employees WHERE 1=1 {active_filter} ORDER BY name")
            employees = cursor.fetchall()
            
            all_reports = []
            
            for employee in employees:
                employee_id = employee['employee_id']
                employee_name = employee['name']
                
                # Get time entries for this employee
                cursor.execute('''
                    SELECT employee_id, clock_type, timestamp, wifi_network
                    FROM time_entries 
                    WHERE employee_id = ? 
                    AND date(timestamp) BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (employee_id, biweekly_period.start_date_str, biweekly_period.end_date_str))
                
                time_entries = [dict(row) for row in cursor.fetchall()]
                
                if time_entries:  # Only include employees who worked
                    sessions = calculate_work_sessions(time_entries)
                    
                    # Add employee name
                    for session in sessions:
                        session.employee_name = employee_name
                    
                    stats = calculate_biweekly_stats(sessions)
                    
                    all_reports.append({
                        "employee_id": employee_id,
                        "employee_name": employee_name,
                        "statistics": stats,
                        "sessions_count": len(sessions)
                    })
            
            return {
                "period": biweekly_period.period_string,
                "date_range": biweekly_period.date_range_string,
                "start_date": biweekly_period.start_date_str,
                "end_date": biweekly_period.end_date_str,
                "total_employees": len(all_reports),
                "employee_reports": all_reports
            }
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating all employee biweekly reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate biweekly reports")
