from __future__ import annotations

from pydantic import BaseModel, Field


class UserUpdateRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(learner|admin)$")


class VocabularyCreateRequest(BaseModel):
    word: str = Field(min_length=1, max_length=80)
    part_of_speech: str = Field(pattern="^(noun|verb|adjective|adverb|phrase|phrasal verb|preposition|conjunction|idiom|collocation)$")
    definition: str = Field(min_length=3, max_length=500)
    example: str = Field(min_length=3, max_length=500)
    synonyms: list[str] = Field(default_factory=list, max_length=10)
    collocations: list[str] = Field(default_factory=list, max_length=10)
    topics: list[str] = Field(default_factory=list, max_length=10)
    cefr: str = Field(default="B2", pattern="^(A1|A2|B1|B2|C1|C2)$")
    is_academic: bool = False
