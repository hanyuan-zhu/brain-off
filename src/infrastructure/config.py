"""
Configuration management for the AI Task Manager application.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="dev-secret-key-change-in-production", alias="SECRET_KEY")
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot",
        alias="DATABASE_URL"
    )

    # DeepSeek API (for LLM)
    deepseek_api_key: str = Field(..., alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="DEEPSEEK_BASE_URL"
    )

    # DashScope API (for Embeddings)
    dashscope_api_key: str = Field(..., alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL"
    )
    dashscope_embedding_model: str = Field(
        default="text-embedding-v4",
        alias="DASHSCOPE_EMBEDDING_MODEL"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
