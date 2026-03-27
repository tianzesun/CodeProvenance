"""
Database configuration module for CodeProvenance.

This module provides database connection configuration and session management.
"""

import os
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')


class DatabaseConfig:
    """
    Database configuration class.
    
    Handles database connection settings and session management.
    """
    
    def __init__(self):
        """
        Initialize database configuration from environment variables.
        """
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        # Connection pool settings
        self.pool_size = int(os.getenv('DB_POOL_SIZE', '20'))
        self.max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '30'))
        self.pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        self.pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '1800'))
        
        # Query settings
        self.echo = os.getenv('DB_ECHO', 'false').lower() == 'true'
        self.echo_pool = os.getenv('DB_ECHO_POOL', 'false').lower() == 'true'
    
    def get_engine(self):
        """
        Create and return a SQLAlchemy engine with connection pooling.
        
        Returns:
            SQLAlchemy Engine instance
        """
        return create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            echo=self.echo,
            echo_pool=self.echo_pool,
            # PostgreSQL specific settings
            connect_args={
                'sslmode': 'require',
                'channel_binding': 'require'
            }
        )
    
    def get_session_factory(self):
        """
        Create and return a session factory.
        
        Returns:
            SQLAlchemy sessionmaker instance
        """
        engine = self.get_engine()
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Global database configuration instance
db_config = DatabaseConfig()

# Global session factory
SessionLocal = db_config.get_session_factory()


def get_db() -> Session:
    """
    Dependency function to get database session.
    
    Yields:
        SQLAlchemy Session instance
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_tenant_context(db: Session, tenant_id: str) -> None:
    """
    Set the tenant context for Row-Level Security (RLS).
    
    This function sets the app.current_tenant_id PostgreSQL setting
    which is used by RLS policies to filter data by tenant.
    
    Args:
        db: SQLAlchemy Session instance
        tenant_id: UUID string of the tenant
    """
    db.execute(f"SET app.current_tenant_id = '{tenant_id}'")


def clear_tenant_context(db: Session) -> None:
    """
    Clear the tenant context.
    
    Args:
        db: SQLAlchemy Session instance
    """
    db.execute("RESET app.current_tenant_id")


def get_tenant_context(db: Session) -> Optional[str]:
    """
    Get the current tenant context.
    
    Args:
        db: SQLAlchemy Session instance
        
    Returns:
        Tenant ID string or None if not set
    """
    result = db.execute("SHOW app.current_tenant_id").scalar()
    return result if result else None


# Event listener to set tenant context on connection
@event.listens_for(Session, 'after_begin')
def set_tenant_on_begin(session, transaction, connection):
    """
    Event listener to set tenant context when a transaction begins.
    
    This ensures that RLS policies are applied for all queries
    within the transaction.
    """
    # Check if tenant_id is set in session info
    tenant_id = session.info.get('tenant_id')
    if tenant_id:
        connection.execute(f"SET app.current_tenant_id = '{tenant_id}'")


# Event listener to clear tenant context on connection close
@event.listens_for(Session, 'after_transaction_end')
def clear_tenant_on_end(session, transaction):
    """
    Event listener to clear tenant context when a transaction ends.
    """
    # Reset the tenant context
    session.execute("RESET app.current_tenant_id")
