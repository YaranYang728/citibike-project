"""Independent checks on the exported routes, inventories and objective."""
from data_preprocessing import latlon_to_km


def check_solution(data, depots, solution, capacity, max_distance, alpha, beta):
    stations = {s['id']: s for s in data['stations']}
    visited = set()
    deliveries = dict.fromkeys(stations, 0)
    distance = 0.0
    for depot in depots:
        truck = depot['truck_id']
        home = f'depot_{truck}'
        route = solution['routes'][truck]
        path = route['path']
        if len(path) <= 1:
            assert not route['transfers'], 'Inactive truck has transfers.'
            continue
        assert path[0] == path[-1] == home, 'Route must return to its own depot.'
        coords = {sid: (s['lat'], s['lon']) for sid, s in stations.items()}
        coords[home] = (depot['lat'], depot['lon'])
        load = 0
        for node in path[1:-1]:
            assert node in stations and node not in visited, 'Unknown or repeatedly visited station.'
            visited.add(node)
            quantity = route['transfers'].get(node, 0)
            assert abs(quantity - round(quantity)) < 1e-5
            deliveries[node] += round(quantity)
            load -= quantity
            assert -1e-5 <= load <= capacity + 1e-5, 'Truck capacity violation.'
            assert abs(load - route['loads'][node]) < 1e-5, 'Inconsistent exported load.'
        assert abs(load) < 1e-5, 'Truck must return empty.'
        length = sum(latlon_to_km(*coords[a], *coords[b]) for a, b in zip(path, path[1:]))
        assert length <= max_distance + 1e-5, 'Distance budget violation.'
        assert abs(length - route['distance_km']) < 1e-5
        distance += length
    expected = {}
    for sid, station in stations.items():
        final = station['I0'] + deliveries[sid]
        assert 0 <= final <= station['C'], 'Station capacity violation.'
        expected[sid] = (final, abs(final - station['I_star']))
    exported = {r['id']: r for r in solution['station_results']}
    assert set(exported) == set(stations)
    for sid, (final, mismatch) in expected.items():
        assert exported[sid]['final_inventory'] == final
        assert exported[sid]['mismatch'] == mismatch
        assert exported[sid]['target'] == stations[sid]['I_star']
    mismatch = sum(m for _, m in expected.values())
    assert sum(deliveries.values()) == 0
    assert mismatch == solution['total_mismatch']
    assert abs(distance - solution['total_distance_km']) < 1e-5
    assert abs(alpha * distance + beta * mismatch - solution['objective']) < 1e-4
    assert abs(solution['objective'] - solution['solver_objective']) < 1e-4
    return {'passed': True, 'visited_stations': len(visited),
            'bikes_moved': sum(max(q, 0) for q in deliveries.values()),
            'total_distance_km': distance, 'total_mismatch': mismatch}
