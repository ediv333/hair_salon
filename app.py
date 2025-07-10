from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages, send_from_directory
import pandas as pd
import json
import csv
from datetime import datetime
from utils.graph_utils import generate_profit_chart, generate_item_profit_chart, generate_service_profit_chart, generate_daily_revenue_chart
import os
import locale
import sys

# Import the path handling utilities
from path_fix import get_data_path, get_data_file_path

# Set locale for Thai Baht formatting
try:
    locale.setlocale(locale.LC_ALL, 'th_TH.UTF-8')
except:
    pass  # Fallback if locale is not supported

app = Flask(__name__)

# API routes for accessing data files
@app.route('/api/customers')
def api_customers():
    customers_path = get_data_file_path('customers.json')
    print(f"Loading customers from: {customers_path}")
    if os.path.exists(customers_path):
        try:
            with open(customers_path, 'r') as f:
                customers_data = json.load(f)
                print(f"Loaded {len(customers_data)} customers: {[c.get('name', 'Unknown') for c in customers_data]}")
                return customers_data
        except Exception as e:
            print(f"Error loading customers: {e}")
            return []
    else:
        print(f"No customers file found at {customers_path}")
        return []

@app.route('/api/services')
def api_services():
    services_path = get_data_file_path('services.json')
    print(f"Loading services from: {services_path}")
    if os.path.exists(services_path):
        try:
            with open(services_path, 'r') as f:
                services_data = json.load(f)
                print(f"Loaded {len(services_data)} services")
                return services_data
        except Exception as e:
            print(f"Error loading services: {e}")
            return []
    else:
        print(f"No services file found at {services_path}")
        return []

