"""
Database Schemas for Misión AMVISION 10K

Each Pydantic model maps to a MongoDB collection (lowercased class name).
Use these to validate incoming data and to help the database viewer.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class Player(BaseModel):
    """
    Collection: "player"
    Represents a user participating in the mission program.
    """
    name: str = Field(..., description="Player full name")
    email: EmailStr = Field(..., description="Unique email for the player")
    av_coins: int = Field(0, ge=0, description="Reward currency balance")
    revenue_usd: float = Field(0, ge=0, description="Accumulated revenue in USD")
    completed_milestones: List[str] = Field(default_factory=list, description="IDs of completed milestones")
    unlocked_worlds: List[str] = Field(default_factory=list, description="Unlocked worlds/upsells")

class Milestone(BaseModel):
    """
    Collection: "milestone"
    Static catalog of program milestones.
    """
    milestone_id: str = Field(..., description="Stable ID, e.g., 'm1'")
    title: str
    description: Optional[str] = None
    order: int = Field(..., ge=1, description="Display order")

class Reward(BaseModel):
    """
    Collection: "reward"
    Tracks coin grants for audit/history.
    """
    player_id: str
    milestone_id: Optional[str] = None
    reason: str = Field(..., description="Why the reward was granted")
    coins: int = Field(..., ge=0)
    created_at: Optional[datetime] = None
