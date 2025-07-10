import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for web server compatibility
from io import BytesIO
import base64
import os

def generate_profit_chart():
    df = pd.read_csv('data/sales.csv')
    df['Month'] = pd.to_datetime(df['Month'])
    df['Profit'] = df['Revenue'] - df['Expenses']
    df = df.sort_values('Month')
    chart = px.line(df, x='Month', y='Profit', title='Profit Trend', markers=True)
    return chart.to_html(full_html=False)

def generate_daily_revenue_chart():
    """Generate chart for total and average profit"""
    jobs_df = pd.read_csv('data/jobs.csv', header=None,
                         names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price'])
    
    # Calculate total revenue and average per day
    jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
    daily_revenue = jobs_df.groupby('date')['revenue'].sum()
    avg_revenue = daily_revenue.mean()
    
    # Create chart with improved styling
    plt.style.use('ggplot')  # Use a nicer style
    fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
    bars = daily_revenue.plot(kind='bar', ax=ax, color='#5a189a', alpha=0.7)
    ax.axhline(y=avg_revenue, color='#e63946', linestyle='--', linewidth=2,
               label=f'Average: ${avg_revenue:.2f}')
    
    ax.set_title('Total Daily Revenue', fontsize=16, fontweight='bold')
    ax.set_ylabel('Revenue ($)', fontsize=12)
    ax.set_xlabel('Date', fontsize=12)
    ax.tick_params(axis='x', rotation=45)
    ax.legend(fontsize=10)
    
    # Convert plot to base64 string
    buffer = BytesIO()
    fig.tight_layout()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    image_png = buffer.getvalue()
    plt.close(fig)  # Explicitly close the figure to free memory
    buffer.close()
    
    chart = base64.b64encode(image_png).decode('utf-8')
    return f'<img src="data:image/png;base64,{chart}" alt="Daily Revenue Chart" style="width:100%;">'

def generate_item_profit_chart():
    """Generate chart for profit per inventory item"""
    jobs_df = pd.read_csv('data/jobs.csv', header=None,
                         names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price'])
    
    # Load inventory for cost data
    if os.path.exists('data/inventory.json'):
        inventory_df = pd.read_json('data/inventory.json')
        # Create a mapping of item name to cost
        cost_map = {item['name']: item['cost'] for _, item in inventory_df.iterrows()}
    else:
        cost_map = {}
    
    # Calculate profit per item
    jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
    
    # Add cost and profit columns
    jobs_df['cost_per_unit'] = jobs_df['item'].map(cost_map).fillna(0)
    jobs_df['cost'] = jobs_df['cost_per_unit'] * jobs_df['quantity']
    jobs_df['profit'] = jobs_df['revenue'] - jobs_df['cost']
    
    # Group by item
    item_profit = jobs_df.groupby('item').agg({
        'quantity': 'sum',
        'revenue': 'sum',
        'cost': 'sum',
        'profit': 'sum'
    }).sort_values('profit', ascending=False)
    
    # Limit to top 10 items for readability
    if len(item_profit) > 10:
        item_profit = item_profit.head(10)
    
    # Create chart with improved styling
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    bars = item_profit['profit'].plot(kind='barh', ax=ax, color='#5a189a', alpha=0.7)
    
    # Add value labels to the bars
    for i, v in enumerate(item_profit['profit']):
        ax.text(v + 0.1, i, f'${v:.2f}', va='center')
    
    ax.set_title('Profit by Top Inventory Items', fontsize=16, fontweight='bold')
    ax.set_xlabel('Profit ($)', fontsize=12)
    ax.set_ylabel('Item', fontsize=12)
    
    # Convert plot to base64 string
    buffer = BytesIO()
    fig.tight_layout()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    image_png = buffer.getvalue()
    plt.close(fig)
    buffer.close()
    
    chart = base64.b64encode(image_png).decode('utf-8')
    return f'<img src="data:image/png;base64,{chart}" alt="Item Profit Chart" style="width:100%;">'

def generate_service_profit_chart():
    """Generate chart for profit per service type"""
    jobs_df = pd.read_csv('data/jobs.csv', header=None,
                         names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price'])
    
    # Load services for service types
    services_df = None
    if os.path.exists('data/services.json'):
        services_df = pd.read_json('data/services.json')
    
    if services_df is not None:
        # Create a mapping of service name to cost
        cost_map = {service['name']: service['cost'] for _, service in services_df.iterrows()}
    else:
        cost_map = {}
    
    # Calculate profit
    jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
    jobs_df['cost_per_unit'] = jobs_df['item'].map(cost_map).fillna(0)
    jobs_df['cost'] = jobs_df['cost_per_unit'] * jobs_df['quantity']
    jobs_df['profit'] = jobs_df['revenue'] - jobs_df['cost']
    
    # Group by item
    service_profit = jobs_df.groupby('item').agg({
        'quantity': 'sum',
        'revenue': 'sum',
        'profit': 'sum'
    }).sort_values('profit', ascending=False)
    
    # Limit to top 6 services for better pie chart readability
    if len(service_profit) > 6:
        # Save the total of others
        others_sum = service_profit.iloc[6:]['profit'].sum()
        service_profit = service_profit.iloc[:6]
        # Add an "Others" category if there are services beyond the top 6
        if others_sum > 0:
            service_profit.loc['Others'] = {'quantity': 0, 'revenue': 0, 'profit': others_sum}
    
    # Create chart with improved styling
    plt.style.use('ggplot')
    colors = plt.cm.tab10.colors
    fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
    wedges, texts, autotexts = ax.pie(
        service_profit['profit'],
        labels=service_profit.index,
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        wedgeprops={'edgecolor': 'w', 'linewidth': 1, 'antialiased': True}
    )
    
    # Styling autotexts
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_fontweight('bold')
    
    ax.set_title('Profit Distribution by Service', fontsize=16, fontweight='bold')
    ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular
    
    # Convert plot to base64 string
    buffer = BytesIO()
    fig.tight_layout()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    image_png = buffer.getvalue()
    plt.close(fig)
    buffer.close()
    
    chart = base64.b64encode(image_png).decode('utf-8')
    return f'<img src="data:image/png;base64,{chart}" alt="Service Profit Chart" style="width:100%;">'