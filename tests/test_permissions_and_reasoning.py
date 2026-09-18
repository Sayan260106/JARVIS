"""Test Suite for 4-Level Permission Architecture and Modular Reasoning Pipeline.

Verifies:
- LEVEL 0 — READ (Automatic)
- LEVEL 1 — REVERSIBLE WRITE (Automatic with audit logging)
- LEVEL 2 — EXTERNAL ACTION (Requires confirmation with Recipient, Subject, Message, Attachment preview)
- LEVEL 3 — DESTRUCTIVE (Pre-scan impact warning: "I found 17 project directories. Deleting them would be irreversible. Would you like me to list them first?")
- Modular Reasoning Architecture: Intent Analyzer -> Task Planner -> Dispatch -> Observer -> Verifier -> Recovery
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict

from jarvis.tools.base import RiskLevel, PermissionLevel, ToolResult, ToolVerification
from jarvis.tools.permissions import PermissionSystem, PermissionDecision
from jarvis.tools.communication_tools import SendEmailTool
from jarvis.tools.safe_delete_tool import SafeDeleteProjectsTool
from jarvis.tools.system_tools import SearchFilesTool, CreateFileTool
from jarvis.tools.productivity_tools import CreateFolderTool, GetHardwareMetricsTool
from jarvis.capabilities.reasoning.intent_analyzer import IntentAnalyzer, IntentType, UserIntent
from jarvis.capabilities.reasoning.reasoning_pipeline import ReasoningPipeline, ReasoningResult
from jarvis.capabilities.agent_planner import AgentToolExecutor
from jarvis.tools.registry import ToolRegistry


class TestPermissionArchitecture(unittest.TestCase):
    """Tests the 4-level safety taxonomy and gatekeeper."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_level_0_read_is_automatic(self):
        """Level 0 read operations should execute automatically without requiring confirmation."""
        perms = PermissionSystem()
        read_tool = GetHardwareMetricsTool()
        self.assertEqual(read_tool.effective_permission_level, PermissionLevel.LEVEL_0_READ)

        decision = perms.check_permission(read_tool, {})
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.user_prompt_required)
        self.assertEqual(decision.permission_level, PermissionLevel.LEVEL_0_READ)

    def test_level_1_reversible_write_is_automatic(self):
        """Level 1 reversible write operations should execute automatically with audit logging."""
        perms = PermissionSystem()
        write_tool = CreateFolderTool()
        self.assertEqual(write_tool.effective_permission_level, PermissionLevel.LEVEL_1_REVERSIBLE_WRITE)

        decision = perms.check_permission(write_tool, {"folder_name": "TestFolder"})
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.user_prompt_required)
        self.assertEqual(decision.permission_level, PermissionLevel.LEVEL_1_REVERSIBLE_WRITE)

    def test_level_2_external_action_requires_preview_and_confirmation(self):
        """Level 2 external actions must halt and provide full parameter preview (Recipient, Subject, Message, Attachment)."""
        perms = PermissionSystem()
        email_tool = SendEmailTool()
        self.assertEqual(email_tool.effective_permission_level, PermissionLevel.LEVEL_2_EXTERNAL_ACTION)

        args = {
            "recipient": "professor@university.edu",
            "subject": "Thesis Submission",
            "message": "Please find my final report attached.",
            "attachment": "thesis_final.pdf",
        }

        # Check permission without approval callback
        decision = perms.check_permission(email_tool, args)
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.user_prompt_required)
        self.assertEqual(decision.permission_level, PermissionLevel.LEVEL_2_EXTERNAL_ACTION)
        self.assertIsNotNone(decision.confirmation_preview)
        self.assertEqual(decision.confirmation_preview["Recipient"], "professor@university.edu")
        self.assertEqual(decision.confirmation_preview["Subject"], "Thesis Submission")
        self.assertEqual(decision.confirmation_preview["Message"], "Please find my final report attached.")
        self.assertEqual(decision.confirmation_preview["Attachment"], "thesis_final.pdf")

        # Now test with approval callback approving the action
        approved_perms = PermissionSystem(approval_callback=lambda tool, arguments, dec: True)
        approved_decision = approved_perms.check_permission(email_tool, args)
        self.assertTrue(approved_decision.allowed)

        # Execute and verify
        res = email_tool.execute(**args)
        self.assertTrue(res.success)
        ver = email_tool.verify(args, res)
        self.assertTrue(ver.verified)

    def test_level_3_destructive_scans_and_warns(self):
        """Level 3 destructive operations must pre-scan blast radius and prompt with exact warning."""
        # Create a mock projects directory with exactly 17 project folders
        projects_dir = os.path.join(self.temp_dir, "Projects")
        os.makedirs(projects_dir, exist_ok=True)
        for i in range(1, 18):
            os.makedirs(os.path.join(projects_dir, f"project_{i}"), exist_ok=True)

        tool = SafeDeleteProjectsTool()
        self.assertEqual(tool.effective_permission_level, PermissionLevel.LEVEL_3_DESTRUCTIVE)

        perms = PermissionSystem()
        args = {"target_directory": projects_dir, "pattern": "*", "confirmed": False}

        decision = perms.check_permission(tool, args)
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.user_prompt_required)
        self.assertEqual(decision.permission_level, PermissionLevel.LEVEL_3_DESTRUCTIVE)
        self.assertIn("I found 17 project directories. Deleting them would be irreversible. Would you like me to list them first?", decision.custom_prompt)

        # Unconfirmed execution halts
        unconfirmed_res = tool.execute(**args)
        self.assertFalse(unconfirmed_res.success)
        self.assertIn("I found 17 project directories", unconfirmed_res.output)

        # Listing first
        list_res = tool.execute(target_directory=projects_dir, pattern="*", list_first=True)
        self.assertTrue(list_res.success)
        self.assertIn("project_1", list_res.output)
        self.assertIn("project_17", list_res.output)

        # Confirmed execution deletes and verifies
        confirmed_res = tool.execute(target_directory=projects_dir, pattern="*", confirmed=True)
        self.assertTrue(confirmed_res.success)
        ver = tool.verify({"target_directory": projects_dir, "pattern": "*"}, confirmed_res)
        self.assertTrue(ver.verified)
        self.assertEqual(len(os.listdir(projects_dir)), 0)


