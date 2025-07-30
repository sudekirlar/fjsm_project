# adapters/driven/gantt_show_adapter.py

import matplotlib.pyplot as plt
from core.models.data_model import PlanResultDTO
from typing import List


class GanttChartRenderer:
    def __init__(self, output_path: str = "gantt_chart.png"):
        self.output_path = output_path

    def render(self, plan_results: List[PlanResultDTO]):
        if not plan_results:
            print("No results to render.")
            return

        machines = sorted(set(result.assigned_machine for result in plan_results))
        machine_to_y = {m: i for i, m in enumerate(machines)}

        colors = plt.cm.tab10.colors
        fig, ax = plt.subplots(figsize=(12, 6))

        for result in plan_results:
            y = machine_to_y[result.assigned_machine]
            start = result.start_time
            end = result.end_time
            label = f"{result.task_name} ({result.job_id})"

            ax.barh(
                y=y,
                width=end - start,
                left=start,
                height=0.5,
                color=colors[result.job_id % len(colors)],
                edgecolor="black"
            )
            ax.text(
                (start + end) / 2,
                y,
                label,
                ha="center",
                va="center",
                fontsize=8,
                color="white"
            )

        ax.set_yticks(range(len(machines)))
        ax.set_yticklabels(machines)
        ax.set_xlabel("Zaman")
        ax.set_title("Gantt Chart - İş Emri Planlaması")
        plt.tight_layout()
        plt.savefig(self.output_path)
        plt.close()
        print(f"✅ Gantt PNG oluşturuldu: {self.output_path}")
