# app/api/endpoints/employees.py - FIXED VERSION
import logging
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from fastapi import APIRouter, HTTPException
from app.core.database import get_db
from app.models.common import Employee, TimeEntry

router = APIRouter()
logger = logging.getLogger(__name__)

# Add the missing models that match the client expectations
class LastAction(BaseModel):
    clock_type: str
    timestamp: datetime
    wifi_network: Optional[str] = None
    formatted_time: str

class CurrentStatus(BaseModel):
    is_clocked_in: bool
    status_text: str
    next_action: str
    next_action_text: str

class EmployeeLastAction(BaseModel):
    employee_id: int
    employee_name: str
    has_previous_action: bool
    last_action: Optional[LastAction] = None
    current_status: CurrentStatus

@router.get("/employees", response_model=List[Employee])
async def list_employees():
    """List all employees"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE active = TRUE ORDER BY name")
        employees = cursor.fetchall()
        
        return [
            Employee(
                employee_id=emp['employee_id'],
                name=emp['name'],
                employee_number=emp['employee_number'],
                created_at=datetime.fromisoformat(emp['created_at']),
                active=bool(emp['active'])
            )
            for emp in employees
        ]

@router.get("/employees/by_id/{employee_id}", response_model=Employee)
async def get_employee_by_id(employee_id: int):
    """Get a single employee by employee_id"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT employee_id, name, employee_number, created_at, active 
            FROM employees 
            WHERE employee_id = ? 
        ''', (employee_id,))
        emp = cursor.fetchone()
        
        if emp is None:
            raise HTTPException(status_code=404, detail=f"Employee with ID {employee_id} not found.")
        
        return Employee(
            employee_id=emp['employee_id'],
            name=emp['name'],
            employee_number=emp['employee_number'],
            created_at=datetime.fromisoformat(emp['created_at']),
            active=bool(emp['active'])
        )

@router.get("/employees/{employee_id}/entries", response_model=List[TimeEntry])
async def get_employee_entries(employee_id: int, limit: int = 50):
    """Get recent time entries for an employee"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM time_entries 
            WHERE employee_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (employee_id, limit))
        
        entries = cursor.fetchall()
        
        return [
            TimeEntry(
                entry_id=entry['entry_id'],
                employee_id=entry['employee_id'],
                clock_type=entry['clock_type'],
                timestamp=datetime.fromisoformat(entry['timestamp']),
                qr_code_used=entry['qr_code_used'],
                synced_to_cloud=bool(entry['synced_to_cloud']),
                wifi_network=entry.get('wifi_network')
            )
            for entry in entries
        ]

@router.get("/employees/{employee_id}/last_action", response_model=EmployeeLastAction)
async def get_employee_last_action(employee_id: int):
    """Get the most recent time entry for a specific employee with computed status."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get employee info
        cursor.execute("SELECT name FROM employees WHERE employee_id = ? AND active = TRUE", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found or inactive")
        
        employee_name = employee['name']
        
        # Get the most recent time entry
        cursor.execute(
            "SELECT * FROM time_entries WHERE employee_id = ? ORDER BY timestamp DESC LIMIT 1",
            (employee_id,)
        )
        last_entry = cursor.fetchone()

        if not last_entry:
            # No previous actions
            return EmployeeLastAction(
                employee_id=employee_id,
                employee_name=employee_name,
                has_previous_action=False,
                last_action=None,
                current_status=CurrentStatus(
                    is_clocked_in=False,
                    status_text="Ready to clock in",
                    next_action="IN",
                    next_action_text="Clock In"
                )
            )
        
        # Format the timestamp for display
        entry_timestamp = datetime.fromisoformat(last_entry['timestamp'])
        formatted_time = entry_timestamp.strftime('%I:%M %p')
        
        # Create LastAction
        last_action = LastAction(
            clock_type=last_entry['clock_type'],
            timestamp=entry_timestamp,
            wifi_network=last_entry['wifi_network'],
            formatted_time=formatted_time
        )
        
        # Determine current status based on last action
        is_clocked_in = last_entry['clock_type'] == 'IN'
        
        if is_clocked_in:
            status_text = f"Clocked in since {formatted_time}"
            next_action = "OUT"
            next_action_text = "Clock Out"
        else:
            status_text = f"Clocked out at {formatted_time}"
            next_action = "IN"
            next_action_text = "Clock In"
        
        current_status = CurrentStatus(
            is_clocked_in=is_clocked_in,
            status_text=status_text,
            next_action=next_action,
            next_action_text=next_action_text
        )
        
        return EmployeeLastAction(
            employee_id=employee_id,
            employee_name=employee_name,
            has_previous_action=True,
            last_action=last_action,
            current_status=current_status
        )
