"""
Employee Lookup Service
Provides methods to search and retrieve employee details by code, name, or ID.
Connects directly to the Oryggi database (same as Access Control API).
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from loguru import logger
import pyodbc
import os


@dataclass
class EmployeeInfo:
    """Employee information data class"""
    ecode: int
    corp_emp_code: str
    name: str
    department: Optional[str] = None
    designation: Optional[str] = None
    card_no: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "ecode": self.ecode,
            "corp_emp_code": self.corp_emp_code,
            "name": self.name,
            "department": self.department,
            "designation": self.designation,
            "card_no": self.card_no,
            "email": self.email,
            "phone": self.phone,
            "active": self.active
        }


class EmployeeLookupService:
    """
    Service for looking up employee details from the Oryggi database.
    Uses direct pyodbc connection to the same database as Access Control API.

    Supports search by:
    - CorpEmpCode (employee code like "28734")
    - Employee name (like "cv", "John Smith")
    - Card number
    """

    # Connection string built from environment variables
    @staticmethod
    def _build_connection_string() -> str:
        """Build connection string from environment variables"""
        driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        server = os.getenv("DB_SERVER", "DESKTOP-UOD2VBS")
        instance = os.getenv("DB_INSTANCE", "MSSQLSERVER2022")
        db_name = os.getenv("DB_NAME", "Oryggi")
        use_windows_auth = os.getenv("DB_USE_WINDOWS_AUTH", "True").lower() == "true"

        server_str = f"{server}\\{instance}" if instance else server

        if use_windows_auth:
            return (
                f"DRIVER={{{driver}}};"
                f"SERVER={server_str};"
                f"DATABASE={db_name};"
                f"Trusted_Connection=yes;"
            )
        else:
            username = os.getenv("DB_USERNAME", "sa")
            password = os.getenv("DB_PASSWORD", "")
            return (
                f"DRIVER={{{driver}}};"
                f"SERVER={server_str};"
                f"DATABASE={db_name};"
                f"UID={username};"
                f"PWD={password};"
            )

    def __init__(self):
        """Initialize the lookup service"""
        pass

    def _get_connection(self) -> pyodbc.Connection:
        """Get a database connection to Oryggi database"""
        conn_str = self._build_connection_string()
        logger.debug(f"[EMPLOYEE_LOOKUP] Connecting with: SERVER={os.getenv('DB_SERVER')}, DB={os.getenv('DB_NAME')}")
        return pyodbc.connect(conn_str)

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a query and return results as list of dictionaries"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            cursor.close()
            conn.close()
            return results
        except Exception as e:
            logger.error(f"[EMPLOYEE_LOOKUP] Database error: {e}")
            return []

    def _execute_query_single(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute a query and return single result as dictionary"""
        results = self._execute_query(query, params)
        return results[0] if results else None

    async def get_employee_by_identifier(self, identifier: str) -> Optional[EmployeeInfo]:
        """
        Look up employee by any identifier (code, name, or card number).
        Tries multiple search strategies in order.

        Args:
            identifier: Employee code, name, or card number

        Returns:
            EmployeeInfo if found, None otherwise
        """
        if not identifier:
            return None

        identifier = str(identifier).strip()
        logger.info(f"[EMPLOYEE_LOOKUP] Looking up employee by identifier: {identifier}")

        # Strategy 1: Try exact match on CorpEmpCode
        employee = await self._get_by_corp_emp_code(identifier)
        if employee:
            logger.info(f"[EMPLOYEE_LOOKUP] Found by CorpEmpCode: {employee.name} ({employee.corp_emp_code})")
            return employee

        # Strategy 2: Try exact match on card number
        employee = await self._get_by_card_number(identifier)
        if employee:
            logger.info(f"[EMPLOYEE_LOOKUP] Found by CardNo: {employee.name} ({employee.corp_emp_code})")
            return employee

        # Strategy 3: Try name search (exact or partial)
        employees = await self._search_by_name(identifier)
        if employees:
            if len(employees) == 1:
                employee = employees[0]
                logger.info(f"[EMPLOYEE_LOOKUP] Found by name: {employee.name} ({employee.corp_emp_code})")
                return employee
            else:
                # Multiple matches - return the first one but log warning
                logger.warning(f"[EMPLOYEE_LOOKUP] Multiple employees found for '{identifier}': {[e.name for e in employees]}")
                return employees[0]

        logger.warning(f"[EMPLOYEE_LOOKUP] No employee found for identifier: {identifier}")
        return None

    async def _get_by_corp_emp_code(self, code: str) -> Optional[EmployeeInfo]:
        """Look up employee by CorpEmpCode"""
        try:
            query = """
                SELECT
                    e.Ecode,
                    e.CorpEmpCode,
                    e.EmpName,
                    des.DesName as Designation,
                    ecr.CardNo,
                    e.E_mail,
                    e.Telephone1,
                    e.Active
                FROM EmployeeMaster e
                LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                WHERE e.CorpEmpCode = ?
            """
            result = self._execute_query_single(query, (code,))
            if result:
                return self._row_to_employee_info(result)
            return None
        except Exception as e:
            logger.error(f"[EMPLOYEE_LOOKUP] Error looking up by CorpEmpCode: {e}")
            return None

    async def _get_by_card_number(self, card_no: str) -> Optional[EmployeeInfo]:
        """Look up employee by card number"""
        try:
            query = """
                SELECT
                    e.Ecode,
                    e.CorpEmpCode,
                    e.EmpName,
                    des.DesName as Designation,
                    ecr.CardNo,
                    e.E_mail,
                    e.Telephone1,
                    e.Active
                FROM EmployeeMaster e
                LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                WHERE ecr.CardNo = ?
            """
            result = self._execute_query_single(query, (card_no,))
            if result:
                return self._row_to_employee_info(result)
            return None
        except Exception as e:
            logger.error(f"[EMPLOYEE_LOOKUP] Error looking up by CardNo: {e}")
            return None

    async def _search_by_name(self, name: str) -> List[EmployeeInfo]:
        """Search employees by name (exact or partial match)"""
        try:
            # First try exact match
            query = """
                SELECT
                    e.Ecode,
                    e.CorpEmpCode,
                    e.EmpName,
                    des.DesName as Designation,
                    ecr.CardNo,
                    e.E_mail,
                    e.Telephone1,
                    e.Active
                FROM EmployeeMaster e
                LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                WHERE LOWER(e.EmpName) = LOWER(?)
            """
            results = self._execute_query(query, (name,))
            if results:
                return [self._row_to_employee_info(r) for r in results]

            # If no exact match, try partial match
            query_partial = """
                SELECT
                    e.Ecode,
                    e.CorpEmpCode,
                    e.EmpName,
                    des.DesName as Designation,
                    ecr.CardNo,
                    e.E_mail,
                    e.Telephone1,
                    e.Active
                FROM EmployeeMaster e
                LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                WHERE LOWER(e.EmpName) LIKE LOWER(?)
            """
            results = self._execute_query(query_partial, (f"%{name}%",))
            return [self._row_to_employee_info(r) for r in results] if results else []

        except Exception as e:
            logger.error(f"[EMPLOYEE_LOOKUP] Error searching by name: {e}")
            return []

    def _row_to_employee_info(self, row: Dict) -> EmployeeInfo:
        """Convert database row to EmployeeInfo object"""
        return EmployeeInfo(
            ecode=row.get("Ecode") or row.get("ecode", 0),
            corp_emp_code=str(row.get("CorpEmpCode") or row.get("corp_emp_code", "")),
            name=row.get("EmpName") or row.get("empname") or row.get("name", "Unknown"),
            department=row.get("Department") or row.get("department"),
            designation=row.get("Designation") or row.get("designation"),
            card_no=row.get("CardNo") or row.get("card_no"),
            email=row.get("E_mail") or row.get("email"),
            phone=row.get("Telephone1") or row.get("phone"),
            active=bool(row.get("Active", True))
        )

    async def search_employees(self, search_term: str, limit: int = 5) -> List[EmployeeInfo]:
        """
        Search employees by name or code (for disambiguation).

        Args:
            search_term: Search term
            limit: Maximum results to return

        Returns:
            List of matching employees
        """
        try:
            query = f"""
                SELECT TOP {limit}
                    e.Ecode,
                    e.CorpEmpCode,
                    e.EmpName,
                    des.DesName as Designation,
                    ecr.CardNo,
                    e.E_mail,
                    e.Telephone1,
                    e.Active
                FROM EmployeeMaster e
                LEFT JOIN DesignationMaster des ON e.DesCode = des.DesCode
                LEFT JOIN Employee_Card_Relation ecr ON e.Ecode = ecr.ECode AND ecr.Status = 1
                WHERE
                    LOWER(e.EmpName) LIKE LOWER(?)
                    OR e.CorpEmpCode LIKE ?
                ORDER BY e.EmpName
            """
            pattern = f"%{search_term}%"
            results = self._execute_query(query, (pattern, pattern))
            return [self._row_to_employee_info(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"[EMPLOYEE_LOOKUP] Error searching employees: {e}")
            return []


# Global instance
employee_lookup_service = EmployeeLookupService()
