"""Comprehensive Test Suite for Phase 17 — Proactive JARVIS.

Verifies:
1. Scheduled tasks ("Every Monday, check Classroom for new assignments.")
   - Natural language schedule parsing and recurrence calculation
   - Background ticker evaluation and SQLite persistence
2. Environment & File System Monitoring ("Watch my Downloads folder for PDFs.")
   - FolderWatcher detecting new files while ignoring partial downloads
   - ProcessWatcher detecting process termination ("Tell me when my GPU training finishes.")
3. Multi-Channel Notifications (Toast, Voice TTS, Visual HUD, SQLite history)
4. Canonical Event-Triggered Autonomous Workflow:
   Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify
5. Proactive Tools in default registry
6. Intent Analyzer & Understanding integration
"""

from __future__ import annotations
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from jarvis.subsystems.proactive.schemas import (
    ConditionRule,
    Event,
    EventType,
    FileEvent,
    NotificationChannel,
    NotificationMessage,
    ProcessEvent,
    ProactiveTrigger,
    ScheduleEvent,
    WorkflowRun,
    WorkflowStatus,
)
from jarvis.subsystems.proactive.scheduler import (
    NaturalScheduleParser,
    ScheduledTask,
    ScheduleManager,
    ScheduleStore,
)
from jarvis.subsystems.proactive.watchers import (
    FolderWatcher,
    ProcessWatcher,
)
from jarvis.subsystems.proactive.notifier import (
    NotificationDispatcher,
    NotificationStore,
)
from jarvis.subsystems.proactive.engine import (
    ProactiveEngine,
    TriggerStore,
)
from jarvis.tools.proactive_tools import (
    ScheduleTaskTool,
    WatchFolderTool,
    WatchProcessTool,
    SendNotificationTool,
    ListProactiveRulesTool,
    CancelProactiveRuleTool,
    TriggerWorkflowTool,
)
from jarvis.tools import get_default_registry
from jarvis.capabilities.reasoning.intent_analyzer import IntentAnalyzer, IntentType
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.core.ui_state import UIStateManager


