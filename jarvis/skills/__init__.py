"""Phase 11 — Workflow / Skill System for JARVIS.

Exports core skill contracts, registry, composer, and pre-instantiated domain namespaces.
"""

from jarvis.skills.base import (
    BaseSkill,
    PreconditionResult,
    RecoveryAction,
    RecoveryStrategy,
    SkillContext,
    SkillParameter,
    SkillResult,
    VerificationResult,
)
from jarvis.skills.registry import SkillRegistry
from jarvis.skills.composer import (
    ComposedSkillStep,
    CompositionExecutionReport,
    SkillComposer,
)

# 9 Domain Skills
from jarvis.skills.browser import (
    BrowserNavigateSkill,
    BrowserSearchSkill,
    BrowserExtractContentSkill,
    BrowserDownloadFileSkill,
)
from jarvis.skills.classroom import (
    ClassroomFindMaterialSkill,
    ClassroomDownloadMaterialSkill,
    ClassroomSubmitTaskSkill,
)
from jarvis.skills.vscode import (
    VSCodeOpenFileSkill,
    VSCodeOpenWorkspaceSkill,
    VSCodeRunTerminalSkill,
)
from jarvis.skills.files import (
    FilesOrganizeSkill,
    FilesSearchSkill,
    FilesSafeDeleteSkill,
)
from jarvis.skills.pdf import (
    PDFReadSkill,
    PDFSummarizeSkill,
    PDFVerifyIntegritySkill,
)
from jarvis.skills.research import (
    ResearchTopicSkill,
    ResearchGatherSourcesSkill,
    ResearchCompareSourcesSkill,
    ResearchSynthesizeReportSkill,
)

from jarvis.skills.coding import (
    CodingAnalyzeCodeSkill,
    CodingFixBugSkill,
    CodingRunTestsSkill,
    CodingFixFailingTestSkill,
    CodingInspectRepoSkill,
    CodingPrepareCommitSkill,
)

from jarvis.skills.system import (
    SystemGetMetricsSkill,
    SystemControlWindowSkill,
    SystemManageProcessSkill,
)
from jarvis.skills.productivity import (
    ProductivitySetReminderSkill,
    ProductivityTrackTaskSkill,
    ProductivitySummarizeSessionSkill,
)


def get_default_skill_registry(tool_registry=None) -> SkillRegistry:
    """Builds and returns a SkillRegistry populated with all default skills across all 9 domains."""
    if tool_registry is None:
        try:
            from jarvis.tools import get_default_registry
            tool_registry = get_default_registry()
        except Exception:
            pass

    registry = SkillRegistry(tool_registry=tool_registry)

    # 1. Browser
    registry.register(BrowserNavigateSkill(tool_registry))
    registry.register(BrowserSearchSkill(tool_registry))
    registry.register(BrowserExtractContentSkill(tool_registry))
    registry.register(BrowserDownloadFileSkill(tool_registry))

    # 2. Classroom
    registry.register(ClassroomFindMaterialSkill(tool_registry))
    registry.register(ClassroomDownloadMaterialSkill(tool_registry))
    registry.register(ClassroomSubmitTaskSkill(tool_registry))

    # 3. VS Code
    registry.register(VSCodeOpenFileSkill(tool_registry))
    registry.register(VSCodeOpenWorkspaceSkill(tool_registry))
    registry.register(VSCodeRunTerminalSkill(tool_registry))

    # 4. Files
    registry.register(FilesOrganizeSkill(tool_registry))
    registry.register(FilesSearchSkill(tool_registry))
    registry.register(FilesSafeDeleteSkill(tool_registry))

    # 5. PDF
    registry.register(PDFReadSkill(tool_registry))
    registry.register(PDFSummarizeSkill(tool_registry))
    registry.register(PDFVerifyIntegritySkill(tool_registry))

    # 6. Research
    registry.register(ResearchTopicSkill(tool_registry))
    registry.register(ResearchGatherSourcesSkill(tool_registry))
    registry.register(ResearchCompareSourcesSkill(tool_registry))
    registry.register(ResearchSynthesizeReportSkill(tool_registry))


    # 7. Coding
    registry.register(CodingAnalyzeCodeSkill(tool_registry))
    registry.register(CodingFixBugSkill(tool_registry))
    registry.register(CodingRunTestsSkill(tool_registry))
    registry.register(CodingFixFailingTestSkill(tool_registry))
    registry.register(CodingInspectRepoSkill(tool_registry))
    registry.register(CodingPrepareCommitSkill(tool_registry))


    # 8. System
    registry.register(SystemGetMetricsSkill(tool_registry))
    registry.register(SystemControlWindowSkill(tool_registry))
    registry.register(SystemManageProcessSkill(tool_registry))

    # 9. Productivity
    registry.register(ProductivitySetReminderSkill(tool_registry))
    registry.register(ProductivityTrackTaskSkill(tool_registry))
    registry.register(ProductivitySummarizeSessionSkill(tool_registry))

    return registry


# Convenience Domain Object Wrappers for direct python calls:
# classroom.find_material(), pdf.summarize(), vscode.open_file()
class _DomainProxy:
    def __init__(self, domain: str, registry_func):
        self._domain = domain
        self._get_reg = registry_func

    def __getattr__(self, action: str):
        skill_name = f"{self._domain}.{action}"
        reg = self._get_reg()
        skill = reg.get(skill_name)
        if not skill:
            raise AttributeError(f"Skill '{skill_name}' does not exist in domain '{self._domain}'.")
        return lambda **kwargs: skill.run(params=kwargs)


# Pre-instantiated domain namespaces
_default_reg_cached = None

def _get_reg():
    global _default_reg_cached
    if _default_reg_cached is None:
        _default_reg_cached = get_default_skill_registry()
    return _default_reg_cached

browser = _DomainProxy("browser", _get_reg)
classroom = _DomainProxy("classroom", _get_reg)
vscode = _DomainProxy("vscode", _get_reg)
files = _DomainProxy("files", _get_reg)
pdf = _DomainProxy("pdf", _get_reg)
research = _DomainProxy("research", _get_reg)
coding = _DomainProxy("coding", _get_reg)
system = _DomainProxy("system", _get_reg)
productivity = _DomainProxy("productivity", _get_reg)


__all__ = [
    "BaseSkill",
    "SkillParameter",
    "PreconditionResult",
    "VerificationResult",
    "RecoveryAction",
    "RecoveryStrategy",
    "SkillResult",
    "SkillContext",
    "SkillRegistry",
    "SkillComposer",
    "ComposedSkillStep",
    "CompositionExecutionReport",
    "get_default_skill_registry",
    # Domain Proxy Namespaces
    "browser",
    "classroom",
    "vscode",
    "files",
    "pdf",
    "research",
    "coding",
    "system",
    "productivity",
]
