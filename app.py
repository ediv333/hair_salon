from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages, send_from_directory, jsonify
import pandas as pd
import json
import csv
from datetime import datetime
from utils.graph_utils import generate_profit_chart, generate_item_profit_chart, generate_service_profit_chart, generate_daily_revenue_chart
import os
import locale
import sys
import logging
from logging.handlers import RotatingFileHandler
import io

# Import the path handling utilities
from path_fix import get_data_path, get_data_file_path
# Import app configuration
from config import configure_app

# Set up logger with FileHandler
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
logger = logging.getLogger('hair_salon_app')
logger.setLevel(logging.DEBUG)

# Create file handler for the logger (10MB max size, keep 5 backup files)
file_handler = RotatingFileHandler(log_file_path, maxBytes=10*1024*1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)

# Create formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Create a stream handler to console as well
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Create custom stdout and stderr streams that log to our logger
class LoggerWriter:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.buffer = ''

    def write(self, message):
        if message and message.strip():
            try:
                self.logger.log(self.level, message.strip())
            except Exception as e:
                # Fail silently if we can't log - prevents recursion errors
                pass

    def flush(self):
        pass

# Only redirect stdout/stderr in development mode, not when running as executable
# This prevents recursion issues in PyInstaller executables
if not getattr(sys, 'frozen', False):
    # Running in normal Python environment
    sys.stdout = LoggerWriter(logger, logging.INFO)
    sys.stderr = LoggerWriter(logger, logging.ERROR)

# Override print function to log messages, but safely
original_print = print
def logged_print(*args, **kwargs):
    try:
        # First ensure normal print works
        original_print(*args, **kwargs)
        # Then try to log it
        if getattr(sys, 'frozen', False):
            # When running as executable, don't try to log via stringIO
            # which can cause recursion issues
            message = ' '.join(str(arg) for arg in args)
            logger.info(message)
        else:
            # In development mode, we can use StringIO
            output = io.StringIO()
            original_print(*args, file=output, **kwargs)
            message = output.getvalue().strip()
            if message:
                logger.info(message)
    except Exception:
        # Fallback in case of any logging errors
        pass

print = logged_print

logger.info('Logger initialized successfully')

# Set locale for Thai Baht formatting
try:
    locale.setlocale(locale.LC_ALL, 'th_TH.UTF-8')
except:
    pass  # Fallback if locale is not supported

app = Flask(__name__)
app = configure_app(app)

# Default to service menu disabled unless specifically enabled by launcher
app.config.setdefault('SERVICE_MENU_ENABLED', False)

# API routes for accessing data files
@app.route('/api/customers')
def api_customers():
    customers_path = get_data_file_path('customers.json')
    print(f"Loading customers from: {customers_path}")
    if os.path.exists(customers_path):
        try:
            with open(customers_path, 'r', encoding='utf-8') as f:
                customers_data = json.load(f)
                print(f"Loaded {len(customers_data)} customers: {[c.get('name', 'Unknown') for c in customers_data]}")
                return jsonify(customers_data)
        except Exception as e:
            print(f"Error loading customers: {e}")
            return jsonify([])
    else:
        print(f"No customers file found at {customers_path}")
        return jsonify([])

@app.route('/api/services')
def api_services():
    services_path = get_data_file_path('services.json')
    print(f"Loading services from: {services_path}")
    if os.path.exists(services_path):
        try:
            with open(services_path, 'r', encoding='utf-8') as f:
                services_data = json.load(f)
                print(f"Loaded {len(services_data)} services")
                return jsonify(services_data)
        except Exception as e:
            print(f"Error loading services: {e}")
            return jsonify([])
    else:
        print(f"No services file found at {services_path}")
        return jsonify([])

@app.route('/api/inventory')
def api_inventory():
    inventory_path = get_data_file_path('inventory.json')
    print(f"Loading inventory from: {inventory_path}")
    if os.path.exists(inventory_path):
        try:
            with open(inventory_path, 'r', encoding='utf-8') as f:
                inventory_data = json.load(f)
                print(f"Loaded {len(inventory_data)} inventory items")
                return jsonify(inventory_data)
        except Exception as e:
            print(f"Error loading inventory: {e}")
            return jsonify([])
    else:
        print(f"No inventory file found at {inventory_path}")
        return jsonify([])

