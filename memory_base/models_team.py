"""
AI 员工团队：角色、能力绑定、提示词版本。

- EmployeeRole: 角色名、描述、状态（enabled/disabled）
- RoleAbility: 角色与能力 ID 多对多
- PromptVersion: 角色系统提示词版本历史
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from memory_base.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EmployeeRole(Base):
    """AI 员工角色：名称、描述、启用状态、绑定的对话模型。"""

    __tablename__ = "employee_roles"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    # 角色调用时使用的对话模型 ID，须为 config chat_providers 中配置的 models 之一
    default_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class RoleAbility(Base):
    """角色与能力绑定（多对多；ability_id 为能力标识字符串）。"""

    __tablename__ = "role_abilities"

    role_name: Mapped[str] = mapped_column(
        String(128), ForeignKey("employee_roles.name", ondelete="CASCADE"), primary_key=True
    )
    ability_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class PromptVersion(Base):
    """角色系统提示词版本历史。"""

    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    role_name: Mapped[str] = mapped_column(
        String(128), ForeignKey("employee_roles.name", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
