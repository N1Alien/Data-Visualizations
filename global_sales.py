from dash import dcc, html


def get_layout(df):
    # Generates structural layout for the Global Sales tab page
    layout = html.Div(
        [
            html.H1("Global Sales Performance", style={"text-align": "center"}),
            # Center-aligned Date filtering widget
            html.Div(
                [
                    dcc.DatePickerRange(
                        id="sales-range",
                        start_date=df["tran_date"].min(),
                        end_date=df["tran_date"].max(),
                        display_format="YYYY-MM-DD",
                    )
                ],
                style={"width": "100%", "text-align": "center"},
            ),
            # Side-by-side flex layout containers for charts
            html.Div(
                [
                    html.Div(
                        [dcc.Graph(id="bar-sales")], style={"width": "50%"}
                    ),
                    html.Div(
                        [dcc.Graph(id="choropleth-sales")],
                        style={"width": "50%"},
                    ),
                ],
                style={"display": "flex"},
            ),
        ]
    )
    return layout