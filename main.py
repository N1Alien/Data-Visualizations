import pandas as pd
import plotly.offline as pyo
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# 1. Download KGHM stock data and copper prices
df_kghm = pd.read_csv('https://uploads.kodilla.com/bootcamp/pro-data-visualization/files/kgh_d.csv', index_col=0, parse_dates=True)
df_copper = pd.read_csv('https://uploads.kodilla.com/bootcamp/pro-data-visualization/files/ca_c_f_d.csv', index_col=0, parse_dates=True)

# 2. Prepare data for the table (merge and clean)
df_kghm_col = df_kghm.iloc[:, :1].rename(columns={df_kghm.columns[0]: 'KGHM'})
df_copper_col = df_copper.iloc[:, :1].rename(columns={df_copper.columns[0]: 'Copper'})
df_merged = df_kghm_col.join(df_copper_col, how='inner').dropna()

# 3. Create a layout grid with three subplots (sharing the X axis)
fig = make_subplots(
    rows=3, cols=1, 
    subplot_titles=['KGHM Closing Prices', 'Copper Prices', 'Comparison Table'], 
    specs=[[{}], [{}], [{"type": "table"}]], 
    shared_xaxes=True
)

# 4. Add the line chart for KGHM (1st row)
fig.add_trace(go.Scatter(x=df_kghm.index, y=df_kghm.iloc[:, 0], mode='lines', name='KGHM'), row=1, col=1)

# 5. Add the line chart for copper (2nd row)
fig.add_trace(go.Scatter(x=df_copper.index, y=df_copper.iloc[:, 0], mode='lines', name='Copper'), row=2, col=1)

# 6. Add the comparison table with aligned data (3rd row)
fig.add_trace(go.Table(
    header=dict(values=['Date', 'KGHM (Closing)', 'Copper (Closing)'], fill_color='paleturquoise', align='left'),
    cells=dict(values=[df_merged.index.strftime('%Y-%m-%d'), df_merged['KGHM'].round(2), df_merged['Copper'].round(2)], fill_color='lavender', align='left')
), row=3, col=1)

# 7. Update layout decoration and general settings
fig.update_layout(title='Comparison of KGHM and Copper Prices', height=950, showlegend=True)
fig.update_yaxes(title_text='KGHM Price', row=1, col=1)
fig.update_yaxes(title_text='Copper Price', row=2, col=1)

# 9. Plot and open the visualization in the browser
pyo.plot(fig)
