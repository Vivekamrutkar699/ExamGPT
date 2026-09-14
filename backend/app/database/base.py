# Import all the models so that Base has them registered before migrations are generated.
# This is used by Alembic.

from app.database.base_class import Base  # noqa
from app.models.user import User  # noqa
from app.models.subject import Subject  # noqa
from app.models.document import Document  # noqa
from app.models.chunk import Chunk  # noqa
from app.models.question import Question  # noqa
from app.models.study_plan import StudyPlan  # noqa
from app.models.quiz import Quiz  # noqa
from app.models.answers_evaluation import AnswersEvaluation  # noqa
from app.models.chat import ChatSession, ChatMessage  # noqa
from app.models.pyq_topic import (  # noqa
    CanonicalTopic,
    PYQPaper,
    PYQQuestionOccurrence,
    QuestionVariant,
)
