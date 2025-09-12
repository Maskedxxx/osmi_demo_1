from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class DocumentFile:
    """Модель для загруженных документов"""
    filename: str
    file_id: str
    file_size: int
    upload_date: datetime
    file_type: str = "docx"
    user_id: Optional[int] = None
    
    def get_metadata_text(self) -> str:
        """Возвращает текст с метаданными для отправки пользователю"""
        size_mb = round(self.file_size / 1024 / 1024, 2)
        return f"""📄 Документ загружен!

📝 Название: {self.filename}
📊 Размер: {size_mb} MB
📅 Загружен: {self.upload_date.strftime('%d.%m.%Y %H:%M')}
🔖 Тип: {self.file_type.upper()}"""