"""JARVIS Tools System: Base classes, registry, validators, permissions, and tool implementations."""

from jarvis.tools.base import (
    BaseTool,
    RiskLevel,
    PermissionLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)
from jarvis.tools.validator import ToolValidator, ValidationResult
from jarvis.tools.permissions import PermissionSystem, PermissionDecision
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.communication_tools import SendEmailTool
from jarvis.tools.safe_delete_tool import SafeDeleteProjectsTool
from jarvis.tools.system_tools import (
    OpenFileTool,
    OpenApplicationTool,
    CloseApplicationTool,
    FocusWindowTool,
    WindowControlTool,
    ListWindowsTool,
    GetActiveWindowTool,
    StartProcessTool,
    StopProcessTool,
    MouseMoveTool,
    MouseClickTool,
    MouseDoubleClickTool,
    MouseRightClickTool,
    SendHotkeyTool,
    ClipboardTool,
    SearchFilesTool,
    CreateFileTool,
    ModifyFileTool,
    MoveFileTool,
    DeleteFileTool,
    RunCommandTool,
    TakeScreenshotTool,
    GetSystemInfoTool,
    VolumeControlTool,
    DisplayControlTool,
    LockPCTool,
    SleepPCTool,
    ShutdownTool,
    RestartTool,
    TypeTextTool,
    KeyboardInputTool,
    ListProcessesTool,
)
from jarvis.tools.productivity_tools import (
    CreateFolderTool,
    CheckProcessTool,
    GetHardwareMetricsTool,
    SetReminderTool,
    ListTasksTool,
    GetTaskStatusTool,
    CancelTaskTool,
)
from jarvis.tools.file_organization_tools import (
    InspectDirectoryTool,
    DetectDuplicatesTool,
    BatchOrganizeFilesTool,
)
from jarvis.tools.service_tools import (
    FreePortTool,
    VerifyEndpointTool,
    StartBackendServiceTool,
)
from jarvis.tools.web_tools import BrowserSearchTool
from jarvis.tools.web_intelligence_tool import ResearchTopicTool
from jarvis.tools.browser_tools import (
    BrowserOpenTool,
    BrowserNewTabTool,
    BrowserSearchPageTool,
    BrowserNavigateTool,
    BrowserClickTool,
    BrowserTypeTool,
    BrowserSelectTool,
    BrowserUploadTool,
    BrowserScrollTool,
    BrowserExtractTool,
    BrowserScreenshotTool,
    BrowserBackTool,
    BrowserCloseTabTool,
    BrowserDownloadTool,
    BrowserGetStateTool,
    BrowserInspectDOMTool,
    BrowserManageTabsTool,
    BrowserDetectPDFsTool,
    BrowserDetectSessionTool,
    BrowserVerifyPDFTool,
    BrowserVerifyNavigationTool,
)
from jarvis.tools.vision_tools import (
    CaptureScreenTool,
    CaptureRegionTool,
    ScreenOCRTool,
    DetectUIElementsTool,
    VisualGroundingTool,
    VisualComputerActionTool,
    VisualVerifyTool,
    InspectScreenTool,
    LocateUIElementTool,
    ClickScreenElementTool,
)
from jarvis.tools.memory_tools import (
    RememberFactTool,
    RecallMemoryTool,
    StoreKnowledgeTool,
    SearchKnowledgeTool,
    ManageWorkingMemoryTool,
    SessionRecallTool,
    ManagePreferenceTool,
    WorkflowMemoryTool,
)
from jarvis.tools.orchestration_tools import RunComplexTaskTool, UnifiedComputerUseTool
from jarvis.tools.document_tools import (
    DocumentReadTool,
    DocumentChunkTool,
    DocumentIndexTool,
    DocumentRetrieveTool,
    DocumentSummarizeTool,
    DocumentExtractTopicsTool,
    DocumentGenerateNotesTool,
    DocumentGenerateQuestionsTool,
    DocumentAnswerQuestionTool,
    DocumentCompareTool,
    DocumentExamPrepTool,
)
from jarvis.tools.model_tools import ModelRouteInspectTool
from jarvis.tools.context_tools import (
    GetSystemContextTool,
    GetActiveDocumentTool,
    GetSelectedTextTool,
    ResolveContextualPromptTool,
)
from jarvis.tools.research_tools import (
    DeepResearchTool,
    CompareSourcesTool,
)



