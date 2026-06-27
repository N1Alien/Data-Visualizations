import datetime as dt
import os
from pathlib import Path
import dash
from dash import dcc, html, Input, Output
import dash_auth
import pandas as pd
import plotly.graph_objects as go

# Import layout modules
import channels
import global_sales
import products

BASE_DIR = Path(__file__).resolve().parent


# --- DATABASE MANAGEMENT CLASS ---
class Db:

    def __init__(self):
        # Initialize and load data sequentially on startup
        self.transactions = self.transaction_init()
        self.cc = pd.read_csv(BASE_DIR / "db" / "country_codes.csv", index_col=0)
        self.customers = pd.read_csv(BASE_DIR / "db" / "customers.csv", index_col=0)
        self.prod_info = pd.read_csv(BASE_DIR / "db" / "prod_cat_info.csv")
        self.merged = None

    @staticmethod
    def transaction_init():
        src = BASE_DIR / "db" / "transactions"
        if not src.exists():
            raise FileNotFoundError(
                f"Directory {src} does not exist. Check file structure."
            )

        # Load all CSV files from the folder into a list
        temp_list = []
        for file_path in src.glob("*.csv"):
            temp_list.append(pd.read_csv(file_path, index_col=0))

        if not temp_list:
            return pd.DataFrame()

        # Concatenate all transaction dataframes efficiently
        transactions = pd.concat(temp_list, ignore_index=True)
        
        # Standardize transaction date formats natively
        transactions["tran_date"] = pd.to_datetime(
            transactions["tran_date"], format="mixed", dayfirst=True
        )
        return transactions

    def merge(self):
        # Left join transactions with product categories
        df = self.transactions.join(
            self.prod_info.drop_duplicates(subset=["prod_cat_code"]).set_index(
                "prod_cat_code"
            )["prod_cat"],
            on="prod_cat_code",
            how="left",
        )
        # Left join with product subcategories
        df = df.join(
            self.prod_info.drop_duplicates(
                subset=["prod_sub_cat_code"]
            ).set_index("prod_sub_cat_code")["prod_subcat"],
            on="prod_subcat_code",
            how="left",
        )

        # Combine customers with country codes, then join to the master dataframe
        customers_with_cc = self.customers.join(
            self.cc, on="country_code"
        ).set_index("customer_Id")
        df = df.join(customers_with_cc, on="cust_id", how="left")

        # Core calculations: total sales amount
        df["total_amt"] = df["Qty"] * df["Rate"]
        
        # Clean and uppercase Gender text values
        if "Gender" in df.columns:
            df["Gender"] = df["Gender"].astype(str).str.strip().str.upper()

        # Extract calendar components for weekday analysis
        df["day_name"] = df["tran_date"].dt.day_name()
        df["day_of_week"] = df["tran_date"].dt.dayofweek

        # Dynamic age group calculations based on Date of Birth (DOB)
        if "DOB" in df.columns:
            df["DOB"] = pd.to_datetime(df["DOB"], format="mixed", dayfirst=True)
            df["Age"] = df["tran_date"].dt.year - df["DOB"].dt.year
            
            # Segment age into specific demographic buckets
            age_bins = [0, 24, 34, 44, 54, 100]
            age_labels = ["<25", "25-34", "35-44", "45-54", "55+"]
            
            df["Age_Group"] = pd.cut(df["Age"], bins=age_bins, labels=age_labels)
            df["Age_Group"] = df["Age_Group"].astype(str).fillna("Unknown")
        else:
            df["Age_Group"] = "Unknown"

        self.merged = df


# Instantiate database and perform the merges
db_instance = Db()
db_instance.merge()
print("Success! Data loaded and merged correctly.")

# --- DASH CONFIGURATION & SECURITY ---
USERNAME_PASSWORD = {"user": "pass"}  # Basic Auth credentials
external_stylesheets = ["https://codepen.io"]

app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,  # Allows multi-tab dynamic layouts
)
auth = dash_auth.BasicAuth(app, USERNAME_PASSWORD)

