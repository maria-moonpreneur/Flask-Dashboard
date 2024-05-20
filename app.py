import base64
import datetime
import io
from flask import Flask, jsonify, redirect, render_template, request, url_for
import csv
from matplotlib import pyplot as plt
import matplotlib
import mysql.connector

matplotlib.use('Agg')

app = Flask(__name__)

# MySQL connection
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="maria@123",
    database="flask"
)

users = {
    'user1': 'password1',
    'user2': 'password2'
}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            #return redirect(url_for('upload.html'))
            return render_template('upload.html')
        else:
            error_message = 'Invalid username or password'
            return render_template('login.html', error_message=error_message, alert=True)

    return render_template('login.html', error_message=None)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return 'No file part'

    file = request.files['file']
    num_columns = int(request.form['num_columns'])
    column_names = [request.form[f'column_name_{i}'] for i in range(num_columns)]
    column_types = [request.form[f'column_type_{i}'] for i in range(num_columns)]

    if file.filename == '':
        return 'No selected file'

    if file:
        # Read CSV data and remove BOM if present
        csv_data = file.read().decode('utf-8-sig').splitlines()

        cursor = mydb.cursor()

        # Drop table if exists
        drop_table_query = "DROP TABLE IF EXISTS csv_data"
        try:
            cursor.execute(drop_table_query)
        except mysql.connector.Error as err:
            return f"Error dropping table: {err}"

        # Construct CREATE TABLE query dynamically with user-entered data types
        create_table_query = f"CREATE TABLE csv_data (id INT AUTO_INCREMENT PRIMARY KEY, {', '.join([f'`{column_names[i]}` {column_types[i]}' for i in range(num_columns)])})"
        print("CREATE TABLE QUERY:", create_table_query)  # Print the generated query
        try:
            cursor.execute(create_table_query)
        except mysql.connector.Error as err:
            return f"Error creating table: {err}"

        # Iterate over CSV data starting from the second row
        for row in csv.reader(csv_data[1:]):
            for i, col_type in enumerate(column_types):
                if col_type.lower() == 'date':
                    # Convert the date string to MySQL-compatible format manually
                    date_parts = row[i].split('-')
                    if len(date_parts) == 3:
                        try:
                            day = int(date_parts[0])
                            month = int(date_parts[1])
                            year = int(date_parts[2])
                            row[i] = f"{year:04d}-{month:02d}-{day:02d}"
                        except ValueError:
                            return 'Invalid date format. Date format should be DD-MM-YYYY.'

            # Construct INSERT INTO query dynamically
            insert_query = f"INSERT INTO csv_data ({', '.join([f'`{column_names[i]}`' for i in range(num_columns)])}) VALUES ({', '.join(['%s'] * num_columns)})"
            try:
                cursor.execute(insert_query, row)
            except mysql.connector.Error as err:
                return f"Error inserting data into table: {err}"

        mydb.commit()
        cursor.close()

        return redirect(url_for('display'))

@app.route('/display', methods=['GET'])
def display():
    cursor = mydb.cursor(dictionary=True)  # Set dictionary=True to fetch rows as dictionaries

    try:
        cursor.execute("SELECT * FROM csv_data")
        data = cursor.fetchall()  # Fetch all rows from the table
        column_names = cursor.column_names  # Get column names
    except mysql.connector.Error as err:
        return f"Error retrieving data from table: {err}"
    finally:
        cursor.close()

    return render_template('display.html', data=data, column_names=column_names)

@app.route('/bar_chart', methods=['POST', 'GET'])
def bar_chart():
    cursor = mydb.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM csv_data")
        data = cursor.fetchall()
        column_names = cursor.column_names
    except mysql.connector.Error as err:
        return f"Error retrieving data from table: {err}"
    finally:
        cursor.close()

    if request.method == 'POST':
        selected_column1 = request.form['column1']
        selected_column2 = request.form['column2']

        # Extract the data for the selected columns
        column1_data = [row[selected_column1] for row in data]
        column2_data = [row[selected_column2] for row in data]

        # Create a bar chart
        plt.figure(figsize=(10, 6))
        plt.bar(column1_data, column2_data)
        plt.xlabel(selected_column1)
        plt.ylabel(selected_column2)
        plt.title(f'Bar Chart of {selected_column2} by {selected_column1}')
        plt.xticks(rotation=45)  # Rotate x-axis labels for better readability
        plt.tight_layout()

        # Save the plot to a buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()

        # Encode the plot image to base64
        graph = base64.b64encode(image_png).decode('utf-8')
        graph_url = f'data:image/png;base64,{graph}'

        return render_template('bar_chart.html', graph_url=graph_url)

    return redirect(url_for('bar_chart'))


