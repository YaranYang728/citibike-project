# Citi Bike Overnight Rebalancing — Midtown Manhattan

A reproducible, fixed-data case for IEOR 4004 Milestone 4. The command-line entry point reads the prepared inputs, solves a MILP with **Gurobi only**, validates the candidate solution, and exports routes and a map. It does not rerun demand prediction or fetch live inventory.

## Quick start

Use Python 3.11 or newer and a valid Gurobi license that permits this model size. The bundled pip package alone provides only a size-limited license. Install your academic license locally; do **not** upload `gurobi.lic` to GitHub. Gurobi's standard license search or an existing `GRB_LICENSE_FILE` setting is respected.

From the extracted project directory:

```bash
python -m pip install -r requirements.txt
python main.py
```

On macOS, use `python3` if `python` is unavailable. Alternatively, open **run_model.ipynb** in Jupyter to run the same command with your notebook's Python environment. Open **citibike_static_demand.ipynb** to inspect the full English research workflow; its earlier forecasting stages do not need to run before `main.py`.

The script resolves inputs relative to its own location, so starting it from another working directory is supported:

```bash
python /path/to/project/main.py
```

Default parameters: two trucks, capacity 25 bikes each, distance budget 25 km per truck, alpha = 1.5 per km, beta = 5 per bike of **absolute inventory target mismatch**, and Gurobi optimization time limit 120 seconds. Building the model and constructing/validating its warm start take additional time. These operating parameters are scenario assumptions, not verified Citi Bike practice.

```bash
python main.py --time_limit 600
python main.py --no-basemap
python main.py --no-map
```

`--no-basemap` keeps the route drawing without online map tiles. `--no-map` skips map generation. Other options: `--inputs`, `--depots`, `--output`, `--truck_capacity`, `--max_dist`, `--alpha`, `--beta`. Old random-sampling and live-trip CLI options have been removed deliberately.

## Fixed input case

- Area: all **166 retained historical station IDs** in the audited Midtown subset. This is not a 12-station sample and is not a claim that all current physical Midtown stations are covered.
- Initial inventory: **2026-10-28 midnight, America/New_York**; 1,978 available bikes across the retained stations.
- Capacity proxy: midnight available bikes plus available docks. This can differ from physical dock capacity.
- Demand window: **06:00–10:00 New York time, Monday–Friday, including holidays**. Pickups and returns are counted separately by endpoint time. Completed trips approximate observed demand; unsuccessful attempts are not observed.
- Historical model data: July–September 2026 official Citi Bike trips; source URLs and cache metadata are retained in the data folders/notebook. Training: July 2–August 31; validation: September 1–15; test: September 16–29. Validation MAE selects Poisson for departures and station-weekday means for returns; test results do not reselect models.
- The full workflow contains a five-date static forecast summary (October 29/30 and November 2/3/4). The optimization inputs use the separately prepared **October 28 case forecasts**, not that five-date average.
- Missing, stale, or ambiguous inventory/ID records are excluded with an audit trail. Never replace missing observations or genuine zeros with random demand.

### Target inventory

Current inputs use `fixed_fleet_scaled_historical_event_replay_v1`, replacing the old inventory-plus-net-flow formula. September weekday morning event sequences are scaled separately so their average pickup/return totals match the October 28 case forecasts. Capacity-limited replay evaluates every integer starting inventory at each station. Dynamic programming selects a combination minimizing average simulated blocked pickup/return volume, subject to:

- `0 <= I_star[i] <= C[i]`, integer;
- `sum(I_star) = sum(I0) = 1978`;
- `G[i] = I_star[i] - I0[i]`, hence `sum(G) = 0`.

There are 67 surplus, 60 deficit and 39 balanced station IDs; surplus and deficit quantities are both 442 bikes. That is the amount needed to reach all targets exactly, **not** a promised routed quantity. The replay is a fluid approximation calibrated on historical sequences, not an independent service evaluation or a forecast of actual failed orders. Compact event data and provenance are in `data/target_inventory/`; target summaries and comparison tables are in `outputs_stage6/`. `outputs_stage6/previous_targets/` preserves the superseded targets for traceability and is never loaded by `main.py`.

### Depots

`outputs_stage7/selected_depots.json` contains two station-coordinate depot candidates, chosen by exhaustive unweighted two-median comparison over the retained stations. This minimizes the sum of distances to each station's nearest candidate; it does **not** jointly optimize depot locations with truck routes. Candidate depot sites are independent nodes without bike stock, even where colocated with a station. Physical parking/access feasibility is unverified.

## MILP and outputs

The objective is `alpha * total_distance + beta * sum_i |final_inventory[i] - target[i]|`. The route stage minimizes target mismatch, not the event-replay loss directly.

Trucks leave and return empty to their own depot. Each station may be visited at most once across the fleet. Station inventory and vehicle loads obey capacities. Flow continuity and MTZ order constraints enforce connected depot tours. Per-truck distance budgets apply. The model can leave stations unvisited and targets unmet; it does not enforce balanced workloads or a minimum number of visits. A multi-stop feasible warm start initializes Gurobi without fixing routes or transfers.

Distances are rounded coordinate-based Manhattan approximations: `84*abs(delta_lon) + 111*abs(delta_lat)` km. Map lines show visit order; they are not street-network routes. Overnight customer rides, one-way roads, traffic, travel/service time and an explicit 06:00 completion constraint are omitted.

`outputs_stage8/` is generated locally:

- `solution.json`: actual Gurobi status, gap, objective, routes, station results and validation;
- `station_results.csv`, `route_stops.csv`;
- `routes.png`, `routes.pdf` (unless `--no-map`);
- `gurobi.log`, `rebalancing.mps`, `warm_start_audit.json`.

A time-limit result with an incumbent is a **candidate feasible solution**, not proven optimal. No feasible incumbent causes an error; old results are not used as a fallback. Independent post-solve checks reconstruct truck loads, station inventories, return-to-depot routes, single visits, distances, fleet conservation and objective values. Do not interpret absolute target mismatch as lost customer trips.

No new full-case Gurobi route result is bundled. Run locally with your license to produce it. The solver limit starts at optimization; warm-start construction and the large model build can take additional time.

## Files and reproducibility

- `main.py`: fixed-input CLI entry point.
- `data_preprocessing.py`: JSON loading and validation only.
- `optimization_model.py`: Gurobi MILP and warm start, synchronized with the notebook implementation.
- `solution_checks.py`: independent checks on the exported solution.
- `plot_routes.py`: map of the actual returned Gurobi routes.
- `run_model.ipynb`: short Jupyter launcher.
- `citibike_static_demand.ipynb`: complete English research workflow and cached earlier results.
- `outputs_stage2` through `outputs_stage7`: historical analysis, forecasts, data quality audits and prepared inputs.
- `data`: compact geography, inventory metadata and historical event caches. Large raw trip ZIPs are excluded; rebuilding earlier stages may require downloading them as documented in the notebook. The direct model run requires only the two input JSONs and the Python modules.

Milestone 4 still requires the team's final algebraic formulation, a 3–5 page report, incorporation of TA feedback, discussion of sanity checks and limitations, and an accessible link to code/data.

## Validation performed for this release

All Python modules and notebook code cells passed syntax checks. The bundled real case passed input checks (166 IDs, initial and target totals both 1,978). A separate **synthetic four-station software test**, not study data, was solved with Gurobi to optimality and passed the independent route/load/inventory checks; deliberately corrupted load output was rejected. Map export without online tiles was checked. The full 166-station optimization was not solved here because this environment only has a restricted Gurobi license. No test routes are included as project results.