@app.route('/')
def analyst():
    chart = None
    report_type = request.args.get('report_type', 'total_profit')
    chart_type = request.args.get('chart_type', 'pie')  # Changed default to pie
    date_range = request.args.get('date_range', 'all')
    comparison = request.args.get('comparison', 'none')
    
    # Default values for stats
    total_revenue = 0
    total_cost = 0
    net_profit = 0
    service_revenue = 0
    product_revenue = 0
    service_profit = 0
    product_profit = 0
    last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
    report_title = 'Sales Analysis'
    
    # Default values for additional metrics
    customer_count = 0
    average_price = 0
    best_profit_item = "N/A"
    best_profit_amount = 0
    customer_growth_rate = 0
    service_growth_rate = 0
    product_growth_rate = 0
    
    # Load jobs data if available
    jobs_path = get_data_file_path('jobs.csv')
    if os.path.exists(jobs_path):
        try:
            # Load jobs data for analysis
            # Debug info
            print(f"Jobs CSV exists: {os.path.exists(jobs_path)}")
            
            # Load jobs.csv with proper header handling
            try:
                # Load CSV with header row (not treating header as data)
                jobs_df = pd.read_csv(jobs_path)
                print(f"Loaded CSV with columns: {jobs_df.columns.tolist()}")
                print(f"Data shape: {jobs_df.shape}")
                
            except Exception as e:
                print(f"Error loading jobs.csv: {e}")
                # Create empty dataframe with needed columns
                jobs_df = pd.DataFrame(columns=['date', 'customer', 'item', 'quantity', 'price', 'cost', 'category'])
            
            # Convert columns to proper types
            if not jobs_df.empty:
                # Ensure numeric columns are properly typed
                jobs_df['quantity'] = pd.to_numeric(jobs_df['quantity'], errors='coerce').fillna(0).astype(int)
                jobs_df['price'] = pd.to_numeric(jobs_df['price'], errors='coerce').fillna(0)
                jobs_df['cost'] = pd.to_numeric(jobs_df['cost'], errors='coerce').fillna(0)
                # Add cost column based on item mappings
                # Get services and inventory for cost mapping
                services = []
                inventory = []
                services_path = get_data_file_path('services.json')
                if os.path.exists(services_path):
                    with open(services_path, 'r', encoding='utf-8') as f:
                        services = json.load(f)
                inventory_path = get_data_file_path('inventory.json')
                if os.path.exists(inventory_path):
                    with open(inventory_path, 'r', encoding='utf-8') as f:
                        inventory = json.load(f)
                
                # Create cost mapping
                cost_map = {}
                for service in services:
                    cost_map[service.get('name')] = float(service.get('cost', 0))
                for item in inventory:
                    cost_map[item.get('name')] = float(item.get('cost', 0))
                
                # Add costs
                costs = []
                for _, row in jobs_df.iterrows():
                    item_name = row['item']
                    quantity = row['quantity']
                    cost = cost_map.get(item_name, 0) * quantity
                    costs.append(cost)
                
                jobs_df['cost'] = costs
            
            # Calculate basic stats
            if not jobs_df.empty:
                # Calculate metrics with defensive checks
                try:
                    # Make sure price and quantity columns exist and are numeric
                    if 'price' in jobs_df.columns and 'quantity' in jobs_df.columns:
                        # Calculate revenue (price * quantity)
                        jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
                        
                        # Use total_profit from CSV if available, otherwise calculate it
                        if 'total_profit' in jobs_df.columns:
                            jobs_df['profit'] = jobs_df['total_profit']
                        elif 'cost' in jobs_df.columns:
                            # Calculate profit: (price - cost) * quantity (cost is unit cost)
                            jobs_df['profit'] = (jobs_df['price'] - jobs_df['cost']) * jobs_df['quantity']
                        else:
                            jobs_df['profit'] = jobs_df['revenue']
                        
                        # Calculate total cost for summary (unit cost * quantity)
                        if 'cost' in jobs_df.columns:
                            jobs_df['total_cost'] = jobs_df['cost'] * jobs_df['quantity']
                        else:
                            jobs_df['total_cost'] = 0
                        
                        # Calculate summary metrics
                        total_revenue = jobs_df['revenue'].sum()
                        total_cost = jobs_df['total_cost'].sum() if 'total_cost' in jobs_df.columns else 0
                        net_profit = jobs_df['profit'].sum()
                    else:
                        print(f"Missing required columns. Available columns: {jobs_df.columns.tolist()}")
                        total_revenue = total_cost = net_profit = 0
                except Exception as calc_error:
                    print(f"Error in calculation: {calc_error}")
                    total_revenue = total_cost = net_profit = 0
                
                # Calculate category-specific metrics
                # Default values
                service_revenue = service_cost = service_profit = 0
                product_revenue = product_cost = product_profit = 0
                
                # Check if we have the necessary columns for category analysis
                if 'category' in jobs_df.columns and 'revenue' in jobs_df.columns:
                    try:
                        # Filter by service and product
                        services_df = jobs_df[jobs_df['category'] == 'service']
                        products_df = jobs_df[jobs_df['category'] == 'product']
                        
                        # Calculate service metrics
                        if not services_df.empty and 'revenue' in services_df:
                            service_revenue = services_df['revenue'].sum()
                            service_cost = services_df['cost'].sum() if 'cost' in services_df else 0
                            service_profit = service_revenue - service_cost
                        
                        # Calculate product metrics
                        if not products_df.empty and 'revenue' in products_df:
                            product_revenue = products_df['revenue'].sum()
                            product_cost = products_df['cost'].sum() if 'cost' in products_df else 0
                            product_profit = product_revenue - product_cost
                    except Exception as cat_error:
                        print(f"Error in category calculations: {cat_error}")
                else:
                    print("Missing category or revenue columns for category analysis")
                
                # Calculate additional analytics metrics
                customer_count = 0
                average_price = 0
                best_profit_item = "N/A"
                best_profit_amount = 0
                customer_growth_rate = 0
                service_growth_rate = 0
                product_growth_rate = 0
                
                try:
                    # Customer count - unique customers (debug the count)
                    if 'customer' in jobs_df.columns:
                        unique_customers = jobs_df['customer'].dropna().unique()
                        customer_count = len(unique_customers)
                        print(f"Debug: Unique customers found: {unique_customers}")
                        print(f"Debug: Customer count: {customer_count}")
                    
                    # Average price per transaction
                    if 'price' in jobs_df.columns and not jobs_df.empty:
                        average_price = jobs_df['price'].mean()
                    
                    # Best profit item
                    if 'item' in jobs_df.columns and 'profit' in jobs_df.columns:
                        item_profits = jobs_df.groupby('item')['profit'].sum().sort_values(ascending=False)
                        if not item_profits.empty:
                            best_profit_item = item_profits.index[0]
                            best_profit_amount = item_profits.iloc[0]
                    
                    # Calculate growth rates (simplified - comparing current period vs previous)
                    # For now, we'll calculate based on available data trends
                    # This is a basic implementation - in a real scenario, you'd compare time periods
                    
                    if 'date' in jobs_df.columns and not jobs_df.empty:
                        # Sort by date to analyze trends
                        jobs_df_sorted = jobs_df.sort_values('date')
                        
                        # For growth rates, we'll use a simple approach:
                        # Compare first half vs second half of data
                        mid_point = len(jobs_df_sorted) // 2
                        if mid_point > 0:
                            first_half = jobs_df_sorted.iloc[:mid_point]
                            second_half = jobs_df_sorted.iloc[mid_point:]
                            
                            # Customer growth rate
                            first_customers = first_half['customer'].nunique() if not first_half.empty else 0
                            second_customers = second_half['customer'].nunique() if not second_half.empty else 0
                            if first_customers > 0:
                                customer_growth_rate = ((second_customers - first_customers) / first_customers) * 100
                            
                            # Service growth rate (by revenue)
                            first_service_revenue = first_half[first_half['category'] == 'service']['revenue'].sum() if not first_half.empty else 0
                            second_service_revenue = second_half[second_half['category'] == 'service']['revenue'].sum() if not second_half.empty else 0
                            if first_service_revenue > 0:
                                service_growth_rate = ((second_service_revenue - first_service_revenue) / first_service_revenue) * 100
                            
                            # Product growth rate (by revenue)
                            first_product_revenue = first_half[first_half['category'] == 'product']['revenue'].sum() if not first_half.empty else 0
                            second_product_revenue = second_half[second_half['category'] == 'product']['revenue'].sum() if not second_half.empty else 0
                            if first_product_revenue > 0:
                                product_growth_rate = ((second_product_revenue - first_product_revenue) / first_product_revenue) * 100
                            
                except Exception as metrics_error:
                    print(f"Error calculating additional metrics: {metrics_error}")
            
            # Import all chart generation functions
            from utils.graph_utils import (generate_daily_revenue_chart, generate_item_profit_chart, 
                                          generate_service_profit_chart, generate_category_comparison_chart)
            
            # Generate charts with the requested chart_type
            if report_type == 'total_profit':
                chart = generate_daily_revenue_chart(chart_type=chart_type)
                report_title = 'Daily Revenue Analysis'
            elif report_type == 'profit_per_item':
                chart = generate_item_profit_chart(chart_type=chart_type)
                report_title = 'Profit Analysis - Inventory Products Only'
            elif report_type == 'profit_per_service':
                chart = generate_service_profit_chart(chart_type=chart_type)
                report_title = 'Profit Per Service Type'
            elif report_type == 'category_comparison':
                chart = generate_category_comparison_chart(chart_type=chart_type)
                report_title = 'Services vs Products Analysis'
        
        except Exception as e:
            print(f"Error processing data: {e}")
    
    # Format values as Thai Baht
    formatted_revenue = format_thai_baht(total_revenue)
    formatted_cost = format_thai_baht(total_cost)
    formatted_profit = format_thai_baht(net_profit)
    
    # Format category metrics
    formatted_service_revenue = format_thai_baht(service_revenue)
    formatted_product_revenue = format_thai_baht(product_revenue)
    formatted_service_profit = format_thai_baht(service_profit)
    formatted_product_profit = format_thai_baht(product_profit)
    
    # Calculate percentages
    service_percentage = (service_revenue / total_revenue * 100) if total_revenue > 0 else 0
    product_percentage = (product_revenue / total_revenue * 100) if total_revenue > 0 else 0
    
    return render_template('analyst.html', 
                          chart=chart, 
                          report_type=report_type,
                          chart_type=chart_type,
                          date_range=date_range,
                          comparison=comparison,
                          total_revenue=formatted_revenue,
                          total_cost=formatted_cost,
                          net_profit=formatted_profit,
                          service_revenue=formatted_service_revenue,
                          product_revenue=formatted_product_revenue,
                          service_profit=formatted_service_profit,
                          product_profit=formatted_product_profit,
                          service_percentage=f"{service_percentage:.1f}%",
                          product_percentage=f"{product_percentage:.1f}%",
                          customer_count=customer_count,
                          average_price=format_thai_baht(average_price),
                          best_profit_item=best_profit_item,
                          best_profit_amount=format_thai_baht(best_profit_amount),
                          customer_growth_rate=f"{customer_growth_rate:.1f}%",
                          service_growth_rate=f"{service_growth_rate:.1f}%",
                          product_growth_rate=f"{product_growth_rate:.1f}%",
                          last_updated=last_updated,
                          report_title=report_title)

