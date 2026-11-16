"""Plotly Dash dashboard over the warehouse marts. Run: python dashboard/app.py  (reads data/*.csv)"""
import json, os
import pandas as pd, plotly.express as px
from dash import Dash, dcc, html, dash_table, Input, Output
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rd = lambda n: pd.read_csv(os.path.join(ROOT, "data", n), keep_default_na=False)
gq, rc, en = rd("mart_game_quarterly.csv"), rd("mart_region_channel.csv"), rd("mart_engagement.csv")
alerts = json.load(open(os.path.join(ROOT, "data", "alerts.json")))
app = Dash(__name__); server = app.server
genres = sorted(gq.genre.unique())
app.layout = html.Div(style={"fontFamily": "system-ui", "maxWidth": 1100, "margin": "0 auto", "padding": 16}, children=[
    html.H2("Game Sales and Engagement Warehouse"),
    html.P("Synthetic data. Marts built by the PySpark pipeline; QoQ alerts flag drops over 15%."),
    html.Div([html.Div([html.Small("Total revenue"), html.H3(f"${gq.revenue.sum():,.0f}")]),
              html.Div([html.Small("Units sold"), html.H3(f"{gq.units.sum():,}")]),
              html.Div([html.Small("Dirty rows flagged (issue counts)"), html.H3(f"{sum(alerts['quality'].values()):,}")]),
              html.Div([html.Small("QoQ drop alerts"), html.H3(len(alerts["alerts"]))])],
             style={"display": "grid", "gridTemplateColumns": "repeat(4,1fr)", "gap": 12}),
    dcc.Dropdown(genres, genres, multi=True, id="genre", placeholder="Filter genres"),
    dcc.Graph(id="trend"), dcc.Graph(figure=px.bar(rc, x="region", y="revenue", color="channel", barmode="group", title="Revenue by region and channel")),
    dcc.Graph(figure=px.scatter(en, x="avg_active_players", y="avg_session_min", color="region", hover_name="title", title="Engagement by game and region")),
    html.H4("Quarter over quarter drop alerts"),
    dash_table.DataTable(alerts["alerts"], [{"name": c, "id": c} for c in ["title", "quarter", "change_pct"]], page_size=10)])
@app.callback(Output("trend", "figure"), Input("genre", "value"))
def trend(g):
    d = gq[gq.genre.isin(g or genres)].groupby(["genre", "quarter"], as_index=False).revenue.sum()
    return px.line(d, x="quarter", y="revenue", color="genre", markers=True, title="Quarterly revenue by genre").update_xaxes(dtick=1)
if __name__ == "__main__": app.run(debug=False, host="0.0.0.0", port=8050)
