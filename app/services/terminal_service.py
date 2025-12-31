"""
Terminal Service
Provides methods to retrieve terminal/door information and manage terminal groups.
Connects directly to the Oryggi database (same pattern as Employee Lookup Service).
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from loguru import logger
import pyodbc


@dataclass
class TerminalInfo:
    """Terminal/Door information data class"""
    terminal_id: int
    terminal_name: str
    location: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    is_active: bool = True
    terminal_group_id: Optional[int] = None
    terminal_group_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "terminal_id": self.terminal_id,
            "terminal_name": self.terminal_name,
            "location": self.location,
            "device_type": self.device_type,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "is_active": self.is_active,
            "terminal_group_id": self.terminal_group_id,
            "terminal_group_name": self.terminal_group_name
        }


@dataclass
class TerminalGroupInfo:
    """Terminal Group/Zone information data class"""
    group_id: int
    group_name: str
    description: Optional[str] = None
    terminal_count: int = 0
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "group_id": self.group_id,
            "group_name": self.group_name,
            "description": self.description,
            "terminal_count": self.terminal_count,
            "is_active": self.is_active
        }


class TerminalService:
    """
    Service for managing terminal/door information from the Oryggi database.
    Uses direct pyodbc connection to the same database as Access Control API.

    Supports:
    - Get all terminals/doors
    - Get terminal by ID or name
    - Get terminal groups/zones
    - Get terminals by group
    - Search terminals by name/location
    """

    # Connection string to Oryggi database (same as Access Control API)
    CONN_STR = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
        "DATABASE=Oryggi;"
        "Trusted_Connection=yes;"
    )

    def __init__(self):
        """Initialize the terminal service"""
        pass

    def _get_connection(self) -> pyodbc.Connection:
        """Get a database connection to Oryggi database"""
        return pyodbc.connect(self.CONN_STR)

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
            logger.error(f"[TERMINAL_SERVICE] Database error: {e}")
            return []

    def _execute_query_single(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute a query and return single result as dictionary"""
        results = self._execute_query(query, params)
        return results[0] if results else None

    async def get_all_terminals(self, active_only: bool = True) -> List[TerminalInfo]:
        """
        Get all terminals/doors from the database.

        Args:
            active_only: If True, only return active terminals

        Returns:
            List of TerminalInfo objects
        """
        try:
            query = """
                SELECT
                    t.TerminalID,
                    t.TerminalName,
                    t.Location,
                    t.DeviceType,
                    t.IP_Address,
                    t.MAC_Address,
                    t.Active,
                    tg.TerminalGroupID,
                    tg.TerminalGroupName
                FROM TerminalMaster t
                LEFT JOIN TerminalGroupRelation tgr ON t.TerminalID = tgr.TerminalID
                LEFT JOIN TerminalGroup tg ON tgr.TerminalGroupID = tg.TerminalGroupID
            """
            if active_only:
                query += " WHERE t.Active = 1"
            query += " ORDER BY t.TerminalName"

            results = self._execute_query(query)
            terminals = [self._row_to_terminal_info(r) for r in results]
            logger.info(f"[TERMINAL_SERVICE] Retrieved {len(terminals)} terminals")
            return terminals
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error getting all terminals: {e}")
            return []

    async def get_terminal_by_id(self, terminal_id: int) -> Optional[TerminalInfo]:
        """
        Get a specific terminal by its ID.

        Args:
            terminal_id: The terminal ID

        Returns:
            TerminalInfo if found, None otherwise
        """
        try:
            query = """
                SELECT
                    t.TerminalID,
                    t.TerminalName,
                    t.Location,
                    t.DeviceType,
                    t.IP_Address,
                    t.MAC_Address,
                    t.Active,
                    tg.TerminalGroupID,
                    tg.TerminalGroupName
                FROM TerminalMaster t
                LEFT JOIN TerminalGroupRelation tgr ON t.TerminalID = tgr.TerminalID
                LEFT JOIN TerminalGroup tg ON tgr.TerminalGroupID = tg.TerminalGroupID
                WHERE t.TerminalID = ?
            """
            result = self._execute_query_single(query, (terminal_id,))
            if result:
                return self._row_to_terminal_info(result)
            return None
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error getting terminal by ID: {e}")
            return None

    async def get_terminal_by_name(self, terminal_name: str) -> Optional[TerminalInfo]:
        """
        Get a specific terminal by its name (case-insensitive).

        Args:
            terminal_name: The terminal name

        Returns:
            TerminalInfo if found, None otherwise
        """
        try:
            query = """
                SELECT
                    t.TerminalID,
                    t.TerminalName,
                    t.Location,
                    t.DeviceType,
                    t.IP_Address,
                    t.MAC_Address,
                    t.Active,
                    tg.TerminalGroupID,
                    tg.TerminalGroupName
                FROM TerminalMaster t
                LEFT JOIN TerminalGroupRelation tgr ON t.TerminalID = tgr.TerminalID
                LEFT JOIN TerminalGroup tg ON tgr.TerminalGroupID = tg.TerminalGroupID
                WHERE LOWER(t.TerminalName) = LOWER(?)
            """
            result = self._execute_query_single(query, (terminal_name,))
            if result:
                return self._row_to_terminal_info(result)
            return None
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error getting terminal by name: {e}")
            return None

    async def search_terminals(self, search_term: str, limit: int = 10) -> List[TerminalInfo]:
        """
        Search terminals by name or location.

        Args:
            search_term: Search term
            limit: Maximum results to return

        Returns:
            List of matching terminals
        """
        try:
            query = f"""
                SELECT TOP {limit}
                    t.TerminalID,
                    t.TerminalName,
                    t.Location,
                    t.DeviceType,
                    t.IP_Address,
                    t.MAC_Address,
                    t.Active,
                    tg.TerminalGroupID,
                    tg.TerminalGroupName
                FROM TerminalMaster t
                LEFT JOIN TerminalGroupRelation tgr ON t.TerminalID = tgr.TerminalID
                LEFT JOIN TerminalGroup tg ON tgr.TerminalGroupID = tg.TerminalGroupID
                WHERE
                    LOWER(t.TerminalName) LIKE LOWER(?)
                    OR LOWER(t.Location) LIKE LOWER(?)
                ORDER BY t.TerminalName
            """
            pattern = f"%{search_term}%"
            results = self._execute_query(query, (pattern, pattern))
            return [self._row_to_terminal_info(r) for r in results]
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error searching terminals: {e}")
            return []

    async def get_all_terminal_groups(self, active_only: bool = True) -> List[TerminalGroupInfo]:
        """
        Get all terminal groups/zones from the database.

        Args:
            active_only: If True, only return active groups

        Returns:
            List of TerminalGroupInfo objects
        """
        try:
            query = """
                SELECT
                    tg.TerminalGroupID,
                    tg.TerminalGroupName,
                    tg.Description,
                    tg.Active,
                    COUNT(tgr.TerminalID) as TerminalCount
                FROM TerminalGroup tg
                LEFT JOIN TerminalGroupRelation tgr ON tg.TerminalGroupID = tgr.TerminalGroupID
            """
            if active_only:
                query += " WHERE tg.Active = 1"
            query += " GROUP BY tg.TerminalGroupID, tg.TerminalGroupName, tg.Description, tg.Active"
            query += " ORDER BY tg.TerminalGroupName"

            results = self._execute_query(query)
            groups = [self._row_to_terminal_group_info(r) for r in results]
            logger.info(f"[TERMINAL_SERVICE] Retrieved {len(groups)} terminal groups")
            return groups
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error getting terminal groups: {e}")
            return []

    async def get_terminal_group_by_id(self, group_id: int) -> Optional[TerminalGroupInfo]:
        """
        Get a specific terminal group by its ID.

        Args:
            group_id: The terminal group ID

        Returns:
            TerminalGroupInfo if found, None otherwise
        """
        try:
            query = """
                SELECT
                    tg.TerminalGroupID,
                    tg.TerminalGroupName,
                    tg.Description,
                    tg.Active,
                    COUNT(tgr.TerminalID) as TerminalCount
                FROM TerminalGroup tg
                LEFT JOIN TerminalGroupRelation tgr ON tg.TerminalGroupID = tgr.TerminalGroupID
                WHERE tg.TerminalGroupID = ?
                GROUP BY tg.TerminalGroupID, tg.TerminalGroupName, tg.Description, tg.Active
            """
            result = self._execute_query_single(query, (group_id,))
            if result:
                return self._row_to_terminal_group_info(result)
            return None
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error getting terminal group by ID: {e}")
            return None

    async def get_terminals_by_group(self, group_id: int) -> List[TerminalInfo]:
        """
        Get all terminals in a specific terminal group.

        Args:
            group_id: The terminal group ID

        Returns:
            List of TerminalInfo objects in the group
        """
        try:
            query = """
                SELECT
                    t.TerminalID,
                    t.TerminalName,
                    t.Location,
                    t.DeviceType,
                    t.IP_Address,
                    t.MAC_Address,
                    t.Active,
                    tg.TerminalGroupID,
                    tg.TerminalGroupName
                FROM TerminalMaster t
                INNER JOIN TerminalGroupRelation tgr ON t.TerminalID = tgr.TerminalID
                INNER JOIN TerminalGroup tg ON tgr.TerminalGroupID = tg.TerminalGroupID
                WHERE tg.TerminalGroupID = ?
                ORDER BY t.TerminalName
            """
            results = self._execute_query(query, (group_id,))
            return [self._row_to_terminal_info(r) for r in results]
        except Exception as e:
            logger.error(f"[TERMINAL_SERVICE] Error getting terminals by group: {e}")
            return []

    async def resolve_terminal_ids(
        self,
        door_ids: Optional[List[int]] = None,
        door_names: Optional[List[str]] = None
    ) -> List[int]:
        """
        Resolve door names to terminal IDs. Combines provided IDs with resolved names.

        Args:
            door_ids: List of terminal IDs (optional)
            door_names: List of terminal names to resolve (optional)

        Returns:
            List of unique terminal IDs
        """
        resolved_ids = set()

        # Add provided IDs
        if door_ids:
            resolved_ids.update(door_ids)

        # Resolve names to IDs
        if door_names:
            for name in door_names:
                terminal = await self.get_terminal_by_name(name)
                if terminal:
                    resolved_ids.add(terminal.terminal_id)
                else:
                    # Try partial match
                    terminals = await self.search_terminals(name, limit=1)
                    if terminals:
                        resolved_ids.add(terminals[0].terminal_id)
                        logger.info(
                            f"[TERMINAL_SERVICE] Resolved '{name}' to terminal ID "
                            f"{terminals[0].terminal_id} ({terminals[0].terminal_name})"
                        )
                    else:
                        logger.warning(f"[TERMINAL_SERVICE] Could not resolve terminal name: {name}")

        return list(resolved_ids)

    async def get_formatted_terminal_list(self, active_only: bool = True) -> str:
        """
        Get a formatted string list of all terminals for display to users.

        Args:
            active_only: If True, only return active terminals

        Returns:
            Formatted string with numbered terminal list
        """
        terminals = await self.get_all_terminals(active_only)
        if not terminals:
            return "No terminals found."

        lines = ["Available Terminals/Doors:"]
        for i, t in enumerate(terminals, 1):
            line = f"  {i}. {t.terminal_name} (ID: {t.terminal_id})"
            if t.location:
                line += f" - {t.location}"
            if t.terminal_group_name:
                line += f" [{t.terminal_group_name}]"
            lines.append(line)

        return "\n".join(lines)

    async def get_formatted_group_list(self, active_only: bool = True) -> str:
        """
        Get a formatted string list of all terminal groups for display to users.

        Args:
            active_only: If True, only return active groups

        Returns:
            Formatted string with numbered group list
        """
        groups = await self.get_all_terminal_groups(active_only)
        if not groups:
            return "No terminal groups found."

        lines = ["Available Terminal Groups/Zones:"]
        for i, g in enumerate(groups, 1):
            line = f"  {i}. {g.group_name} (ID: {g.group_id}) - {g.terminal_count} terminals"
            if g.description:
                line += f" [{g.description}]"
            lines.append(line)

        return "\n".join(lines)

    def _row_to_terminal_info(self, row: Dict) -> TerminalInfo:
        """Convert database row to TerminalInfo object"""
        return TerminalInfo(
            terminal_id=row.get("TerminalID") or row.get("terminal_id", 0),
            terminal_name=row.get("TerminalName") or row.get("terminal_name", "Unknown"),
            location=row.get("Location") or row.get("location"),
            device_type=row.get("DeviceType") or row.get("device_type"),
            ip_address=row.get("IP_Address") or row.get("ip_address"),
            mac_address=row.get("MAC_Address") or row.get("mac_address"),
            is_active=bool(row.get("Active", True)),
            terminal_group_id=row.get("TerminalGroupID") or row.get("terminal_group_id"),
            terminal_group_name=row.get("TerminalGroupName") or row.get("terminal_group_name")
        )

    def _row_to_terminal_group_info(self, row: Dict) -> TerminalGroupInfo:
        """Convert database row to TerminalGroupInfo object"""
        return TerminalGroupInfo(
            group_id=row.get("TerminalGroupID") or row.get("group_id", 0),
            group_name=row.get("TerminalGroupName") or row.get("group_name", "Unknown"),
            description=row.get("Description") or row.get("description"),
            terminal_count=row.get("TerminalCount") or row.get("terminal_count", 0),
            is_active=bool(row.get("Active", True))
        )


# Global instance
terminal_service = TerminalService()