# Main Application Frame Shell
app.layout = html.Div(
    [
        html.Div(
            [
                dcc.Tabs(
                    id="tabs",
                    value="tab-1",
                    children=[
                        dcc.Tab(label="Global Sales", value="tab-1"),
                        dcc.Tab(label="Products Analysis", value="tab-2"),
                        dcc.Tab(label="Sales Channels", value="tab-3"),
                    ],
                ),
                html.Div(id="tabs-content"),
            ],
            style={"width": "80%", "margin": "auto"},
        )
    ],
    style={"height": "100%"},
)


# --- 1. CORE TAB CONTROLLER CALLBACK ---
@app.callback(Output("tabs-content", "children"), [Input("tabs", "value")])
def update_tab_content(tab):
    if tab == "tab-1":
        return global_sales.get_layout(db_instance.merged)
    elif tab == "tab-2":
        return products.get_layout(db_instance.merged)
    elif tab == "tab-3":
        return channels.get_layout(db_instance.merged)


# --- 2. GLOBAL SALES CALLBACKS (TAB 1) ---
@app.callback(
    Output("bar-sales", "figure"),
    [Input("sales-range", "start_date"), Input("sales-range", "end_date")],
)
def tab1_bar_sales(start_date, end_date):
    data_df = db_instance.merged
    if start_date is None or end_date is None:
        return go.Figure(layout=go.Layout(title="Please select a date range"))
    truncated = data_df[
        (data_df["tran_date"] >= start_date) & (data_df["tran_date"] <= end_date)
    ]
    
    # Group revenue by Monthly Ends (ME) and store channel types
    grouped = (
        truncated[truncated["total_amt"] > 0]
        .groupby([pd.Grouper(key="tran_date", freq="ME"), "Store_type"])[
            "total_amt"
        ]
        .sum()
        .round(2)
        .unstack()
    )
    
    traces = []
    for col in grouped.columns:
        y_values = grouped[col].fillna(0).values
        traces.append(
            go.Bar(
                x=grouped.index,
                y=y_values,
                name=str(col),
                hoverinfo="text",
                hovertext=[f"{y/1e3:.2f}k" for y in y_values],
            )
        )
    return go.Figure(
        data=traces,
        layout=go.Layout(
            title="Revenue Over Time", barmode="stack", legend=dict(x=0, y=-0.5)
        ),
    )


@app.callback(
    Output("choropleth-sales", "figure"),
    [Input("sales-range", "start_date"), Input("sales-range", "end_date")],
)
def tab1_choropleth_sales(start_date, end_date):
    data_df = db_instance.merged
    if start_date is None or end_date is None:
        return go.Figure(layout=go.Layout(title="Please select a date range"))
    truncated = data_df[
        (data_df["tran_date"] >= start_date) & (data_df["tran_date"] <= end_date)
    ]
    
    country_col = (
        "country" if "country" in truncated.columns else truncated.columns[-1]
    )
    grouped = (
        truncated[truncated["total_amt"] > 0]
        .groupby(country_col)["total_amt"]
        .sum()
        .round(2)
    )

    trace0 = go.Choropleth(
        colorscale="Viridis",
        reversescale=True,
        locations=grouped.index,
        locationmode="country names",
        z=grouped.values,
        colorbar=dict(title="Sales (USD)"),
    )
    return go.Figure(
        data=[trace0],
        layout=go.Layout(
            title="Country Revenue Map",
            geo=dict(showframe=False, projection={"type": "natural earth"}),
        ),
    )


