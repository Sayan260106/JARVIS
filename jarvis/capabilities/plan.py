"""2. PLAN Capability — 'What steps are required?'"""

from typing import List, Optional
from jarvis.capabilities.base import PlanCapability
from jarvis.core.schemas import (
    TaskObjective,
    ExecutionPlan,
    PlanStep,
    SubsystemType,
    IntentCategory,
)
from jarvis.core.state import AgentSessionState
from jarvis.tools.registry import ToolRegistry


class DefaultPlanCapability(PlanCapability):
    """Decomposes an objective into ordered PlanSteps with explicit dependencies and tool selection."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry

    def plan(self, objective: TaskObjective, state: AgentSessionState) -> ExecutionPlan:
        steps: List[PlanStep] = []

        # 0. Conversational Cancellation / Rollback Directives
        entities = objective.extracted_entities or {}
        if entities.get("action") == "cancel":
            steps.append(
                PlanStep.create(
                    description="Cancel active task or action",
                    subsystem=SubsystemType.SYSTEM,
                    tool_name="cancel_task",
                    arguments={"task_id": state.task_id or "", "reason": "User requested cancellation"},
                    expected_outcome="Active task marked as cancelled.",
                )
            )
            return ExecutionPlan.create(objective=objective, steps=steps)

        if entities.get("action") == "rollback":
            steps.append(
                PlanStep.create(
                    description="Revert previous action and restore state",
                    subsystem=SubsystemType.SYSTEM,
                    tool_name="rollback_action",
                    arguments={"task_id": state.task_id or ""},
                    expected_outcome="Previous action reverted.",
                )
            )
            return ExecutionPlan.create(objective=objective, steps=steps)

        # 1. Compound editor automation: "Open <App>, type <Text>, save it as <File>"
        if "app_name" in entities and "text" in entities and "file_path" in entities:
            app_name = entities["app_name"]
            text_content = entities["text"]
            file_path = entities["file_path"]

            step_open = PlanStep.create(
                description=f"Launch application '{app_name}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="open_application",
                arguments={"app_name": app_name},
                expected_outcome=f"Application '{app_name}' launched and process running.",
                depends_on=[],
            )
            step_type = PlanStep.create(
                description=f"Type text '{text_content}' into {app_name}",
                subsystem=SubsystemType.SYSTEM,
                tool_name="type_text",
                arguments={"text": text_content},
                expected_outcome=f"Text '{text_content}' successfully entered into {app_name}.",
                depends_on=[step_open.step_id],
            )
            step_save = PlanStep.create(
                description=f"Save document as '{file_path}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="create_file",
                arguments={"path": file_path, "content": text_content, "overwrite": True},
                expected_outcome=f"File '{file_path}' saved on disk and verified.",
                depends_on=[step_type.step_id],
            )
            steps.extend([step_open, step_type, step_save])
            return ExecutionPlan.create(objective=objective, steps=steps)

        # 1.3 Session Recall: "What were we doing?"
        if entities.get("action") == "session_recall":
            steps.append(
                PlanStep.create(
                    description="Recall active session state and recent actions",
                    subsystem=SubsystemType.LOCAL,
                    tool_name="session_recall",
                    arguments={"query": entities.get("query", objective.raw_input)},
                    expected_outcome="Session progress and recent actions summarized.",
                )
            )
            return ExecutionPlan.create(objective=objective, steps=steps)

        # 1.35 Visual Computer Control Action (e.g. "Click the blue submit button")
        if entities.get("action") == "visual_computer_action":
            target = entities.get("target", "Run")
            action_type = entities.get("action_type", "click")
            steps.append(
                PlanStep.create(
                    description=f"Visually locate, interact with '{target}', and verify change",
                    subsystem=SubsystemType.VISION,
                    tool_name="visual_computer_action",
                    arguments={"target": target, "action_type": action_type},
                    expected_outcome=f"Target '{target}' visually grounded, action executed, and state change verified.",
                )
            )
        # 1.38 Unified Computer-Use Workflow (13-step pipeline across Web, System, Document, LLM, Vision)
        if entities.get("action") == "unified_computer_use_workflow":
            course = entities.get("course", "DBMS")
            dest = entities.get("destination_folder", "college folder")
            editor = entities.get("editor", "VS Code")
            dest_dir = f"data/college_folder/{course}"
            sol_file = f"{dest_dir}/{course}_Assignment_Solution.sql"
            pdf_path = f"{dest_dir}/{course}_Assignment_1.pdf"

            # 1. Open Chrome
            s1 = PlanStep.create(
                description=f"Launch Chrome with institutional profile",
                subsystem=SubsystemType.WEB,
                tool_name="browser_open",
                arguments={"channel": "chrome", "profile_name": "institutional"},
                expected_outcome="Google Chrome launched with institutional profile.",
                depends_on=[],
            )
            # 2. Navigate Classroom
            s2 = PlanStep.create(
                description="Navigate to Google Classroom dashboard",
                subsystem=SubsystemType.WEB,
                tool_name="browser_navigate",
                arguments={"url": "https://classroom.google.com"},
                expected_outcome="Navigated to Google Classroom.",
                depends_on=[s1.step_id],
            )
            # 3. Find DBMS
            s3 = PlanStep.create(
                description=f"Find and enter {course} course stream",
                subsystem=SubsystemType.WEB,
                tool_name="browser_search_page",
                arguments={"query": course},
                expected_outcome=f"Located course card for '{course}'.",
                depends_on=[s2.step_id],
            )
            # 4. Find assignment
            s4 = PlanStep.create(
                description=f"Locate latest assignment in {course}",
                subsystem=SubsystemType.WEB,
                tool_name="browser_extract",
                arguments={"selector": ".assignment-item, body"},
                expected_outcome=f"Identified latest {course} assignment.",
                depends_on=[s3.step_id],
            )
            # 5. Download
            s5 = PlanStep.create(
                description="Download assignment document",
                subsystem=SubsystemType.WEB,
                tool_name="browser_download",
                arguments={"url": f"https://classroom.google.com/c/{course.lower()}/a/1", "destination": dest_dir},
                expected_outcome="Assignment file downloaded.",
                depends_on=[s4.step_id],
            )
            # 6. Verify file
            s6 = PlanStep.create(
                description="Verify assignment file integrity",
                subsystem=SubsystemType.SYSTEM,
                tool_name="browser_verify_pdf",
                arguments={"file_path": pdf_path},
                expected_outcome="File integrity verified (%PDF magic bytes and size).",
                depends_on=[s5.step_id],
            )
            # 7. Parse assignment
            s7 = PlanStep.create(
                description="Parse assignment text and questions",
                subsystem=SubsystemType.DOCUMENT,
                tool_name="document_read",
                arguments={"file_path": pdf_path},
                expected_outcome="Parsed assignment structure and problem statements.",
                depends_on=[s6.step_id],
            )
            # 8. Solve
            s8 = PlanStep.create(
                description=f"Solve all {course} questions using local reasoning model",
                subsystem=SubsystemType.LOCAL,
                tool_name="document_answer_question",
                arguments={"query": f"Solve all questions for {course} assignment with full SQL and proofs."},
                expected_outcome="High-yield solutions, DDL queries, and normalization proofs formulated.",
                depends_on=[s7.step_id],
            )
            # 9. Create solution
            s9 = PlanStep.create(
                description="Create formatted solution document",
                subsystem=SubsystemType.DOCUMENT,
                tool_name="document_generate_notes",
                arguments={"topic": f"{course} Assignment 1 Solution"},
                expected_outcome="Structured solution document compiled.",
                depends_on=[s8.step_id],
            )
            # 10. Save
            s10 = PlanStep.create(
                description=f"Save solution to {dest}",
                subsystem=SubsystemType.SYSTEM,
                tool_name="create_file",
                arguments={"path": sol_file, "content": "-- SQL Solution", "overwrite": True},
                expected_outcome=f"Solution file verified at '{sol_file}'.",
                depends_on=[s9.step_id],
            )
            # 11. Open VS Code
            s11 = PlanStep.create(
                description=f"Launch {editor} with solution file",
                subsystem=SubsystemType.SYSTEM,
                tool_name="open_application",
                arguments={"app_name": "code", "file_path": sol_file},
                expected_outcome=f"{editor} active with solution file.",
                depends_on=[s10.step_id],
            )
            # 12. Verify file opened
            s12 = PlanStep.create(
                description=f"Verify {editor} window active",
                subsystem=SubsystemType.VISION,
                tool_name="get_active_window",
                arguments={},
                expected_outcome=f"Verified {editor} window active.",
                depends_on=[s11.step_id],
            )
            # 13. Report completion
            s13 = PlanStep.create(
                description="Report end-to-end task completion",
                subsystem=SubsystemType.LOCAL,
                tool_name="session_recall",
                arguments={"query": "Summarize assignment completion and report final status."},
                expected_outcome="Task summary synthesized and reported.",
                depends_on=[s12.step_id],
            )
            steps.extend([s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13])
            return ExecutionPlan.create(objective=objective, steps=steps)

        # 1.4 Academic Lecture Search & Exam Study workflow
        if entities.get("action") == "lecture_study_and_summarize":
            browser = entities.get("browser", "chrome")
            profile = entities.get("profile", "institutional")
            course = entities.get("course", "ECE")
            materials = entities.get("materials", ["Lecture 3", "Lecture 4"])
            exam_name = entities.get("exam_name", "Upcoming Exam")

            # 1. Browser: Open
            step_open = PlanStep.create(
                description=f"Launch {browser.title()} with {profile} profile",
                subsystem=SubsystemType.WEB,
                tool_name="browser_open",
                arguments={"channel": browser, "profile_name": profile},
                expected_outcome="Browser launched and institutional profile active.",
                depends_on=[],
            )
            # 2. Browser: Detect session
            step_auth = PlanStep.create(
                description="Detect Google session authentication state",
                subsystem=SubsystemType.WEB,
                tool_name="browser_detect_session",
                arguments={"service": "google"},
                expected_outcome="Session authenticated.",
                depends_on=[step_open.step_id],
            )
            # 3. Browser: Navigate to Classroom
            step_nav = PlanStep.create(
                description=f"Navigate to {course} course in Google Classroom",
                subsystem=SubsystemType.WEB,
                tool_name="browser_navigate",
                arguments={"url": "https://classroom.google.com"},
                expected_outcome="Course portal loaded.",
                depends_on=[step_auth.step_id],
            )
            # 4. Browser: Find PDFs
            step_detect = PlanStep.create(
                description=f"Locate PDFs for {', '.join(materials)}",
                subsystem=SubsystemType.WEB,
                tool_name="browser_detect_pdfs",
                arguments={"filter_text": materials[0] if materials else "Lecture"},
                expected_outcome="Target lecture PDFs detected.",
                depends_on=[step_nav.step_id],
            )

            steps.extend([step_open, step_auth, step_nav, step_detect])
            prev_dep = step_detect.step_id

            downloaded_paths = []
            for mat in materials:
                safe_name = mat.replace(" ", "_")
                dest_path = f"downloads/{safe_name}.pdf"
                downloaded_paths.append(dest_path)
                step_dl = PlanStep.create(
                    description=f"Download {mat} PDF to local storage",
                    subsystem=SubsystemType.WEB,
                    tool_name="browser_download",
                    arguments={"url": f"https://classroom.google.com/download/{safe_name}.pdf", "download_path": dest_path},
                    expected_outcome=f"{mat} downloaded successfully.",
                    depends_on=[prev_dep],
                )
                steps.append(step_dl)
                prev_dep = step_dl.step_id

            # Document Intelligence: Read PDFs
            for idx, mat in enumerate(materials):
                path = downloaded_paths[idx]
                step_read = PlanStep.create(
                    description=f"Parse {mat} PDF and extract document structure",
                    subsystem=SubsystemType.DOCUMENT,
                    tool_name="document_read",
                    arguments={"file_path": path, "format_hint": "pdf"},
                    expected_outcome=f"{mat} parsed with headings and elements.",
                    depends_on=[prev_dep],
                )
                steps.append(step_read)
                prev_dep = step_read.step_id

            # Document Intelligence: Structure Chunking
            step_chunk = PlanStep.create(
                description=f"Chunk {materials[0]} with heading hierarchy preservation",
                subsystem=SubsystemType.DOCUMENT,
                tool_name="document_chunk",
                arguments={"file_path": downloaded_paths[0]},
                expected_outcome="Structure-aware chunks generated.",
                depends_on=[prev_dep],
            )
            steps.append(step_chunk)
            prev_dep = step_chunk.step_id

            # Document Intelligence: Vector Indexing
            step_index = PlanStep.create(
                description=f"Index {materials[0]} into semantic vector store",
                subsystem=SubsystemType.DOCUMENT,
                tool_name="document_index",
                arguments={"file_path": downloaded_paths[0]},
                expected_outcome="Document chunks embedded and indexed.",
                depends_on=[prev_dep],
            )
            steps.append(step_index)
            prev_dep = step_index.step_id

            # Document Intelligence: Extract Important Topics
            step_topics = PlanStep.create(
                description=f"Extract high-yield topics and key concepts from {materials[0]}",
                subsystem=SubsystemType.DOCUMENT,
                tool_name="document_extract_topics",
                arguments={"file_path": downloaded_paths[0], "top_n": 8},
                expected_outcome="Key topics and concepts identified.",
                depends_on=[prev_dep],
            )
            steps.append(step_topics)
            prev_dep = step_topics.step_id

            # Document Intelligence: Exam-Oriented Summarization & Notes
            safe_course = course.replace(" ", "_")
            notes_file = f"notes/{safe_course}_Exam_Revision_{'_and_'.join([m.replace(' ', '_') for m in materials])}.md"
            step_exam = PlanStep.create(
                description=f"Generate exam-oriented summary and study notes for {exam_name}",
                subsystem=SubsystemType.DOCUMENT,
                tool_name="document_exam_prep",
                arguments={
                    "file_paths": downloaded_paths,
                    "course_or_subject": course,
                    "save_to_path": notes_file,
                },
                expected_outcome=f"Exam revision pack compiled and saved to '{notes_file}'.",
                depends_on=[prev_dep],
            )
            steps.append(step_exam)

            return ExecutionPlan.create(objective=objective, steps=steps)

        # 1.5 Academic Classroom Lecture Extraction workflow
        if entities.get("action") == "classroom_lecture_extraction":
            browser = entities.get("browser", "chrome")
            profile = entities.get("profile", "institutional")
            course = entities.get("course", "ECE")
            materials = entities.get("materials", ["Lecture 3", "Lecture 4"])

            step_open = PlanStep.create(
                description=f"Launch {browser.title()} with {profile} profile",
                subsystem=SubsystemType.WEB,
                tool_name="browser_open",
                arguments={"channel": browser, "profile_name": profile},
                expected_outcome="Browser launched and profile session active.",
                depends_on=[],
            )
            step_auth = PlanStep.create(
                description="Detect Google session authentication state",
                subsystem=SubsystemType.WEB,
                tool_name="browser_detect_session",
                arguments={"service": "google"},
                expected_outcome="Google Classroom session authenticated.",
                depends_on=[step_open.step_id],
            )
            step_nav = PlanStep.create(
                description="Navigate to Google Classroom portal",
                subsystem=SubsystemType.WEB,
                tool_name="browser_navigate",
                arguments={"url": "https://classroom.google.com"},
                expected_outcome="Google Classroom portal loaded.",
                depends_on=[step_auth.step_id],
            )
            step_course = PlanStep.create(
                description=f"Select course '{course}'",
                subsystem=SubsystemType.WEB,
                tool_name="browser_click",
                arguments={"selector": course},
                expected_outcome=f"Navigated to '{course}' course page.",
                depends_on=[step_nav.step_id],
            )
            step_inspect = PlanStep.create(
                description="Inspect course stream and classwork DOM elements",
                subsystem=SubsystemType.WEB,
                tool_name="browser_inspect_dom",
                arguments={"query": "Lecture"},
                expected_outcome="Course elements inspected.",
                depends_on=[step_course.step_id],
            )
            query_str = " ".join(materials)
            step_detect = PlanStep.create(
                description=f"Locate PDF materials for {query_str}",
                subsystem=SubsystemType.WEB,
                tool_name="browser_detect_pdfs",
                arguments={"query": "Lecture"},
                expected_outcome="Target lecture PDFs detected.",
                depends_on=[step_inspect.step_id],
            )
            save_path = f"data/lectures/{course}_Lecture_3_4.pdf"
            step_download = PlanStep.create(
                description=f"Download {course} lecture PDF",
                subsystem=SubsystemType.WEB,
                tool_name="browser_download",
                arguments={"url": "data:application/pdf;base64,mock", "save_path": save_path},
                expected_outcome=f"PDF saved to {save_path}.",
                depends_on=[step_detect.step_id],
            )
            step_verify = PlanStep.create(
                description="Verify downloaded PDF file integrity",
                subsystem=SubsystemType.WEB,
                tool_name="browser_verify_pdf",
                arguments={"file_path": save_path},
                expected_outcome="Valid PDF verified on filesystem.",
                depends_on=[step_download.step_id],
            )

            steps.extend([step_open, step_auth, step_nav, step_course, step_inspect, step_detect, step_download, step_verify])
            return ExecutionPlan.create(objective=objective, steps=steps)

        # 2. Typed Windows Control Action decomposition
        if "action" in entities:
            action = entities["action"]
            if action == "open_application":
                app_name = entities.get("app_name", "")
                steps.append(
                    PlanStep.create(
                        description=f"Launch application '{app_name}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="open_application",
                        arguments={"app_name": app_name},
                        expected_outcome=f"Application '{app_name}' launched and process running.",
                    )
                )
            elif action == "close_application":
                app_name = entities.get("app_name", "")
                steps.append(
                    PlanStep.create(
                        description=f"Close application '{app_name}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="close_application",
                        arguments={"app_name": app_name},
                        expected_outcome=f"Application '{app_name}' closed.",
                    )
                )
            elif action == "create_folder":
                folder_path = entities.get("path", "")
                steps.append(
                    PlanStep.create(
                        description=f"Create folder '{folder_path}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="create_folder",
                        arguments={"path": folder_path},
                        expected_outcome=f"Folder '{folder_path}' created on filesystem.",
                    )
                )
            elif action == "shutdown":
                delay = entities.get("delay_seconds", 60)
                steps.append(
                    PlanStep.create(
                        description=f"Schedule computer shutdown ({delay}s delay)",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="shutdown",
                        arguments={"delay_seconds": delay},
                        expected_outcome="Computer shutdown scheduled.",
                    )
                )
            elif action == "restart":
                delay = entities.get("delay_seconds", 60)
                steps.append(
                    PlanStep.create(
                        description=f"Schedule computer restart ({delay}s delay)",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="restart",
                        arguments={"delay_seconds": delay},
                        expected_outcome="Computer restart scheduled.",
                    )
                )
            elif action == "lock_pc":
                steps.append(
                    PlanStep.create(
                        description="Lock workstation",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="lock_pc",
                        arguments={},
                        expected_outcome="Workstation locked.",
                    )
                )
            elif action == "sleep_pc":
                steps.append(
                    PlanStep.create(
                        description="Put computer to sleep",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="sleep_pc",
                        arguments={},
                        expected_outcome="Computer in sleep mode.",
                    )
                )
            elif action == "volume_control":
                v_act = entities.get("vol_action", "set")
                v_args = {"action": v_act}
                if "level" in entities:
                    v_args["level"] = entities["level"]
                steps.append(
                    PlanStep.create(
                        description=f"Adjust volume ({v_act})",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="volume_control",
                        arguments=v_args,
                        expected_outcome="System volume adjusted.",
                    )
                )
            elif action == "focus_window":
                title = entities.get("title", "")
                steps.append(
                    PlanStep.create(
                        description=f"Focus window '{title}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="focus_window",
                        arguments={"title": title},
                        expected_outcome=f"Window '{title}' focused.",
                    )
                )
            elif action == "window_control":
                w_act = entities.get("action", "minimize")
                title = entities.get("title", "")
                steps.append(
                    PlanStep.create(
                        description=f"{w_act.capitalize()} window '{title}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="window_control",
                        arguments={"action": w_act, "title": title},
                        expected_outcome=f"Window '{title}' {w_act}d.",
                    )
                )
            if steps:
                return ExecutionPlan.create(objective=objective, steps=steps)

        # 3. Intent-based decomposition & tool selection
        if objective.intent == IntentCategory.SYSTEM_COMMAND:
            lower_input = objective.raw_input.lower().strip().rstrip(".")
            if lower_input.startswith("open "):
                target_app = objective.raw_input.strip()[5:].rstrip(".").strip()
                steps.append(
                    PlanStep.create(
                        description=f"Open application '{target_app}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="open_application",
                        arguments={"app_name": target_app},
                        expected_outcome=f"Application '{target_app}' launched.",
                    )
                )
            elif lower_input.startswith("close "):
                target_app = objective.raw_input.strip()[6:].rstrip(".").strip()
                steps.append(
                    PlanStep.create(
                        description=f"Close application '{target_app}'",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="close_application",
                        arguments={"app_name": target_app},
                        expected_outcome=f"Application '{target_app}' closed.",
                    )
                )
            else:
                steps.append(
                    PlanStep.create(
                        description=f"Execute system command for: {objective.raw_input}",
                        subsystem=SubsystemType.SYSTEM,
                        tool_name="powershell_exec",
                        arguments={"command": objective.raw_input},
                        expected_outcome="Exit code 0 with expected stdout.",
                    )
                )

        elif objective.intent == IntentCategory.RESEARCH:
            step_search = PlanStep.create(
                description=f"Query search engine for: {objective.raw_input}",
                subsystem=SubsystemType.WEB,
                tool_name="web_search",
                arguments={"query": objective.raw_input},
                expected_outcome="Relevant search results extracted.",
                depends_on=[],
            )
            step_summary = PlanStep.create(
                description="Synthesize research findings",
                subsystem=SubsystemType.LOCAL,
                tool_name="local_summarizer",
                arguments={"style": "concise"},
                expected_outcome="Summary generated without hallucinations.",
                depends_on=[step_search.step_id],
            )
            steps.extend([step_search, step_summary])

        elif objective.intent == IntentCategory.QUERY:
            steps.append(
                PlanStep.create(
                    description=f"Process informational query: {objective.raw_input}",
                    subsystem=SubsystemType.LOCAL,
                    tool_name="local_reasoning",
                    arguments={"prompt": objective.raw_input},
                    expected_outcome="Direct, accurate answer formulated.",
                )
            )

        else:
            # Check WorkflowMemory for matching reusable workflows
            try:
                from jarvis.tools.memory_tools import get_memory_manager
                mem = get_memory_manager()
                matched_wf = mem.workflow.find_matching_workflow(objective.raw_input)
                if matched_wf and matched_wf.steps:
                    prev_dep = None
                    for s_data in matched_wf.steps:
                        tool = s_data.get("tool", "")
                        args = s_data.get("arguments", {})
                        subsystem = SubsystemType.WEB if "browser" in tool else SubsystemType.SYSTEM
                        step_obj = PlanStep.create(
                            description=f"Execute '{tool}' as part of '{matched_wf.name}'",
                            subsystem=subsystem,
                            tool_name=tool,
                            arguments=args,
                            expected_outcome=f"Completed {tool} from reusable workflow '{matched_wf.name}'.",
                            depends_on=[prev_dep] if prev_dep else [],
                        )
                        steps.append(step_obj)
                        prev_dep = step_obj.step_id
                    return ExecutionPlan.create(objective=objective, steps=steps)
            except Exception:
                pass

            # General fallback decomposition
            steps.append(
                PlanStep.create(
                    description=f"Execute task: {objective.raw_input}",
                    subsystem=SubsystemType.SYSTEM,
                    tool_name="task_runner",
                    arguments={"task": objective.raw_input},
                    expected_outcome="Task completion status verified.",
                )
            )

        return ExecutionPlan.create(objective=objective, steps=steps)

