import asyncio
import uuid

from app.database.session import SessionLocal
from app.models.user import User
from app.models.subject import Subject
from app.services.agents import agent_orchestration_service


async def test_agent_graph_routing():
    print("Beginning LangGraph AI Agents Integration and Routing Test...")
    
    async with SessionLocal() as db:
        # Setup temporary course Subject & User
        test_user = User(
            email=f"agentist_{uuid.uuid4().hex[:6]}@sppu.edu.in",
            hashed_password="hashed_password",
            full_name="Agent Tester",
            role="student"
        )
        db.add(test_user)
        
        test_subject = Subject(
            code=f"CS-AG-{uuid.uuid4().hex[:4].upper()}",
            name="Testing LangGraph Workflow Routing",
            semester=6,
            branch="Computer Engineering"
        )
        db.add(test_subject)
        await db.commit()
        await db.refresh(test_user)
        await db.refresh(test_subject)

        # Query 1: Study Planner Router Trigger Check
        print("\nExecuting Query 1: 'create a study calendar plan for my exams'...")
        state_plan = await agent_orchestration_service.run_agent_workflow(
            query="create a study calendar plan for my exams",
            subject_id=test_subject.id,
            user_id=test_user.id
        )
        assert state_plan["next_agent"] == "end"
        assert "Study Plan" in state_plan["response"]
        assert "|" in state_plan["response"]  # Markdown table verified
        print("OK: Study planner routed and generated plan successfully.")

        # Query 2: Exam Predictor Router Trigger Check
        print("\nExecuting Query 2: 'predict exam focus areas'...")
        state_predict = await agent_orchestration_service.run_agent_workflow(
            query="predict exam focus areas",
            subject_id=test_subject.id,
            user_id=test_user.id
        )
        assert state_predict["next_agent"] == "end"
        assert "Disclaimer" in state_predict["response"]  # Predictor disclaimer verification
        assert "Probability" in state_predict["response"]
        print("OK: Exam predictor routed and output disclaimer successfully.")

        # Query 3: Answer Evaluator Router Trigger Check
        print("\nExecuting Query 3: 'evaluate my answer: loaders copy program segments to RAM'...")
        state_eval = await agent_orchestration_service.run_agent_workflow(
            query="evaluate my answer: loaders copy program segments to RAM",
            subject_id=test_subject.id,
            user_id=test_user.id
        )
        assert state_eval["next_agent"] == "end"
        assert "Evaluation" in state_eval["response"]
        assert "Marks" in state_eval["response"]
        print("OK: Answer evaluator routed and graded answer successfully.")

        # Cleanup
        await db.delete(test_subject)
        await db.delete(test_user)
        await db.commit()
        print("\nDatabase entities cleared.")
        print("LangGraph AI Agents Integration and Routing Test: PASSED")


if __name__ == "__main__":
    asyncio.run(test_agent_graph_routing())
