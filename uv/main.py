from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator, ConfigDict

app = FastAPI()


# ---------- 原有路由，保留 ----------
@app.get("/")
def read_root():
    return {"message": "Hello, uv + FastAPI"}


# ---------- 新增：Pydantic 模型 ----------
class Message(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content 不能只包含空白字符")
        return value.strip()


class Request(BaseModel):
    model: str = Field(min_length=1, max_length=64)
    messages: list[Message] = Field(min_length=1, max_length=50)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)


# ---------- 新增：使用模型的 POST 路由 ----------
@app.post("/chat")
def chat(request: Request):
    return {
        "model": request.model,
        "messages": request.messages,
        "temperature": request.temperature,
    }