from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).parent.parent  # luôn trỏ đến root dù chạy từ đâu
SYSTEM_PROMPT = """
Bạn là hệ thống trả lời dựa trên tài liệu (RAG).

QUY TẮC:
1. Chỉ dùng thông tin trong CONTEXT
2. Mỗi ý phải có citation dạng [id]
3. Nếu không đủ thông tin → trả lời: "Không đủ dữ liệu"
4. Không suy đoán
"""


class LLMConfig(BaseSettings):
    OPENAI_API_KEY: str = Field(alias="OPENAI_API_KEY")
    SYSTEM_PROMPT: str = SYSTEM_PROMPT
    
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=str(ROOT / ".env"),  # đường dẫn tuyệt đối đến .env
        populate_by_name=True,
    )