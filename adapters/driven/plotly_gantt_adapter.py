# adapters/driven/plotly_gantt_adapter.py

from typing import List
from core.models.data_model import PlanResultDTO
import plotly.graph_objects as go
import random

def render_interactive_gantt(plan_results: List[PlanResultDTO], output_path: str = "fjsm_gantt_interactive.html"):
    if not plan_results:
        print("No plans to render.")
        return

    # Job ID → renk sözlüğü
    job_colors = {}
    job_ids = list(set(result.job_id for result in plan_results))
    random.seed(42)
    for jid in job_ids:
        job_colors[jid] = f"rgb({random.randint(50, 200)}, {random.randint(50, 200)}, {random.randint(50, 200)})"

    # Bar objelerini oluştur
    bars = []
    for result in plan_results:
        duration = result.end_time - result.start_time
        bars.append(go.Bar(
            x=[duration],
            y=[result.assigned_machine],
            base=[result.start_time],
            orientation="h",
            name=f"Job {result.job_id}",
            marker=dict(color=job_colors[result.job_id]),
            hovertemplate=(
                f"Package: {result.package_uid}<br>"
                f"Task: {result.task_name}<br>"
                f"Job ID: {result.job_id}<br>"
                f"Machine: {result.assigned_machine}<br>"
                f"Start: {result.start_time}<br>"
                f"End: {result.end_time}<extra></extra>"
            )
        ))

    fig = go.Figure(data=bars)
    fig.update_layout(
        title="FJSM Gantt Chart (Interactive)",
        barmode='stack',
        xaxis_title="Time",
        yaxis_title="Machine",
        showlegend=True,
        height=max(400, len(set(r.assigned_machine for r in plan_results)) * 30),
        legend_title="Job ID",
        template="plotly_white"
    )

    fig.write_html(output_path)
    print(f"Gantt chart saved to {output_path}")