class TestProactiveJarvis(unittest.TestCase):
    """Test suite for Phase 17 Proactive JARVIS subsystem."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_proactive_test_")
        self.db_path = os.path.join(self.test_dir, "test_proactive.db")
        self.ui_state = UIStateManager()
        self.engine = ProactiveEngine(
            db_path=self.db_path,
            notifier=NotificationDispatcher(
                store=NotificationStore(db_path=self.db_path),
                ui_state=self.ui_state,
                tts_enabled=False,
            ),
        )

    def tearDown(self):
        self.engine.stop()
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir, ignore_errors=True)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # 1. Scheduled Tasks & Natural Language Parsing
    # --------------------------------------------------------------------------

    def test_natural_schedule_parsing_and_next_run(self):
        """Verify parsing 'Every Monday', 'Every day at 9:00 AM', 'Every 15 minutes'."""
        # 1. Monday recurrence
        next_mon = NaturalScheduleParser.calculate_next_run("Every Monday at 09:00")
        self.assertGreater(next_mon, time.time())

        # 2. Minute intervals
        now = time.time()
        next_10m = NaturalScheduleParser.calculate_next_run("Every 10 minutes", reference_time=now)
        self.assertAlmostEqual(next_10m, now + 600, delta=2.0)

        # 3. Seconds intervals
        next_30s = NaturalScheduleParser.calculate_next_run("Every 30 seconds", reference_time=now)
        self.assertAlmostEqual(next_30s, now + 30, delta=2.0)

        # 4. Daily
        next_daily = NaturalScheduleParser.calculate_next_run("Every day at 18:00", reference_time=now)
        self.assertGreater(next_daily, now)

    def test_schedule_manager_lifecycle_and_due_check(self):
        """Verify schedule registration, SQLite persistence, and due trigger execution."""
        store = ScheduleStore(db_path=self.db_path)
        events_fired: list[ScheduleEvent] = []

        mgr = ScheduleManager(
            store=store,
            event_callback=lambda evt: events_fired.append(evt),
            poll_interval=0.1,
        )

        # Schedule: "Every Monday, check Classroom for new assignments."
        task = mgr.create_schedule(
            schedule_expr="Every Monday at 09:00",
            objective="Check Classroom for new assignments",
            title="Classroom Assignment Check",
        )
        self.assertIsNotNone(task.schedule_id)
        self.assertEqual(task.title, "Classroom Assignment Check")

        # Persistence verification: reload from store
        loaded = store.get(task.schedule_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.objective, "Check Classroom for new assignments")

        # Force next_run to past to simulate due time
        past_time = time.time() - 10
        loaded.next_run = past_time
        store.save(loaded)

        # Evaluate due schedules
        due_events = mgr.check_due_schedules()
        self.assertEqual(len(due_events), 1)
        self.assertEqual(due_events[0].schedule_id, task.schedule_id)
        self.assertIn("Classroom", due_events[0].payload["objective"])

        # Subsequent next_run should be recalculated into the future
        updated = store.get(task.schedule_id)
        self.assertGreater(updated.next_run, time.time())
        self.assertEqual(updated.run_count, 1)

    # --------------------------------------------------------------------------
    # 2. Environment & File System Monitoring
    # --------------------------------------------------------------------------

    def test_folder_watcher_downloads_pdf(self):
        """Verify FolderWatcher monitors directory for PDFs and ignores partial downloads."""
        watch_dir = os.path.join(self.test_dir, "Downloads")
        os.makedirs(watch_dir, exist_ok=True)

        events: list[FileEvent] = []
        watcher = FolderWatcher(
            folder_path=watch_dir,
            file_pattern="*.pdf",
            callback=lambda evt: events.append(evt),
        )

        # 1. Partial download (.crdownload) should be ignored
        temp_download = os.path.join(watch_dir, "lecture.pdf.crdownload")
        with open(temp_download, "w") as f:
            f.write("partial content")

        found = watcher.poll_once()
        self.assertEqual(len(found), 0)
        self.assertEqual(len(events), 0)

        # 2. Complete PDF download created
        pdf_file = os.path.join(watch_dir, "dbms_assignment.pdf")
        with open(pdf_file, "w") as f:
            f.write("%PDF-1.4 mock assignment content")

        found = watcher.poll_once()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].file_name, "dbms_assignment.pdf")
        self.assertEqual(found[0].action, "created")
        self.assertEqual(found[0].extension, ".pdf")

    def test_process_watcher_gpu_training_completion(self):
        """Verify ProcessWatcher detects process termination and calculates elapsed runtime."""
        events: list[ProcessEvent] = []
        watcher = ProcessWatcher(
            process_name_pattern="*train*",
            callback=lambda evt: events.append(evt),
            description="GPU Training",
        )

        # Manually set a mock PID and start time
        watcher._monitored_pid = 99999
        watcher._resolved_name = "train.py"
        watcher._detected_running = True
        watcher._start_time = time.time() - 42.5

        # When process is no longer active, poll_once emits completion event
        evt = watcher.poll_once()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.process_name, "train.py")
        self.assertEqual(evt.status, "finished")
        self.assertEqual(evt.exit_code, 0)
        self.assertGreaterEqual(evt.runtime_seconds, 40.0)

    # --------------------------------------------------------------------------
    # 3. Multi-Channel Notifications
    # --------------------------------------------------------------------------

    def test_multi_channel_notification_dispatcher(self):
        """Verify notification dispatch across HUD state, Voice, and persistent SQLite store."""
        dispatcher = self.engine.notifier

        notif = dispatcher.notify(
            title="GPU Training Complete",
            message="Epoch 100/100 finished with loss 0.042.",
            severity="SUCCESS",
            channel=NotificationChannel.ALL,
        )

        self.assertTrue(notif.delivered)
        self.assertEqual(notif.title, "GPU Training Complete")

        # Verify persistent record in SQLite
        recent = dispatcher.store.list_recent()
        self.assertGreaterEqual(len(recent), 1)
        self.assertEqual(recent[0].title, "GPU Training Complete")

        # Verify HUD message added
        self.assertTrue(any("GPU Training Complete" in m.text for m in self.ui_state.messages))

    # --------------------------------------------------------------------------
    # 4. Canonical 7-Stage Autonomous Workflow:
    #    Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify
    # --------------------------------------------------------------------------

    def test_canonical_proactive_pipeline_file_event(self):
        """Verify full Event -> Condition -> JARVIS -> Plan -> Execute -> Verify -> Notify pipeline."""
        watch_folder = os.path.join(self.test_dir, "Downloads")
        os.makedirs(watch_folder, exist_ok=True)

        # Register trigger: "Watch my Downloads folder for PDFs."
        trigger = self.engine.watch_folder(
            folder_path=watch_folder,
            file_pattern="*.pdf",
            target_objective="Inspect and organize new PDF assignment",
            title="Download PDF Watcher",
            channel=NotificationChannel.HUD,
        )

        # Stage 1: Event
        file_path = os.path.join(watch_folder, "DSA_Module_3.pdf")
        with open(file_path, "w") as f:
            f.write("mock PDF data")

        event = FileEvent(
            source="test_runner",
            payload={
                "file_path": file_path,
                "file_name": "DSA_Module_3.pdf",
                "action": "created",
                "extension": ".pdf",
            }
        )

        # Trigger execution of the 7-stage workflow
        run = self.engine.execute_proactive_workflow(trigger, event)

        # Stage 2: Condition check
        self.assertTrue(run.condition_matched)

        # Stage 3: JARVIS cognitive objective formulation
        self.assertIn("DSA_Module_3.pdf", run.objective)

        # Stage 4: Plan
        self.assertGreaterEqual(len(run.plan_steps), 2)
        step_names = [s["name"] for s in run.plan_steps]
        self.assertTrue(any("DSA_Module_3.pdf" in name for name in step_names))

        # Stage 5: Execute
        self.assertGreaterEqual(len(run.execution_records), 2)
        self.assertTrue(all(r["success"] for r in run.execution_records))

        # Stage 6: Verify
        self.assertTrue(run.verified)
        self.assertIn("verified", run.verification_details.lower())

        # Stage 7: Notify
        self.assertTrue(run.notification_sent)
        self.assertIsNotNone(run.notification_id)
        self.assertEqual(run.status, WorkflowStatus.SUCCESS)

    def test_condition_filter_skips_unmatched_events(self):
        """Verify events that do not match the condition rule are skipped and not executed."""
        trigger = ProactiveTrigger(
            title="PDF Only Trigger",
            trigger_type="FOLDER_WATCH",
            condition=ConditionRule(
                event_type=EventType.FILE_SYSTEM,
                folder_path=self.test_dir,
                file_pattern="*.pdf",
            ),
            target_objective="Process PDF",
        )
        self.engine.register_trigger(trigger)

        # Non-matching event (ZIP file)
        unmatched_event = FileEvent(
            source="test",
            payload={"file_path": os.path.join(self.test_dir, "archive.zip"), "file_name": "archive.zip", "extension": ".zip"}
        )

        runs = self.engine.emit_event(unmatched_event)
        self.assertEqual(len(runs), 0)

    # --------------------------------------------------------------------------
    # 5. Proactive Tools Integration
    # --------------------------------------------------------------------------

    def test_proactive_tools_in_registry(self):
        """Verify all 7 proactive tools are registered in get_default_registry()."""
        registry = get_default_registry()

        expected_tools = [
            "schedule_task",
            "watch_folder",
            "watch_process",
            "send_notification",
            "list_proactive_rules",
            "cancel_proactive_rule",
            "trigger_proactive_workflow",
        ]

        for tool_name in expected_tools:
            tool = registry.get_tool(tool_name)
            self.assertIsNotNone(tool, f"Tool '{tool_name}' missing from default registry.")

    def test_schedule_task_tool_execution(self):
        """Verify ScheduleTaskTool executes and schedules successfully."""
        tool = ScheduleTaskTool(engine=self.engine)
        res = tool.execute(
            expression="Every Monday at 09:00",
            objective="Check Classroom for new assignments",
            title="Classroom Task",
        )
        self.assertTrue(res.success)
        self.assertIn("schedule_id", res.output)
        self.assertIn("Next run", res.output["message"])

        ver = tool.verify({}, res)
        self.assertTrue(ver.verified)

    def test_watch_folder_tool_execution(self):
        """Verify WatchFolderTool registers folder monitor."""
        tool = WatchFolderTool(engine=self.engine)
        res = tool.execute(
            folder_path="Downloads",
            file_pattern="*.pdf",
            target_objective="Process new PDF",
        )
        self.assertTrue(res.success)
        self.assertIn("trigger_id", res.output)
        self.assertIn("*.pdf", res.output["message"])

    def test_watch_process_tool_execution(self):
        """Verify WatchProcessTool registers process watcher."""
        tool = WatchProcessTool(engine=self.engine)
        res = tool.execute(
            process_name="python.exe",
            target_objective="Tell me when my GPU training finishes.",
        )
        self.assertTrue(res.success)
        self.assertIn("trigger_id", res.output)
        self.assertIn("python.exe", res.output["message"])

    def test_list_and_cancel_proactive_rule_tools(self):
        """Verify listing rules and cancelling them by ID."""
        trig = self.engine.watch_folder(self.test_dir, "*.csv", "Process CSV")

        list_tool = ListProactiveRulesTool(engine=self.engine)
        list_res = list_tool.execute()
        self.assertTrue(list_res.success)
        self.assertGreaterEqual(list_res.output["trigger_count"], 1)

        cancel_tool = CancelProactiveRuleTool(engine=self.engine)
        cancel_res = cancel_tool.execute(rule_id=trig.trigger_id)
        self.assertTrue(cancel_res.success)

        # Confirm deleted
        self.assertIsNone(self.engine.trigger_store.get_trigger(trig.trigger_id))

    # --------------------------------------------------------------------------
    # 6. Intent Analyzer & Semantic Understanding Integration
    # --------------------------------------------------------------------------

    def test_intent_analyzer_proactive_queries(self):
        """Verify intent analyzer correctly maps the 3 core prompt scenarios to proactive tools."""
        analyzer = IntentAnalyzer()

        # Scenario 1: Scheduled task
        intent1 = analyzer.analyze("Every Monday, check Classroom for new assignments.")
        self.assertEqual(intent1.target_tool, "schedule_task")
        self.assertEqual(intent1.parameters.get("expression"), "Every Monday")
        self.assertIn("Classroom", intent1.parameters.get("objective", ""))

        # Scenario 2: Monitoring
        intent2 = analyzer.analyze("Watch my Downloads folder for PDFs.")
        self.assertEqual(intent2.target_tool, "watch_folder")
        self.assertEqual(intent2.parameters.get("file_pattern"), "*.pdf")

        # Scenario 3: Process notifications
        intent3 = analyzer.analyze("Tell me when my GPU training finishes.")
        self.assertEqual(intent3.target_tool, "watch_process")
        self.assertIn("train", intent3.parameters.get("process_name", ""))

    def test_understand_capability_proactive_intents(self):
        """Verify DefaultUnderstandCapability parses proactive commands into structured objectives."""
        understand = DefaultUnderstandCapability()

        # Target 1
        obj1 = understand.understand("Every Monday, check Classroom for new assignments.", {})
        self.assertEqual(obj1.extracted_entities.get("action"), "schedule_task")
        self.assertEqual(obj1.extracted_entities.get("expression"), "Every Monday")

        # Target 2
        obj2 = understand.understand("Watch my Downloads folder for PDFs.", {})
        self.assertEqual(obj2.extracted_entities.get("action"), "watch_folder")
        self.assertEqual(obj2.extracted_entities.get("pattern"), "*.pdf")

        # Target 3
        obj3 = understand.understand("Tell me when my GPU training finishes.", {})
        self.assertEqual(obj3.extracted_entities.get("action"), "watch_process")


if __name__ == "__main__":
    unittest.main()