@app.route('/api/inventory')
def api_inventory():
    inventory_path = get_data_file_path('inventory.json')
    print(f"Loading inventory from: {inventory_path}")
    if os.path.exists(inventory_path):
        try:
            with open(inventory_path, 'r') as f:
                inventory_data = json.load(f)
                print(f"Loaded {len(inventory_data)} inventory items")
                return inventory_data
        except Exception as e:
            print(f"Error loading inventory: {e}")
            return []
    else:
        print(f"No inventory file found at {inventory_path}")
        return []

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
    
    # Load jobs data if available
    jobs_path = get_data_file_path('jobs.csv')
    if os.path.exists(jobs_path):
        try:
            # Load jobs data for analysis
            # Debug info
            print(f"Jobs CSV exists: {os.path.exists(jobs_path)}")
            
            # Try to load jobs.csv with different approaches
            try:
                # First attempt: Try with the full column set
                jobs_df = pd.read_csv(jobs_path, header=None, 
                               names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price', 'cost', 'category'])
                print("Loaded with 8 columns")
                
            except Exception as e1:
                print(f"Error loading with 8 columns: {e1}")
                try:
                    # Second attempt: Try with just cost
                    jobs_df = pd.read_csv(jobs_path, header=None, 
                                   names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price', 'cost'])
                    print("Loaded with 7 columns")
                    # Add category column
                    jobs_df['category'] = 'unknown'
                    
                except Exception as e2:
                    print(f"Error loading with 7 columns: {e2}")
                    try:
                        # Third attempt: Try original format
                        jobs_df = pd.read_csv(jobs_path, header=None, 
                                      names=['timestamp', 'date', 'customer', 'item', 'quantity', 'price'])
                        print("Loaded with 6 columns")
                        # Add missing columns
                        jobs_df['cost'] = 0.0
                        jobs_df['category'] = 'unknown'
                        
                    except Exception as e3:
                        print(f"Failed to load jobs.csv: {e3}")
                        # Create empty dataframe with needed columns
                        jobs_df = pd.DataFrame(columns=['timestamp', 'date', 'customer', 'item', 'quantity', 'price', 'cost', 'category'])
            
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
                    with open(services_path, 'r') as f:
                        services = json.load(f)
                inventory_path = get_data_file_path('inventory.json')
                if os.path.exists(inventory_path):
                    with open(inventory_path, 'r') as f:
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
                        
                        # Calculate profit (revenue - cost)
                        if 'cost' in jobs_df.columns:
                            jobs_df['profit'] = jobs_df['revenue'] - jobs_df['cost']
                        else:
                            jobs_df['cost'] = 0
                            jobs_df['profit'] = jobs_df['revenue']
                        
                        # Calculate summary metrics
                        total_revenue = jobs_df['revenue'].sum()
                        total_cost = jobs_df['cost'].sum() if 'cost' in jobs_df.columns else 0
                        net_profit = total_revenue - total_cost
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
                          last_updated=last_updated,
                          report_title=report_title)

@app.route('/simulator')
def simulator():
    """Pricing simulator to help optimize profit based on historical data"""
    # Default values
    items_data = []
    last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
    
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
                jobs_df['profit'] = jobs_df['revenue'] - (jobs_df['cost'] * jobs_df['quantity'])
                
                # Group by item
                item_metrics = jobs_df.groupby('item').agg({
                    'quantity': 'sum',
                    'revenue': 'sum',
                    'profit': 'sum',
                    'price': 'mean',
                    'cost': 'mean'
                }).reset_index()
                
                # Calculate profit margin and potential optimizations
                item_metrics['profit_margin'] = (item_metrics['profit'] / item_metrics['revenue'] * 100).round(2)
                
                # Calculate potential price increases (5%, 10%, 15%)
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
                
                # Convert to list of dicts for template
                items_data = item_metrics.to_dict('records')
                
                # Sort by potential profit increase (10% scenario)
                items_data = sorted(items_data, key=lambda x: x.get('profit_increase_10pct', 0), reverse=True)
                
                # Format currency values for display
                for item in items_data:
                    for key in item:
                        if key in ['price', 'cost'] or 'price_' in key:
                            item[key] = f'฿{item[key]:,.0f}'
                        elif any(term in key for term in ['revenue', 'profit']):
                            item[key] = f'฿{item[key]:,.2f}'
        
        except Exception as e:
            print(f"Error in simulator calculations: {e}")
    
    return render_template('simulator.html', 
                           items_data=items_data,
                           last_updated=last_updated)

@app.route('/customers', methods=['GET', 'POST'])
def customers():
    path = get_data_file_path('customers.json')
    _customers = []
    if os.path.exists(path):
        # Load customers
        with open(path, 'r') as f:
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
        with open(path, 'w') as f:
            json.dump(_customers, f, indent=2)
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
        with open(path, 'r') as f:
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
        with open(path, 'w') as f:
            json.dump(_services, f, indent=2)
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
    search_customer = request.args.get('search_customer', '').strip().lower()
    
    # Load jobs data for search results
    try:
        jobs_path = get_data_file_path('jobs.csv')
        if os.path.exists(jobs_path):
            # Get existing job data
            jobs_df = pd.read_csv(jobs_path)
            
            # Convert price, quantity, and cost columns to numeric values
            if not jobs_df.empty:
                for col in ['price', 'quantity', 'cost']:
                    if col in jobs_df.columns:
                        jobs_df[col] = pd.to_numeric(jobs_df[col], errors='coerce').fillna(0)
            
            # Apply search filter if provided
            if search_customer:
                # Filter jobs by customer name containing the search term
                jobs_df = jobs_df[jobs_df['customer'].str.lower().str.contains(search_customer, na=False)]
            
            # Make sure the timestamp column is in datetime format for proper sorting
            if 'timestamp' in jobs_df.columns:
                try:
                    jobs_df['timestamp'] = pd.to_datetime(jobs_df['timestamp'], errors='coerce')
                except:
                    pass
            
            # Sort by timestamp in descending order (newest first)
            jobs_df = jobs_df.sort_values(by='timestamp', ascending=False)
            
            # Convert to list of dictionaries for the template
            jobs = jobs_df.to_dict('records')
    except Exception as e:
        print(f"Error loading jobs data: {e}")
    
    # Prevent use if services.json or inventory.json is missing
    services_path = get_data_file_path('services.json')
    inventory_path = get_data_file_path('inventory.json')
    if not (os.path.exists(services_path) and os.path.exists(inventory_path)):
        # Remove flash, just render with disable_form
        return render_template('job.html', disable_form=True, jobs=jobs, search_customer=search_customer)

    _customers = [ {
        "name": "dummy",
        "phone": '',
        "birthday": '',
        "note": ""
      }]
    customers_path = get_data_file_path('customers.json')
    if os.path.exists(customers_path):
        with open(customers_path, 'r') as f:
            _customers = json.load(f)
    services_path = get_data_file_path('services.json')
    with open(services_path, 'r') as f:
        services = json.load(f)
    inventory_path = get_data_file_path('inventory.json')
    with open(inventory_path, 'r') as f:
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
        
        # Determine item category (service or product)
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
        
        # If no jobs.csv file exists, create it with headers
        jobs_path = get_data_file_path('jobs.csv')
        if not os.path.exists(jobs_path):
            # Ensure data directory exists
            data_dir = get_data_path()
            with open(jobs_path, 'w', newline='') as f:
                csv.writer(f).writerow(['timestamp', 'date', 'customer', 'item', 'quantity', 'price', 'cost', 'category'])

        # Append the new job
        with open(jobs_path, 'a', newline='') as f:
            csv.writer(f).writerow([datetime.now().isoformat(), date, customer, item_name, quantity, price, total_cost, item_category])

        for item in inventory:
            if item['name'] == item_name:
                try:
                    item['current_quantity'] = int(item.get('current_quantity', 0)) - quantity
                    item['last_date_sell'] = date
                except Exception:
                    pass
                break
        inventory_path = get_data_file_path('inventory.json')
        with open(inventory_path, 'w') as f:
            json.dump(inventory, f, indent=2)
        # Redirect to job route - load jobs again to show updated data
        return redirect(url_for('job'))

    # No need to duplicate data in static folder
    return render_template('job.html', disable_form=False, jobs=jobs, search_customer=search_customer)

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    path = get_data_file_path('inventory.json')
    try:
        with open(path, 'r') as f:
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
        with open(path, 'w') as f:
            json.dump(inventory, f, indent=2)
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

# Route to serve files from data directory
@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

if __name__ == '__main__':
    app.run(debug=True)