import unittest
from openai import OpenAI
from chatbot import AIClient, Action, MyAssistant, Comms, OpenAIRunManager
from unittest.mock import patch, MagicMock

class TestRun(object):
    def __init__(self):
        self.status = None

ALL_STATUSES = [
    "requires_action", 
    "queued",
    "in_progress",
    "cancelling",
    "cancelled",
    "completed",
    "expired",
    "failed"
]

ACTIVE_STATUSES = [
    "requires_action", 
    "queued",
    "in_progress",
    "cancelling"
]

INACTIVE_STATUSES = [
    "cancelled",
    "completed",
    "expired",
    "failed"
]

class TestAIClient(unittest.TestCase):

    def setUp(self):
        self.client = AIClient()
    
    def test_is_run_active_returns_false_when_done(self):
        tr = TestRun()
        for status in INACTIVE_STATUSES:
            tr.status = status
            is_active = self.client.is_run_active(tr)
            self.assertFalse(is_active)

    def test_is_run_active_returns_true_when_running(self):
        tr = TestRun()
        statuses = ACTIVE_STATUSES
        for status in statuses:
            tr.status = status
            is_active = self.client.is_run_active(tr)
            self.assertTrue(is_active)

    def test_run_requires_action_is_true_when_status_is_requires_action(self):
        tr = TestRun()
        tr.status = "requires_action"
        requires_action = self.client.run_requires_action(tr)
        self.assertTrue(requires_action)

    def test_run_requires_action_is_false_when_status_is_not_requires_action(self):
        tr = TestRun()
        statuses = ALL_STATUSES
        statuses.remove("requires_action")
        for status in statuses:
            tr.status = status
            requires_action = self.client.run_requires_action(tr)
            self.assertFalse(requires_action)


if __name__ == '__main__':
    unittest.main()
