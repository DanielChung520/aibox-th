"""
AITask Service Unit Tests

Standalone tests that verify model structures without requiring dependencies.

# Last Update: 2026-03-18 04:00:00
# Author: Daniel Chung
# Version: 1.0.0
"""

import ast
import os


def test_aitask_models_are_defined():
    """Verify all required models are defined in aitask/main.py"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/aitask/main.py")
    
    with open(filepath, "r") as f:
        tree = ast.parse(f.read())
    
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    
    assert "ChatMessage" in class_names, "ChatMessage class not found"
    assert "ChatRequest" in class_names, "ChatRequest class not found"
    assert "ServiceInfo" in class_names, "ServiceInfo class not found"
    assert "HealthResponse" in class_names, "HealthResponse class not found"
    
    print("✓ All required models are defined")


def test_aitask_endpoints_are_defined():
    """Verify all required endpoints are defined"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/aitask/main.py")
    
    with open(filepath, "r") as f:
        content = f.read()
    
    assert 'app.get("/"' in content, "Root endpoint not found"
    assert 'app.get("/health"' in content, "Health endpoint not found"
    assert 'app.post("/v1/chat/completions"' in content, "Chat completions endpoint not found"
    assert 'app.post("/chat"' in content, "Chat endpoint not found"
    assert 'app.get("/models"' in content, "List models endpoint not found"
    
    print("✓ All required endpoints are defined")


def test_aitask_stream_chat_generator():
    """Verify stream_chat function exists and is async generator"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/aitask/main.py")
    
    with open(filepath, "r") as f:
        content = f.read()
    
    assert "async def stream_chat" in content, "stream_chat function not found"
    assert "async def chat_completions" in content, "chat_completions function not found"
    assert "async def chat" in content, "chat function not found"
    
    print("✓ All required functions are defined")


def test_bpa_models_are_defined():
    """Verify BPA models are defined"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/bpa/main.py")
    
    with open(filepath, "r") as f:
        tree = ast.parse(f.read())
    
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    
    assert "WorkflowStatus" in class_names, "WorkflowStatus enum not found"
    assert "WorkflowStep" in class_names, "WorkflowStep class not found"
    assert "Workflow" in class_names, "Workflow class not found"
    
    print("✓ BPA models are defined")


def test_mcp_tools_registry():
    """Verify MCP tools registry is defined"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/mcp_tools/main.py")
    
    with open(filepath, "r") as f:
        content = f.read()
    
    assert "TOOL_REGISTRY" in content, "TOOL_REGISTRY not found"
    assert '"calculator"' in content, "Calculator tool not found"
    assert '"web_search"' in content, "Web search tool not found"
    assert '"weather"' in content, "Weather tool not found"
    assert '"code_executor"' in content, "Code executor tool not found"
    
    print("✓ MCP tools registry is defined")


def test_data_query_system_prompt():
    """Verify Data Query has system prompt for AQL generation"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/data_query/main.py")
    
    with open(filepath, "r") as f:
        content = f.read()
    
    assert "SYSTEM_PROMPT" in content, "SYSTEM_PROMPT not found"
    assert "FOR...FILTER...RETURN" in content, "AQL pattern not in prompt"
    
    print("✓ Data Query system prompt is defined")


def test_knowledge_assets_rag_functions():
    """Verify Knowledge Assets has RAG functions"""
    filepath = os.path.join(os.path.dirname(__file__), "../../ai-services/knowledge_assets/main.py")
    
    with open(filepath, "r") as f:
        content = f.read()
    
    assert "async def get_embedding" in content, "get_embedding function not found"
    assert "async def search_similar" in content, "search_similar function not found"
    assert "async def generate_answer" in content, "generate_answer function not found"
    
    print("✓ Knowledge Assets RAG functions are defined")


if __name__ == "__main__":
    test_aitask_models_are_defined()
    test_aitask_endpoints_are_defined()
    test_aitask_stream_chat_generator()
    test_bpa_models_are_defined()
    test_mcp_tools_registry()
    test_data_query_system_prompt()
    test_knowledge_assets_rag_functions()
    print("\n✅ All Wave 4 unit tests passed!")
