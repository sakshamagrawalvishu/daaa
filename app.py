from flask import Flask, request, jsonify
from flask_cors import CORS
from db import init_db, connect, rows
from algorithms import greedy_rank, knapsack_select, nearest_neighbour_route, two_opt, route_distance, build_graph, dijkstra

app = Flask(__name__)
CORS(app)
init_db()

@app.get('/api/health')
def health():
    return jsonify({'status':'ok','message':'Waste optimizer API is running'})

@app.get('/api/bins')
def get_bins():
    return jsonify(rows('SELECT * FROM bins ORDER BY id'))

@app.post('/api/bins')
def add_bin():
    data = request.get_json(force=True)
    required = ['name','area','lat','lon','waste_kg','priority']
    if any(k not in data for k in required):
        return jsonify({'error':'Missing required fields'}), 400
    with connect() as con:
        cur = con.execute('INSERT INTO bins(name,area,lat,lon,waste_kg,priority,status) VALUES(?,?,?,?,?,?,?)',
            (data['name'],data['area'],float(data['lat']),float(data['lon']),float(data['waste_kg']),int(data['priority']),'Pending'))
        new_id = cur.lastrowid
    return jsonify(next(x for x in rows('SELECT * FROM bins') if x['id']==new_id)), 201

@app.put('/api/bins/<int:bin_id>')
def update_bin(bin_id):
    data = request.get_json(force=True)
    fields = ['name','area','lat','lon','waste_kg','priority','status']
    allowed = {k:data[k] for k in fields if k in data}
    if not allowed: return jsonify({'error':'No fields to update'}), 400
    sql = ','.join(f'{k}=?' for k in allowed)
    with connect() as con:
        cur = con.execute(f'UPDATE bins SET {sql} WHERE id=?', (*allowed.values(),bin_id))
        if cur.rowcount == 0: return jsonify({'error':'Bin not found'}), 404
    return jsonify(next(x for x in rows('SELECT * FROM bins') if x['id']==bin_id))

@app.delete('/api/bins/<int:bin_id>')
def delete_bin(bin_id):
    with connect() as con:
        cur = con.execute('DELETE FROM bins WHERE id=?',(bin_id,))
        if cur.rowcount == 0: return jsonify({'error':'Bin not found'}), 404
    return jsonify({'deleted':bin_id})

@app.get('/api/vehicles')
def get_vehicles():
    return jsonify(rows('SELECT * FROM vehicles ORDER BY id'))

@app.post('/api/vehicles')
def add_vehicle():
    d=request.get_json(force=True)
    required=['name','capacity_kg','lat','lon']
    if any(k not in d for k in required): return jsonify({'error':'Missing required fields'}),400
    with connect() as con:
        cur=con.execute('INSERT INTO vehicles(name,capacity_kg,available,lat,lon) VALUES(?,?,1,?,?)',(d['name'],float(d['capacity_kg']),float(d['lat']),float(d['lon'])))
        vid=cur.lastrowid
    return jsonify(next(x for x in rows('SELECT * FROM vehicles') if x['id']==vid)),201

@app.put('/api/vehicles/<int:vehicle_id>')
def update_vehicle(vehicle_id):
    d=request.get_json(force=True)
    fields=['name','capacity_kg','available','lat','lon']
    allowed={k:d[k] for k in fields if k in d}
    if not allowed:return jsonify({'error':'No fields to update'}),400
    sql=','.join(f'{k}=?' for k in allowed)
    with connect() as con:
        cur=con.execute(f'UPDATE vehicles SET {sql} WHERE id=?',(*allowed.values(),vehicle_id))
        if cur.rowcount==0:return jsonify({'error':'Vehicle not found'}),404
    return jsonify(next(x for x in rows('SELECT * FROM vehicles') if x['id']==vehicle_id))

@app.post('/api/optimize')
def optimize():
    bins = rows("SELECT * FROM bins WHERE status != 'Collected'")
    vehicles = rows('SELECT * FROM vehicles WHERE available=1 ORDER BY id')
    if not bins: return jsonify({'error':'No pending collection points'}),400
    if not vehicles: return jsonify({'error':'No available vehicles'}),400
    ranked = greedy_rank(bins)
    remaining = ranked[:]
    assignments=[]
    all_points = bins[:]
    for v in vehicles:
        if not remaining: break
        # DP chooses a capacity-feasible subset from the highest-priority candidates.
        candidate_pool = remaining[:min(18,len(remaining))]
        selected, score = knapsack_select(candidate_pool, v['capacity_kg'])
        if not selected: continue
        selected_ids={x['id'] for x in selected}
        remaining=[x for x in remaining if x['id'] not in selected_ids]
        point_by_id={x['id']:x for x in all_points}
        point_by_id[v['id'] + 1000000] = {'id':v['id']+1000000,'lat':v['lat'],'lon':v['lon'],'name':v['name']}
        depot=point_by_id[v['id']+1000000]
        route=nearest_neighbour_route(depot,selected,point_by_id)
        before=route_distance(route,point_by_id)
        route=two_opt(route,point_by_id)
        after=route_distance(route,point_by_id)
        # Dijkstra demonstration on the location graph for depot-to-first-stop shortest path.
        graph_points=[depot]+selected
        graph=build_graph(graph_points)
        dijkstra_dist,_=dijkstra(graph,depot['id'])
        route_names=[v['name'] if x==depot['id'] else point_by_id[x]['name'] for x in route]
        assignments.append({'vehicle':v,'bins':selected,'route_ids':route,'route_names':route_names,
            'total_waste_kg':round(sum(x['waste_kg'] for x in selected),1),'capacity_kg':v['capacity_kg'],
            'distance_before_km':round(before,3),'distance_after_km':round(after,3),
            'dp_priority_score':score,'dijkstra_depot_distances':{str(k):round(val,3) for k,val in dijkstra_dist.items() if k!=depot['id']}})
    assigned_ids=[b['id'] for a in assignments for b in a['bins']]
    total_distance=round(sum(a['distance_after_km'] for a in assignments),3)
    total_waste=round(sum(a['total_waste_kg'] for a in assignments),1)
    # Baseline: input-order round trip from each vehicle depot, used only as a transparent comparator.
    baseline=0.0
    for a in assignments:
        v=a['vehicle']; pts=a['bins']; depot={'lat':v['lat'],'lon':v['lon']}
        baseline += sum(__import__('algorithms').haversine(depot if i==0 else pts[i-1], p) for i,p in enumerate(pts))
        if pts: baseline += __import__('algorithms').haversine(pts[-1],depot)
    return jsonify({'assignments':assignments,'summary':{'total_bins':len(bins),'assigned_bins':len(assigned_ids),
        'unassigned_bins':len(bins)-len(assigned_ids),'vehicles_used':len(assignments),'total_waste_kg':total_waste,
        'optimized_distance_km':total_distance,'baseline_distance_km':round(baseline,3),
        'distance_saved_km':round(max(0,baseline-total_distance),3),
        'estimated_fuel_litres_saved':round(max(0,baseline-total_distance)*0.30,2)},
        'unassigned': [b for b in bins if b['id'] not in assigned_ids],
        'methodology':'Greedy ranking + 0/1 DP capacity selection + Dijkstra shortest paths + Nearest Neighbour route construction + 2-opt improvement. Distances are haversine estimates, not live road distances.'})

@app.post('/api/reset-demo')
def reset_demo():
    with connect() as con:
        con.execute("UPDATE bins SET status='Pending'")
    return jsonify({'message':'All bins reset to Pending'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