def get_default_registry() -> ToolRegistry:
    """Build and return a ToolRegistry populated with all default tools."""
    registry = ToolRegistry()
    # System & Computer Control
    registry.register(OpenFileTool())
    registry.register(OpenApplicationTool())
    registry.register(CloseApplicationTool())
    registry.register(FocusWindowTool())
    registry.register(WindowControlTool())
    registry.register(ListWindowsTool())
    registry.register(GetActiveWindowTool())
    registry.register(StartProcessTool())
    registry.register(StopProcessTool())
    registry.register(MouseMoveTool())
    registry.register(MouseClickTool())
    registry.register(MouseDoubleClickTool())
    registry.register(MouseRightClickTool())
    registry.register(SendHotkeyTool())
    registry.register(ClipboardTool())
    registry.register(SearchFilesTool())
    registry.register(CreateFileTool())
    registry.register(ModifyFileTool())
    registry.register(MoveFileTool())
    registry.register(DeleteFileTool())
    registry.register(RunCommandTool())
    registry.register(TakeScreenshotTool())
    registry.register(GetSystemInfoTool())
    registry.register(VolumeControlTool())
    registry.register(DisplayControlTool())
    registry.register(LockPCTool())
    registry.register(SleepPCTool())
    registry.register(ShutdownTool())
    registry.register(RestartTool())
    registry.register(TypeTextTool())
    registry.register(KeyboardInputTool())
    registry.register(ListProcessesTool())
    # Productivity, Telemetry & Task Management
    registry.register(CreateFolderTool())
    registry.register(CheckProcessTool())
    registry.register(GetHardwareMetricsTool())
    registry.register(SetReminderTool())
    registry.register(ListTasksTool())
    registry.register(GetTaskStatusTool())
    registry.register(CancelTaskTool())
    # File Organization & Inspection
    registry.register(InspectDirectoryTool())
    registry.register(DetectDuplicatesTool())
    registry.register(BatchOrganizeFilesTool())
    # Service Execution & Recovery
    registry.register(FreePortTool())
    registry.register(VerifyEndpointTool())
    registry.register(StartBackendServiceTool())
    # Web & Auxiliary Cloud Intelligence
    registry.register(BrowserSearchTool())
    registry.register(ResearchTopicTool())
    # Playwright Browser Automation (Chrome / Edge / Chromium)
    registry.register(BrowserOpenTool())
    registry.register(BrowserNewTabTool())
    registry.register(BrowserSearchPageTool())
    registry.register(BrowserNavigateTool())
    registry.register(BrowserClickTool())
    registry.register(BrowserTypeTool())
    registry.register(BrowserSelectTool())
    registry.register(BrowserUploadTool())
    registry.register(BrowserScrollTool())
    registry.register(BrowserExtractTool())
    registry.register(BrowserScreenshotTool())
    registry.register(BrowserBackTool())
    registry.register(BrowserCloseTabTool())
    registry.register(BrowserDownloadTool())
    registry.register(BrowserGetStateTool())
    registry.register(BrowserInspectDOMTool())
    registry.register(BrowserManageTabsTool())
    registry.register(BrowserDetectPDFsTool())
    registry.register(BrowserDetectSessionTool())
    registry.register(BrowserVerifyPDFTool())
    registry.register(BrowserVerifyNavigationTool())
    registry.register(CaptureScreenTool())
    registry.register(CaptureRegionTool())
    registry.register(ScreenOCRTool())
    registry.register(DetectUIElementsTool())
    registry.register(VisualGroundingTool())
    registry.register(VisualComputerActionTool())
    registry.register(VisualVerifyTool())
    registry.register(InspectScreenTool())
    registry.register(LocateUIElementTool())
    registry.register(ClickScreenElementTool())
    registry.register(RememberFactTool())
    registry.register(RecallMemoryTool())
    registry.register(StoreKnowledgeTool())
    registry.register(SearchKnowledgeTool())
    registry.register(ManageWorkingMemoryTool())
    registry.register(RunComplexTaskTool())
    registry.register(UnifiedComputerUseTool())
    # External Action (Level 2) & Safe Destructive (Level 3)
    registry.register(SendEmailTool())
    registry.register(SafeDeleteProjectsTool())
    # Document Intelligence Tools
    registry.register(DocumentReadTool())
    registry.register(DocumentChunkTool())
    registry.register(DocumentIndexTool())
    registry.register(DocumentRetrieveTool())
    registry.register(DocumentSummarizeTool())
    registry.register(DocumentExtractTopicsTool())
    registry.register(DocumentGenerateNotesTool())
    registry.register(DocumentGenerateQuestionsTool())
    registry.register(DocumentAnswerQuestionTool())
    registry.register(DocumentCompareTool())
    registry.register(DocumentExamPrepTool())
    # Model Routing Inspection
    registry.register(ModelRouteInspectTool())
    # Memory 2.0 Tools
    registry.register(SessionRecallTool())
    registry.register(ManagePreferenceTool())
    registry.register(WorkflowMemoryTool())
    # Phase 10 Context Awareness Tools
    registry.register(GetSystemContextTool())
    registry.register(GetActiveDocumentTool())
    registry.register(GetSelectedTextTool())
    registry.register(ResolveContextualPromptTool())
    # Phase 12 Research Agent Tools
    registry.register(DeepResearchTool())
    registry.register(CompareSourcesTool())
    return registry