class TestModularReasoningArchitecture(unittest.TestCase):
    """Tests the decoupled components: Intent Analyzer, Task Planner, Dispatch, Observer, Verifier, Recovery."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = os.path.join(self.temp_dir, "Projects")
        os.makedirs(self.projects_dir, exist_ok=True)
        for i in range(1, 18):
            os.makedirs(os.path.join(self.projects_dir, f"old_proj_{i}"), exist_ok=True)

        self.analyzer = IntentAnalyzer(projects_directory=self.projects_dir)
        self.registry = ToolRegistry()
        self.registry.register(SendEmailTool())
        self.registry.register(SafeDeleteProjectsTool())
        self.registry.register(GetHardwareMetricsTool())
        self.registry.register(CreateFolderTool())

        self.pipeline = ReasoningPipeline(
            intent_analyzer=self.analyzer,
            registry=self.registry,
            max_recovery_attempts=3,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_intent_analyzer_classification(self):
        """Verify IntentAnalyzer correctly classifies all safety levels and intents."""
        # Level 0
        intent_read = self.analyzer.analyze("How much RAM am I using?")
        self.assertEqual(intent_read.intent_type, IntentType.READ_QUERY)
        self.assertEqual(intent_read.permission_level, PermissionLevel.LEVEL_0_READ)
        self.assertFalse(intent_read.requires_confirmation)

        # Level 1
        intent_write = self.analyzer.analyze("Create a folder called GATE 2027")
        self.assertEqual(intent_write.intent_type, IntentType.WRITE_ACTION)
        self.assertEqual(intent_write.permission_level, PermissionLevel.LEVEL_1_REVERSIBLE_WRITE)
        self.assertEqual(intent_write.parameters.get("folder_name"), "GATE 2027")

        # Level 2
        intent_email = self.analyzer.analyze("Send this email to alex@example.com with subject 'Report' saying 'All done'")
        self.assertEqual(intent_email.intent_type, IntentType.EXTERNAL_ACTION)
        self.assertEqual(intent_email.permission_level, PermissionLevel.LEVEL_2_EXTERNAL_ACTION)
        self.assertTrue(intent_email.requires_confirmation)
        self.assertEqual(intent_email.confirmation_preview["Recipient"], "alex@example.com")

        # Level 3
        intent_delete = self.analyzer.analyze("Delete all my old projects.")
        self.assertEqual(intent_delete.intent_type, IntentType.DESTRUCTIVE_ACTION)
        self.assertEqual(intent_delete.permission_level, PermissionLevel.LEVEL_3_DESTRUCTIVE)
        self.assertTrue(intent_delete.requires_confirmation)
        self.assertIn("I found 17 project directories. Deleting them would be irreversible. Would you like me to list them first?", intent_delete.warning_prompt)

    def test_reasoning_pipeline_blocks_destructive_without_confirmation(self):
        """ReasoningPipeline should halt at SAFETY_GATE phase and prompt the user."""
        res = self.pipeline.execute("Delete all my old projects.")
        self.assertFalse(res.success)
        self.assertTrue(res.requires_user_action)
        self.assertIn("I found 17 project directories", res.output)

        phases = [step.phase for step in res.steps]
        self.assertIn("INTENT_ANALYSIS", phases)
        self.assertIn("SAFETY_GATE", phases)
        self.assertNotIn("OBSERVATION", phases)  # Action was never executed!

    def test_reasoning_pipeline_requires_email_confirmation(self):
        """ReasoningPipeline halts and returns preview for Level 2 email action."""
        res = self.pipeline.execute("Send this email to client@acme.com with subject 'Invoice'")
        self.assertFalse(res.success)
        self.assertTrue(res.requires_user_action)
        self.assertIn("External Action Confirmation Required:", res.output)
        self.assertIn("client@acme.com", res.output)
        self.assertIsNotNone(res.confirmation_preview)

    def test_reasoning_pipeline_auto_runs_read_and_write(self):
        """ReasoningPipeline executes through Task Planner -> Dispatch -> Observer -> Verifier -> Synthesis for Level 0."""
        res = self.pipeline.execute("How much RAM am I using?")
        self.assertTrue(res.success)
        phases = [step.phase for step in res.steps]
        self.assertEqual(phases, ["INTENT_ANALYSIS", "TASK_PLANNING", "AGENT_DISPATCH", "OBSERVATION", "VERIFICATION", "SYNTHESIS"])


class TestAgentTurnPermissionsIntegration(unittest.TestCase):
    """Verifies AgentToolExecutor integration with the 4-level safety gate."""

    def test_agent_turn_intercepts_delete_and_email(self):
        executor = AgentToolExecutor()

        # Delete all my old projects prompt
        del_turn = executor.run_turn("Delete all my old projects.")
        self.assertTrue(del_turn.tool_called)
        self.assertEqual(del_turn.tool_name, "safe_delete_projects")
        self.assertIn("I found", del_turn.final_response)
        self.assertIn("Deleting them would be irreversible. Would you like me to list them first?", del_turn.final_response)

        # Send this email prompt
        email_turn = executor.run_turn("Send this email to manager@company.com with subject 'Weekly Update'")
        self.assertTrue(email_turn.tool_called)
        self.assertEqual(email_turn.tool_name, "send_email")
        self.assertIn("External Action Confirmation Required:", email_turn.final_response)
        self.assertIn("manager@company.com", email_turn.final_response)
        self.assertIn("Would you like me to send this email?", email_turn.final_response)


if __name__ == "__main__":
    unittest.main()
