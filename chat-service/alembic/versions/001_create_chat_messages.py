"""create chat_messages table

Revision ID: chat_001
Revises:
Create Date: 2025-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'chat_001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chat_messages table with indexes."""
    op.create_table(
        'chat_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False, comment='Primary key — unique message ID'),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True, comment='Internal user UUID — can be NULL if only window_id is known'),
        sa.Column('window_id', sa.String(length=255), nullable=False, comment='Zalo user ID — always present'),
        sa.Column('role', sa.String(length=50), nullable=False, comment="Message role: 'user', 'assistant', or 'system'"),
        sa.Column('content', sa.Text(), nullable=False, comment='Message text content'),
        sa.Column('metadata', JSONB, nullable=False, server_default='{}', comment='Extensible metadata (tool_calls, model_name, etc.)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Message creation timestamp'),
    )

    # Create indexes
    op.create_index('ix_chat_messages_user_id', 'chat_messages', ['user_id'])
    op.create_index('ix_chat_messages_window_id', 'chat_messages', ['window_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])

    # Composite indexes for fast top-K queries
    op.create_index(
        'ix_chat_messages_user_id_created_at',
        'chat_messages',
        ['user_id', sa.text('created_at DESC')],
    )
    op.create_index(
        'ix_chat_messages_window_id_created_at',
        'chat_messages',
        ['window_id', sa.text('created_at DESC')],
    )


def downgrade() -> None:
    """Drop chat_messages table."""
    op.drop_index('ix_chat_messages_window_id_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_user_id_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_window_id', table_name='chat_messages')
    op.drop_index('ix_chat_messages_user_id', table_name='chat_messages')
    op.drop_table('chat_messages')