# --- 3. PRODUCTS CALLBACKS (TAB 2) ---
@app.callback(
    Output("barh-prod-subcat", "figure"), [Input("prod_dropdown", "value")]
)
def tab2_barh_prod_subcat(chosen_cat):
    data_df = db_instance.merged
    if not chosen_cat:
        chosen_cat = data_df["prod_cat"].unique().tolist()
    elif isinstance(chosen_cat, str):
        chosen_cat = [chosen_cat]

    filtered = data_df[
        (data_df["total_amt"] > 0) & (data_df["prod_cat"].isin(chosen_cat))
    ]
    
    # Pivot subcategory revenue by gender columns
    grouped = filtered.pivot_table(
        index="prod_subcat", columns="Gender", values="total_amt", aggfunc="sum"
    ).fillna(0)
    
    for gender in ["F", "M"]:
        if gender not in grouped.columns:
            grouped[gender] = 0
            
    grouped = (
        grouped.assign(_sum=lambda x: x["F"] + x["M"])
        .sort_values(by="_sum")
        .round(2)
    )
    
    traces = []
    for col in ["F", "M"]:
        traces.append(
            go.Bar(x=grouped[col], y=grouped.index, orientation="h", name=col)
        )
    return go.Figure(
        data=traces, layout=go.Layout(barmode="stack", margin={"t": 20})
    )


# --- 4. SALES CHANNELS CALLBACKS (TAB 3) ---
@app.callback(Output("channels-weekday-graph", "figure"), [Input("tabs", "value")])
def update_weekday_graph(tab):
    data_df = db_instance.merged
    
    # Aggregate data chronologically by day number
    grouped = (
        data_df[data_df["total_amt"] > 0]
        .groupby(["day_of_week", "day_name", "Store_type"])["total_amt"]
        .sum()
        .reset_index()
        .sort_values("day_of_week")
    )

    traces = []
    for store in grouped["Store_type"].unique():
        store_df = grouped[grouped["Store_type"] == store]
        traces.append(
            go.Bar(
                x=store_df["day_name"],
                y=store_df["total_amt"],
                name=str(store),
            )
        )

    return go.Figure(
        data=traces,
        layout=go.Layout(
            barmode="group",
            xaxis={"title": "Day of the Week"},
            yaxis={"title": "Total Revenue"},
            margin={"t": 30},
        ),
    )


@app.callback(
    Output("channels-gender-graph", "figure"), [Input("store_dropdown", "value")]
)
def update_gender_graph(chosen_store):
    data_df = db_instance.merged
    if not chosen_store:
        chosen_store = []
    elif isinstance(chosen_store, str):
        chosen_store = [chosen_store]
    filtered = data_df[
        data_df["Store_type"].isin(chosen_store) & (data_df["total_amt"] > 0)

    ]
    grouped = filtered.groupby("Gender")["total_amt"].sum().reset_index()

    fig = go.Figure(
        data=[
            go.Bar(
                x=grouped["Gender"],
                y=grouped["total_amt"],
                marker_color=["#ff66b2" if g == "F" else "#66b2ff" for g in grouped["Gender"]],
            )
        ],
        layout=go.Layout(
            title=f"Revenue by Gender in Channel: {chosen_store}",
            xaxis={"title": "Gender"},
            yaxis={"title": "Total Revenue"},
        ),
    )
    return fig


@app.callback(
    Output("channels-age-graph", "figure"), [Input("store_dropdown", "value")]
)
def update_age_graph(chosen_store):
    data_df = db_instance.merged
    if not chosen_store:
        chosen_store = []
    elif isinstance(chosen_store, str):
        chosen_store = [chosen_store]
    filtered = data_df[
        data_df["Store_type"].isin(chosen_store) & (data_df["total_amt"] > 0)
    ]
    grouped = (
        filtered.groupby("Age_Group", observed=False)["total_amt"].sum().reset_index()
    )
    fig = go.Figure(
        data=[
            go.Pie(
                labels=grouped["Age_Group"],
                values=grouped["total_amt"],
                hole=0.4,  # Creates a modern donut chart
            )
        ],
        layout=go.Layout(title=f"Customer Age Structure Revenue: {chosen_store}"),
    )
    return fig


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print(" >>> DASH SERVER IS STARTING!")
    print(" >>> Open your browser and navigate to: 127.0.0.1:8050")
    print("=" * 50 + "\n")
    app.run(debug=True, port=8050)