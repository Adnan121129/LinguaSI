from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, auth, comprehension, health, lab, learner, me, mistakes, speaking, tutor, vocabulary, writing

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(writing.router)
api_router.include_router(vocabulary.router)
api_router.include_router(mistakes.router)
api_router.include_router(mistakes.practice_router)
api_router.include_router(comprehension.reading_router)
api_router.include_router(comprehension.listening_router)
api_router.include_router(speaking.router)
api_router.include_router(learner.onboarding_router)
api_router.include_router(learner.dashboard_router)
api_router.include_router(learner.progress_router)
api_router.include_router(learner.recommendations_router)
api_router.include_router(learner.gamification_router)
api_router.include_router(tutor.router)
api_router.include_router(lab.router)
api_router.include_router(admin.router)
