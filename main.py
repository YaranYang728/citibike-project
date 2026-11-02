"""Run the fixed Midtown case without rerunning historical demand prediction."""
import argparse
import csv
import hashlib
import json
from data_preprocessing import build_problem_dataset, load_depots, project_path
from optimization_model import solve_citi_bike_rebalancing
from solution_checks import check_solution
from plot_routes import plot_rebalancing_solution


def main():
    parser = argparse.ArgumentParser(description='Citi Bike Midtown — fixed 2026-10-28 inventory, Gurobi MILP')
    parser.add_argument('--inputs', default='outputs_stage6/model_station_inputs.json')
    parser.add_argument('--depots', default='outputs_stage7/selected_depots.json')
    parser.add_argument('--truck_capacity', '-Q', type=int, default=25)
    parser.add_argument('--max_dist', '-w', type=float, default=25.0)
    parser.add_argument('--alpha', type=float, default=1.5)
    parser.add_argument('--beta', type=float, default=5.0)
    parser.add_argument('--time_limit', type=float, default=120)
    parser.add_argument('--output', default='outputs_stage8')
    parser.add_argument('--no-map', action='store_true')
    parser.add_argument('--no-basemap', action='store_true', help='Plot without online map tiles.')
    args = parser.parse_args()
    if args.truck_capacity <= 0 or args.max_dist <= 0 or args.time_limit <= 0 or args.alpha < 0 or args.beta <= 0:
        parser.error('Capacity, distance, time limit and beta must be positive; alpha must be nonnegative.')
    data = build_problem_dataset(args.inputs)
    depots = load_depots(args.depots)
    out = project_path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    stations = data['stations']
    print(f'Midtown: {len(stations)} retained stations; case {stations[0]["case_date"]}')
    print(f'Initial bikes: {sum(s["I0"] for s in stations)}; target bikes: {sum(s["I_star"] for s in stations)}')
    solution = solve_citi_bike_rebalancing(
        data, depots, truck_capacity=args.truck_capacity,
        max_distance_w=args.max_dist, alpha=args.alpha, beta=args.beta,
        time_limit=args.time_limit, output_dir=str(out))
    audit = check_solution(data, depots, solution, args.truck_capacity, args.max_dist, args.alpha, args.beta)
    solution['validation'] = audit
    solution['case_date'] = stations[0]['case_date']
    solution['input_sha256'] = hashlib.sha256(project_path(args.inputs).read_bytes()).hexdigest()
    solution['depot_sha256'] = hashlib.sha256(project_path(args.depots).read_bytes()).hexdigest()
    solution['summary'] = {'total_cost': solution['objective'],
                           'transport_cost': args.alpha * solution['total_distance_km'],
                           'penalty_cost': args.beta * solution['total_mismatch'],
                           'total_unmet_bikes': solution['total_mismatch']}
    (out / 'solution.json').write_text(json.dumps(solution, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'station_results.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(solution['station_results'][0]))
        writer.writeheader(); writer.writerows(solution['station_results'])
    with (out / 'route_stops.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['truck', 'order', 'station_id', 'name', 'net_delivery', 'load_after'])
        names = {s['id']: s['name'] for s in stations}
        for truck, route in solution['routes'].items():
            print(f'\n{truck}: {route["distance_km"]:.3f} km')
            for order, node in enumerate(route['path']):
                name = names.get(node, node)
                transfer = route['transfers'].get(node, 0)
                load = route['loads'].get(node, 0)
                writer.writerow([truck, order, node, name, transfer, load])
                print(f'  {order}. {name}: transfer {transfer:+d}, load {load:g}/{args.truck_capacity}')
    print(json.dumps({key: solution[key] for key in ['solver', 'status', 'runtime_seconds', 'gap', 'objective', 'validation']}, indent=2))
    print('Time-limited feasible results are candidate solutions, not proven optimal.')
    if not args.no_map:
        plot_rebalancing_solution(data, depots, solution, out / 'routes.png', basemap=not args.no_basemap)
    print(f'Results saved to {out}')


if __name__ == '__main__':
    main()
