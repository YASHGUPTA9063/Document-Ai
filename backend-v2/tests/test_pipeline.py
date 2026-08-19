import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from platform_core.pipeline.engine import PipelineEngine, PipelineDefinition, StepDefinition
from platform_core.pipeline.checkpoint import CheckpointManager
from platform_core.isolation.sandbox import StepSandbox
from platform_core.registry import ProviderRegistry

@pytest.mark.asyncio
async def test_pipeline_engine_success():
    """Test that the pipeline engine runs steps sequentially and modifies context."""
    
    # Mock handlers
    async def step1(ctx):
        return {"step1": "done", "value": 10}
        
    async def step2(ctx):
        assert ctx["value"] == 10
        return {"step2": "done", "value": 20}
        
    pipeline = PipelineDefinition(name="test_pipe", steps=[
        StepDefinition(name="s1", handler=step1),
        StepDefinition(name="s2", handler=step2),
    ])
    
    engine = PipelineEngine(checkpoint_mgr=CheckpointManager())
    context = {"document_id": "test_doc"}
    
    result = await engine.run(pipeline, context)
    
    assert result["step1"] == "done"
    assert result["step2"] == "done"
    assert result["value"] == 20
    assert len(result["_step_results"]) == 2
    assert result["_step_results"][0]["status"] == "completed"

@pytest.mark.asyncio
async def test_pipeline_engine_hitl_pause():
    """Test that the pipeline pauses correctly when HumanInputRequired is raised."""
    from platform_core.pipeline.engine import HumanInputRequired
    
    async def step1(ctx):
        return {"step1": "done"}
        
    async def step2(ctx):
        raise HumanInputRequired(reason="Need human approval")
        
    pipeline = PipelineDefinition(name="test_pipe", steps=[
        StepDefinition(name="s1", handler=step1),
        StepDefinition(name="s2", handler=step2),
    ])
    
    checkpoint_mgr = CheckpointManager()
    engine = PipelineEngine(checkpoint_mgr=checkpoint_mgr)
    context = {"document_id": "hitl_doc"}
    
    result = await engine.run(pipeline, context)
    
    assert result.get("_paused_at") == "s2"
    assert result.get("_paused_reason") == "Need human approval"
    
    # Verify checkpoint was saved
    checkpoint = await checkpoint_mgr.load("hitl_doc")
    assert checkpoint is not None
    assert checkpoint["completed_step_index"] == 0 # s1 completed, s2 failed/paused
