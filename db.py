import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name('waste.db')

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS bins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            area TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            waste_kg REAL NOT NULL,
            priority INTEGER NOT NULL DEFAULT 3,
            status TEXT NOT NULL DEFAULT 'Pending'
        );
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            capacity_kg REAL NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        );
        ''')
        if con.execute('SELECT COUNT(*) FROM bins').fetchone()[0] == 0:
            bins = [
                ('B1 Chowk','Manipal University Jaipur',26.8437,75.5652,65,5,'Pending'),
                ('Main Gate','Manipal University Jaipur',26.8430,75.5659,42,4,'Pending'),
                ('Hostel Block A','Manipal University Jaipur',26.8450,75.5671,80,5,'Pending'),
                ('Academic Block','Manipal University Jaipur',26.8420,75.5680,35,3,'Pending'),
                ('Food Court','Manipal University Jaipur',26.8416,75.5642,55,4,'Pending'),
                ('Sports Complex','Manipal University Jaipur',26.8461,75.5638,28,2,'Pending'),
                ('Parking Area','Manipal University Jaipur',26.8409,75.5670,47,3,'Pending'),
                ('Library','Manipal University Jaipur',26.8434,75.5690,32,2,'Pending'),
                ('Hostel Block C','Manipal University Jaipur',26.8460,75.5660,70,5,'Pending'),
                ('Auditorium','Manipal University Jaipur',26.8428,75.5629,24,2,'Pending')]
            con.executemany('INSERT INTO bins(name,area,lat,lon,waste_kg,priority,status) VALUES(?,?,?,?,?,?,?)', bins)
        if con.execute('SELECT COUNT(*) FROM vehicles').fetchone()[0] == 0:
            vehicles = [('Truck 01',180,1,26.8437,75.5652),('Truck 02',150,1,26.8437,75.5652),('Truck 03',120,1,26.8437,75.5652)]
            con.executemany('INSERT INTO vehicles(name,capacity_kg,available,lat,lon) VALUES(?,?,?,?,?)', vehicles)

def rows(query, params=()):
    with connect() as con:
        return [dict(r) for r in con.execute(query, params).fetchall()]
