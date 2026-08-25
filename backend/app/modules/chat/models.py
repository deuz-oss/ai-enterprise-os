"""Fase 11 — Chat Workspace ala Slack (PRD §9).

Model: Channel, ChannelMember, Message, MessageReaction.
Akses di-paksakan server-side: karyawan outsourcing hanya melihat channel
proyeknya + DM se-scope. WebSocket menyusul; v1 memakai polling.
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tenancy import TenantMixin


class ChannelType(str, enum.Enum):
    public = "public"
    private = "private"
    dm = "dm"
    broadcast = "broadcast"  # hanya admin/Ops bisa posting


class Channel(TenantMixin, Base):
    __tablename__ = "chat_channels"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), index=True)  # mis. #proyek-pt-x
    channel_type: Mapped[str] = mapped_column(
        String(20), default="public"
    )  # public | private | dm | broadcast
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members = relationship("ChatChannelMember", back_populates="channel")
    messages = relationship("ChatMessage", back_populates="channel")


class ChatChannelMember(TenantMixin, Base):
    __tablename__ = "chat_channel_members"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_chat_member"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("chat_channels.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("Channel", back_populates="members")


class ChatMessage(TenantMixin, Base):
    """Pesan chat; parent_id untuk thread reply; soft delete."""

    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("chat_channels.id"), index=True)
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id"), default=None, index=True
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Card interaktif (Fase 11 lanjutan): notifikasi ber-tombol aksi.
    message_type: Mapped[str] = mapped_column(String(20), default="text")
    card_data: Mapped[dict | None] = mapped_column(JSON(), default=None)
    actions: Mapped[list | None] = mapped_column(JSON(), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("Channel", back_populates="messages")
    reactions = relationship(
        "ChatMessageReaction", back_populates="message", cascade="all, delete-orphan"
    )


class ChatMessageReaction(TenantMixin, Base):
    __tablename__ = "chat_message_reactions"
    __table_args__ = (UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(ForeignKey("chat_messages.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    emoji: Mapped[str] = mapped_column(String(20))

    message = relationship("ChatMessage", back_populates="reactions")