@app.route('/update_price', methods=['POST'])
def update_price():
    """Update price in services.json or inventory.json"""
    try:
        # Get JSON data from request
        data = request.get_json()
        if not data or 'itemName' not in data or 'newPrice' not in data:
            return jsonify({'success': False, 'message': 'Invalid data'}), 400
            
        item_name = data['itemName']
        new_price = float(data['newPrice'])
        
        # Search for the item in services.json
        services_path = get_data_file_path('services.json')
        services_updated = False
        if os.path.exists(services_path):
            with open(services_path, 'r', encoding='utf-8') as f:
                services = json.load(f)
                
            # Look for the item in services
            for service in services:
                if service.get('name') == item_name:
                    service['price'] = str(int(new_price))  # Convert to integer string to match format
                    services_updated = True
                    break
            
            # Save updates if any were made
            if services_updated:
                with open(services_path, 'w', encoding='utf-8') as f:
                    json.dump(services, f, indent=2, ensure_ascii=False)
                return jsonify({'success': True, 'message': 'Service price updated', 'type': 'service'})
        
        # If not found in services, check inventory.json
        inventory_path = get_data_file_path('inventory.json')
        if os.path.exists(inventory_path):
            with open(inventory_path, 'r', encoding='utf-8') as f:
                inventory = json.load(f)
                
            # Look for the item in inventory
            for item in inventory:
                if item.get('name') == item_name:
                    item['retail_price'] = int(new_price)  # Convert to integer
                    with open(inventory_path, 'w', encoding='utf-8') as f:
                        json.dump(inventory, f, indent=2, ensure_ascii=False)
                    return jsonify({'success': True, 'message': 'Inventory price updated', 'type': 'inventory'})
        
        return jsonify({'success': False, 'message': 'Item not found in services or inventory'}), 404
        
    except Exception as e:
        print(f"Error updating price: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/simulator', methods=['GET', 'POST'])
def simulator():
    """Pricing simulator to help optimize profit based on historical data"""
    # Default values
    items_data = []
    last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
    summary_stats = {}
    custom_prices = {}
    
    # Process form submission for custom prices
    if request.method == 'POST':
        for key, value in request.form.items():
            if key.startswith('custom_price_') and value.strip():
                item_name = key.replace('custom_price_', '')
                try:
                    custom_prices[item_name] = float(value)
                except ValueError:
                    pass
    
    # Use our path utility to get the correct path to the jobs.csv file
    jobs_path = get_data_file_path('jobs.csv')
    if os.path.exists(jobs_path):
        try:
            # Load jobs data using the correct path
            jobs_df = pd.read_csv(jobs_path)
            
            # Ensure required columns exist
            if all(col in jobs_df.columns for col in ['item', 'quantity', 'price', 'cost']):
                # Calculate current metrics
                jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
                
                # Use total_profit from CSV if available, otherwise calculate it
                if 'total_profit' in jobs_df.columns:
                    jobs_df['profit'] = jobs_df['total_profit']
                else:
                    # Calculate profit: (price - cost) * quantity (cost is unit cost)
                    jobs_df['profit'] = (jobs_df['price'] - jobs_df['cost']) * jobs_df['quantity']
                
                # Calculate summary statistics
                summary_stats = {
                    'avg_price': jobs_df['price'].mean(),
                    'customer_count': jobs_df['customer'].nunique(),
                    'most_requested_item': jobs_df.groupby('item')['quantity'].sum().idxmax(),
                    'most_requested_price': jobs_df[jobs_df['item'] == jobs_df.groupby('item')['quantity'].sum().idxmax()]['price'].mean()
                }
                
                # Group by item
                item_metrics = jobs_df.groupby('item').agg({
                    'quantity': 'sum',
                    'revenue': 'sum',
                    'profit': 'sum',
                    'price': 'mean',
                    'cost': 'mean',
                    'customer': pd.Series.nunique
                }).reset_index()
                
                # Calculate profit margin and potential optimizations
                item_metrics['profit_margin'] = (item_metrics['profit'] / item_metrics['revenue'] * 100).round(2)
                
                # Determine suggested price increase percentage based on profit margin
                def suggest_increase(margin):
                    if margin < 20:
                        return 15
                    elif margin < 35:
                        return 10
                    elif margin < 50:
                        return 5
                    else:
                        return 0
                    
                item_metrics['suggested_increase'] = item_metrics['profit_margin'].apply(suggest_increase)
                
                # Calculate potential price increases (suggested and fixed percentages)
                for pct in [5, 10, 15]:
                    # New price with increase
                    new_price_col = f'price_{pct}pct'
                    item_metrics[new_price_col] = (item_metrics['price'] * (1 + pct/100)).round(0)
                    
                    # Estimate new profit (assuming same quantity sold)
                    new_revenue_col = f'revenue_{pct}pct'
                    item_metrics[new_revenue_col] = item_metrics['quantity'] * item_metrics[new_price_col]
                    
                    # New profit
                    new_profit_col = f'profit_{pct}pct'
                    item_metrics[new_profit_col] = item_metrics[new_revenue_col] - (item_metrics['cost'] * item_metrics['quantity'])
                    
                    # Profit increase
                    profit_increase_col = f'profit_increase_{pct}pct'
                    item_metrics[profit_increase_col] = item_metrics[new_profit_col] - item_metrics['profit']
                
                # Calculate suggested price and profit based on suggested increase percentage
                item_metrics['price_suggested'] = item_metrics.apply(
                    lambda row: row['price'] * (1 + row['suggested_increase']/100), axis=1
                ).round(0)
                
                item_metrics['revenue_suggested'] = item_metrics['quantity'] * item_metrics['price_suggested']
                item_metrics['profit_suggested'] = item_metrics['revenue_suggested'] - (item_metrics['cost'] * item_metrics['quantity'])
                item_metrics['profit_increase_suggested'] = item_metrics['profit_suggested'] - item_metrics['profit']
                
                # Add custom price and profit calculations
                item_metrics['custom_price'] = item_metrics['price']
                for idx, row in item_metrics.iterrows():
                    if row['item'] in custom_prices:
                        item_metrics.at[idx, 'custom_price'] = custom_prices[row['item']]
                
                # Calculate custom profit metrics
                item_metrics['custom_price_increase_pct'] = ((item_metrics['custom_price'] / item_metrics['price']) - 1) * 100
                item_metrics['revenue_custom'] = item_metrics['quantity'] * item_metrics['custom_price']
                item_metrics['profit_custom'] = item_metrics['revenue_custom'] - (item_metrics['cost'] * item_metrics['quantity'])
                item_metrics['profit_increase_custom'] = item_metrics['profit_custom'] - item_metrics['profit']
                
                # Calculate custom profit margin: (Custom Profit / Custom Revenue) * 100
                item_metrics['custom_profit_margin'] = (item_metrics['profit_custom'] / item_metrics['revenue_custom'] * 100).round(2)
                # Handle division by zero
                item_metrics['custom_profit_margin'] = item_metrics['custom_profit_margin'].fillna(0)
                
                # Calculate total profit summary
                total_current_profit = item_metrics['profit'].sum()
                total_suggested_profit = item_metrics['profit_suggested'].sum()
                total_custom_profit = item_metrics['profit_custom'].sum()
                
                # Convert to list of dicts for template
                items_data = item_metrics.to_dict('records')
                
                # Sort by potential profit increase (using suggested percentage)
                items_data = sorted(items_data, key=lambda x: x.get('profit_increase_suggested', 0), reverse=True)
                
                # Format numeric values for display
                for item in items_data:
                    # Format currency values
                    for key in ['price', 'cost', 'price_5pct', 'price_10pct', 'price_15pct', 'price_suggested', 'custom_price']:
                        if key in item:
                            item[key] = f'฿{item[key]:,.0f}'
                    
                    for key in item:
                        if any(term in key for term in ['revenue', 'profit']) and 'pct' not in key:
                            item[key] = f'฿{item[key]:,.2f}'
                    
                    # Format percentages
                    if 'custom_price_increase_pct' in item:
                        item['custom_price_increase_pct'] = f'{item["custom_price_increase_pct"]:.1f}%'
                
                # Format summary statistics
                summary_stats['avg_price'] = f'฿{summary_stats["avg_price"]:,.0f}'
                summary_stats['most_requested_price'] = f'฿{summary_stats["most_requested_price"]:,.0f}'
                summary_stats['total_current_profit'] = f'฿{total_current_profit:,.2f}'
                summary_stats['total_suggested_profit'] = f'฿{total_suggested_profit:,.2f}'
                summary_stats['total_custom_profit'] = f'฿{total_custom_profit:,.2f}'
                summary_stats['suggested_profit_increase'] = f'฿{(total_suggested_profit - total_current_profit):,.2f}'
                summary_stats['custom_profit_increase'] = f'฿{(total_custom_profit - total_current_profit):,.2f}'
                summary_stats['suggested_profit_increase_pct'] = f'{((total_suggested_profit - total_current_profit) / total_current_profit * 100) if total_current_profit > 0 else 0:.1f}%'
                summary_stats['custom_profit_increase_pct'] = f'{((total_custom_profit - total_current_profit) / total_current_profit * 100) if total_current_profit > 0 else 0:.1f}%'
        
        except Exception as e:
            print(f"Error in simulator calculations: {e}")
    
    return render_template('simulator.html', 
                           items_data=items_data,
                           summary_stats=summary_stats,
                           last_updated=last_updated)

@app.route('/customers', methods=['GET', 'POST'])
def customers():
    path = get_data_file_path('customers.json')
    _customers = []
    if os.path.exists(path):
        # Load customers
        with open(path, 'r', encoding='utf-8') as f:
            _customers = json.load(f)
    search_query = request.args.get('search', '').strip().lower()
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name')
        phone = request.form.get('phone', '').strip() or None
        birthday = request.form.get('birthday', '').strip() or None
        note = request.form.get('note', '')
        # No validation for phone or birthday, just store as is (can be None or empty)
        if action == 'add':
            _customers.append({'name': name, 'phone': phone, 'birthday': birthday, 'note': note})
        elif action == 'update':
            idx = int(request.form.get('idx'))
            _customers[idx] = {'name': name, 'phone': phone, 'birthday': birthday, 'note': note}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(_customers, f, indent=2, ensure_ascii=False)
        return redirect(url_for('customers'))
    # Filter customers if search query is present
    if search_query:
        filtered_customers = [c for c in _customers if search_query in c.get('name', '').lower()]
    else:
        filtered_customers = _customers
    return render_template('customers.html', customers=filtered_customers, search=request.args.get('search', ''))

@app.route('/services', methods=['GET', 'POST'])
def services():
    path = get_data_file_path('services.json')
    _services = []
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            _services = json.load(f)
    search_query = request.args.get('search', '').strip().lower()
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name')
        # Remove type field
        cost = request.form.get('cost')
        price = request.form.get('price')
        if action == 'add':
            _services.append({'name': name, 'cost': cost, 'price': price})
        elif action == 'update':
            idx = int(request.form.get('idx'))
            _services[idx] = {'name': name, 'cost': cost, 'price': price}
        elif action == 'remove':
            idx = int(request.form.get('idx'))
            _services.pop(idx)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(_services, f, indent=2, ensure_ascii=False)
        return redirect(url_for('services'))
    # Filter services if search query is present
    if search_query:
        filtered_services = [s for s in _services if search_query in s.get('name', '').lower()]
    else:
        filtered_services = _services
    return render_template('services.html', services=filtered_services, search=request.args.get('search', ''))

@app.route('/job', methods=['GET', 'POST'])
def job():
    # Initialize variables that will be used across all code paths
    jobs = []
    
    # We've removed history functionality from this route - it's now in the /history route
    
    # Prevent use if services.json or inventory.json is missing
    services_path = get_data_file_path('services.json')
    inventory_path = get_data_file_path('inventory.json')
    if not (os.path.exists(services_path) and os.path.exists(inventory_path)):
        # Remove flash, just render with disable_form
        return render_template('job.html', disable_form=True, jobs=[])

    _customers = [ {
        "name": "dummy",
        "phone": '',
        "birthday": '',
        "note": ""
      }]
    customers_path = get_data_file_path('customers.json')
    if os.path.exists(customers_path):
        with open(customers_path, 'r', encoding='utf-8') as f:
            _customers = json.load(f)
    services_path = get_data_file_path('services.json')
    with open(services_path, 'r') as f:
        services = json.load(f)
    inventory_path = get_data_file_path('inventory.json')
    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)
    if request.method == 'POST':
        date = request.form.get('date')
        customer = request.form.get('customer')
        item_name = request.form.get('item')
        quantity = int(request.form.get('quantity', 1))
        price = float(request.form.get('price', 0))
        cost = float(request.form.get('cost', 0))  # Get the cost from the form

        if not item_name:
            flash('Please select an item.', 'error')
            return redirect(url_for('job'))
            
        # Calculate total price and cost
        total_price = price * quantity
        total_cost = cost  # Cost is already calculated based on quantity in the frontend
        
        # Determine item category (service, product, or promotion)
        item_category = "unknown"
        # Check if item is in services
        for service in services:
            if service.get('name') == item_name:
                item_category = "service"
                break
        # If not found in services, check inventory
        if item_category == "unknown":
            for item in inventory:
                if item.get('name') == item_name:
                    item_category = "product"
                    break
                    
        # If not found in services or inventory, check promotions
        if item_category == "unknown":
            promotions_path = get_data_file_path('promotions.json')
            if os.path.exists(promotions_path):
                try:
                    with open(promotions_path, 'r', encoding='utf-8') as f:
                        promotions_data = json.load(f)
                        for promo in promotions_data:
                            if promo.get('name') == item_name:
                                item_category = "promotion"
                                break
                except Exception as e:
                    logger.error(f"Error checking promotions: {e}")
                    pass
        
        # If no jobs.csv file exists, create it with headers
        jobs_path = get_data_file_path('jobs.csv')
        if not os.path.exists(jobs_path):
            # Ensure data directory exists
            data_dir = get_data_path()
            with open(jobs_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(['date', 'customer', 'item', 'quantity', 'price', 'cost', 'category', 'promotion_id'])

        # Get promotion ID if this is a promotion
        promotion_id = None
        if item_category == "promotion":
            promotions_path = get_data_file_path('promotions.json')
            if os.path.exists(promotions_path):
                try:
                    with open(promotions_path, 'r', encoding='utf-8') as f:
                        promotions_data = json.load(f)
                        for promo in promotions_data:
                            if promo.get('name') == item_name:
                                promotion_id = promo.get('id')
                                break
                except Exception as e:
                    logger.error(f"Error finding promotion ID: {e}")
                    pass

        # Append the new job
        with open(jobs_path, 'a', newline='', encoding='utf-8') as f:
            # Format the date in DD/MM/YYYY format to be consistent
            formatted_date = date
            try:
                # Try to parse the date and reformat it
                parsed_date = pd.to_datetime(date, dayfirst=True)
                formatted_date = parsed_date.strftime('%d/%m/%Y')
            except:
                pass  # Keep the original format if parsing fails
            
            # Check if we need to add promotion_id
            job_row = [formatted_date, customer, item_name, quantity, price, total_cost, item_category]
            
            # Only add promotion_id if it exists and if jobs.csv already has the column
            # Read the first line to check headers
            with open(jobs_path, 'r', newline='', encoding='utf-8') as check_file:
                reader = csv.reader(check_file)
                headers = next(reader, None)
                
            # If we have 8 columns and the last is promotion_id, add it
            if headers and len(headers) >= 8 and headers[-1] == 'promotion_id':
                job_row.append(promotion_id)
                
            # Write the row with the appropriate number of columns
            csv.writer(f).writerow(job_row)

        for item in inventory:
            if item['name'] == item_name:
                try:
                    item['current_quantity'] = int(item.get('current_quantity', 0)) - quantity
                    item['last_date_sell'] = date
                except Exception:
                    pass
                break
        inventory_path = get_data_file_path('inventory.json')
        with open(inventory_path, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, indent=2, ensure_ascii=False)
        # Redirect to job route - load jobs again to show updated data
        return redirect(url_for('job'))

    # No need to duplicate data in static folder
    return render_template('job.html', disable_form=False, jobs=jobs)

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    path = get_data_file_path('inventory.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            inventory = json.load(f)
    except FileNotFoundError:
        inventory = []
    # Remove types list
    search_name = request.args.get('search_name', '').strip().lower()
    search_type = request.args.get('search_type', '').strip()
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name')
        # Remove type field
        def to_int(val):
            try:
                return int(val)
            except Exception:
                return 0
        initial_quantity = to_int(request.form.get('initial_quantity'))
        current_quantity = to_int(request.form.get('current_quantity'))
        cost = to_int(request.form.get('cost'))
        retail_price = to_int(request.form.get('retail_price'))
        discount = to_int(request.form.get('discount'))
        last_date_sell = request.form.get('last_date_sell')
        date_purchase = request.form.get('date_purchase')
        if action == 'add':
            inventory.append({
                'name': name,
                'initial_quantity': initial_quantity,
                'current_quantity': current_quantity,
                'cost': cost,
                'retail_price': retail_price,
                'discount': discount,
                'last_date_sell': last_date_sell,
                'date_purchase': date_purchase
            })
        elif action == 'update':
            idx = int(request.form.get('idx'))
            inventory[idx] = {
                'name': name,
                'initial_quantity': initial_quantity,
                'current_quantity': current_quantity,
                'cost': cost,
                'retail_price': retail_price,
                'discount': discount,
                'last_date_sell': last_date_sell,
                'date_purchase': date_purchase
            }
        elif action == 'remove':
            idx = int(request.form.get('idx'))
            inventory.pop(idx)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(inventory, f, indent=2, ensure_ascii=False)
        return redirect(url_for('inventory'))
    filtered_inventory = inventory
    if search_name:
        filtered_inventory = [item for item in filtered_inventory if search_name in item.get('name', '').lower()]
    # Remove search_type filter
    return render_template(
        'inventory.html',
        inventory=filtered_inventory,
        search_name=request.args.get('search_name', '')
    )


# Helper function for Thai Baht formatting
def format_thai_baht(amount):
    if amount is None:
        return '฿0.00'
    try:
        return '฿{:,.2f}'.format(float(amount))
    except (ValueError, TypeError):
        return '฿0.00'

@app.route('/history')
def history():
    """Display job history with filtering options"""
    # Get filter parameters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    customer_filter = request.args.get('customer_filter', '').strip()
    type_filter = request.args.get('type_filter', '')
    item_filter = request.args.get('item_filter', '').strip()
    
    # Store filters for template
    filters = {
        'date_from': date_from,
        'date_to': date_to,
        'customer_filter': customer_filter,
        'type_filter': type_filter,
        'item_filter': item_filter
    }
    
    # Default values
    jobs = []
    total_revenue = 0
    total_profit = 0
    available_customers = []
    available_items = []
    items_by_category = {'service': [], 'product': []}
    
    try:
        jobs_path = get_data_file_path('jobs.csv')
        if os.path.exists(jobs_path):
            # Load jobs data
            jobs_df = pd.read_csv(jobs_path)
            
            # If dataframe is empty, return early
            if jobs_df.empty:
                return render_template('history.html', jobs=[], filters=filters, 
                                      total_revenue='0.00', total_profit='0.00')
            
            # Gather unique customers and items for dropdown menus (before applying filters)
            if 'customer' in jobs_df.columns:
                available_customers = sorted(jobs_df['customer'].dropna().unique().tolist())
            if 'item' in jobs_df.columns:
                available_items = sorted(jobs_df['item'].dropna().unique().tolist())
            
            # Organize items by category for dynamic filtering
            items_by_category = {'service': [], 'product': [], 'promotion': []}
            if 'item' in jobs_df.columns and 'category' in jobs_df.columns:
                for category in ['service', 'product', 'promotion']:
                    category_items = jobs_df[jobs_df['category'] == category]['item'].dropna().unique().tolist()
                    items_by_category[category] = sorted(category_items)
                
                # Convert any 'unknown' category items that match promotion names to promotion category
                promotions_path = get_data_file_path('promotions.json')
                promotion_names = []
                if os.path.exists(promotions_path):
                    try:
                        with open(promotions_path, 'r', encoding='utf-8') as f:
                            promotions_data = json.load(f)
                            promotion_names = [p.get('name') for p in promotions_data if p.get('name')]
                    except Exception as e:
                        logger.error(f"Error reading promotions for history: {e}")
                
                # Update unknown categories to promotion if item name matches
                if promotion_names:
                    mask = jobs_df['item'].isin(promotion_names)
                    jobs_df.loc[mask, 'category'] = 'promotion'
            
            # Convert columns to appropriate types
            for col in ['price', 'quantity', 'cost']:
                if col in jobs_df.columns:
                    jobs_df[col] = pd.to_numeric(jobs_df[col], errors='coerce').fillna(0)
            
            # Parse date column and handle missing dates
            if 'date' in jobs_df.columns:
                try:
                    jobs_df['date'] = pd.to_datetime(jobs_df['date'], errors='coerce')
                    
                    # Fill in missing dates with today's date for display
                    if jobs_df['date'].isna().any():
                        logger.info(f"Found {jobs_df['date'].isna().sum()} jobs with missing dates. Filling with today's date for display.")
                        today = pd.Timestamp(datetime.now().date())
                        jobs_df.loc[jobs_df['date'].isna(), 'date'] = today
                except Exception as e:
                    logger.error(f"Error parsing date: {e}")
            
            # Apply filters
            # Date range filter
            if date_from:
                try:
                    from_date = pd.to_datetime(date_from)
                    jobs_df = jobs_df[jobs_df['date'] >= from_date]
                except Exception as e:
                    print(f"Error filtering by from_date: {e}")
            
            if date_to:
                try:
                    to_date = pd.to_datetime(date_to)
                    jobs_df = jobs_df[jobs_df['date'] <= to_date]
                except Exception as e:
                    print(f"Error filtering by to_date: {e}")
            
            # Customer name filter (exact match for dropdown)
            if customer_filter:
                jobs_df = jobs_df[jobs_df['customer'] == customer_filter]
            
            # Item type filter (service/product)
            if type_filter:
                jobs_df = jobs_df[jobs_df['category'] == type_filter]
            
            # Item name filter (exact match for dropdown)
            if item_filter:
                jobs_df = jobs_df[jobs_df['item'] == item_filter]
            
            # Sort by date (newest first)
            if 'date' in jobs_df.columns:
                jobs_df = jobs_df.sort_values(by='date', ascending=False)
            
            # Calculate totals
            if not jobs_df.empty:
                # Add revenue column
                jobs_df['revenue'] = jobs_df['price'] * jobs_df['quantity']
                
                # Use total_profit from CSV if available, otherwise calculate it
                if 'total_profit' in jobs_df.columns:
                    jobs_df['profit'] = jobs_df['total_profit']
                else:
                    # Calculate profit: (price - cost) * quantity (cost is unit cost)
                    jobs_df['profit'] = (jobs_df['price'] - jobs_df['cost']) * jobs_df['quantity']
                
                total_revenue = jobs_df['revenue'].sum()
                total_profit = jobs_df['profit'].sum()
            
            # Convert datetime columns back to string format for display
            if 'date' in jobs_df.columns:
                if pd.api.types.is_datetime64_any_dtype(jobs_df['date']):
                    # Handle NaT (Not a Time) values by replacing with empty string
                    jobs_df['date'] = jobs_df['date'].dt.strftime('%Y-%m-%d').fillna('')
                else:
                    # If not datetime, ensure no NaN values are displayed
                    jobs_df['date'] = jobs_df['date'].fillna('')
            
            # Convert to list of dictionaries for the template
            jobs = jobs_df.to_dict('records')
    except Exception as e:
        print(f"Error processing jobs data: {e}")
    
    # Format totals for display
    formatted_revenue = format_thai_baht(total_revenue)
    formatted_profit = format_thai_baht(total_profit)
    
    return render_template('history.html', jobs=jobs, filters=filters, 
                          total_revenue=formatted_revenue, total_profit=formatted_profit,
                          available_customers=available_customers, available_items=available_items,
                          items_by_category=items_by_category)

# Route to serve files from data directory
@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

@app.route('/clean-cookies')
def clean_cookies():
    """Clear all cookies for the application"""
    response = redirect(url_for('job'))
    
    # Get list of cookies and remove each one
    cookies = request.cookies
    for key in cookies.keys():
        response.delete_cookie(key)
    
    flash('All cookies have been cleared', 'success')
    return response

@app.route('/api/price-suggestions/<item_name>')
def get_price_suggestions(item_name):
    """Get intelligent price suggestions based on historical data"""
    try:
        jobs_file = get_data_file_path('jobs.csv')
        
        # Read historical data
        df = pd.read_csv(jobs_file)
        
        # Filter data for the specific item
        item_data = df[df['item'].str.lower() == item_name.lower()]
        
        if item_data.empty:
            return jsonify({
                'success': True,
                'suggestions': [],
                'message': 'No historical data available for this item'
            })
        
        # Calculate statistics
        avg_price = item_data['price'].mean()
        min_price = item_data['price'].min()
        max_price = item_data['price'].max()
        avg_cost = item_data['cost'].mean()
        total_sales = len(item_data)
        
        # Calculate suggested promotional prices
        suggestions = []
        
        # Conservative discount (10-15%)
        conservative_price = avg_price * 0.85
        if conservative_price > avg_cost:
            profit_retention = round(((conservative_price - avg_cost) / (avg_price - avg_cost)) * 100, 1)
            suggestions.append({
                'type': 'conservative',
                'price': round(conservative_price, 2),
                'discount_percent': 15,
                'description': 'Safe discount maintaining good profit',
                'explanation': f'Retains {profit_retention}% of original profit while offering attractive 15% discount. Low risk strategy.',
                'profit_margin': round(((conservative_price - avg_cost) / conservative_price) * 100, 1),
                'profit_retention': profit_retention,
                'risk_level': 'Low'
            })
        
        # Moderate discount (20-25%)
        moderate_price = avg_price * 0.75
        if moderate_price > avg_cost:
            profit_retention = round(((moderate_price - avg_cost) / (avg_price - avg_cost)) * 100, 1)
            customer_savings = round(avg_price - moderate_price, 2)
            suggestions.append({
                'type': 'moderate',
                'price': round(moderate_price, 2),
                'discount_percent': 25,
                'description': 'Attractive discount for customer appeal',
                'explanation': f'Customers save ฿{customer_savings} per item. Retains {profit_retention}% profit while being competitive.',
                'profit_margin': round(((moderate_price - avg_cost) / moderate_price) * 100, 1),
                'profit_retention': profit_retention,
                'risk_level': 'Medium'
            })
        
        # Aggressive discount (30-35%)
        aggressive_price = avg_price * 0.65
        if aggressive_price > avg_cost:
            profit_retention = round(((aggressive_price - avg_cost) / (avg_price - avg_cost)) * 100, 1)
            customer_savings = round(avg_price - aggressive_price, 2)
            suggestions.append({
                'type': 'aggressive',
                'price': round(aggressive_price, 2),
                'discount_percent': 35,
                'description': 'High discount for maximum customer attraction',
                'explanation': f'Major ฿{customer_savings} savings per item. {profit_retention}% profit retention. Best for clearing inventory or attracting new customers.',
                'profit_margin': round(((aggressive_price - avg_cost) / aggressive_price) * 100, 1),
                'profit_retention': profit_retention,
                'risk_level': 'High'
            })
        
        # Most popular price (mode)
        if total_sales > 1:
            popular_price = item_data['price'].mode().iloc[0] if not item_data['price'].mode().empty else avg_price
            popular_discount = round((1 - (popular_price * 0.8) / avg_price) * 100)
            if popular_price * 0.8 > avg_cost:
                profit_retention = round(((popular_price * 0.8 - avg_cost) / (popular_price - avg_cost)) * 100, 1)
                frequency = len(item_data[item_data['price'] == popular_price])
                suggestions.append({
                    'type': 'popular',
                    'price': round(popular_price * 0.8, 2),
                    'discount_percent': popular_discount,
                    'description': f'Based on most popular historical price (฿{popular_price})',
                    'explanation': f'This price was used {frequency} times out of {total_sales} sales. Proven customer acceptance with {profit_retention}% profit retention.',
                    'profit_margin': round(((popular_price * 0.8 - avg_cost) / (popular_price * 0.8)) * 100, 1),
                    'profit_retention': profit_retention,
                    'risk_level': 'Low'
                })
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'historical_data': {
                'avg_price': round(avg_price, 2),
                'min_price': round(min_price, 2),
                'max_price': round(max_price, 2),
                'avg_cost': round(avg_cost, 2),
                'total_sales': total_sales
            }
        })
        
    except Exception as e:
        logger.error(f'Error getting price suggestions: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Error analyzing historical data: {str(e)}'
        })

