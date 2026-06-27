from dash import dcc, html
import plotly.graph_objects as go


def get_layout(df):
    # Generate aggregate product categories pie data instantly upon loading
    grouped = df[df["total_amt"] > 0].groupby("prod_cat")["total_amt"].sum()
    fig = go.Figure(
        data=[go.Pie(labels=grouped.index, values=grouped.values)],
        layout=go.Layout(title="Product Categories Market Share"),
    )

    # Dynamically locate unique category names for menu drop listing
    unique_cats = df["prod_cat"].dropna().unique()
    default_value = unique_cats if len(unique_cats) > 0 else None

    layout = html.Div(
        [
            html.H1("Products & Inventory Insights", style={"text-align": "center"}),
            html.Div(
                [
                    # Left hand side static share pie graphic chart
                    html.Div(
                        [dcc.Graph(id="pie-prod-cat", figure=fig)],
                        style={"width": "50%"},
                    ),
                    # Right hand side interactive drop menu with callback receiver chart
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="prod_dropdown",
                                options=[
                                    {"label": cat, "value": cat}
                                    for cat in unique_cats
                                ],
                                value=default_value,
                            ),
                            dcc.Graph(id="barh-prod-subcat"),
                        ],
                        style={"width": "50%"},
                    ),
                ],
                style={"display": "flex"},
            ),
        ]
    )
    return layout
