#!/usr/bin/env python3
"""
Comprehensive test suite for CollabSession v1.0

Tests:
- Session creation and management
- Agent add/remove
- Role assignment
- Resource locking
- Status tracking
- History tracking
- Notifications
- Database persistence

Author: Atlas (Team Brain)
Date: January 19, 2026
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from collabsession import CollabSession, Agent, ResourceLock, AgentStatus, SessionStatus, list_sessions


class TestCollabSession(unittest.TestCase):
    """Test suite for CollabSession."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database
        self.test_db = Path(tempfile.mkdtemp()) / "test_collab.db"
        self.session_id = "test_session_001"
        self.session = CollabSession(self.session_id, db_path=self.test_db)
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database
        if self.test_db.parent.exists():
            shutil.rmtree(self.test_db.parent, ignore_errors=True)
    
    def test_01_session_creation(self):
        """Test session creation."""
        status = self.session.get_status()
        
        self.assertEqual(status["session_id"], self.session_id)
        self.assertEqual(status["status"], SessionStatus.ACTIVE.value)
        self.assertIsNotNone(status["created_at"])
        self.assertEqual(len(status["agents"]), 0)  # No agents yet
    
    def test_02_add_agent(self):
        """Test adding agents to session."""
        # Add first agent
        success = self.session.add_agent("FORGE", role="planner")
        self.assertTrue(success)
        
        # Add second agent
        success = self.session.add_agent("BOLT", role="builder")
        self.assertTrue(success)
        
        # Verify agents added
        agents = self.session.get_agents()
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0].agent_name, "FORGE")
        self.assertEqual(agents[0].role, "planner")
        self.assertEqual(agents[1].agent_name, "BOLT")
        self.assertEqual(agents[1].role, "builder")
    
    def test_03_add_duplicate_agent(self):
        """Test adding duplicate agent fails."""
        self.session.add_agent("FORGE", role="planner")
        
        # Try to add same agent again
        success = self.session.add_agent("FORGE", role="reviewer")
        self.assertFalse(success)  # Should fail
        
        # Verify only one instance
        agents = self.session.get_agents()
        self.assertEqual(len(agents), 1)
    
    def test_04_remove_agent(self):
        """Test removing agents from session."""
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        
        # Remove one agent
        success = self.session.remove_agent("FORGE")
        self.assertTrue(success)
        
        # Verify removed
        agents = self.session.get_agents()
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_name, "BOLT")
    
    def test_05_lock_resource(self):
        """Test locking a resource."""
        self.session.add_agent("FORGE", role="planner")
        
        # Lock a resource
        success = self.session.lock_resource("spec.md", "FORGE", resource_type="file")
        self.assertTrue(success)
        
        # Verify lock exists
        self.assertTrue(self.session.is_locked("spec.md"))
        
        locks = self.session.get_locks()
        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].resource_id, "spec.md")
        self.assertEqual(locks[0].locked_by, "FORGE")
    
    def test_06_duplicate_lock_fails(self):
        """Test that locking already-locked resource fails."""
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        
        # FORGE locks resource
        success = self.session.lock_resource("code.py", "FORGE")
        self.assertTrue(success)
        
        # BOLT tries to lock same resource
        success = self.session.lock_resource("code.py", "BOLT")
        self.assertFalse(success)  # Should fail
        
        # Verify only one lock
        locks = self.session.get_locks()
        self.assertEqual(len(locks), 1)
        self.assertEqual(locks[0].locked_by, "FORGE")
    
    def test_07_unlock_resource(self):
        """Test unlocking a resource."""
        self.session.add_agent("FORGE", role="planner")
        self.session.lock_resource("file.txt", "FORGE")
        
        # Unlock
        success = self.session.unlock_resource("file.txt")
        self.assertTrue(success)
        
        # Verify unlocked
        self.assertFalse(self.session.is_locked("file.txt"))
        locks = self.session.get_locks()
        self.assertEqual(len(locks), 0)
    
    def test_08_remove_agent_releases_locks(self):
        """Test that removing agent releases their locks."""
        self.session.add_agent("FORGE", role="planner")
        self.session.lock_resource("file1.txt", "FORGE")
        self.session.lock_resource("file2.txt", "FORGE")
        
        # Verify locks exist
        self.assertEqual(len(self.session.get_locks()), 2)
        
        # Remove agent
        self.session.remove_agent("FORGE")
        
        # Verify locks released
        self.assertEqual(len(self.session.get_locks()), 0)
    
    def test_09_update_agent_status(self):
        """Test updating agent status."""
        self.session.add_agent("BOLT", role="builder")
        
        # Update status
        success = self.session.update_agent_status("BOLT", AgentStatus.ACTIVE.value, "Building feature X")
        self.assertTrue(success)
        
        # Verify update
        agents = self.session.get_agents()
        self.assertEqual(agents[0].status, AgentStatus.ACTIVE.value)
        self.assertEqual(agents[0].current_task, "Building feature X")
    
    def test_10_get_agent_by_role(self):
        """Test retrieving agent by role."""
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        self.session.add_agent("ATLAS", role="tester")
        
        # Get specific roles
        planner = self.session.get_agent_by_role("planner")
        self.assertIsNotNone(planner)
        self.assertEqual(planner.agent_name, "FORGE")
        
        builder = self.session.get_agent_by_role("builder")
        self.assertEqual(builder.agent_name, "BOLT")
        
        tester = self.session.get_agent_by_role("tester")
        self.assertEqual(tester.agent_name, "ATLAS")
        
        # Non-existent role
        reviewer = self.session.get_agent_by_role("reviewer")
        self.assertIsNone(reviewer)
    
    def test_11_history_tracking(self):
        """Test session history is tracked."""
        self.session.add_agent("FORGE", role="planner")
        self.session.lock_resource("spec.md", "FORGE")
        self.session.unlock_resource("spec.md")
        
        # Get history
        history = self.session.get_history()
        
        # Should have: session_created, agent_joined, resource_locked, resource_unlocked
        self.assertGreaterEqual(len(history), 4)
        
        # Verify history entries have required fields
        for entry in history:
            self.assertIn("timestamp", entry)
            self.assertIn("agent", entry)
            self.assertIn("action", entry)
    
    def test_12_session_status(self):
        """Test getting complete session status."""
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        self.session.lock_resource("code.py", "BOLT")
        
        status = self.session.get_status()
        
        # Verify all sections present
        self.assertIn("session_id", status)
        self.assertIn("status", status)
        self.assertIn("agents", status)
        self.assertIn("locks", status)
        self.assertIn("recent_history", status)
        
        # Verify counts
        self.assertEqual(len(status["agents"]), 2)
        self.assertEqual(len(status["locks"]), 1)
    
    def test_13_complete_session(self):
        """Test marking session as complete."""
        self.session.add_agent("FORGE", role="planner")
        self.session.lock_resource("file.txt", "FORGE")
        
        # Complete session
        success = self.session.complete_session()
        self.assertTrue(success)
        
        # Verify status updated
        status = self.session.get_status()
        self.assertEqual(status["status"], SessionStatus.COMPLETED.value)
        
        # Verify locks released
        self.assertEqual(len(status["locks"]), 0)
        
        # Verify agents marked done
        for agent in status["agents"]:
            self.assertEqual(agent["status"], AgentStatus.DONE.value)
    
    def test_14_multiple_locks(self):
        """Test managing multiple resource locks."""
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        
        # Lock multiple resources
        self.session.lock_resource("file1.py", "FORGE", "file")
        self.session.lock_resource("file2.py", "BOLT", "file")
        self.session.lock_resource("task_001", "FORGE", "task")
        
        locks = self.session.get_locks()
        self.assertEqual(len(locks), 3)
        
        # Verify different resource types
        file_locks = [l for l in locks if l.resource_type == "file"]
        task_locks = [l for l in locks if l.resource_type == "task"]
        
        self.assertEqual(len(file_locks), 2)
        self.assertEqual(len(task_locks), 1)
    
    def test_15_database_persistence(self):
        """Test that session persists across instances."""
        # Add agents and locks
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        self.session.lock_resource("file.txt", "FORGE")
        
        # Create new instance with same session_id and database
        new_session = CollabSession(self.session_id, db_path=self.test_db)
        
        # Verify data persisted
        agents = new_session.get_agents()
        self.assertEqual(len(agents), 2)
        
        locks = new_session.get_locks()
        self.assertEqual(len(locks), 1)
    
    def test_16_list_sessions(self):
        """Test listing all sessions."""
        # Create multiple sessions
        session1 = CollabSession("session_001", db_path=self.test_db)
        session2 = CollabSession("session_002", db_path=self.test_db)
        session3 = CollabSession("session_003", db_path=self.test_db)
        
        # List all sessions
        sessions = list_sessions(db_path=self.test_db)
        
        self.assertGreaterEqual(len(sessions), 3)
        self.assertIn("session_001", sessions)
        self.assertIn("session_002", sessions)
        self.assertIn("session_003", sessions)
    
    def test_17_workflow_simulation(self):
        """Test complete collaboration workflow."""
        # Setup: Add agents with roles
        self.session.add_agent("FORGE", role="planner")
        self.session.add_agent("BOLT", role="builder")
        self.session.add_agent("ATLAS", role="tester")
        
        # Phase 1: Planning
        self.session.lock_resource("spec.md", "FORGE")
        self.session.update_agent_status("FORGE", AgentStatus.ACTIVE.value, "Writing specification")
        # ... FORGE works ...
        self.session.unlock_resource("spec.md")
        self.session.update_agent_status("FORGE", AgentStatus.DONE.value)
        
        # Phase 2: Building
        self.session.notify_next_role("builder")
        builder = self.session.get_agent_by_role("builder")
        self.assertEqual(builder.status, AgentStatus.ACTIVE.value)
        
        self.session.lock_resource("feature.py", "BOLT")
        self.session.update_agent_status("BOLT", AgentStatus.ACTIVE.value, "Implementing feature")
        # ... BOLT works ...
        self.session.unlock_resource("feature.py")
        self.session.update_agent_status("BOLT", AgentStatus.DONE.value)
        
        # Phase 3: Testing
        self.session.notify_next_role("tester")
        tester = self.session.get_agent_by_role("tester")
        self.assertEqual(tester.status, AgentStatus.ACTIVE.value)
        
        self.session.lock_resource("test_feature.py", "ATLAS")
        self.session.update_agent_status("ATLAS", AgentStatus.ACTIVE.value, "Testing feature")
        # ... ATLAS works ...
        self.session.unlock_resource("test_feature.py")
        self.session.update_agent_status("ATLAS", AgentStatus.DONE.value)
        
        # Complete session
        self.session.complete_session()
        
        # Verify workflow completed
        status = self.session.get_status()
        self.assertEqual(status["status"], SessionStatus.COMPLETED.value)
        
        # Verify all agents done
        for agent in status["agents"]:
            self.assertEqual(agent["status"], AgentStatus.DONE.value)
        
        # Verify history captured workflow
        history = self.session.get_history(limit=100)
        self.assertGreater(len(history), 10)  # Many actions logged


def run_tests():
    """Run all tests."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCollabSession)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print(f"[SUCCESS] All {result.testsRun} tests passed!")
    else:
        print(f"[FAILED] {len(result.failures)} failures, {len(result.errors)} errors")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
