from typing import List, Optional
from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    username: str
    pin: str
    email: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    pin: str


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    type: str  # 'unica' | 'periodica' | 'manual'
    recurrence_kind: Optional[str] = None  # 'intervalo_dias' | 'dia_fixo_mes' | 'dia_semana'
    recurrence_value: Optional[str] = None
    recurrence_end_date: Optional[str] = None  # 'YYYY-MM-DD', fim da recorrência
    recurrence_max_occurrences: Optional[int] = None  # limite de repetições
    priority: str = "media"  # 'baixa' | 'media' | 'alta'
    assigned_to: Optional[int] = None
    due_date: Optional[str] = None  # 'YYYY-MM-DD', data limite (só tarefas únicas)
    tags: Optional[List[str]] = None
    needs_confirmation: bool = False


class TaskUpdate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "media"  # 'baixa' | 'media' | 'alta'
    assigned_to: Optional[int] = None
    due_date: Optional[str] = None  # 'YYYY-MM-DD', só tarefas únicas; None = sem prazo
    tags: Optional[List[str]] = None
    needs_confirmation: bool = False


class CommentCreate(BaseModel):
    text: str


class ConfirmationDecision(BaseModel):
    action: str  # 'concluir' | 'devolver'
    comment: str
