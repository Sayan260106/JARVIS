from typing import Optional
import re
from typing import Any, Dict, List
from jarvis.capabilities.base import UnderstandCapability
from jarvis.core.schemas import TaskObjective, IntentCategory


class DefaultUnderstandCapability(UnderstandCapability):
    """Parses user input into structured objectives with entity extraction and ambiguity detection."""

    def understand(self, user_input: str, context: Dict[str, Any]) -> TaskObjective:
        cleaned = user_input.strip()
        if not cleaned:
            return TaskObjective(
                raw_input=user_input,
                intent=IntentCategory.UNKNOWN,
                description="Empty request",
                target_criteria="",
                is_ambiguous=True,
                clarification_needed="Please provide a task or question for JARVIS to execute.",
            )

        lower = cleaned.lower()
        sub_goals: List[str] = []
        extracted_entities: Dict[str, Any] = {}

        # 0. Conversational Cancellation / Interruption Directive
        if re.search(r"^(?:actually[,\s]+)?(?:cancel(?:\s+that)?|abort|stop(?:\s+that)?)(?:[\s,:\.\?!]+.*)?$", cleaned, re.I):
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.SYSTEM_COMMAND,
                description="Cancel active task or in-flight action.",
                target_criteria="Active task or operation terminated immediately.",
                context=context,
                extracted_entities={"action": "cancel", "directive": "cancel_task"},
                is_ambiguous=False,
            )

        # 0.5 Conversational Revert / Undo / Go Back Directive
        if re.search(r"^(?:wait[,\s]+)?(?:go\s+back|undo(?:\s+that)?|revert(?:\s+last\s+action)?)(?:[\s,:\.\?!]+.*)?$", cleaned, re.I):
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.SYSTEM_COMMAND,
                description="Revert or undo previous action and step back.",
                target_criteria="Previous state or application state restored.",
                context=context,
                extracted_entities={"action": "rollback", "directive": "undo_action"},
                is_ambiguous=False,
            )

        # 0.7 Context-Aware Deictic Resolution ("Summarize this", "Fix this", "Explain this")
        from jarvis.subsystems.context.resolver import ContextResolver
        from jarvis.subsystems.context.collector import ContextCollector
        from jarvis.subsystems.context.schemas import DeicticTargetType

        if ContextResolver.contains_deictic_reference(cleaned):
            sys_snapshot = context.get("system_context") if context else None
            if sys_snapshot is None:
                collector = ContextCollector.get_instance()
                sys_snapshot = collector.collect(refresh=False, capture_selection=True)

            resolved_action = ContextResolver.resolve(cleaned, sys_snapshot)
            if resolved_action.confidence >= 0.7:
                tt = resolved_action.target_type
                if tt == DeicticTargetType.OPEN_DOCUMENT:
                    return TaskObjective(
                        raw_input=cleaned,
                        intent=IntentCategory.TASK_AUTOMATION,
                        description=resolved_action.resolved_prompt,
                        target_criteria=f"Document '{resolved_action.target_name}' read and summarized.",
                        context=context,
                        sub_goals=[
                            f"Inspect active document '{resolved_action.target_name}'",
                            "Extract content and parse structure",
                            "Generate structured summary and key takeaways",
                        ],
                        extracted_entities={
                            "action": "summarize_document",
                            "target_type": "open_document",
                            "file_name": resolved_action.target_name,
                            "file_path": resolved_action.target_path or "",
                            "content": resolved_action.content_payload,
                            "resolved_context": resolved_action.to_dict(),
                        },
                        is_ambiguous=False,
                    )
                elif tt == DeicticTargetType.CODE_IN_EDITOR:
                    return TaskObjective(
                        raw_input=cleaned,
                        intent=IntentCategory.TASK_AUTOMATION,
                        description=resolved_action.resolved_prompt,
                        target_criteria=f"Code in '{resolved_action.target_name}' analyzed, bugs diagnosed, and fix verified.",
                        context=context,
                        sub_goals=[
                            f"Inspect active code in '{resolved_action.target_name}'",
                            "Diagnose syntax errors, logic flaws, or runtime exceptions",
                            "Apply targeted fix to code",
                            "Verify changes in file",
                        ],
                        extracted_entities={
                            "action": "fix_code",
                            "target_type": "code_in_editor",
                            "file_name": resolved_action.target_name,
                            "file_path": resolved_action.target_path or "",
                            "content": resolved_action.content_payload,
                            "resolved_context": resolved_action.to_dict(),
                        },
                        is_ambiguous=False,
                    )
                elif tt == DeicticTargetType.SELECTED_TEXT:
                    is_fix = any(w in lower for w in ["fix", "debug", "correct"])
                    is_sum = any(w in lower for w in ["summarize", "summary", "tldr"])
                    action_name = "fix_code" if is_fix else ("summarize_selection" if is_sum else "explain_selection")
                    intent_cat = IntentCategory.TASK_AUTOMATION if is_fix else IntentCategory.QUERY
                    return TaskObjective(
                        raw_input=cleaned,
                        intent=intent_cat,
                        description=resolved_action.resolved_prompt,
                        target_criteria="Selected text analyzed and comprehensive response produced.",
                        context=context,
                        sub_goals=[
                            "Parse highlighted text selection",
                            "Perform contextual analysis and semantic reasoning",
                            "Deliver clear, structured answer to user",
                        ],
                        extracted_entities={
                            "action": action_name,
                            "target_type": "selected_text",
                            "text": resolved_action.content_payload,
                            "resolved_context": resolved_action.to_dict(),
                        },
                        is_ambiguous=False,
                    )
                elif tt == DeicticTargetType.BROWSER_PAGE:
                    return TaskObjective(
                        raw_input=cleaned,
                        intent=IntentCategory.TASK_AUTOMATION,
                        description=resolved_action.resolved_prompt,
                        target_criteria=f"Web page '{resolved_action.target_name}' analyzed and summarized.",
                        context=context,
                        sub_goals=[
                            f"Inspect active browser page '{resolved_action.target_name}'",
                            "Extract webpage contents from active browser session",
                            "Synthesize comprehensive summary",
                        ],
                        extracted_entities={
                            "action": "summarize_webpage",
                            "target_type": "browser_page",
                            "url": resolved_action.content_payload,
                            "page_title": resolved_action.target_name,
                            "resolved_context": resolved_action.to_dict(),
                        },
                        is_ambiguous=False,
                    )

        # 0.9 Direct or Composed Skill Invocation (Phase 11 Skill System)
        from jarvis.skills import get_default_skill_registry
        skill_reg = get_default_skill_registry()
        m_direct = re.match(r"^([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)(?:\((.*)\))?$", cleaned)
        if m_direct:
            skill_name = f"{m_direct.group(1)}.{m_direct.group(2)}".lower()
            skill_obj = skill_reg.get(skill_name)
            if skill_obj:
                raw_args = m_direct.group(3) or ""
                parsed_args = {}
                if raw_args:
                    for part in raw_args.split(","):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            parsed_args[k.strip()] = v.strip().strip("'\"")
                return TaskObjective(
                    raw_input=cleaned,
                    intent=IntentCategory.TASK_AUTOMATION,
                    description=f"Execute skill '{skill_name}': {skill_obj.capability}",
                    target_criteria=f"Skill '{skill_name}' executed and verified.",
                    context=context,
                    sub_goals=[f"Execute skill '{skill_name}'"],
                    extracted_entities={
                        "action": skill_name,
                        "params": parsed_args,
                        "composed_skills": [(skill_name, parsed_args)],
                    },
                    is_ambiguous=False,
                )

        # 0.95 Deep Research Agent Pipeline (Phase 12: "Research the latest developments in X and make me a report")
        research_match = re.search(
            r"^(?:please\s+)?research(?:\s+the)?(?:\s+latest)?(?:\s+developments)?(?:\s+in)?\s+(.+?)(?:\s+and\s+make(?:\s+me)?\s+a\s+report.*)?$",
            cleaned,
            re.IGNORECASE,
        ) or re.search(
            r"^(?:please\s+)?(?:do(?:\s+some)?\s+research\s+(?:on|into|about)|investigate|prepare\s+a\s+research\s+report\s+(?:on|about))\s+(.+?)(?:\s+and\s+make(?:\s+me)?\s+a\s+report.*)?$",
            cleaned,
            re.IGNORECASE,
        )
        if research_match:
            raw_topic = research_match.group(1).strip()
            topic = re.sub(r"\s+and\s+make(?:\s+me)?\s+a\s+report.*$", "", raw_topic, flags=re.IGNORECASE).strip(".?! ")
            if topic:
                sub_goals = [
                    f"Formulate research plan and decompose '{topic}' into targeted sub-queries",
                    f"Search web and harvest multiple independent sources",
                    f"Open web pages and extract body text and evidence",
                    f"Extract atomic claims and benchmarks across sources",
                    f"Cross-check claims and identify conflicting information or divergences",
                    f"Synthesize comprehensive report with citations and bibliography",
                    f"Save generated research report locally to reports directory",
                ]
                return TaskObjective(
                    raw_input=cleaned,
                    intent=IntentCategory.RESEARCH,
                    description=f"Conduct deep research on '{topic}' and generate cited report.",
                    target_criteria=f"Autonomous research on '{topic}' completed across multiple sources, claims cross-checked, conflicts detected, and cited report saved locally.",
                    context=context,
                    sub_goals=sub_goals,
                    extracted_entities={
                        "action": "deep_research",
                        "topic": topic,
                        "make_report": True,
                    },
                    is_ambiguous=False,
                )

        # 0.98 Autonomous Coding Agent Pipeline (Phase 13: "Open my JARVIS project and fix the failing test.")
        coding_match = re.search(
            r"^(?:please\s+)?open\s+(?:my\s+)?(?:the\s+)?([a-zA-Z0-9_\-\.\s]+?)\s+project\s+and\s+fix\s+(?:the\s+)?failing\s+test(?:s)?(?:\s+(?:in|at)\s+(.+?))?[\.\?!]?$",
            cleaned,
            re.IGNORECASE,
        ) or re.search(
            r"^(?:please\s+)?fix\s+(?:the\s+)?failing\s+test(?:s)?(?:\s+(?:in|at|for)\s+(.+?))?[\.\?!]?$",
            cleaned,
            re.IGNORECASE,
        )
        if coding_match:
            if "project and fix" in cleaned.lower():
                project_name = coding_match.group(1).strip()
                test_path = (coding_match.group(2) or "").strip() if coding_match.lastindex >= 2 and coding_match.group(2) else "tests"
            else:
                project_name = "JARVIS"
                test_path = (coding_match.group(1) or "").strip() if coding_match.group(1) else "tests"

            sub_goals = [
                f"Open Visual Studio Code on project '{project_name}'",
                "Inspect repository awareness, active branch, and git status",
                "Analyze AST file dependencies and correlate source to test suites",
                f"Execute test suite '{test_path}' in terminal and observe failure",
                "Parse traceback and understand root cause of error",
                "Apply surgical AST-validated code modification",
                "Re-run test suite in terminal to verify fix",
                "Inspect git diff and verify zero unintended regressions",
                "Prepare commit metadata with staged files and diff summary",
                "Explain changes (enforce security gate: autonomous push blocked)",
            ]

            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Open project '{project_name}', diagnose and fix failing tests in '{test_path}', verify with git diff and prepare commit.",
                target_criteria=f"Failing tests in '{test_path}' diagnosed, patched with verified syntax, test suite passing, and git commit prepared.",
                context=context,
                sub_goals=sub_goals,
                extracted_entities={
                    "action": "fix_failing_test",
                    "project": project_name,
                    "test_path": test_path,
                    "open_vscode": True,
                },
                is_ambiguous=False,
            )

        # 1. Compound multi-step task detection (e.g. "Open Notepad, type Hello, save it as test.txt")
        compound_match = self._parse_compound_editor_task(cleaned)


        if compound_match:
            app_name = compound_match["app_name"]
            text_to_type = compound_match["text"]
            file_name = compound_match["file_name"]

            extracted_entities = {
                "app_name": app_name,
                "text": text_to_type,
                "file_path": file_name,
            }
            sub_goals = [
                f"Open application '{app_name}'",
                f"Type text '{text_to_type}' into {app_name}",
                f"Save document as '{file_name}'",
            ]
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Open {app_name}, type '{text_to_type}', and save as '{file_name}'.",
                target_criteria=f"Application '{app_name}' launched, text '{text_to_type}' entered, and file '{file_name}' verified on disk.",
                context=context,
                sub_goals=sub_goals,
                extracted_entities=extracted_entities,
                is_ambiguous=False,
            )

        # 1.3 Session Recall: "What were we doing?"
        if re.search(r"\b(?:what\s+(?:were|are)\s+we\s+doing|what\s+was\s+(?:the\s+)?last\s+task|where\s+did\s+we\s+leave\s+off)\b", cleaned, re.I):
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.QUERY,
                description="Recall current session activity and summarize in-flight task progress.",
                target_criteria="Active session history inspected and answer provided to user.",
                context=context,
                sub_goals=["Inspect active session activity history", "Synthesize summary of recent actions"],
                extracted_entities={"action": "session_recall", "query": cleaned},
                is_ambiguous=False,
            )

        # 1.4 Academic Lecture Search & Exam Study workflow
        study_match = self._parse_document_study_workflow(cleaned)
        if study_match:
            sub_goals = [
                f"Locate requested lecture materials ({', '.join(study_match['materials'])})",
                f"Download lecture PDFs to local workspace",
                f"Parse document structure and extract text",
                f"Chunk document preserving section hierarchy",
                f"Index chunks for vector retrieval",
                f"Analyze key concepts and high-yield topics",
                f"Generate exam-oriented summary ({study_match['exam_name']})",
                f"Compile and return structured exam revision notes",
            ]
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Find {', '.join(study_match['materials'])} PDFs, analyze key concepts, and generate structured notes for {study_match['exam_name']}.",
                target_criteria=f"Lecture PDFs parsed, high-yield concepts extracted, and {study_match['exam_name']} revision pack generated.",
                context=context,
                sub_goals=sub_goals,
                extracted_entities=study_match,
                is_ambiguous=False,
            )

        # 1.45 Unified Computer-Use Workflow (e.g. "Find the latest DBMS assignment in Classroom, download it, solve it, save the solution in my college folder, and open it in VS Code.")
        unified_match = self._parse_unified_computer_use_workflow(cleaned)
        if unified_match:
            course = unified_match["course"]
            dest = unified_match["destination_folder"]
            editor = unified_match["editor"]
            sub_goals = [
                "Open Chrome with institutional profile",
                "Navigate to Google Classroom",
                f"Find {course} course card and stream",
                f"Find latest {course} assignment",
                "Download assignment document",
                "Verify downloaded file integrity",
                "Parse assignment structure and questions",
                "Solve assignment problems and generate SQL/code",
                "Create complete structured solution artifact",
                f"Save solution into {dest}",
                f"Open solution file in {editor}",
                f"Verify {editor} window active with solution",
                "Report end-to-end task completion",
            ]
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Retrieve latest {course} assignment from Classroom, solve questions, save to {dest}, and open in {editor}.",
                target_criteria=f"Assignment downloaded from Classroom, solved, saved to {dest}, and opened in {editor}.",
                context=context,
                sub_goals=sub_goals,
                extracted_entities={
                    "action": "unified_computer_use_workflow",
                    "course": course,
                    "destination_folder": dest,
                    "editor": editor,
                    "browser": unified_match.get("browser", "Chrome"),
                    "service": unified_match.get("service", "Classroom"),
                },
                is_ambiguous=False,
            )

        # 1.5 Academic Classroom Lecture Extraction workflow
        classroom_match = self._parse_classroom_workflow(cleaned)
        if classroom_match:
            sub_goals = [
                f"Launch {classroom_match['browser'].title()} using {classroom_match['profile']} profile",
                f"Detect existing authentication session for {classroom_match['service']}",
                f"Navigate to {classroom_match['service']}",
                f"Open course '{classroom_match['course']}'",
                f"Inspect course materials and locate {', '.join(classroom_match['materials'])} PDFs",
                f"Download lecture PDFs to local storage",
                f"Verify PDF file integrity (%PDF magic bytes)",
            ]
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Open Google Classroom in {classroom_match['profile']} profile, locate {classroom_match['course']} course, and extract {', '.join(classroom_match['materials'])} PDFs.",
                target_criteria=f"Course '{classroom_match['course']}' located and requested lecture PDFs downloaded and verified.",
                context=context,
                sub_goals=sub_goals,
                extracted_entities=classroom_match,
                is_ambiguous=False,
            )

        # 1.6 Visual Computer Control & UI Action detection (e.g. "Click the blue submit button")
        visual_match = self._parse_visual_computer_action(cleaned)
        if visual_match:
            target = visual_match["target"]
            action_type = visual_match.get("action_type", "click")
            return TaskObjective(
                raw_input=cleaned,
                intent=IntentCategory.TASK_AUTOMATION,
                description=f"Visually ground and execute {action_type} on '{target}' with closed-loop verification.",
                target_criteria=f"Element '{target}' visually located and clicked, follow-up screenshot verified.",
                context=context,
                sub_goals=[
                    "Capture pre-action screenshot",
                    f"Visually ground '{target}' and map pixel coordinates",
                    f"Execute mouse {action_type} on target",
                    "Capture post-action verification screenshot",
                    "Verify visual state transition",
                ],
                extracted_entities={"action": "visual_computer_action", "target": target, "action_type": action_type},
                is_ambiguous=False,
            )

        # 2. Windows Control Actions detection
        win_control = self._parse_windows_control_action(cleaned)
        if win_control:
            action = win_control["action"]
            extracted_entities = win_control.get("entities", {})
            intent = win_control.get("intent", IntentCategory.SYSTEM_COMMAND)
            desc = win_control.get("description", f"Execute Windows action: {action}")
            target_crit = win_control.get("target_criteria", f"Windows action '{action}' verified.")
            return TaskObjective(
                raw_input=cleaned,
                intent=intent,
                description=desc,
                target_criteria=target_crit,
                context=context,
                sub_goals=[desc],
                extracted_entities={"action": action, **extracted_entities},
                is_ambiguous=False,
            )

        # 3. General Intent classification heuristics
        if any(w in lower for w in ["automate", "backup", "sync", "organize"]):
            intent = IntentCategory.TASK_AUTOMATION
        elif any(w in lower for w in ["run", "execute", "create", "delete", "mkdir", "write", "open", "close", "kill"]):
            intent = IntentCategory.SYSTEM_COMMAND
        elif any(w in lower for w in ["search", "find online", "browse", "look up", "google"]):
            intent = IntentCategory.RESEARCH
        elif any(w in lower for w in ["play", "pause", "volume", "music", "mute"]):
            intent = IntentCategory.MEDIA_CONTROL
        else:
            intent = IntentCategory.QUERY

        # Ambiguity check (e.g. extremely short or underspecified commands)
        is_ambiguous = False
        clarification_needed = None

        if len(cleaned.split()) == 1 and intent in (IntentCategory.SYSTEM_COMMAND, IntentCategory.TASK_AUTOMATION):
            is_ambiguous = True
            clarification_needed = f"The objective '{cleaned}' is missing specific target arguments or file paths."

        return TaskObjective(
            raw_input=cleaned,
            intent=intent,
            description=f"Accomplish user goal: {cleaned}",
            target_criteria=f"Goal '{cleaned}' successfully achieved and verified.",
            context=context,
            is_ambiguous=is_ambiguous,
            clarification_needed=clarification_needed,
            sub_goals=sub_goals,
            extracted_entities=extracted_entities,
        )

    def _parse_compound_editor_task(self, text: str) -> Dict[str, str] | None:
        """Parses patterns like 'Open Notepad, type Hello, save it as test.txt'."""
        # Normalize punctuation
        norm = text.rstrip(".").strip()

        # Regex for 'open <app>, type <text>, save (it)? as <file>'
        pattern = re.compile(
            r"open\s+([a-zA-Z0-9_\-\s]+?)"
            r"(?:,\s*|\s+and\s+|\s*;\s*|\s+then\s+)"
            r"(?:type|write|input)\s+['\"]?(.+?)['\"]?"
            r"(?:,\s*|\s+and\s+|\s*;\s*|\s+then\s+)"
            r"(?:save\s+(?:it\s+)?as|save\s+to|write\s+to)\s+['\"]?([^\s'\"]+)['\"]?",
            re.IGNORECASE,
        )
        m = pattern.search(norm)
        if m:
            return {
                "app_name": m.group(1).strip(),
                "text": m.group(2).strip(),
                "file_name": m.group(3).strip(),
            }

    def _parse_document_study_workflow(self, text: str) -> Dict[str, Any] | None:
        """Parses complete document research and exam study workflows like:
        'Find Lecture 3 and 4 PDF and summarize them for my upcoming exam.'
        """
        lower = text.lower()
        has_study_goal = any(kw in lower for kw in ["summariz", "exam", "notes", "study", "revision", "explain"])
        has_material = any(kw in lower for kw in ["lecture", "pdf", "docx", "slides", "notes", "material", "document"])

        if has_study_goal and has_material:
            profile = "institutional"
            browser = "chrome"

            # Course name detection
            course = "ECE"
            matches = re.findall(r"(?:open|enter|go\s+to|in|for)\s+([A-Za-z0-9_\-]+)\s+(?:classroom|course|class)", text, re.IGNORECASE)
            course_candidates = [m for m in matches if m.lower() not in ("google", "my", "the")]
            if course_candidates:
                course = course_candidates[0].strip()
            else:
                m_course2 = re.search(r"\b([A-Z]{2,6})\b", text)
                if m_course2 and m_course2.group(1) not in ("PDF", "DOCX", "PPTX", "TXT"):
                    course = m_course2.group(1).strip()

            # Target materials detection (e.g. "Lecture 3 and 4")
            materials = []
            m_compound = re.search(r"lecture(?:s)?\s*(\d+)\s*(?:and|&|,)\s*(\d+)", text, re.IGNORECASE)
            if m_compound:
                materials = [f"Lecture {m_compound.group(1)}", f"Lecture {m_compound.group(2)}"]
            else:
                m_lectures = re.findall(r"lecture\s*\d+", text, re.IGNORECASE)
                if m_lectures:
                    materials = [m.title() for m in m_lectures]
                else:
                    materials = ["Lecture 3", "Lecture 4"]

            # Exam or goal
            exam_name = "Upcoming Exam"
            m_exam = re.search(r"(?:for\s+(?:my\s+)?|upcoming\s+)([a-zA-Z0-9_\-\s]+?\s+exam)", text, re.IGNORECASE)
            if m_exam:
                exam_name = m_exam.group(1).strip().title()

            return {
                "action": "lecture_study_and_summarize",
                "browser": browser,
                "profile": profile,
                "service": "Google Classroom",
                "course": course,
                "materials": materials,
                "target_type": "pdf",
                "goal": "exam_summary",
                "exam_name": exam_name,
            }
        return None

    def _parse_classroom_workflow(self, text: str) -> Dict[str, Any] | None:
        """Parses compound academic workflows like:
        'Open Chrome, go to my institutional profile, open Google Classroom, open ECE Classroom, find Lecture 3 and 4 PDF.'
        """
        lower = text.lower()
        if "classroom" in lower and any(kw in lower for kw in ["lecture", "pdf", "course", "notes", "material"]):
            profile = "institutional" if any(kw in lower for kw in ["institutional", "college", "university", "academic"]) else "Default"
            browser = "chrome" if "chrome" in lower else "msedge"

            # Detect course name: e.g. "ECE Classroom" or "ECE" or "DBMS"
            # Detect course name: e.g. "ECE Classroom" or "ECE" or "DBMS"
            course = "ECE"
            matches = re.findall(r"(?:open|enter|go\s+to)\s+([A-Za-z0-9_\-]+)\s+classroom", text, re.IGNORECASE)
            course_candidates = [m for m in matches if m.lower() != "google"]
            if course_candidates:
                course = course_candidates[0].strip()
            else:
                m_course2 = re.search(r"(?:course|class)\s+([A-Za-z0-9_\-]+)", text, re.IGNORECASE)
                if m_course2:
                    course = m_course2.group(1).strip()

            # Detect target lectures/materials (e.g. "Lecture 3 and 4" or "Lecture 3, Lecture 4")
            materials = []
            m_compound = re.search(r"lecture(?:s)?\s*(\d+)\s*(?:and|&|,)\s*(\d+)", text, re.IGNORECASE)
            if m_compound:
                materials = [f"Lecture {m_compound.group(1)}", f"Lecture {m_compound.group(2)}"]
            else:
                m_lectures = re.findall(r"lecture\s*\d+", text, re.IGNORECASE)
                if m_lectures:
                    materials = [m.title() for m in m_lectures]
                else:
                    materials = ["Lecture 3", "Lecture 4"]

            return {
                "action": "classroom_lecture_extraction",
                "browser": browser,
                "profile": profile,
                "service": "Google Classroom",
                "course": course,
                "materials": materials,
                "target_type": "pdf",
            }
        return None

    def _parse_windows_control_action(self, text: str) -> Dict[str, Any] | None:
        """Parses natural language commands directly into typed Windows control actions."""
        norm = text.rstrip(".").strip()
        lower = norm.lower()

        # 1. Shutdown / Power Off
        if re.match(r"^(?:shut\s*down|power\s*off|turn\s*off)\s*(?:the\s+)?(?:computer|pc|system)?$", lower):
            return {
                "action": "shutdown",
                "entities": {"delay_seconds": 60},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Schedule computer shutdown (60s delay)",
                "target_criteria": "Computer shutdown scheduled.",
            }

        # 2. Restart / Reboot
        if re.match(r"^(?:restart|reboot)\s*(?:the\s+)?(?:computer|pc|system)?$", lower):
            return {
                "action": "restart",
                "entities": {"delay_seconds": 60},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Schedule computer restart (60s delay)",
                "target_criteria": "Computer restart scheduled.",
            }

        # 3. Lock PC
        if re.match(r"^lock\s*(?:the\s+)?(?:computer|pc|system|screen)?$", lower):
            return {
                "action": "lock_pc",
                "entities": {},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Lock the workstation",
                "target_criteria": "Workstation locked.",
            }

        # 4. Sleep PC
        if re.match(r"^(?:sleep|put\s+to\s+sleep)\s*(?:the\s+)?(?:computer|pc|system)?$", lower):
            return {
                "action": "sleep_pc",
                "entities": {},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": "Put computer to sleep",
                "target_criteria": "Computer in sleep mode.",
            }

        # 5. Create Folder: "Create a folder called GATE 2027", "Make folder Work", "mkdir test"
        m_folder = re.match(r"^(?:create|make|mkdir)\s+(?:a\s+)?(?:folder|directory)\s+(?:called\s+|named\s+)?['\"]?(.+?)['\"]?$", norm, re.IGNORECASE)
        if m_folder:
            folder_path = m_folder.group(1).strip()
            return {
                "action": "create_folder",
                "entities": {"path": folder_path},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"Create folder '{folder_path}'",
                "target_criteria": f"Folder '{folder_path}' verified on filesystem.",
            }

        # 6. Close Application: "Close Chrome", "Quit Notepad", "Kill VS Code"
        m_close = re.match(r"^(?:close|quit|exit|kill|terminate)\s+(?:application\s+|app\s+|window\s+|process\s+)?(.+)$", norm, re.IGNORECASE)
        if m_close:
            app_target = m_close.group(1).strip()
            return {
                "action": "close_application",
                "entities": {"app_name": app_target},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"Close application '{app_target}'",
                "target_criteria": f"Application '{app_target}' closed.",
            }

        # 7. Focus Window: "Focus Chrome", "Switch to VS Code"
        m_focus = re.match(r"^(?:focus|switch\s+to)\s+(?:window\s+)?(.+)$", norm, re.IGNORECASE)
        if m_focus:
            win_title = m_focus.group(1).strip()
            return {
                "action": "focus_window",
                "entities": {"title": win_title},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"Focus window '{win_title}'",
                "target_criteria": f"Window '{win_title}' focused.",
            }

        # 8. Minimize / Maximize / Restore Window
        m_win = re.match(r"^(minimize|maximize|restore)\s+(?:window\s+)?(.+)$", norm, re.IGNORECASE)
        if m_win:
            win_action = m_win.group(1).lower()
            win_title = m_win.group(2).strip()
            return {
                "action": "window_control",
                "entities": {"action": win_action, "title": win_title},
                "intent": IntentCategory.SYSTEM_COMMAND,
                "description": f"{win_action.capitalize()} window '{win_title}'",
                "target_criteria": f"Window '{win_title}' {win_action}d.",
            }

        # 9. Volume Control
        m_vol_set = re.match(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d+)(?:%)?$", lower)
        if m_vol_set:
            level = int(m_vol_set.group(1))
            return {
                "action": "volume_control",
                "entities": {"vol_action": "set", "level": level},
                "intent": IntentCategory.MEDIA_CONTROL,
                "description": f"Set volume to {level}%",
                "target_criteria": f"Volume set to {level}%.",
            }
        if re.match(r"^mute\s*(?:volume|audio|sound)?$", lower):
            return {
                "action": "volume_control",
                "entities": {"vol_action": "mute"},
                "intent": IntentCategory.MEDIA_CONTROL,
                "description": "Mute system audio",
                "target_criteria": "Audio muted.",
            }
        if re.match(r"^unmute\s*(?:volume|audio|sound)?$", lower):
            return {
                "action": "volume_control",
                "entities": {"vol_action": "unmute"},
                "intent": IntentCategory.MEDIA_CONTROL,
                "description": "Unmute system audio",
                "target_criteria": "Audio unmuted.",
            }

        # 10. Open Application / Directory: "Open VS Code", "Open Downloads", "Launch notepad"
        m_open = re.match(r"^(?:open|launch|start)\s+(.+)$", norm, re.IGNORECASE)
        if m_open:
            app_target = m_open.group(1).strip()
            # Do not hijack compound sentences with commas or 'and'
            if not any(sep in app_target.lower() for sep in [",", " and ", ";", " then "]):
                return {
                    "action": "open_application",
                    "entities": {"app_name": app_target},
                    "intent": IntentCategory.SYSTEM_COMMAND,
                    "description": f"Open application '{app_target}'",
                    "target_criteria": f"Application '{app_target}' launched and active.",
                }

        return None

    def _parse_visual_computer_action(self, text: str) -> Optional[Dict[str, Any]]:
        """Detects visual UI interaction requests (e.g. 'Click the blue submit button')."""
        clean = text.strip()
        m = re.search(
            r"\b(?P<act>double\s+click|right\s+click|click|press|tap)\s+(?:on\s+)?(?:the\s+)?(?P<target>[a-zA-Z0-9_\-\s]+?(?:button|icon|control|link|box|field|tab|submit|run|cancel|close|save|debug))\b",
            clean,
            re.IGNORECASE,
        )
        if m:
            act_raw = m.group("act").lower().replace(" ", "_")
            target = m.group("target").strip()
            return {"action_type": act_raw, "target": target}
        return None

    def _parse_unified_computer_use_workflow(self, text: str) -> Optional[Dict[str, Any]]:
        """Detects compound multi-subsystem workflows bridging browser, documents, LLM, filesystem, and editor."""
        clean = text.strip()
        lower = clean.lower()

        # Check for key markers: classroom/portal + assignment/lab + solve + save + vs code/editor
        has_source = any(w in lower for w in ["classroom", "portal", "lms", "moodle"])
        has_task = any(w in lower for w in ["assignment", "homework", "problem set", "lab task"])
        has_solve = any(w in lower for w in ["solve", "solution", "complete it", "do it"])
        has_editor = any(w in lower for w in ["vs code", "vscode", "editor", "code", "notepad"])

        if has_source and has_task and (has_solve or has_editor):
            # Extract course
            course = "DBMS"
            course_m = re.search(r"\b([A-Z]{2,6}|[A-Za-z0-9]+)\s+assignment\b", clean, re.IGNORECASE)
            if course_m and course_m.group(1).lower() not in ["latest", "the", "my", "new", "this"]:
                course = course_m.group(1).upper()
            else:
                for cand in ["DBMS", "ECE", "OS", "DSA", "CN", "AI", "ML"]:
                    if cand.lower() in lower:
                        course = cand
                        break

            # Extract destination folder
            dest_folder = "college folder"
            folder_m = re.search(r"in\s+(?:my\s+)?([a-zA-Z0-9_\-\s]+?\s+folder)", clean, re.IGNORECASE)
            if folder_m:
                dest_folder = folder_m.group(1).strip()

            # Extract editor
            editor = "VS Code"
            if "notepad" in lower:
                editor = "Notepad"

            return {
                "course": course,
                "destination_folder": dest_folder,
                "editor": editor,
                "service": "Classroom",
                "browser": "Chrome",
            }
        return None