__all__ = [
    "UnifiedComputerUseTool",
    "CaptureRegionTool",
    "ScreenOCRTool",
    "DetectUIElementsTool",
    "VisualGroundingTool",
    "VisualComputerActionTool",
    "VisualVerifyTool",
    "SessionRecallTool",
    "ManagePreferenceTool",
    "WorkflowMemoryTool",
    "ModelRouteInspectTool",
    "DocumentReadTool",
    "DocumentChunkTool",
    "DocumentIndexTool",
    "DocumentRetrieveTool",
    "DocumentSummarizeTool",
    "DocumentExtractTopicsTool",
    "DocumentGenerateNotesTool",
    "DocumentGenerateQuestionsTool",
    "DocumentAnswerQuestionTool",
    "DocumentCompareTool",
    "DocumentExamPrepTool",
    "BaseTool",
    "RiskLevel",
    "PermissionLevel",
    "ToolParameter",
    "ToolResult",
    "ToolVerification",
    "ToolValidator",
    "ValidationResult",
    "PermissionSystem",
    "PermissionDecision",
    "ToolRegistry",
    "SendEmailTool",
    "SafeDeleteProjectsTool",
    "OpenFileTool",
    "OpenApplicationTool",
    "CloseApplicationTool",
    "FocusWindowTool",
    "WindowControlTool",
    "ListWindowsTool",
    "GetActiveWindowTool",
    "StartProcessTool",
    "StopProcessTool",
    "MouseMoveTool",
    "MouseClickTool",
    "MouseDoubleClickTool",
    "MouseRightClickTool",
    "SendHotkeyTool",
    "ClipboardTool",
    "SearchFilesTool",
    "CreateFileTool",
    "ModifyFileTool",
    "MoveFileTool",
    "DeleteFileTool",
    "RunCommandTool",
    "TakeScreenshotTool",
    "GetSystemInfoTool",
    "VolumeControlTool",
    "DisplayControlTool",
    "LockPCTool",
    "SleepPCTool",
    "ShutdownTool",
    "RestartTool",
    "TypeTextTool",
    "KeyboardInputTool",
    "ListProcessesTool",
    "CreateFolderTool",
    "CheckProcessTool",
    "GetHardwareMetricsTool",
    "SetReminderTool",
    "InspectDirectoryTool",
    "DetectDuplicatesTool",
    "BatchOrganizeFilesTool",
    "BrowserSearchTool",
    "BrowserOpenTool",
    "BrowserNewTabTool",
    "BrowserSearchPageTool",
    "BrowserNavigateTool",
    "BrowserClickTool",
    "BrowserTypeTool",
    "BrowserSelectTool",
    "BrowserUploadTool",
    "BrowserScrollTool",
    "BrowserExtractTool",
    "BrowserScreenshotTool",
    "BrowserBackTool",
    "BrowserCloseTabTool",
    "BrowserDownloadTool",
    "BrowserGetStateTool",
    "BrowserInspectDOMTool",
    "BrowserManageTabsTool",
    "BrowserDetectPDFsTool",
    "BrowserDetectSessionTool",
    "BrowserVerifyPDFTool",
    "BrowserVerifyNavigationTool",
    "CaptureScreenTool",
    "InspectScreenTool",
    "LocateUIElementTool",
    "ClickScreenElementTool",
    "RememberFactTool",
    "RecallMemoryTool",
    "StoreKnowledgeTool",
    "SearchKnowledgeTool",
    "ManageWorkingMemoryTool",
    "RunComplexTaskTool",
    "GetSystemContextTool",
    "GetActiveDocumentTool",
    "GetSelectedTextTool",
    "ResolveContextualPromptTool",
    "DeepResearchTool",
    "CompareSourcesTool",
    "get_default_registry",
]

