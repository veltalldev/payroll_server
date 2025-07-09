import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from app.core.config import ServerConfig, WiFiConfig # Import configs
from app.core.database import get_db # Import get_db
from app.core.security import admin_auth # Import security dependency
from app.models.admin import ManualTimeEntry, TimeEntryEdit, TimeEntryCreate, ProblemTimeEntry # Import admin models
from app.services.admin_service import detect_time_entry_problems # Import service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/admin/wifi-config", dependencies=[Depends(admin_auth)])
async def get_wifi_config():
    """Get current WiFi verification configuration"""
    return {
        "wifi_verification_enabled": WiFiConfig.WIFI_VERIFICATION_ENABLED,
        "approved_networks": WiFiConfig.APPROVED_WORKPLACE_NETWORKS,
        "pattern_matching_enabled": WiFiConfig.WIFI_PATTERN_MATCHING_ENABLED,
        "approved_patterns": WiFiConfig.APPROVED_NETWORK_PATTERNS,
        "allow_manual_override": WiFiConfig.ALLOW_MANUAL_OVERRIDE,
    }

@router.get("/admin/wifi-attempts", dependencies=[Depends(admin_auth)])
async def get_wifi_verification_attempts(days: int = 7, employee_id: Optional[int] = None):
    """Get WiFi verification attempts for monitoring"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT wvl.*, e.name, e.employee_number
            FROM wifi_verification_log wvl
            JOIN employees e ON wvl.employee_id = e.employee_id
            WHERE wvl.timestamp >= datetime('now', '-{} days')
        '''.format(days)
        
        params = []
        if employee_id:
            query += " AND wvl.employee_id = ?"
            params.append(employee_id)
        
        query += " ORDER BY wvl.timestamp DESC LIMIT 1000"
        
        cursor.execute(query, params)
        attempts = cursor.fetchall()
        
        return {
            "total_attempts": len(attempts),
            "success_rate": sum(1 for a in attempts if a['success']) / len(attempts) if attempts else 0,
            "attempts": [dict(attempt) for attempt in attempts]
        }

@router.post("/admin/manual-entry", dependencies=[Depends(admin_auth)])
async def create_manual_time_entry(entry: ManualTimeEntry):
    """Create manual time entry for network outages or emergencies"""
    
    # Validate employee exists
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT employee_id, name FROM employees WHERE employee_id = ? AND active = TRUE",
            (entry.employee_id,)
        )
        employee = cursor.fetchone()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found or inactive")
        
        # Create manual entry with special QR code
        manual_qr = f"MANUAL_OVERRIDE_{entry.reason}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        cursor.execute('''
            INSERT INTO time_entries (employee_id, clock_type, timestamp, qr_code_used, wifi_network)
            VALUES (?, ?, ?, ?, ?)
        ''', (entry.employee_id, entry.clock_type, entry.timestamp.isoformat(), manual_qr, "MANUAL_OVERRIDE"))
        
        conn.commit()
        
        logger.info(f"Manual {entry.clock_type} entry created for employee {entry.employee_id} ({employee['name']}) - Reason: {entry.reason}")
        
        return {
            "success": True,
            "message": f"Manual {entry.clock_type} entry created for {employee['name']}",
            "employee_name": employee['name'],
            "clock_type": entry.clock_type,
            "timestamp": entry.timestamp.isoformat(),
            "reason": entry.reason
        }

@router.get("/admin/time-entries/problems", dependencies=[Depends(admin_auth)])
async def get_time_entry_problems(
    employee_id: Optional[int] = None,
    start_date: str = None,
    end_date: str = None,
    days_back: int = 7
):
    """Detect problematic time entries"""
    
    # Default date range
    if not start_date or not end_date:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days_back)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')
    
    try:
        all_problems = []
        
        if employee_id:
            # Check specific employee
            problems = detect_time_entry_problems(employee_id, start_date, end_date)
            all_problems.extend(problems)
        else:
            # Check all employees
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT employee_id FROM employees WHERE active = TRUE")
                employees = cursor.fetchall()
                
                for emp in employees:
                    problems = detect_time_entry_problems(emp['employee_id'], start_date, end_date)
                    all_problems.extend(problems)
        
        # Group by problem type for summary
        problem_summary = {}
        for problem in all_problems:
            prob_type = problem.problem_type
            if prob_type not in problem_summary:
                problem_summary[prob_type] = 0
            problem_summary[prob_type] += 1
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_problems": len(all_problems),
            "problem_summary": problem_summary,
            "problems": all_problems
        }
        
    except Exception as e:
        logger.error(f"Error detecting time entry problems: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect problems")

@router.get("/admin/time-entries", dependencies=[Depends(admin_auth)])
async def get_raw_time_entries(
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """Get raw time entries for editing"""
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Build query
            where_conditions = []
            params = []
            
            if employee_id:
                where_conditions.append("te.employee_id = ?")
                params.append(employee_id)
            
            if start_date:
                where_conditions.append("date(te.timestamp) >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("date(te.timestamp) <= ?")
                params.append(end_date)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f'''
                SELECT te.entry_id, te.employee_id, e.name as employee_name, 
                       te.clock_type, te.timestamp, te.wifi_network, te.qr_code_used
                FROM time_entries te
                JOIN employees e ON te.employee_id = e.employee_id
                {where_clause}
                ORDER BY te.timestamp DESC
                LIMIT ?
            '''
            params.append(limit)
            
            cursor.execute(query, params)
            entries = [dict(row) for row in cursor.fetchall()]
            
            return {
                "total_entries": len(entries),
                "entries": entries
            }
            
    except Exception as e:
        logger.error(f"Error fetching time entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch time entries")

@router.put("/admin/time-entries/{entry_id}", dependencies=[Depends(admin_auth)])
async def edit_time_entry(entry_id: int, edit_data: TimeEntryEdit):
    """Edit an existing time entry"""
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Verify entry exists
            cursor.execute("SELECT * FROM time_entries WHERE entry_id = ?", (entry_id,))
            existing_entry = cursor.fetchone()
            
            if not existing_entry:
                raise HTTPException(status_code=404, detail="Time entry not found")
            
            # Update the entry
            cursor.execute('''
                UPDATE time_entries 
                SET clock_type = ?, timestamp = ?
                WHERE entry_id = ?
            ''', (edit_data.new_clock_type, edit_data.new_timestamp.isoformat(), entry_id))
            
            # Log the admin action
            logger.info(f"Admin edited time entry {entry_id}: {edit_data.admin_notes}")
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"Time entry {entry_id} updated successfully",
                "admin_notes": edit_data.admin_notes
            }
            
    except Exception as e:
        logger.error(f"Error editing time entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to edit time entry")

@router.post("/admin/time-entries", dependencies=[Depends(admin_auth)])
async def create_time_entry(entry_data: TimeEntryCreate):
    """Create a new time entry (for missing punches)"""
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Verify employee exists
            cursor.execute("SELECT name FROM employees WHERE employee_id = ? AND active = TRUE", 
                           (entry_data.employee_id,))
            employee = cursor.fetchone()
            
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found or inactive")
            
            # Create special QR code for admin entries
            admin_qr = f"ADMIN_CREATED_{entry_data.employee_id}_{entry_data.timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            # Insert the entry
            cursor.execute('''
                INSERT INTO time_entries (employee_id, clock_type, timestamp, qr_code_used, wifi_network)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                entry_data.employee_id, 
                entry_data.clock_type, 
                entry_data.timestamp.isoformat(),
                admin_qr,
                entry_data.wifi_network
            ))
            
            entry_id = cursor.lastrowid
            
            # Log the admin action
            logger.info(f"Admin created time entry for employee {entry_data.employee_id}: {entry_data.admin_notes}")
            
            conn.commit()
            
            return {
                "success": True,
                "entry_id": entry_id,
                "message": f"Time entry created for {employee['name']}",
                "admin_notes": entry_data.admin_notes
            }
            
    except Exception as e:
        logger.error(f"Error creating time entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to create time entry")

@router.delete("/admin/time-entries/{entry_id}", dependencies=[Depends(admin_auth)])
async def delete_time_entry(entry_id: int, reason: str):
    """Delete a time entry (for double punches)"""
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get entry details for logging
            cursor.execute('''
                SELECT te.*, e.name 
                FROM time_entries te 
                JOIN employees e ON te.employee_id = e.employee_id 
                WHERE te.entry_id = ?
            ''', (entry_id,))
            entry = cursor.fetchone()
            
            if not entry:
                raise HTTPException(status_code=404, detail="Time entry not found")
            
            # Delete the entry
            cursor.execute("DELETE FROM time_entries WHERE entry_id = ?", (entry_id,))
            
            # Log the admin action
            logger.info(f"Admin deleted time entry {entry_id} for {entry['name']}: {reason}")
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"Time entry deleted for {entry['name']}",
                "reason": reason
            }
            
    except Exception as e:
        logger.error(f"Error deleting time entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete time entry")

@router.get("/admin/time-entries/employee/{employee_id}/raw", dependencies=[Depends(admin_auth)])
async def get_employee_raw_entries(
    employee_id: int, 
    start_date: str, 
    end_date: str
):
    """Get raw time entries for a specific employee - useful for editing"""
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get employee info
            cursor.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
            employee = cursor.fetchone()
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")
            
            # Get entries
            cursor.execute('''
                SELECT entry_id, employee_id, clock_type, timestamp, wifi_network, qr_code_used
                FROM time_entries 
                WHERE employee_id = ? 
                AND date(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (employee_id, start_date, end_date))
            
            entries = [dict(row) for row in cursor.fetchall()]
            
            # Detect problems for this employee
            problems = detect_time_entry_problems(employee_id, start_date, end_date)
            
            return {
                "employee_id": employee_id,
                "employee_name": employee['name'],
                "start_date": start_date,
                "end_date": end_date,
                "total_entries": len(entries),
                "entries": entries,
                "problems": problems,
                "has_problems": len(problems) > 0
            }
            
    except Exception as e:
        logger.error(f"Error fetching employee raw entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch entries")

@router.post("/admin/time-entries/quick-fix/missing-punch", dependencies=[Depends(admin_auth)])
async def quick_fix_missing_punch(
    employee_id: int,
    missing_type: str,  # "IN" or "OUT"
    estimated_time: datetime,
    reason: str = "Missing punch - admin estimated"
):
    """Quick fix for missing punch"""
    
    entry_data = TimeEntryCreate(
        employee_id=employee_id,
        clock_type=missing_type,
        timestamp=estimated_time,
        admin_notes=f"Quick fix: {reason}",
        wifi_network="ADMIN_ESTIMATED"
    )
    
    # We call the create_time_entry endpoint directly to reuse its logic
    return await create_time_entry(entry_data)

@router.post("/admin/time-entries/bulk-delete", dependencies=[Depends(admin_auth)])
async def bulk_delete_entries(
    entry_ids: List[int],
    reason: str = "Bulk cleanup"
):
    """Delete multiple entries at once (for cleaning up test data)"""
    
    try:
        deleted_count = 0
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            for entry_id in entry_ids:
                cursor.execute("DELETE FROM time_entries WHERE entry_id = ?", (entry_id,))
                if cursor.rowcount > 0:
                    deleted_count += 1
            
            conn.commit()
            
            logger.info(f"Admin bulk deleted {deleted_count} time entries: {reason}")
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "reason": reason
            }
            
    except Exception as e:
        logger.error(f"Error bulk deleting entries: {e}")
        raise HTTPException(status_code=500, detail="Failed to bulk delete entries")