@app.route('/options', methods=['GET', 'POST'])
def options():
    cursor = mydb.cursor()    
    try:
        cursor.execute("SHOW COLUMNS FROM csv_data")  # Assuming 'csv_data' is your table name
        column_names = [column[0] for column in cursor.fetchall()]  # Fetch all column names
    except mysql.connector.Error as err:
        return f"Error retrieving column names from the database: {err}"
    finally:
        cursor.close()

    if request.method == 'POST':
        selected_column1 = request.form['column1']
        selected_column2 = request.form['column2']

        # For now, let's just render the bar chart template with the selected columns
        return redirect(url_for('bar_chart', column1=selected_column1, column2=selected_column2))

    # If method is GET, simply render the options form with the fetched column names
    return render_template('options.html', column_names=column_names)

@app.route('/poptions', methods=['GET', 'POST'])
def poptions():
    cursor = mydb.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM csv_data")  # Assuming 'csv_data' is your table name
        column_names = [column[0] for column in cursor.fetchall()]  # Fetch all column names
    except mysql.connector.Error as err:
        return f"Error retrieving column names from the database: {err}"
    finally:
        cursor.close()

    if request.method == 'POST':
        selected_column = request.form['column']
        if selected_column:
            return redirect(url_for('pie_chart', column=selected_column))
        else:
            return "Please select a column"
    return render_template('poptions.html', column_names=column_names)


@app.route('/pie_chart', methods=['GET', 'POST'])
def pie_chart():
    if request.method == 'POST':
        selected_column = request.form['column']
    # selected_column = request.args.get('column')
    # if not selected_column:
    #     return "No column selected"    
        
    cursor = mydb.cursor()
    try:
        cursor.execute(f"SELECT `{selected_column}`, COUNT(*) FROM csv_data GROUP BY `{selected_column}`")
        data = cursor.fetchall()  # Fetch all rows
    except mysql.connector.Error as err:
        return f"Error retrieving data for selected column from the database: {err}"
    finally:
        cursor.close()

    # Prepare data for pie chart
    labels = [row[0] for row in data]
    counts = [row[1] for row in data]

    # Create the pie chart
    plt.figure(figsize=(8, 8))
    plt.pie(counts, labels=labels, autopct='%1.1f%%', startangle=140)
    plt.title(f'Pie Chart of {selected_column}')
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.tight_layout()

    # Save the plot to a buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()

    # Encode the plot image to base64
    graph = base64.b64encode(image_png).decode('utf-8')
    graph_url = f'data:image/png;base64,{graph}'

    return render_template('pie_chart.html', graph_url=graph_url)

@app.route('/soptions', methods=['GET', 'POST'])
def soptions():
    cursor = mydb.cursor()
    try:
        cursor.execute("SHOW COLUMNS FROM csv_data")  # Assuming 'csv_data' is your table name
        column_names = [column[0] for column in cursor.fetchall()]  # Fetch all column names
    except mysql.connector.Error as err:
        return f"Error retrieving column names from the database: {err}"
    finally:
        cursor.close()

    if request.method == 'POST':
        selected_column1 = request.form['column1']
        selected_column2 = request.form['column2']
        if selected_column1 and selected_column2:
            return redirect(url_for('scatter_plot', column1=selected_column1, column2=selected_column2))
        else:
            return "Please select columns for both X and Y axes"
    return render_template('soptions.html', column_names=column_names)

@app.route('/scatter_plot', methods=['POST', 'GET'])
def scatter_plot():
    cursor = mydb.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM csv_data")
        data = cursor.fetchall()
        column_names = cursor.column_names
    except mysql.connector.Error as err:
        return f"Error retrieving data from table: {err}"
    finally:
        cursor.close()

    if request.method == 'POST':
        selected_column1 = request.form['column1']
        selected_column2 = request.form['column2']

        # Extract the data for the selected columns
        column1_data = [row[selected_column1] for row in data]
        column2_data = [row[selected_column2] for row in data]

        # Create a scatter plot
        plt.figure(figsize=(10, 6))
        plt.scatter(column1_data, column2_data)
        plt.xlabel(selected_column1)
        plt.ylabel(selected_column2)
        plt.title(f'Scatter Plot of {selected_column2} vs {selected_column1}')
        plt.tight_layout()

        # Save the plot to a buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()

        # Encode the plot image to base64
        graph = base64.b64encode(image_png).decode('utf-8')
        graph_url = f'data:image/png;base64,{graph}'

        return render_template('scatter_plot.html', graph_url=graph_url)

    return redirect(url_for('scatter_plot'))

if __name__ == '__main__':
    app.run(debug=True)