import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from tests.test_security import test_password_hashing, test_jwt_generation
from tests.test_database import test_database_flow
from tests.test_upload import test_document_upload_flow
from tests.test_processing import test_processing_orchestration
from tests.test_vector import test_vector_indexing_and_search
from tests.test_rag import test_rag_grounding_flow
from tests.test_agents import test_agent_graph_routing
from tests.test_chat import test_chat_assistant_flow
from tests.test_pyq_analytics import test_pyq_analytics_flow
from tests.test_study_planner import test_study_planner_flow
from tests.test_quiz_generator import test_quiz_generator_flow
from tests.test_answers_evaluation import test_essay_evaluation_flow
from tests.test_analytics import test_analytics_dashboard_flow

def run_tests():
    print("Running Security Unit Tests...")
    try:
        test_password_hashing()
        print("OK: Password hashing tests passed.")
        
        test_jwt_generation()
        print("OK: JWT generation tests passed.")
        
        print("\nRunning Database Integration Tests...")
        asyncio.run(test_database_flow())
        print("OK: Database integration tests passed.")
        
        print("\nRunning Document Ingestion Pipeline Tests...")
        asyncio.run(test_document_upload_flow())
        print("OK: Document ingestion pipeline tests passed.")
        
        print("\nRunning Document Processing Pipeline Tests...")
        asyncio.run(test_processing_orchestration())
        print("OK: Document processing pipeline tests passed.")
        
        print("\nRunning Vector Database Integration Tests...")
        asyncio.run(test_vector_indexing_and_search())
        print("OK: Vector database integration tests passed.")
        
        print("\nRunning RAG Engine Integration Tests...")
        asyncio.run(test_rag_grounding_flow())
        print("OK: RAG engine integration tests passed.")
        
        print("\nRunning LangGraph AI Agents Integration Tests...")
        asyncio.run(test_agent_graph_routing())
        print("OK: LangGraph AI Agents integration tests passed.")
        
        print("\nRunning Chat Assistant E2E Tests...")
        asyncio.run(test_chat_assistant_flow())
        print("OK: Chat Assistant E2E tests passed.")
        
        print("\nRunning PYQ Ingestion & Analytics Tests...")
        asyncio.run(test_pyq_analytics_flow())
        print("OK: PYQ Ingestion & Analytics tests passed.")
        
        print("\nRunning Study Planner E2E Tests...")
        asyncio.run(test_study_planner_flow())
        print("OK: Study Planner E2E tests passed.")
        
        print("\nRunning Quiz Generator E2E Tests...")
        asyncio.run(test_quiz_generator_flow())
        print("OK: Quiz Generator E2E tests passed.")
        
        print("\nRunning Essay Answer Evaluation E2E Tests...")
        asyncio.run(test_essay_evaluation_flow())
        print("OK: Essay Answer Evaluation E2E tests passed.")
        
        print("\nRunning Analytics Dashboard E2E Tests...")
        asyncio.run(test_analytics_dashboard_flow())
        print("OK: Analytics Dashboard E2E tests passed.")
        
        print("\nAll unit and integration tests passed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: Assert Error during testing: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
