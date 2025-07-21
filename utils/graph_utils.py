import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.patheffects as patheffects
matplotlib.use('Agg')  # Use non-interactive backend for web server compatibility
from io import BytesIO
import base64
import os
import json
import numpy as np
import sys

# Import path handling utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from path_fix import get_data_path, get_data_file_path

# Thai Baht symbol
BAHT_SYMBOL = '฿'

# Helper function to load jobs data safely
def load_jobs_data():
    """Load jobs data from jobs.csv with fallbacks for different formats"""
    try:
        # Try to load with headers first
        jobs_path = get_data_file_path('jobs.csv')
        print(f"Looking for jobs file at: {jobs_path}")
        try:
            jobs_df = pd.read_csv(jobs_path)
            print("Loaded jobs.csv with headers")
        except Exception as e1:
            print(f"Error loading with headers: {e1}")
            # Try different column configurations
            try:
                jobs_df = pd.read_csv(jobs_path, header=None,
                              names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price', 'cost', 'category'])
                print("Loaded jobs.csv with 8 columns")
            except Exception as e2:
                print(f"Error loading with 8 columns: {e2}")
                try:
                    jobs_df = pd.read_csv(jobs_path, header=None,
                                  names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price', 'cost'])
                    print("Loaded jobs.csv with 7 columns")
                except Exception as e3:
                    print(f"Error loading with 7 columns: {e3}")
                    jobs_df = pd.read_csv('data/jobs.csv', header=None,
                                 names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price'])
                    print("Loaded jobs.csv with 6 columns")
                    
        # Ensure numeric columns
        for col in ['quantity', 'price']:
            if col in jobs_df.columns:
                jobs_df[col] = pd.to_numeric(jobs_df[col], errors='coerce').fillna(0)
                if col == 'quantity':
                    jobs_df[col] = jobs_df[col].astype(int)
                    
        # Add cost if missing but we have the mapping
        if 'cost' not in jobs_df.columns:
            # Load cost data from services and inventory
            cost_map = {}
            if os.path.exists('data/services.json'):
                with open('data/services.json', 'r') as f:
                    services = json.load(f)
                    for service in services:
                        cost_map[service.get('name')] = float(service.get('cost', 0))
                        
            if os.path.exists('data/inventory.json'):
                with open('data/inventory.json', 'r') as f:
                    inventory = json.load(f)
                    for item in inventory:
                        cost_map[item.get('name')] = float(item.get('cost', 0))
                        
            # Calculate costs
            costs = []
            for _, row in jobs_df.iterrows():
                item_name = row['item']
                quantity = row['quantity']
                cost = cost_map.get(item_name, 0) * quantity
                costs.append(cost)
                
            jobs_df['cost'] = costs
        else:
            # Ensure cost is numeric
            jobs_df['cost'] = pd.to_numeric(jobs_df['cost'], errors='coerce').fillna(0)
            
        # Add category if missing
        if 'category' not in jobs_df.columns:
            # Create category mapping
            category_map = {}
            services_path = get_data_file_path('services.json')
            if os.path.exists(services_path):
                with open(services_path, 'r') as f:
                    services_data = json.load(f)
                    service_costs = {service['name']: service.get('cost', 0) for service in services_data}
            
            inventory_path = get_data_file_path('inventory.json')
            if os.path.exists(inventory_path):
                with open(inventory_path, 'r') as f:
                    inventory = json.load(f)
                    for item in inventory:
                        category_map[item.get('name')] = "product"
                        
            # Assign categories
            jobs_df['category'] = jobs_df['item'].map(category_map).fillna("unknown")
            
        # Calculate revenue and profit
        jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
        
        # Use total_profit from CSV if available, otherwise calculate it
        if 'total_profit' in jobs_df.columns:
            jobs_df['profit'] = jobs_df['total_profit']
        else:
            # Calculate profit: (price - cost) * quantity (cost is unit cost)
            jobs_df['profit'] = (jobs_df['price'] - jobs_df['cost']) * jobs_df['quantity']
        
        return jobs_df
        
    except Exception as e:
        print(f"Failed to load jobs data: {e}")
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=['timestamp', 'date', 'customer', 'item', 
                                   'quantity', 'price', 'cost', 'category', 
                                   'revenue', 'profit'])

def generate_profit_chart():
    """Generate profit trend chart using jobs.csv data"""
    try:
        # Load jobs data
        jobs_df = load_jobs_data()
        
        if jobs_df.empty:
            return "<div class='alert alert-info'>No data available for analysis</div>"
        
        # Convert date to datetime and group by date
        jobs_df['date'] = pd.to_datetime(jobs_df['date'], errors='coerce')
        daily_profit = jobs_df.groupby('date')['profit'].sum().reset_index()
        daily_profit = daily_profit.sort_values('date')
        
        # Create a line chart using plotly
        chart = px.line(
            daily_profit, 
            x='date', 
            y='profit', 
            title=f'Daily Profit Trend ({BAHT_SYMBOL})', 
            markers=True,
            template='plotly_white',
            color_discrete_sequence=['#5a189a']
        )
        
        # Update layout
        chart.update_layout(
            xaxis_title="Date",
            yaxis_title=f"Profit ({BAHT_SYMBOL})",
            font=dict(family="Arial, sans-serif", size=12),
            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial, sans-serif"),
        )
        
        return chart.to_html(full_html=False)
    except Exception as e:
        print(f"Error generating profit chart: {e}")
        return "<div class='alert alert-danger'>Error generating profit chart</div>"

def generate_daily_revenue_chart(chart_type='bar'):
    """Generate chart for total daily revenue with different visualization types
    
    Args:
        chart_type: Type of chart to generate ('bar', 'line', or 'pie')
    """
    try:
        # Load jobs data using our helper
        jobs_df = load_jobs_data()
        
        if jobs_df.empty:
            return "<div class='alert alert-info'>No data available for analysis</div>"
        
        # Group by date
        daily_revenue = jobs_df.groupby('date')['revenue'].sum()
        avg_revenue = daily_revenue.mean()
        
        # Create chart with improved styling
        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        if chart_type == 'bar':
            # Bar chart
            bars = daily_revenue.plot(kind='bar', ax=ax, color='#5a189a', alpha=0.7)
            ax.axhline(y=avg_revenue, color='#e63946', linestyle='--', linewidth=2,
                       label=f'Average: {BAHT_SYMBOL}{avg_revenue:.2f}')
            
            # Add value labels on top of bars
            if not daily_revenue.empty:
                for i, v in enumerate(daily_revenue):
                    ax.text(i, v + (max(daily_revenue) * 0.02), f'{BAHT_SYMBOL}{v:.0f}', 
                            ha='center', fontsize=8, rotation=0, fontweight='bold')
            
            ax.set_title('Daily Revenue - Bar Chart', fontsize=16, fontweight='bold')
            ax.tick_params(axis='x', rotation=45)
            
        elif chart_type == 'line':
            # Line chart
            dates = daily_revenue.index
            values = daily_revenue.values
            
            # Plot the line chart
            ax.plot(dates, values, marker='o', linestyle='-', color='#5a189a', linewidth=2)
            ax.axhline(y=avg_revenue, color='#e63946', linestyle='--', linewidth=2,
                      label=f'Average: {BAHT_SYMBOL}{avg_revenue:.2f}')
                      
            # Add value labels on top of points
            if not daily_revenue.empty:
                for i, (x, y) in enumerate(zip(dates, values)):
                    ax.annotate(f'{BAHT_SYMBOL}{y:.0f}', (i, y), textcoords="offset points",
                              xytext=(0, 5), ha='center', fontsize=8, fontweight='bold')
                              
            ax.set_title('Daily Revenue - Line Chart', fontsize=16, fontweight='bold')
            plt.xticks(range(len(dates)), dates, rotation=45)
            
        elif chart_type == 'pie':
            # Pie chart (only for data with a reasonable number of dates)
            plt.close(fig)  # Close the current figure and create a new one for pie
            fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
            
            if len(daily_revenue) > 10:
                # If too many dates, aggregate smallest values
                top_dates = daily_revenue.nlargest(9)
                other_sum = daily_revenue.sum() - top_dates.sum()
                pie_data = top_dates.copy()
                if other_sum > 0:
                    pie_data['Other dates'] = other_sum
            else:
                pie_data = daily_revenue
            
            # Plot pie chart
            wedges, texts, autotexts = ax.pie(
                pie_data, 
                labels=pie_data.index, 
                autopct='%1.1f%%',
                startangle=90,
                colors=plt.cm.tab10.colors,
                wedgeprops={'edgecolor': 'w', 'linewidth': 1}
            )
            
            # Styling
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontsize(10)
                autotext.set_fontweight('bold')
                
            ax.set_title('Revenue by Date - Pie Chart', fontsize=16, fontweight='bold')
            ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular
        
        # Common settings
        ax.set_ylabel(f'Revenue ({BAHT_SYMBOL})', fontsize=12)
        if chart_type != 'pie':
            ax.set_xlabel('Date', fontsize=12)
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
    except Exception as e:
        print(f"Error generating daily revenue chart ({chart_type}): {e}")
        return f"<div class='alert alert-danger'>Error generating {chart_type} chart for daily revenue: {e}</div>"

def generate_item_profit_chart(chart_type='pie'):
    """Generate chart for profit per inventory item with different visualization types
    
    Args:
        chart_type: Type of chart to generate ('bar', 'line', 'pie', or 'table')
    """
    try:
        # Load jobs data
        jobs_df = load_jobs_data()
        
        if jobs_df.empty:
            return "<div class='alert alert-info'>No data available for analysis</div>"
            
        # Filter to only show inventory items (products), not services
        if 'category' in jobs_df.columns:
            # Use category column if available to filter for products only
            products_df = jobs_df[jobs_df['category'] == 'product']
            
            if products_df.empty:
                return "<div class='alert alert-info'>No inventory items data available for analysis</div>"
                
            # Group by inventory item
            item_profit = products_df.groupby('item').agg({
                'quantity': 'sum',
                'revenue': 'sum',
                'cost': 'sum',
                'profit': 'sum'
            }).sort_values('profit', ascending=False)
        else:
            # If no category column, try to determine products by loading inventory data
            inventory_items = []
            try:
                inventory_path = get_data_file_path('inventory.json')
                if os.path.exists(inventory_path):
                    with open(inventory_path, 'r') as f:
                        inventory = json.load(f)
                        inventory_items = [item.get('name') for item in inventory]
            except Exception as e:
                print(f"Error loading inventory data: {e}")
                
            if not inventory_items:
                # If no inventory data, just group by item
                item_profit = jobs_df.groupby('item').agg({
                    'quantity': 'sum',
                    'revenue': 'sum',
                    'cost': 'sum',
                    'profit': 'sum'
                }).sort_values('profit', ascending=False)
            else:
                # Filter jobs to only include inventory items
                products_df = jobs_df[jobs_df['item'].isin(inventory_items)]
                
                if products_df.empty:
                    return "<div class='alert alert-info'>No inventory items data available for analysis</div>"
                    
                # Group by inventory item
                item_profit = products_df.groupby('item').agg({
                    'quantity': 'sum',
                    'revenue': 'sum',
                    'cost': 'sum',
                    'profit': 'sum'
                }).sort_values('profit', ascending=False)
        
        # Handle empty dataset
        if item_profit.empty:
            return "<div class='alert alert-info'>No inventory items profit data available for analysis</div>"
        
        # Limit to top 10 items for readability
        if len(item_profit) > 10:
            item_profit = item_profit.head(10)
        
        # Create chart with improved styling
        plt.style.use('ggplot')
        
        # Table display option - show data in text format instead of chart
        if chart_type == 'table':
            # Create an HTML table to display the data
            table_html = '<div class="table-responsive">'
            table_html += '<table class="table table-striped table-hover">'
            table_html += '<thead class="table-light"><tr>'
            table_html += '<th>Item</th>'
            table_html += '<th>Quantity Sold</th>'
            table_html += '<th>Revenue</th>'
            table_html += '<th>Cost</th>'
            table_html += '<th>Profit</th>'
            table_html += '<th>Profit Margin</th>'
            table_html += '</tr></thead>'
            table_html += '<tbody>'
            
            # Add rows for each item
            for item, row in item_profit.iterrows():
                # Calculate profit margin
                profit_margin = (row['profit'] / row['revenue'] * 100) if row['revenue'] > 0 else 0
                
                table_html += f'<tr>'
                table_html += f'<td>{item}</td>'
                table_html += f'<td>{int(row["quantity"])}</td>'
                table_html += f'<td>{BAHT_SYMBOL}{row["revenue"]:.2f}</td>'
                table_html += f'<td>{BAHT_SYMBOL}{row["cost"]:.2f}</td>'
                table_html += f'<td><strong>{BAHT_SYMBOL}{row["profit"]:.2f}</strong></td>'
                table_html += f'<td>{profit_margin:.2f}%</td>'
                table_html += '</tr>'
                
            table_html += '</tbody></table></div>'
            
            # Add summary statistics
            total_profit = item_profit['profit'].sum()
            avg_profit = item_profit['profit'].mean()
            table_html += f'<div class="mt-3 p-3 bg-light rounded">'
            table_html += f'<p><strong>Total Profit:</strong> {BAHT_SYMBOL}{total_profit:.2f}</p>'
            table_html += f'<p><strong>Average Profit per Item:</strong> {BAHT_SYMBOL}{avg_profit:.2f}</p>'
            table_html += '</div>'
            
            return table_html
            
        elif chart_type == 'bar' or chart_type == 'line':
            # For bar and line charts, we use a horizontal bar chart (easier to read item names)
            fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
            
            if chart_type == 'bar':
                # Horizontal bar chart
                bars = item_profit['profit'].plot(kind='barh', ax=ax, color='#5a189a', alpha=0.7)
                
                # Add value labels to the bars
                for i, v in enumerate(item_profit['profit']):
                    ax.text(v + 0.1, i, f'{BAHT_SYMBOL}{v:.2f}', va='center')
                    
                ax.set_title('Profit by Item - Bar Chart', fontsize=16, fontweight='bold')
                
            else:  # Line chart 
                # For line charts with categorical data, we'll use a connected scatter plot
                x = range(len(item_profit))
                y = item_profit['profit'].values
                
                ax.plot(x, y, marker='o', linestyle='-', color='#5a189a', linewidth=2)
                
                # Add value labels
                for i, v in enumerate(y):
                    ax.annotate(f'{BAHT_SYMBOL}{v:.2f}', (i, v), 
                               xytext=(0, 5), textcoords='offset points',
                               ha='center', fontsize=9)
                               
                plt.xticks(x, item_profit.index, rotation=45, ha='right')
                ax.set_title('Profit by Item - Line Chart', fontsize=16, fontweight='bold')
                ax.set_xlabel('Item', fontsize=12)
                ax.set_ylabel(f'Profit ({BAHT_SYMBOL})', fontsize=12)
                
            # Common settings for bar and line
            if chart_type == 'bar':
                ax.set_xlabel(f'Profit ({BAHT_SYMBOL})', fontsize=12)
                ax.set_ylabel('Item', fontsize=12)
            
        elif chart_type == 'pie':
            # Pie chart for profit distribution
            fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
            
            # For better readability, limit the number of items shown directly on pie
            # and use a legend for the rest
            if len(item_profit) > 4:
                # Use the top 3 items and group others
                top_items = item_profit.head(3)
                other_items = item_profit.iloc[3:]
                other_profit = other_items['profit'].sum()
                
                # Create new dataframe with Others group
                pie_data = pd.DataFrame({
                    'profit': list(top_items['profit']) + [other_profit]
                })
                pie_labels = list(top_items.index) + ['Other Items']
                
                # Define clear, contrasting colors
                colors = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2']
            else:
                pie_data = item_profit
                pie_labels = item_profit.index
                colors = plt.cm.tab10.colors
            
            # Plot improved pie chart with clearer labels
            wedges, texts, autotexts = ax.pie(
                pie_data['profit'],
                labels=None,  # Don't show labels directly on pie
                autopct='%1.1f%%',
                startangle=90,
                colors=colors,
                wedgeprops={'edgecolor': 'w', 'linewidth': 1.5, 'antialiased': True}
            )
            
            # Enhance percentage text styling for maximum readability
            plt.setp(autotexts, size=16, weight="bold", color="white", 
                      path_effects=[patheffects.withStroke(linewidth=3, foreground='black')])
            
            # Add a clearer, more readable legend
            legend = ax.legend(wedges, pie_labels, 
                      title="Items",
                      loc="center left",
                      bbox_to_anchor=(1, 0.5),
                      fontsize=14,
                      frameon=True,
                      framealpha=0.95,
                      edgecolor='gray')
            
            # Make the legend title more prominent
            legend.get_title().set_fontsize(16)
            legend.get_title().set_fontweight('bold')
            
            ax.set_title('Profit Distribution by Item', fontsize=18, fontweight='bold')
            ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular
        
        # Convert plot to base64 string with improved quality and resolution
        buffer = BytesIO()
        fig.tight_layout()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=120, pad_inches=0.25)
        buffer.seek(0)
        image_png = buffer.getvalue()
        plt.close(fig)
        buffer.close()
        
        chart = base64.b64encode(image_png).decode('utf-8')
        # Add CSS classes for responsive behavior while maintaining readability
        return f'<img src="data:image/png;base64,{chart}" alt="Item Profit Chart" class="img-fluid chart-img" style="max-width:100%; width:auto; margin:0 auto; display:block;">'  
    except Exception as e:
        print(f"Error generating item profit chart ({chart_type}): {e}")
        return f"<div class='alert alert-danger'>Error generating {chart_type} chart for item profit: {e}</div>"

def generate_service_profit_chart(chart_type='bar'):
    """Generate chart for profit per service type with different visualization types
    
    Args:
        chart_type: Type of chart to generate ('bar', 'line', or 'pie')
    """
    try:
        # Load jobs data
        jobs_df = load_jobs_data()
        
        if jobs_df.empty:
            return "<div class='alert alert-info'>No data available for analysis</div>"
        
        # Get jobs that are services
        if 'category' in jobs_df.columns:
            # If we have category column, filter by it
            services_df = jobs_df[jobs_df['category'] == 'service']
        else:
            # Otherwise, assume all are services (can be refined with better logic if needed)
            services_df = jobs_df
        
        if services_df.empty:
            return "<div class='alert alert-info'>No service data available for analysis</div>"
        
        # Group by service name (item)
        service_profit = services_df.groupby('item').agg({
            'quantity': 'sum',
            'revenue': 'sum',
            'cost': 'sum',
            'profit': 'sum'
        }).sort_values('profit', ascending=False)
        
        # Handle empty dataset
        if service_profit.empty:
            return "<div class='alert alert-info'>No service profit data available for analysis</div>"
        
        # Limit to top services for better readability
        original_length = len(service_profit)
        if original_length > 8:
            # For charts other than pie, we'll keep top items
            top_services = service_profit.head(8)
            # For pie chart, we'll aggregate others
            if chart_type == 'pie' and original_length > 8:
                others_sum = {
                    'quantity': service_profit.iloc[8:]['quantity'].sum(),
                    'revenue': service_profit.iloc[8:]['revenue'].sum(), 
                    'cost': service_profit.iloc[8:]['cost'].sum(),
                    'profit': service_profit.iloc[8:]['profit'].sum()
                }
                # Only add Others if there's meaningful profit to show
                if others_sum['profit'] > 0:
                    service_profit_with_others = top_services.copy()
                    service_profit_with_others.loc['Others'] = others_sum
                else:
                    service_profit_with_others = top_services
            else:
                service_profit_with_others = top_services
        else:
            service_profit_with_others = service_profit
            
        # Create chart with improved styling
        plt.style.use('ggplot')
        
        if chart_type == 'pie':
            # Pie chart for profit distribution
            fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
            
            # Plot pie chart
            wedges, texts, autotexts = ax.pie(
                service_profit_with_others['profit'],
                labels=service_profit_with_others.index,
                autopct='%1.1f%%',
                startangle=90,
                colors=plt.cm.tab10.colors,
                wedgeprops={'edgecolor': 'w', 'linewidth': 1, 'antialiased': True}
            )
            
            # Styling autotexts
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontsize(10)
                autotext.set_fontweight('bold')
            
            ax.set_title('Service Profit Distribution - Pie Chart', fontsize=16, fontweight='bold')
            ax.axis('equal')  # Equal aspect ratio ensures the pie chart is circular
            
        elif chart_type == 'bar':
            # Bar chart for profit by service
            fig, ax = plt.subplots(figsize=(12, 8), dpi=100)
            
            # Use horizontal bar for better label display
            bars = ax.barh(service_profit.index, service_profit['profit'], color='#5a189a', alpha=0.7)
            
            # Add value labels to the bars
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(width + 0.1, i, f'{BAHT_SYMBOL}{width:.2f}', va='center', fontweight='bold')
                
            ax.set_title('Service Profit Analysis - Bar Chart', fontsize=16, fontweight='bold')
            ax.set_xlabel(f'Profit ({BAHT_SYMBOL})', fontsize=12)
            ax.set_ylabel('Service', fontsize=12)
            
        elif chart_type == 'line':
            # Line chart (connected scatter for categories)
            fig, ax = plt.subplots(figsize=(12, 8), dpi=100)
            
            # Create x-axis positions for categories
            x_pos = np.arange(len(service_profit))
            
            # Plot revenue and profit lines
            ax.plot(x_pos, service_profit['revenue'], marker='o', linestyle='-', 
                   label=f'Revenue ({BAHT_SYMBOL})', color='#4287f5', linewidth=2)
            ax.plot(x_pos, service_profit['profit'], marker='s', linestyle='--', 
                   label=f'Profit ({BAHT_SYMBOL})', color='#5a189a', linewidth=2)
            
            # Set x-axis labels to service names with rotation
            plt.xticks(x_pos, service_profit.index, rotation=45, ha='right')
            
            # Add grid and legend
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.legend(fontsize=10)
            
            ax.set_title('Service Revenue vs. Profit - Line Chart', fontsize=16, fontweight='bold')
            ax.set_xlabel('Service', fontsize=12)
            ax.set_ylabel(f'Amount ({BAHT_SYMBOL})', fontsize=12)
        
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
    except Exception as e:
        print(f"Error generating service profit chart ({chart_type}): {e}")
        return f"<div class='alert alert-danger'>Error generating {chart_type} chart for service profit: {e}</div>"

def generate_category_comparison_chart(chart_type='bar'):
    """Generate chart comparing revenue and profit by category (service vs product)
    
    Args:
        chart_type: Type of chart to generate ('bar', 'line', 'pie', or 'stacked')
    """
    try:
        # Load jobs data
        jobs_df = load_jobs_data()
        
        if jobs_df.empty or 'category' not in jobs_df.columns:
            return "<div class='alert alert-info'>No category data available for analysis</div>"
        
        # Group by category
        category_metrics = jobs_df.groupby('category').agg({
            'revenue': 'sum',
            'cost': 'sum',
            'profit': 'sum'
        })
        
        # Filter out unknown category if present
        if 'unknown' in category_metrics.index:
            category_metrics = category_metrics.drop('unknown')
        
        # Focus on service and product
        if 'service' not in category_metrics.index:
            category_metrics.loc['service'] = {'revenue': 0, 'cost': 0, 'profit': 0}
            
        if 'product' not in category_metrics.index:
            category_metrics.loc['product'] = {'revenue': 0, 'cost': 0, 'profit': 0}
        
        # Create appropriate chart based on type
        plt.style.use('ggplot')
        
        if chart_type == 'bar':
            # Create a grouped bar chart
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            
            # Data preparation
            categories = ['Service', 'Product']
            x = np.arange(len(categories))
            width = 0.35
            
            # Extract values
            revenues = [category_metrics.loc['service', 'revenue'], category_metrics.loc['product', 'revenue']]
            profits = [category_metrics.loc['service', 'profit'], category_metrics.loc['product', 'profit']]
            
            # Create bars
            revenue_bars = ax.bar(x - width/2, revenues, width, label=f'Revenue ({BAHT_SYMBOL})', color='#5a189a')
            profit_bars = ax.bar(x + width/2, profits, width, label=f'Profit ({BAHT_SYMBOL})', color='#7b2cbf')
            
            # Add labels and title
            ax.set_xlabel('Category')
            ax.set_ylabel(f'Amount ({BAHT_SYMBOL})')
            ax.set_title('Revenue and Profit by Category - Bar Chart', fontsize=16, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.legend()
            
            # Add value annotations
            def add_value_labels(bars):
                for bar in bars:
                    height = bar.get_height()
                    ax.annotate(f'{BAHT_SYMBOL}{height:,.0f}',
                               xy=(bar.get_x() + bar.get_width() / 2, height),
                               xytext=(0, 3),  # 3 points vertical offset
                               textcoords="offset points",
                               ha='center', va='bottom',
                               fontweight='bold')
            
            add_value_labels(revenue_bars)
            add_value_labels(profit_bars)
            
        elif chart_type == 'pie':
            # Create a pie chart comparing service vs product revenue
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), dpi=100)
            
            # Revenue pie chart
            revenue_data = [category_metrics.loc['service', 'revenue'], category_metrics.loc['product', 'revenue']]
            wedges1, texts1, autotexts1 = ax1.pie(
                revenue_data,
                labels=['Services', 'Products'],
                autopct='%1.1f%%',
                startangle=90,
                colors=['#5a189a', '#7b2cbf'],
                wedgeprops={'edgecolor': 'w', 'linewidth': 1}
            )
            ax1.set_title('Revenue Distribution', fontsize=14, fontweight='bold')
            
            # Profit pie chart
            profit_data = [category_metrics.loc['service', 'profit'], category_metrics.loc['product', 'profit']]
            wedges2, texts2, autotexts2 = ax2.pie(
                profit_data,
                labels=['Services', 'Products'],
                autopct='%1.1f%%',
                startangle=90,
                colors=['#5a189a', '#7b2cbf'],
                wedgeprops={'edgecolor': 'w', 'linewidth': 1}
            )
            ax2.set_title('Profit Distribution', fontsize=14, fontweight='bold')
            
            # Style both pie charts
            for autotexts in [autotexts1, autotexts2]:
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontsize(10)
                    autotext.set_fontweight('bold')
                    
            # Set equal aspect ratio for both pie charts
            ax1.axis('equal')
            ax2.axis('equal')
            
            # Add overall title
            plt.suptitle('Category Comparison - Pie Charts', fontsize=16, fontweight='bold')
            
        elif chart_type == 'line':
            # Create a line chart showing trends between categories
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            
            # Extract data points
            categories = ['Service', 'Product']
            metrics = ['Revenue', 'Cost', 'Profit']
            
            # Plot multiple metrics as lines
            x = np.arange(len(categories))
            
            # Plot each metric
            ax.plot(x, [category_metrics.loc['service', 'revenue'], category_metrics.loc['product', 'revenue']], 
                   marker='o', linestyle='-', linewidth=2, label=f'Revenue ({BAHT_SYMBOL})', color='#5a189a')
            
            ax.plot(x, [category_metrics.loc['service', 'cost'], category_metrics.loc['product', 'cost']], 
                   marker='s', linestyle='--', linewidth=2, label=f'Cost ({BAHT_SYMBOL})', color='#e63946')
            
            ax.plot(x, [category_metrics.loc['service', 'profit'], category_metrics.loc['product', 'profit']], 
                   marker='^', linestyle='-.', linewidth=2, label=f'Profit ({BAHT_SYMBOL})', color='#7b2cbf')
            
            # Add data point labels
            for i, metric in enumerate(['revenue', 'cost', 'profit']):
                for j, category in enumerate(['service', 'product']):
                    value = category_metrics.loc[category, metric]
                    # Adjust y-offset to prevent overlap
                    y_offset = 10 if metric == 'revenue' else (-10 if metric == 'cost' else 0)
                    ax.annotate(f'{BAHT_SYMBOL}{value:,.0f}', 
                               xy=(j, value), 
                               xytext=(0, y_offset), 
                               textcoords='offset points',
                               ha='center', 
                               fontsize=8, 
                               fontweight='bold')
            
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.set_title('Category Comparison - Line Chart', fontsize=16, fontweight='bold')
            ax.set_xlabel('Category')
            ax.set_ylabel(f'Amount ({BAHT_SYMBOL})')
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.7)
            
        elif chart_type == 'stacked':
            # Create a stacked bar chart
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            
            # Data preparation
            categories = ['Service', 'Product']
            x = np.arange(len(categories))
            
            # Extract values
            profits = [category_metrics.loc['service', 'profit'], category_metrics.loc['product', 'profit']]
            costs = [category_metrics.loc['service', 'cost'], category_metrics.loc['product', 'cost']]
            
            # Create stacked bars
            profit_bars = ax.bar(x, profits, label=f'Profit ({BAHT_SYMBOL})', color='#5a189a')
            cost_bars = ax.bar(x, costs, bottom=profits, label=f'Cost ({BAHT_SYMBOL})', color='#e63946')
            
            # Add labels and title
            ax.set_xlabel('Category')
            ax.set_ylabel(f'Amount ({BAHT_SYMBOL})')
            ax.set_title('Cost and Profit by Category - Stacked Bar Chart', fontsize=16, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.legend()
            
            # Add value annotations to profit bars
            for i, bar in enumerate(profit_bars):
                height = bar.get_height()
                ax.annotate(f'{BAHT_SYMBOL}{height:,.0f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height / 2),  # Position in middle of bar
                           ha='center', va='center',
                           color='white', fontweight='bold')
                           
            # Add value annotations to cost bars
            for i, bar in enumerate(cost_bars):
                height = bar.get_height()
                profit = profits[i]
                ax.annotate(f'{BAHT_SYMBOL}{height:,.0f}',
                           xy=(bar.get_x() + bar.get_width() / 2, profit + height / 2),  # Position in middle of bar
                           ha='center', va='center',
                           color='white', fontweight='bold')
                           
            # Add revenue annotations
            for i, category in enumerate(['service', 'product']):
                revenue = category_metrics.loc[category, 'revenue']
                ax.annotate(f'Revenue: {BAHT_SYMBOL}{revenue:,.0f}',
                           xy=(i, revenue + 10),
                           ha='center', va='bottom',
                           fontweight='bold')
        
        # Convert plot to base64 string
        buffer = BytesIO()
        fig.tight_layout()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        image_png = buffer.getvalue()
        plt.close(fig)
        buffer.close()
        
        chart = base64.b64encode(image_png).decode('utf-8')
        return f'<img src="data:image/png;base64,{chart}" alt="Category Comparison Chart" style="width:100%;">'
    except Exception as e:
        print(f"Error generating category comparison chart ({chart_type}): {e}")
        return f"<div class='alert alert-danger'>Error generating {chart_type} chart for category comparison: {e}</div>"