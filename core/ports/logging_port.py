# core/ports/logging_port.py

from abc import ABC, abstractmethod

class ILoggingPort(ABC):
    @abstractmethod
    def info(self, message: str) -> None:
        pass

    @abstractmethod
    def warning(self, message: str) -> None:
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        pass

    @abstractmethod
    def debug(self, message: str) -> None:
        pass

# Info: Önemli olaylar, başlatma, tamamlama, durum özeti için kullanılır.
# Warning: İş devam eder ama ileride problem çıkabilir demek için kullanılır.
# Error: Sistemsel hata, görev atanamadı, çözüm bulunamadı gibi şeyler için kullanılır.
# Debug: Geliştirici içindir, değerler, flow, iteration, kararlar için kullanılır.
# Critical: Tüm sistemin durduğu zamanlar için kullanılır. (Şuanda bu konulmadı.)