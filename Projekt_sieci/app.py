from flask import Flask, render_template, request, url_for
import sqlite3
import hypernetx as hynx
import matplotlib
matplotlib.use('Agg')  # Ustawienie backendu bez GUI
import matplotlib.pyplot as plt
import os

# Tworzenie instancji aplikacji Flask
app = Flask(__name__)

# Ścieżka do bazy danych
DATABASE = 'smoke_data.db'

# Funkcja do połączenia z bazą danych
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Funkcja do czyszczenia wygenerowanego grafu
def clear_hypergraph_image():
    image_path = os.path.join('static', 'hypergraph.png')
    if os.path.exists(image_path):
        os.remove(image_path)




# Strona główna
@app.route('/')
def home():
    return render_template('index.html')

# Endpoint do wyświetlania danych z czujników
@app.route('/sensor_data')
def sensor_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM smoke_data')
    data = cursor.fetchall()
    conn.close()

    # Konwersja wartości "Fire Alarm" na czytelny format
    formatted_data = []
    for row in data:
        formatted_row = dict(row)
        formatted_row['Fire Alarm'] = 'Yes' if formatted_row['Fire Alarm'] == 1 else 'No'
        formatted_data.append(formatted_row)

    return render_template('sensor_data.html', data=formatted_data)

# Endpoint do generowania i wyświetlania hipergrafu
@app.route('/hypergraph', methods=['GET', 'POST'])
def hypergraph():
    if request.method == 'POST':
        # Obsługa przycisku "Wyczyść filtry"
        if request.form.get('clear_filters'):
            clear_hypergraph_image()
            return render_template('hypergraph.html', image_path=None, devices_by_edge=None, node_attributes=None)

        # Obsługa generowania grafu
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM smoke_data')
        rows = cursor.fetchall()
        conn.close()

        # Pobieranie wartości filtrów z formularza
        filter_fire_alarm = request.form.get('filter_fire_alarm')
        min_temp = request.form.get('min_temp', type=float)
        max_temp = request.form.get('max_temp', type=float)
        min_smoke_level = request.form.get('min_smoke_level', type=int)
        max_smoke_level = request.form.get('max_smoke_level', type=int)
        min_tvoc = request.form.get('min_tvoc', type=int)
        max_tvoc = request.form.get('max_tvoc', type=int)
        locations_to_connect = request.form.get('locations_to_connect')

        # Tworzenie danych dla hipergrafu
        edges = {}
        devices_by_edge = {}
        temp_edge = set()
        smoke_level_edge = set()
        tvoc_edge = set()
        connected_locations_edge = set()
        node_attributes = {}

        selected_locations = None
        if locations_to_connect:
            selected_locations = [loc.strip() for loc in locations_to_connect.split(',')]

        for row in rows:
            location = row['Location']
            node_id = row['ID_smokedetector']
            temperature = row['Temperature[C]']
            smoke_level = row['Smoke_Level']
            tvoc = row['TVOC[ppb]']

            # Filtracja urządzeń na podstawie wartości Fire Alarm
            if filter_fire_alarm == '1' and row['Fire Alarm'] != 1:
                continue

            # Filtracja urządzeń na podstawie lokalizacji
            if selected_locations and location not in selected_locations:
                continue

            # Dodawanie urządzenia do krawędzi temperatury, jeśli spełnia zakres
            if min_temp is not None and max_temp is not None:
                if min_temp <= temperature <= max_temp:
                    temp_edge.add(node_id)

            # Dodawanie urządzenia do krawędzi smoke level, jeśli spełnia zakres
            if min_smoke_level is not None and max_smoke_level is not None:
                if min_smoke_level <= smoke_level <= max_smoke_level:
                    smoke_level_edge.add(node_id)

            # Dodawanie urządzenia do krawędzi TVOC, jeśli spełnia zakres
            if min_tvoc is not None and max_tvoc is not None:
                if min_tvoc <= tvoc <= max_tvoc:
                    tvoc_edge.add(node_id)

            # Dodawanie urządzenia do lokalizacji
            if location not in edges:
                edges[location] = set()
                devices_by_edge[location] = []
            edges[location].add(node_id)
            devices_by_edge[location].append({
                'ID': node_id,
                'Temperature': temperature,
                'Humidity': row['Humidity[%]'],
                'Battery_Level': row['Battery_Level'],
                'Smoke_Level': smoke_level,
                'TVOC': tvoc,
                'Fire_Alarm': 'Yes' if row['Fire Alarm'] == 1 else 'No'
            })

            # Dodawanie urządzenia do krawędzi połączonych lokalizacji
            if selected_locations and location in selected_locations:
                connected_locations_edge.add(node_id)

            # Zapisywanie atrybutów wierzchołka
            node_attributes[node_id] = {
                'ID': node_id,
                'Location': location,
                'Temperature': temperature,
                'Humidity': row['Humidity[%]'],
                'Battery_Level': row['Battery_Level'],
                'Smoke_Level': smoke_level,
                'TVOC': tvoc,
                'Fire_Alarm': 'Yes' if row['Fire Alarm'] == 1 else 'No'
            }

        # Dodawanie krawędzi dla filtrów do hipergrafu
        if temp_edge:
            edges[f"Temperature [{min_temp}-{max_temp}]"] = temp_edge
        if smoke_level_edge:
            edges[f"Smoke Level [{min_smoke_level}-{max_smoke_level}]"] = smoke_level_edge
        if tvoc_edge:
            edges[f"TVOC [{min_tvoc}-{max_tvoc}]"] = tvoc_edge
        if connected_locations_edge:
            edges[", ".join(selected_locations)] = connected_locations_edge

        # Tworzenie hipergrafu
        H = hynx.Hypergraph(edges)

        # Rysowanie hipergrafu i zapisywanie jako obraz
        clear_hypergraph_image()  # Usuwamy stary graf przed zapisaniem nowego
        plt.figure(figsize=(14, 10))
        hynx.drawing.draw(H, with_node_labels=True)
        image_path = os.path.join('static', 'hypergraph.png')
        plt.savefig(image_path)
        plt.close()

        return render_template(
            'hypergraph.html',
            image_path=url_for('static', filename='hypergraph.png'),
            devices_by_edge=devices_by_edge,
            node_attributes=node_attributes,
            filter_fire_alarm=filter_fire_alarm,
            min_temp=min_temp,
            max_temp=max_temp,
            min_smoke_level=min_smoke_level,
            max_smoke_level=max_smoke_level,
            min_tvoc=min_tvoc,
            max_tvoc=max_tvoc,
            locations_to_connect=locations_to_connect
        )

    # Domyślny przypadek bez filtrów
    clear_hypergraph_image()
    return render_template('hypergraph.html', image_path=None, devices_by_edge=None, node_attributes=None)

if __name__ == '__main__':
    app.run(debug=True)
