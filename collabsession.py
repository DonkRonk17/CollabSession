#!/usr/bin/env python3
"""
CollabSession v1.0 - Multi-Agent Coordination Framework

Enables multiple AI agents to work together on complex tasks with role assignment,
resource locking, and real-time coordination.

Author: Atlas (Team Brain)
Q-Mode Tool #5 (Tier 1: Critical Foundation)
Date: January 19, 2026
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

VERSION = "1.0.0"

# Default database path
DEFAULT_DB_PATH = Path("D:/BEACON_HQ/COLLAB_SESSIONS/collab_sessions.db")


class AgentStatus(Enum):
    """Agent status in session."""
    ACTIVE = "active"
    IDLE = "idle"
    WAITING = "waiting"
    DONE = "done"


class SessionStatus(Enum):
    """Session status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Agent:
    """Represents an agent in a collaboration session."""
    agent_name: str
    role: str
    status: str
    joined_at: str
    current_task: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ResourceLock:
    """Represents a locked resource."""
    resource_id: str
    locked_by: str
    locked_at: str
    resource_type: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


class CollabSession:
    """
    Multi-agent coordination framework for complex tasks.
    
    Enables multiple agents to work together with:
    - Role assignment (planner, builder, tester, etc.)
    - Resource locking (prevent conflicts)
    - Status tracking (who's working on what)
    - Shared context (all agents see same state)
    - History/replay (audit trail)
    
    Usage:
        session = CollabSession("build_feature_x")
        session.add_agent("FORGE", role="planner")
        session.add_agent("BOLT", role="builder")
        session.lock_resource("spec.md", "FORGE")
        # FORGE works...
        session.unlock_resource("spec.md")
        session.notify_next_role("builder")
    """
    
    def __init__(self, session_id: str, db_path: Optional[Path] = None):
        """
        Initialize a collaboration session.
        
        Args:
            session_id: Unique identifier for this session
            db_path: Path to database file (optional)
        """
        self.session_id = session_id
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        self._create_or_load_session()
    
    def _init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                context TEXT,
                metadata TEXT
            )
        ''')
        
        # Agents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                current_task TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        # Resource locks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resource_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                locked_by TEXT NOT NULL,
                locked_at TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        # History table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _create_or_load_session(self):
        """Create new session or load existing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if session exists
        cursor.execute('SELECT status FROM sessions WHERE session_id = ?', (self.session_id,))
        result = cursor.fetchone()
        
        if not result:
            # Create new session
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO sessions (session_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (self.session_id, SessionStatus.ACTIVE.value, now, now))
            conn.commit()
            self._log_history("SYSTEM", "session_created", "Session initialized")
        
        conn.close()
    
    def _log_history(self, agent_name: str, action: str, details: str = ""):
        """Log action to session history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO session_history (session_id, timestamp, agent_name, action, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.session_id, datetime.now().isoformat(), agent_name, action, details))
        
        conn.commit()
        conn.close()
    
    def add_agent(self, agent_name: str, role: str) -> bool:
        """
        Add an agent to the session.
        
        Args:
            agent_name: Name of the agent (e.g., "FORGE", "BOLT")
            role: Role in this session (e.g., "planner", "builder", "tester")
        
        Returns:
            True if added successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if agent already in session
        cursor.execute('''
            SELECT id FROM session_agents 
            WHERE session_id = ? AND agent_name = ?
        ''', (self.session_id, agent_name))
        
        if cursor.fetchone():
            conn.close()
            return False  # Already in session
        
        # Add agent
        cursor.execute('''
            INSERT INTO session_agents (session_id, agent_name, role, status, joined_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.session_id, agent_name, role, AgentStatus.IDLE.value, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        self._log_history(agent_name, "agent_joined", f"Role: {role}")
        return True
    
    def remove_agent(self, agent_name: str) -> bool:
        """
        Remove an agent from the session.
        
        Args:
            agent_name: Name of the agent to remove
        
        Returns:
            True if removed successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Release any locks held by this agent
        cursor.execute('''
            DELETE FROM resource_locks 
            WHERE session_id = ? AND locked_by = ?
        ''', (self.session_id, agent_name))
        
        # Remove agent
        cursor.execute('''
            DELETE FROM session_agents 
            WHERE session_id = ? AND agent_name = ?
        ''', (self.session_id, agent_name))
        
        rows_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_deleted > 0:
            self._log_history(agent_name, "agent_left", "Removed from session")
            return True
        return False
    
    def lock_resource(self, resource_id: str, agent_name: str, resource_type: str = "file") -> bool:
        """
        Lock a resource for exclusive access.
        
        Args:
            resource_id: Identifier for the resource (e.g., filename, task ID)
            agent_name: Agent requesting the lock
            resource_type: Type of resource ("file", "task", "data")
        
        Returns:
            True if locked successfully, False if already locked
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if resource is already locked
        cursor.execute('''
            SELECT locked_by FROM resource_locks 
            WHERE session_id = ? AND resource_id = ?
        ''', (self.session_id, resource_id))
        
        result = cursor.fetchone()
        if result:
            conn.close()
            return False  # Already locked
        
        # Create lock
        cursor.execute('''
            INSERT INTO resource_locks (session_id, resource_id, locked_by, locked_at, resource_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.session_id, resource_id, agent_name, datetime.now().isoformat(), resource_type))
        
        conn.commit()
        conn.close()
        
        self._log_history(agent_name, "resource_locked", f"Resource: {resource_id} ({resource_type})")
        return True
    
    def unlock_resource(self, resource_id: str) -> bool:
        """
        Unlock a resource.
        
        Args:
            resource_id: Identifier for the resource to unlock
        
        Returns:
            True if unlocked successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get lock info for history
        cursor.execute('''
            SELECT locked_by FROM resource_locks 
            WHERE session_id = ? AND resource_id = ?
        ''', (self.session_id, resource_id))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False  # Not locked
        
        locked_by = result[0]
        
        # Remove lock
        cursor.execute('''
            DELETE FROM resource_locks 
            WHERE session_id = ? AND resource_id = ?
        ''', (self.session_id, resource_id))
        
        conn.commit()
        conn.close()
        
        self._log_history(locked_by, "resource_unlocked", f"Resource: {resource_id}")
        return True
    
    def get_locks(self) -> List[ResourceLock]:
        """
        Get all current resource locks.
        
        Returns:
            List of ResourceLock objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT resource_id, locked_by, locked_at, resource_type
            FROM resource_locks 
            WHERE session_id = ?
        ''', (self.session_id,))
        
        locks = []
        for row in cursor.fetchall():
            locks.append(ResourceLock(
                resource_id=row[0],
                locked_by=row[1],
                locked_at=row[2],
                resource_type=row[3]
            ))
        
        conn.close()
        return locks
    
    def is_locked(self, resource_id: str) -> bool:
        """
        Check if a resource is currently locked.
        
        Args:
            resource_id: Resource to check
        
        Returns:
            True if locked
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM resource_locks 
            WHERE session_id = ? AND resource_id = ?
        ''', (self.session_id, resource_id))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def update_agent_status(self, agent_name: str, status: str, current_task: Optional[str] = None) -> bool:
        """
        Update an agent's status.
        
        Args:
            agent_name: Agent to update
            status: New status (active, idle, waiting, done)
            current_task: Optional task description
        
        Returns:
            True if updated successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE session_agents 
            SET status = ?, current_task = ?
            WHERE session_id = ? AND agent_name = ?
        ''', (status, current_task, self.session_id, agent_name))
        
        rows_updated = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_updated > 0:
            self._log_history(agent_name, "status_updated", f"Status: {status}, Task: {current_task}")
            return True
        return False
    
    def get_agents(self) -> List[Agent]:
        """
        Get all agents in the session.
        
        Returns:
            List of Agent objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT agent_name, role, status, joined_at, current_task
            FROM session_agents 
            WHERE session_id = ?
        ''', (self.session_id,))
        
        agents = []
        for row in cursor.fetchall():
            agents.append(Agent(
                agent_name=row[0],
                role=row[1],
                status=row[2],
                joined_at=row[3],
                current_task=row[4]
            ))
        
        conn.close()
        return agents
    
    def get_agent_by_role(self, role: str) -> Optional[Agent]:
        """
        Get the agent assigned to a specific role.
        
        Args:
            role: Role to look up
        
        Returns:
            Agent object or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT agent_name, role, status, joined_at, current_task
            FROM session_agents 
            WHERE session_id = ? AND role = ?
        ''', (self.session_id, role))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return Agent(
                agent_name=result[0],
                role=result[1],
                status=result[2],
                joined_at=result[3],
                current_task=result[4]
            )
        return None
    
    def notify_next_role(self, next_role: str) -> bool:
        """
        Notify the agent assigned to the next role that it's their turn.
        
        Args:
            next_role: Role to notify (e.g., "builder" after "planner" finishes)
        
        Returns:
            True if notification sent successfully
        """
        agent = self.get_agent_by_role(next_role)
        if not agent:
            return False
        
        # Update agent status to active
        self.update_agent_status(agent.agent_name, AgentStatus.ACTIVE.value, f"Ready to work on {next_role} tasks")
        
        # Try to send via SynapseLink if available
        try:
            from synapselink import quick_send
            quick_send(
                agent.agent_name,
                f"CollabSession: Your Turn - {self.session_id}",
                f"Session: {self.session_id}\nRole: {next_role}\nStatus: Active - ready to start work!\n\nCheck session status for details.",
                priority="NORMAL"
            )
        except:
            pass  # SynapseLink not available, just update status
        
        self._log_history("SYSTEM", "role_notified", f"Notified {agent.agent_name} ({next_role})")
        return True
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get session history.
        
        Args:
            limit: Maximum number of history entries to return
        
        Returns:
            List of history entries (newest first)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, agent_name, action, details
            FROM session_history 
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (self.session_id, limit))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "timestamp": row[0],
                "agent": row[1],
                "action": row[2],
                "details": row[3]
            })
        
        conn.close()
        return history
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get complete session status.
        
        Returns:
            Dictionary with session info, agents, locks, recent history
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get session info
        cursor.execute('SELECT status, created_at, updated_at FROM sessions WHERE session_id = ?', (self.session_id,))
        session_info = cursor.fetchone()
        
        conn.close()
        
        agents = self.get_agents()
        locks = self.get_locks()
        history = self.get_history(limit=10)
        
        return {
            "session_id": self.session_id,
            "status": session_info[0] if session_info else "unknown",
            "created_at": session_info[1] if session_info else None,
            "updated_at": session_info[2] if session_info else None,
            "agents": [a.to_dict() for a in agents],
            "locks": [l.to_dict() for l in locks],
            "recent_history": history[:5]  # Last 5 actions
        }
    
    def complete_session(self) -> bool:
        """
        Mark session as completed.
        
        Returns:
            True if marked complete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE sessions 
            SET status = ?, updated_at = ?
            WHERE session_id = ?
        ''', (SessionStatus.COMPLETED.value, datetime.now().isoformat(), self.session_id))
        
        # Release all locks
        cursor.execute('DELETE FROM resource_locks WHERE session_id = ?', (self.session_id,))
        
        # Mark all agents as done
        cursor.execute('''
            UPDATE session_agents 
            SET status = ?
            WHERE session_id = ?
        ''', (AgentStatus.DONE.value, self.session_id))
        
        conn.commit()
        conn.close()
        
        self._log_history("SYSTEM", "session_completed", "Session marked as complete")
        return True


def list_sessions(db_path: Optional[Path] = None, status: Optional[str] = None) -> List[str]:
    """
    List all collaboration sessions.
    
    Args:
        db_path: Path to database file (optional)
        status: Filter by status (optional)
    
    Returns:
        List of session IDs
    """
    db = db_path or DEFAULT_DB_PATH
    
    if not db.exists():
        return []
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    
    if status:
        cursor.execute('SELECT session_id FROM sessions WHERE status = ? ORDER BY created_at DESC', (status,))
    else:
        cursor.execute('SELECT session_id FROM sessions ORDER BY created_at DESC')
    
    sessions = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return sessions


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("CollabSession v1.0 - Multi-Agent Coordination Framework")
        print("\nUsage:")
        print("  python collabsession.py <session_id>")
        print("\nExamples:")
        print("  python collabsession.py build_feature_x")
        print("  python collabsession.py code_review_session")
        sys.exit(0)
    
    session_id = sys.argv[1]
    session = CollabSession(session_id)
    
    # Display session status
    status = session.get_status()
    print(f"\n{'='*70}")
    print(f"CollabSession: {session_id}")
    print(f"{'='*70}")
    print(f"Status: {status['status']}")
    print(f"Created: {status['created_at']}")
    print(f"\nAgents ({len(status['agents'])}):")
    for agent in status['agents']:
        print(f"  - {agent['agent_name']:12} | Role: {agent['role']:12} | Status: {agent['status']}")
    
    print(f"\nLocks ({len(status['locks'])}):")
    for lock in status['locks']:
        print(f"  - {lock['resource_id']:20} | Locked by: {lock['locked_by']}")
    
    print(f"\nRecent History:")
    for entry in status['recent_history']:
        print(f"  [{entry['timestamp']}] {entry['agent']:12} | {entry['action']:20} | {entry['details']}")
    
    print(f"{'='*70}\n")
