from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
import pandas as pd
import json
import csv
from datetime import datetime
from utils.graph_utils import generate_profit_chart, generate_item_profit_chart, generate_service_profit_chart, generate_daily_revenue_chart
import os

app = Flask(__name__)

@app.route('/')
def analyst():
    chart = None
    report_type = request.args.get('report_type', 'total_profit')
    
    if os.path.exists('data/jobs.csv'):
        if report_type == 'total_profit':
            chart = generate_daily_revenue_chart()  # Change to daily_revenue_chart function
        elif report_type == 'profit_per_item':
            chart = generate_item_profit_chart()
        elif report_type == 'profit_per_service':
            chart = generate_service_profit_chart()
    
    return render_template('analyst.html', chart=chart, report_type=report_type)

@app.route('/customers', methods=['GET', 'POST'])
def customers():
    path = 'data/customers.json'
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
    path = 'data/services.json'
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
    # Prevent use if services.json or inventory.json is missing
    if not (os.path.exists('data/services.json') and os.path.exists('data/inventory.json')):
        # Remove flash, just render with disable_form
        return render_template('job.html', disable_form=True)

    _customers = [ {
        "name": "dummy",
        "phone": '',
        "birthday": '',
        "note": ""
      }]
    if os.path.exists('data/customers.json'):  # Fix: Changed customers.csv to customers.json
        with open('data/customers.json', 'r') as f:
            _customers = json.load(f)
    with open('data/services.json', 'r') as f:
        services = json.load(f)
    with open('data/inventory.json', 'r') as f:
        inventory = json.load(f)
    if request.method == 'POST':
        date = request.form.get('date')
        customer = request.form.get('customer')
        item_name = request.form.get('item')
        quantity = int(request.form.get('quantity', 1))
        price = float(request.form.get('price', 0))

        if not item_name:
            flash('Please select an item.', 'error')
            return redirect(url_for('job'))

        with open('data/jobs.csv', 'a', newline='') as f:
            csv.writer(f).writerow([datetime.now().isoformat(), date, customer, item_name, quantity, price])

        for item in inventory:
            if item['name'] == item_name:
                try:
                    item['current_quantity'] = int(item.get('current_quantity', 0)) - quantity
                    item['last_date_sell'] = date
                except Exception:
                    pass
                break
        with open('data/inventory.json', 'w') as f:
            json.dump(inventory, f, indent=2)
        return redirect(url_for('job'))

    with open('static/customers.json', 'w') as f:
        json.dump(_customers, f)
    with open('static/services.json', 'w') as f:
        json.dump(services, f)
    with open('static/inventory.json', 'w') as f:
        json.dump(inventory, f)
    return render_template('job.html')

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    path = 'data/inventory.json'
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


if __name__ == '__main__':
    app.run(debug=True)