"""Tests for LLMProvider Abstraction, Intelligent Multi-Model Routing, and Ollama Implementation.

Verifies:
- Fast model -> Intent classification
- Reasoning-capable model -> Planning
- Vision model -> Screen analysis
- Embedding model -> Memory retrieval
- Changing models dynamically without changing JARVIS architecture
- MockLLMProvider testability
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional

from jarvis.core.llm_provider import LLMProvider, ModelRole
from jarvis.core.model_manager import ModelManager, DEFAULT_ROLE_MODELS
from jarvis.subsystems.local.ollama_provider import OllamaProvider
from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.subsystems.memory.vector_store import SQLiteVectorStore
from jarvis.subsystems.memory.long_term_memory import KnowledgeMemory
from jarvis.subsystems.memory.schemas import KnowledgeItem
from jarvis.subsystems.vision.vision_model import VisionModel
from jarvis.subsystems.vision.screen_capture import CapturedScreen
from jarvis.capabilities.reasoning.intent_analyzer import IntentAnalyzer, IntentType


class MockCustomLLMProvider(LLMProvider):
    """Custom mock provider demonstrating swappable model backends without touching JARVIS."""

    def __init__(self):
        self.call_log: List[Dict[str, Any]] = []

    def generate(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, role: Optional[ModelRole] = None, **kwargs) -> str:
        self.call_log.append({"method": "generate", "prompt": prompt, "role": role, "model": model})
        return f"Mock generated response for {prompt}"

    def structured_output(self, prompt: str, schema: Dict[str, Any], system_prompt: Optional[str] = None, model: Optional[str] = None, role: Optional[ModelRole] = None, **kwargs) -> Dict[str, Any]:
        self.call_log.append({"method": "structured_output", "prompt": prompt, "role": role, "model": model})
        return {"intent_type": "READ_QUERY", "target_tool": "get_hardware_metrics"}

    def embed(self, text: str, model: Optional[str] = None, role: Optional[ModelRole] = None, **kwargs) -> List[float]:
        self.call_log.append({"method": "embed", "text": text, "role": role, "model": model})
        # Return a simple 4-dimensional normalized vector
        if "database" in text.lower() or "dbms" in text.lower():
            return [1.0, 0.0, 0.0, 0.0]
        elif "network" in text.lower():
            return [0.0, 1.0, 0.0, 0.0]
        return [0.5, 0.5, 0.0, 0.0]

    def vision(self, image_data: str, prompt: str, model: Optional[str] = None, role: Optional[ModelRole] = None, **kwargs) -> str:
        self.call_log.append({"method": "vision", "prompt": prompt, "role": role, "model": model})
        return "Screen analysis: Terminal active with zero error dialogs."


class TestLLMProviderArchitecture(unittest.TestCase):
    """Test model abstraction, dynamic model swapping, and role routing."""

    def test_model_roles_and_manager(self):
        """Verify ModelManager maps roles and allows runtime model reassignment."""
        manager = ModelManager()
        self.assertEqual(manager.get_model(ModelRole.FAST), "qwen2.5:1.5b")
        self.assertEqual(manager.get_model(ModelRole.REASONING), "qwen2.5:3b")
        self.assertEqual(manager.get_model(ModelRole.VISION), "llava")
        self.assertEqual(manager.get_model(ModelRole.EMBEDDING), "nomic-embed-text")

        # Swap model dynamically
        manager.set_model(ModelRole.FAST, "llama3.2:1b")
        self.assertEqual(manager.get_model(ModelRole.FAST), "llama3.2:1b")
        # Other roles remain unchanged
        self.assertEqual(manager.get_model(ModelRole.REASONING), "qwen2.5:3b")

    def test_ollama_provider_contract(self):
        """Verify OllamaProvider adheres to the LLMProvider interface."""
        provider = OllamaProvider()
        self.assertIsInstance(provider, LLMProvider)

        # Test embed deterministic fallback
        vec = provider.embed("Sample text for embedding test")
        self.assertIsInstance(vec, list)
        self.assertEqual(len(vec), 64)

        # Test structured_output fallback
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "active": {"type": "boolean"},
            },
        }
        res = provider.structured_output("Generate mock object", schema=schema)
        self.assertIn("name", res)
        self.assertIn("count", res)
        self.assertIn("active", res)

    def test_fast_model_intent_classification(self):
        """Verify IntentAnalyzer utilizes ModelRole.FAST for classification."""
        mock_provider = MockCustomLLMProvider()
        analyzer = IntentAnalyzer(llm_provider=mock_provider)

        intent = analyzer.classify_with_fast_model("Tell me my CPU and RAM stats")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.intent_type, IntentType.READ_QUERY)

        # Check call log proves ModelRole.FAST was passed
        fast_calls = [c for c in mock_provider.call_log if c.get("role") == ModelRole.FAST]
        self.assertTrue(len(fast_calls) > 0)
        self.assertEqual(fast_calls[0]["method"], "structured_output")

    def test_vision_model_uses_vision_role(self):
        """Verify VisionModel delegates to LLMProvider with ModelRole.VISION."""
        mock_provider = MockCustomLLMProvider()
        vision_model = VisionModel(llm_provider=mock_provider)

        screen = CapturedScreen(
            image_path="test.png",
            width=1920,
            height=1080,
            base64_data="mock_base64_data",
            source="virtual_framebuffer",
            timestamp=12345.0,
        )
        analysis = vision_model.analyze_screen(screen, prompt="Inspect desktop")
        self.assertIn("Screen analysis:", analysis.description)

        # Verify vision call logged with ModelRole.VISION
        vision_calls = [c for c in mock_provider.call_log if c.get("role") == ModelRole.VISION]
        self.assertTrue(len(vision_calls) > 0)
        self.assertEqual(vision_calls[0]["method"], "vision")

    def test_embedding_model_memory_retrieval(self):
        """Verify KnowledgeMemory uses ModelRole.EMBEDDING and vector store cosine similarity."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_memory.db")

        try:
            mock_provider = MockCustomLLMProvider()
            vstore = SQLiteVectorStore(db_path=db_path)
            km = KnowledgeMemory(db_path=db_path, llm_provider=mock_provider, vector_store=vstore)

            # Store two items
            item1 = KnowledgeItem(id="doc_1", title="Database Notes", content="ACID transactions in DBMS", tags=["db", "sql"])
            item2 = KnowledgeItem(id="doc_2", title="Networking Guide", content="TCP/IP sockets and routing", tags=["net"])
            km.add_item(item1)
            km.add_item(item2)

            # Check that embedding calls were logged with ModelRole.EMBEDDING
            embed_calls = [c for c in mock_provider.call_log if c.get("role") == ModelRole.EMBEDDING]
            self.assertTrue(len(embed_calls) >= 2)

            # Perform semantic search for "database query"
            results = km.semantic_search("database query", limit=1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].id, "doc_1")
            self.assertEqual(results[0].title, "Database Notes")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_ollama_client_backward_compatibility(self):
        """Verify OllamaClient maintains complete backward compatibility while exposing new provider methods."""
        client = OllamaClient()
        self.assertTrue(hasattr(client, "chat"))
        self.assertTrue(hasattr(client, "generate"))
        self.assertTrue(hasattr(client, "structured_output"))
        self.assertTrue(hasattr(client, "embed"))
        self.assertTrue(hasattr(client, "vision"))
        self.assertEqual(client.model, "qwen2.5:3b")


if __name__ == "__main__":
    unittest.main()
