"""All ORM models. Importing this package registers every table on Base.metadata (used by Alembic)."""

from app.models.base import Base
from app.models.gamification import Achievement, DailyMission, Streak, UserAchievement, UserChallenge, XPTransaction
from app.models.learner import IELTS_SKILLS, SKILLS, LearnerSkillProfile, ProgressSnapshot, SIEvent, StudySession
from app.models.listening import ListeningAttempt, ListeningQuestion, ListeningScript
from app.models.misc import (
    AIInteractionLog,
    DiagnosticAttempt,
    Recommendation,
    SystemLog,
    TutorConversation,
    TutorMessage,
)
from app.models.mistakes import MISTAKE_STATUSES, Mistake
from app.models.practice import GrammarExercise, PracticeSet
from app.models.reading import ReadingAttempt, ReadingPassage, ReadingQuestion
from app.models.speaking import SpeakingEvaluation, SpeakingSession, SpeakingTopic, SpeakingTranscript
from app.models.user import AuthSession, LearningGoal, Profile, User
from app.models.vocabulary import VOCAB_STATES, UserVocabulary, VocabularyItem, VocabularyReview
from app.models.writing import WritingError, WritingEvaluation, WritingSubmission, WritingTask

__all__ = [
    "AIInteractionLog",
    "Achievement",
    "AuthSession",
    "Base",
    "DailyMission",
    "DiagnosticAttempt",
    "GrammarExercise",
    "IELTS_SKILLS",
    "LearnerSkillProfile",
    "LearningGoal",
    "ListeningAttempt",
    "ListeningQuestion",
    "ListeningScript",
    "MISTAKE_STATUSES",
    "Mistake",
    "PracticeSet",
    "Profile",
    "ProgressSnapshot",
    "ReadingAttempt",
    "ReadingPassage",
    "ReadingQuestion",
    "Recommendation",
    "SIEvent",
    "SKILLS",
    "SpeakingEvaluation",
    "SpeakingSession",
    "SpeakingTopic",
    "SpeakingTranscript",
    "Streak",
    "StudySession",
    "SystemLog",
    "TutorConversation",
    "TutorMessage",
    "User",
    "UserAchievement",
    "UserChallenge",
    "UserVocabulary",
    "VOCAB_STATES",
    "VocabularyItem",
    "VocabularyReview",
    "WritingError",
    "WritingEvaluation",
    "WritingSubmission",
    "WritingTask",
    "XPTransaction",
]
