# adapters/logging/logger_adapter.py

import logging
from core.ports.logging_port import ILoggingPort

class LoggerAdapter(ILoggingPort):
    def __init__(self, level=logging.INFO, file_path: str | None = None):
        # Projeye özel logger nesnesi yaratılıyor. getLogger kullanarak daha önce bir logger yaratılmışsa onu getiriyoruz, yoksa yaratıyoruz.
        # Yani aynı isimle tekrar tekrar çağırırsan aynı nesneyi verecektir. (singleton)
        self.logger = logging.getLogger("FJSMLogger")
        # Nesnenin seviyesini ayarlıyoruz.
        self.logger.setLevel(level)
        formatter = logging.Formatter('[%(levelname)s] %(message)s')

        # Mesajları konsola gönderen handler'dır.
        console_handler = logging.StreamHandler()
        # Bu handler'a verdiğimiz formatı kullan diyoruz.
        console_handler.setFormatter(formatter)
        # Handler'ımızı ana logger'a ekliyoruz. Artık logger'a gelen her mesaj konsola basılır.
        self.logger.addHandler(console_handler)

        if file_path:
            # Mesajları eğer bir dosya yolu vermişsek ikincil bir handler yaratıyoruz.
            # Her çalıştırıldığında temizlenip üzerine yazılması için modunu koydum.
            file_handler = logging.FileHandler(file_path, mode = "w")
            # Bu handler'ın da formatımızı kullanmasını sağlıyoruz.
            file_handler.setFormatter(formatter)
            # Bu handler'ımızı da ana logger'a ekliyoruz. Artık logger'a gelen her mesaj dosyaya (verilmişse yolu) yazılacak.
            self.logger.addHandler(file_handler)

    def info(self, message: str) -> None:
        # Verdiğimiz mesajı logging kütüphanesine yolluyoruz, işi kütüphane yapar.
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)
