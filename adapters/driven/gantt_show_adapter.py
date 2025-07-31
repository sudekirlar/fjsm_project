# adapters/driven/gantt_show_adapter.py

import matplotlib.pyplot as plt
from core.models.data_model import PlanResultDTO
from typing import List
from core.ports.logging_port import ILoggingPort

class GanttChartRenderer:
    def __init__(self, output_path: str = "gantt_chart.png", logger: ILoggingPort | None = None):
        self.output_path = output_path
        self.logger = logger

    def render(self, plan_results: List[PlanResultDTO]):
        """
        Sonuç listesini alır ve matplotlib ile çizimini yapar.
        """
        if not plan_results:
            # Eğer plan listemiz boşsa bir şey yaptırmayalım.
            self.logger.error("No plans found.")
            return

        # Tüm sonuçları gezer ve her sonucun atandığı makine adını alırız.
        # Bu isimleri bir küme (set) içine koyarız. Tekrarlanan elemanların otomatik elenmesi gibi bir özelliği vardır.
        # Bu listeyi alfabetik sıralarız.
        machines = sorted(set(result.assigned_machine for result in plan_results))
        # Dictionary comprehension denir.
        # Matplotlib'in grafiği çizebilmesi için sayısal koordinatlara ihtiyacı vardır.
        # Bu satır, her makine ismini (m), sayısal bir y pozisyonuna (i) eşleyen bir sözlük yaratır.
        # Yapısı ise şuna benzer: {"kesme_0" = 1, "kesme_1" = 2 ...}
        machine_to_y = {m: i for i, m in enumerate(machines)}

        # matplotlib'in içindeki bir palet olan tab10 paleti alınır.
        colors = plt.cm.tab10.colors
        # Tüm resmi tutan ana pencere ve asıl kullanacağımız alanın boyutunu inç ölçüsüyle belirtiyoruz.
        # Burada 12 inç genişliğe 6 inç yükseklik belirledik.
        fig, ax = plt.subplots(figsize=(12, 6))

        for result in plan_results:
            # Tüm sonuçları gezerek çizim için gerekli bilgileri (eksenler, başlangıçlar gibi) veriyoruz.
            y = machine_to_y[result.assigned_machine]
            start = result.start_time
            end = result.end_time
            label = f"{result.task_name} ({result.job_id})"

            # Çizim gerçekleştirir.
            ax.barh(
                y=y,                                       # Çubuğun dikey konumu
                width=end - start,                         # Çubuğun genişliği (görev süresi)
                left=start,                                # Çubuğun x ekseninde nereden başlayacağı
                height=0.5,                                # Çubuğun kalınlığı
                color=colors[result.job_id % len(colors)], # Her çubuğa ID'sine göre renk veriyoruz. Eğer iş sayısı renk sayısından fazlaysa renkler başa dönecek şekilde tekrarlanır.
                edgecolor="black"                          # Çubuk kenarlık rengi
            )
            ax.text(
                (start + end) / 2,                         # x ekseninde orta nokta
                y,                                         # y ekseni (görev hangi sıradaysa oraya yazılır)
                label,                                     # Yazılacak metin
                ha="center",                               # Horizontal Alignment (x ekseninde ortalama)
                va="center",                               # Vertical Alignment (y ekseninde ortalama)
                fontsize=8,                                # Yazı boyutu
                color="white"                              # Text rengi
            )

        ax.set_yticks(range(len(machines))) # Makine sayısı sıra sayısı için alınır.
        ax.set_yticklabels(machines)   # Bu sırnın ismi verilir. Bizde makine isimleri.
        ax.set_xlabel("Zaman")  # x ekseni etiketi eklenir.
        ax.set_title("Gantt Chart - İş Emri Planlaması")   # x ekseni başlığı eklenir.
        plt.tight_layout()  # Grafikteki elemanların birbirine girmemesi için otomatik boşluk ayarlar.
        plt.savefig(self.output_path)  # Hazırlanan grafiği belirtilen dosya şeklinde kaydeder.
        plt.close()   # Grafiği hafızadan temizler.
        self.logger.info("Gantt chart saved to '{}'".format(self.output_path))