@app.route('/promotion', methods=['GET', 'POST'])
def promotion():
    """Handle promotion creation and display"""
    if request.method == 'GET':
        return render_template('promotion.html')
    
    elif request.method == 'POST':
        try:
            promotion_data = request.get_json()
            
            # Validate required fields
            if not promotion_data.get('name') or not promotion_data.get('promotion'):
                return jsonify({'success': False, 'message': 'Name and promotion items are required'})
            
            # Load existing promotions or create new list
            promotions_file = get_data_file_path('promotions.json')
            try:
                with open(promotions_file, 'r', encoding='utf-8') as f:
                    promotions = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                promotions = []
            
            # Add new promotion with ID
            promotion_data['id'] = len(promotions) + 1
            promotions.append(promotion_data)
            
            # Save to file
            with open(promotions_file, 'w', encoding='utf-8') as f:
                json.dump(promotions, f, indent=2, ensure_ascii=False)
            
            logger.info(f'New promotion created: {promotion_data["name"]}')
            return jsonify({'success': True, 'message': 'Promotion created successfully'})
            
        except Exception as e:
            logger.error(f'Error creating promotion: {str(e)}')
            return jsonify({'success': False, 'message': f'Error creating promotion: {str(e)}'})

@app.route('/api/promotions', methods=['GET'])
def get_promotions():
    """Return all promotions as JSON"""
    try:
        promotions_file = get_data_file_path('promotions.json')
        try:
            with open(promotions_file, 'r', encoding='utf-8') as f:
                promotions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            promotions = []
        
        logger.info(f'Retrieved {len(promotions)} promotions')
        return jsonify({'success': True, 'promotions': promotions})
    
    except Exception as e:
        logger.error(f'Error retrieving promotions: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to retrieve promotions', 'error': str(e)})

@app.route('/api/promotions/<int:promotion_id>', methods=['GET'])
def get_promotion(promotion_id):
    """Return a specific promotion by ID"""
    try:
        promotions_file = get_data_file_path('promotions.json')
        try:
            with open(promotions_file, 'r', encoding='utf-8') as f:
                promotions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            promotions = []
        
        # Find the promotion with the given ID
        promotion = next((p for p in promotions if p.get('id') == promotion_id), None)
        
        if promotion:
            logger.info(f'Retrieved promotion with ID {promotion_id}')
            return jsonify({'success': True, 'promotion': promotion})
        else:
            logger.warning(f'Promotion with ID {promotion_id} not found')
            return jsonify({'success': False, 'message': 'Promotion not found'}), 404
    
    except Exception as e:
        logger.error(f'Error retrieving promotion {promotion_id}: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to retrieve promotion', 'error': str(e)})

@app.route('/api/promotions/<int:promotion_id>', methods=['PUT'])
def update_promotion(promotion_id):
    """Update an existing promotion"""
    try:
        # Get the promotion data from request
        promotion_data = request.get_json()
        
        # Validate required fields
        if not promotion_data.get('name') or not promotion_data.get('promotion'):
            return jsonify({'success': False, 'message': 'Name and promotion items are required'}), 400
        
        # Load existing promotions
        promotions_file = get_data_file_path('promotions.json')
        try:
            with open(promotions_file, 'r', encoding='utf-8') as f:
                promotions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            promotions = []
        
        # Find the promotion with the given ID
        promotion_index = next((i for i, p in enumerate(promotions) if p.get('id') == promotion_id), None)
        
        if promotion_index is None:
            return jsonify({'success': False, 'message': 'Promotion not found'}), 404
        
        # Preserve the ID and update other fields
        promotion_data['id'] = promotion_id
        promotions[promotion_index] = promotion_data
        
        # Save to file
        with open(promotions_file, 'w', encoding='utf-8') as f:
            json.dump(promotions, f, indent=2, ensure_ascii=False)
        
        logger.info(f'Updated promotion with ID {promotion_id}')
        return jsonify({'success': True, 'message': 'Promotion updated successfully'})
    
    except Exception as e:
        logger.error(f'Error updating promotion {promotion_id}: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to update promotion', 'error': str(e)})

@app.route('/api/promotions/<int:promotion_id>', methods=['DELETE'])
def delete_promotion(promotion_id):
    """Delete a promotion by ID"""
    try:
        # Load existing promotions
        promotions_file = get_data_file_path('promotions.json')
        try:
            with open(promotions_file, 'r', encoding='utf-8') as f:
                promotions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            promotions = []
        
        # Find the promotion with the given ID
        promotion_index = next((i for i, p in enumerate(promotions) if p.get('id') == promotion_id), None)
        
        if promotion_index is None:
            return jsonify({'success': False, 'message': 'Promotion not found'}), 404
        
        # Remove the promotion
        removed_promotion = promotions.pop(promotion_index)
        
        # Save to file
        with open(promotions_file, 'w', encoding='utf-8') as f:
            json.dump(promotions, f, indent=2, ensure_ascii=False)
        
        logger.info(f'Deleted promotion with ID {promotion_id}: {removed_promotion["name"]}')
        return jsonify({'success': True, 'message': 'Promotion deleted successfully'})
    
    except Exception as e:
        logger.error(f'Error deleting promotion {promotion_id}: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to delete promotion', 'error': str(e)})

if __name__ == '__main__':
    logger.info('Starting Flask application')
    app.run(host='0.0.0.0', debug=True)