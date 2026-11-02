# Citi Bike Overnight Rebalancing — Midtown Manhattan

**IEOR 4004 · Milestone 4 · Python & Gurobi**

This project prepares station-level morning demand estimates and uses a **Mixed-Integer Linear Programming (MILP)** model to plan overnight bike transfers in Midtown Manhattan. The goal is to move the available bikes closer to their target distribution while controlling travel cost.

> **Start here:** To solve the prepared case, open **`run_model.ipynb`**. You do not need to repeat demand prediction. To inspect or rerun the research workflow, open **`citibike_static_demand.ipynb`**.

| Case detail | Setting |
| :--- | :--- |
| Study area | Midtown Manhattan, approximately between 14th and 59th Streets, with street-based boundaries |
| Model coverage | **166 audited station IDs**; no random station sampling |
| Initial inventory | **October 28, 2026, midnight**, New York time |
| Available bikes | **1,978** across the retained stations |
| Morning demand window | **06:00–10:00**, Monday–Friday, including holidays |
| Fleet | **2 trucks**, each with capacity **25 bikes** |
| Distance budget | **25 km per truck** |
| Default optimization limit | **120 seconds** |

---

## Contents

1. [Setup and quick start](#1-setup-and-quick-start)
2. [Files and folders](#2-files-and-folders)
3. [Data and demand prediction](#3-data-and-demand-prediction)
4. [Target inventory and depots](#4-target-inventory-and-depots)
5. [Optimization model](#5-optimization-model)
6. [Parameters and examples](#6-parameters-and-examples)
7. [Results and validation](#7-results-and-validation)
8. [Assumptions and troubleshooting](#8-assumptions-and-troubleshooting)

---

## 1. Setup and quick start

### Requirements

- Python **3.11 or newer** and the packages listed in `requirements.txt`.
- A local Gurobi license that permits the full model size, such as an academic license. Installing `gurobipy` alone does not provide an unrestricted license.
- Internet access if downloading data or displaying online map tiles.

Download the repository using **Code → Download ZIP**, then extract it. Keep the files and folders together.

### Option A — Run in Jupyter

1. Open **`run_model.ipynb`** from the extracted project directory.
2. On first use, install dependencies in a notebook cell:

   ```python
   %pip install -r requirements.txt
   ```

3. Restart the kernel after installation, then run the notebook cells in order.

The notebook calls `main.py`, reads the saved model inputs, runs Gurobi, checks the result, and displays the route map.

### Option B — Run in a terminal

From the project directory:

```bash
python -m pip install -r requirements.txt
python main.py --time_limit 120
```

On macOS, use `python3` if `python` is unavailable. The time limit applies to **Gurobi optimization**; building the model, preparing its initial solution, and drawing the map take additional time.

**Keep `gurobi.lic` private.** Use Gurobi's standard local license location or an existing `GRB_LICENSE_FILE` setting; do not upload the license to this repository.

---

## 2. Files and folders

### Code and notebooks

| File | Purpose |
| :--- | :--- |
| `run_model.ipynb` | Short launcher: run optimization from prepared inputs |
| `citibike_static_demand.ipynb` | Full research workflow: data preparation, regional comparison, demand prediction, inventories, depots, optimization, and diagnostics |
| `main.py` | Command-line entry point for the prepared case |
| `data_preprocessing.py` | Load and validate prepared JSON inputs; this module does **not** clean raw trip records |
| `optimization_model.py` | Gurobi MILP and construction of an initial feasible solution |
| `solution_checks.py` | Independent checks of routes, loads, inventories, and objective values |
| `plot_routes.py` | Draw the returned routes on a map |
| `requirements.txt` | Python dependencies |

### Data and analysis outputs

| Folder | Contents | Needed to run optimization directly? |
| :--- | :--- | :---: |
| `outputs_stage2/` | Data quality, cleaned historical aggregates, station geography, and ID alignment | No |
| `outputs_stage3/` | Comparison of Lower Manhattan, Midtown, and Upper Manhattan | No |
| `outputs_stage4/` | Demand forecasts, model comparisons, and evaluation tables | No |
| `outputs_stage5/` | Midnight inventory audit, station matching, and preliminary parameters | No |
| `outputs_stage6/` | **Final station inputs and fleet-conserving targets**, plus exclusion and target audits | **Yes: station input JSON** |
| `outputs_stage7/` | **Selected depots**, candidate comparisons, and location plots | **Yes: depot JSON** |
| `outputs_stage8/` | New solver results and maps, generated when `main.py` runs | Generated |
| `outputs_stage9/` | Additional validation and plots from the full notebook | No |
| `data/` | Geography files, archived inventory responses, and ordered historical event caches | No; needed for corresponding preparation steps |

The direct solver needs these two input files:

```text
outputs_stage6/model_station_inputs.json
outputs_stage7/selected_depots.json
```

**Why save earlier outputs?** Data cleaning and prediction generate trustworthy inputs; saving those results avoids repeating the preparation every time the routing model runs. Stages 2–5 also document where the final inputs came from.

**To rerun the complete research notebook:** retain the corresponding `data/` files as well as the analysis outputs. Stages 2–7 alone do not provide every preparation input. Compatible caches can avoid rereading raw trips. Large official trip ZIPs are excluded from the package and may need to be downloaded when rebuilding caches; the notebook documents these steps. Run the full notebook from top to bottom, rather than treating each stage as independent.

Keep folder names unchanged unless all matching code paths are updated.

---

## 3. Data and demand prediction

| Source | Period / timestamp | Use |
| :--- | :--- | :--- |
| [Official Citi Bike trip data](https://citibikenyc.com/system-data) | July–September 2026; analysis uses July 2–September 29 | Regional comparison and station pickup/return prediction |
| [ctbk.dev historical inventory](https://ctbk.dev/) | October 28, 2026, midnight, New York time | Observed starting inventory and station status checks |
| Saved GBFS station metadata | Snapshot documented in the data files | Station names, IDs, coordinates, and capacity consistency checks |
| NYC geography and street centerlines | Sources documented in the notebook | Main-island filtering and street-based region boundaries |

**Demand means completed morning pickup and return events**, counted separately at their respective station and event time. It is measured in **events per station per weekday morning peak**. These records do not reveal every unsuccessful attempt to rent or return a bike.

The prediction step compares two simple methods:

- **Baseline:** the station's historical mean for the same weekday, with documented fallback rules.
- **Regularized Poisson regression:** station ID, weekday, and a date trend; no deep learning or hyperparameter search.

| Split | Dates | Purpose |
| :--- | :--- | :--- |
| Training | July 2–August 31 | Fit models |
| Validation | September 1–15 | Select each flow's method using MAE |
| Test | September 16–29 | Evaluate the selected methods without reselecting them |

Preprocessing is fitted within each training set. In the saved Midtown analysis, validation selects **Poisson for pickups** and **station-weekday means for returns**. MAE is average absolute count error, not an accuracy percentage.

The notebook also exports a five-weekday static summary for October 29/30 and November 2/3/4. **The optimization uses the separately prepared October 28 case forecasts**, not that five-date average. Midnight inventory is an observation, not a prediction.

Missing, stale, or ambiguous station records are excluded with recorded reasons. The retained 166 IDs form an audited subset, not a claim to cover every current physical Midtown station.

---

## 4. Target inventory and depots

### From predicted trips to target bike stock

Pickup/return counts are **flows over time**; target inventory is the **number of bikes to place at a station before the peak**. They are different quantities because bikes can be returned and used again.

The current target method:

1. Uses ordered September morning events to represent the sequence of pickups and returns.
2. Scales pickup and return volumes separately to match the October 28 forecasts on average.
3. Simulates each possible integer starting stock within a station's capacity.
4. Allocates the existing fleet across stations to minimize average simulated blocked pickup/return volume.

The targets satisfy:

$$
0 \leq I_i^* \leq C_i, \qquad I_i^* \in \mathbb{Z},
\qquad \sum_i I_i^* = \sum_i I_i^0 = 1{,}978.
$$

| Symbol | Meaning |
| :--- | :--- |
| $I_i^0$ | Observed midnight stock of available bikes |
| $C_i$ | Effective capacity proxy: midnight available bikes plus available docks |
| $P_i$, $R_i$ | Predicted morning pickups and returns |
| $I_i^*$ | Target starting inventory under the fixed fleet total |
| $G_i = I_i^* - I_i^0$ | Net delivery needed to reach the target |

- **$G_i > 0$:** delivery station.
- **$G_i < 0$:** pickup station.
- **$G_i = 0$:** already at its target.

The saved case contains **67 surplus, 60 deficit, and 39 balanced IDs**. Surplus and deficit quantities each total **442 bikes**. This is the transfer quantity needed to reach every target exactly, not a promise that the trucks can achieve it.

The method preserves demand forecasts while allocating a limited vehicle stock. It does **not** assume that all customer demand can be served. It replaces the earlier heuristic targets; files in `outputs_stage6/previous_targets/` are retained for comparison and are not loaded by `main.py`.

### Two depot candidates

| Truck | Candidate location | Latitude | Longitude |
| :--- | :--- | ---: | ---: |
| `Truck_1` | Near Broadway & W 25 St | 40.742869 | -73.989186 |
| `Truck_2` | Near W 47 St & 6 Ave | 40.758154 | -73.981957 |

The two sites are selected by comparing all station-coordinate pairs and minimizing the sum of distances to each station's nearest candidate. This is an **unweighted two-median location calculation**, separate from truck routing.

Depots are independent routing nodes with no extra bike supply. Their physical parking and loading feasibility is unverified; they are not jointly optimized with the routes.

---

## 5. Optimization model

Gurobi chooses **which stations to visit, their visit order, and how many bikes to transfer**.

The objective combines travel cost and remaining inventory target mismatch:

$$
\min \quad
\alpha \sum_{k}\sum_{i,j} D_{ij}x_{ijk}
+ \beta \sum_i u_i,
\qquad
u_i \geq \left|I_i^{\mathrm{final}}-I_i^*\right|.
$$

Here $x_{ijk}$ indicates whether truck $k$ travels directly from node $i$ to node $j$. Absolute deviations are implemented through linear inequalities. The route model minimizes target mismatch; it does not directly minimize the earlier event-replay loss.

### Core constraints

- Station inventories stay between zero and effective capacity.
- A truck's simultaneous load never exceeds 25 bikes.
- Each station is visited at most once across the fleet.
- Every active route is connected to its truck's own depot.
- Trucks start and finish empty at the same depot.
- Each truck stays within its distance budget.

Unvisited stations and unmet targets are allowed and penalized. The model does not require equal truck workloads or a minimum number of station visits. An initial feasible solution helps start Gurobi; it does not fix the final routes.

Distances use the original rounded coordinate approximation:

$$
D_{ij}=\operatorname{round}\!\left(
84|\mathrm{lon}_i-\mathrm{lon}_j|
+111|\mathrm{lat}_i-\mathrm{lat}_j|,\,3\right)\ \mathrm{km}.
$$

**Map lines represent visiting order, not actual street navigation.** This version does not enforce road-network or one-way-street rules.

---

## 6. Parameters and examples

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `--truck_capacity`, `-Q` | `25` | Maximum bikes carried simultaneously per truck |
| `--max_dist`, `-w` | `25.0` | Distance budget per truck, km |
| `--alpha` | `1.5` | Assumed travel cost per km |
| `--beta` | `5.0` | Assumed penalty per bike of absolute target mismatch |
| `--time_limit` | `120` | Gurobi optimization limit, seconds |
| `--inputs` | `outputs_stage6/model_station_inputs.json` | Station inputs |
| `--depots` | `outputs_stage7/selected_depots.json` | Depot inputs |
| `--output` | `outputs_stage8` | Result directory |


Two trucks are defined by the depot input file. Costs, capacities, and budgets are **study assumptions**, not verified Citi Bike operating parameters. The penalty applies to both excess and shortage relative to targets.

**Run for two minutes:**

```bash
python main.py --time_limit 120
```

**Change the travel/mismatch trade-off:**

```bash
python main.py --time_limit 120 --alpha 1.5 --beta 10
```

**Run without online map tiles:**

```bash
python main.py --time_limit 120 --no-basemap
```

A larger beta gives inventory mismatch more weight relative to distance. It does not guarantee more visits in a time-limited run. The old `--sample_pct`, `--num_stations`, and `--trip_data` options do not apply to this prepared-input version.

---

## 7. Results and validation

After a successful run, `main.py` writes the following into `outputs_stage8/`:

| File | Contents |
| :--- | :--- |
| `solution.json` | Solver status, objective, relative gap, routes, station results, and validation |
| `station_results.csv` | Before/after inventory, targets, and transfers |
| `route_stops.csv` | Ordered stops, net deliveries, and truck loads |
| `routes.png`, `routes.pdf` | Route maps, unless map generation is disabled |
| `gurobi.log` | Solver progress log |
| `rebalancing.mps` | Exported optimization model |
| `warm_start_audit.json` | Checks of the initial solution provided to Gurobi |

Independent checks reconstruct route connectivity, single visits, vehicle loads, final inventories, fleet conservation, distances, and objective values.

### How to interpret the result

- **Target mismatch:** total absolute difference between final and target inventory, in bikes. It is not a count of lost trips.
- **Relative MIP gap:** uncertainty about optimality of the objective, not a shortage of physical bikes or prediction error. In `solution.json`, a gap of `0.60` means **60%**.
- **Time limit reached with a feasible incumbent:** report a **candidate solution**, not a proven optimum.
- **No feasible incumbent:** the program raises an error; it does not substitute an old route.

Compare final mismatch with no rebalancing, then examine distance, transferred bikes, stop counts, and feasibility. Visiting every input station is not required.

The release was checked for syntax, real-input consistency, and small synthetic Gurobi cases with independent validation. Those software tests are not study results. **Full-case results must come from an actual run with a suitable local license.**

---

## 8. Assumptions and troubleshooting

### Interpretation limits

- Overnight customer rides are ignored.
- Effective capacity is a snapshot proxy, not necessarily physical dock capacity.
- Historical completed rides approximate demand; unobserved failed attempts are missing.
- Historical event replay is a fluid approximation, not an independent service evaluation.
- Late-October forecast accuracy is not established by September test performance.
- Travel and loading times, traffic, one-way streets, and explicit completion by 06:00 are not modeled.
- Fixed-fleet targets and separately selected depots do not guarantee that all targets can be reached within routing constraints.

### Common problems

| Problem | What to do |
| :--- | :--- |
| Missing `model_station_inputs.json` or `selected_depots.json` | Confirm both Stage 6/7 files exist at the paths above and the full project was extracted |
| Notebook looks in the wrong directory | Open Jupyter in the project directory; run `print(Path.cwd())` after importing `Path` to check |
| `ModuleNotFoundError` | Install `requirements.txt` in the active notebook kernel, then restart it |
| Model too large for the license | Activate a full academic or other suitable Gurobi license locally |
| Map tiles cannot load | Run with `--no-basemap` to retain the route drawing |
| Missing inputs while rerunning early notebook stages | Add the corresponding `data/` files from the English project package, or follow the notebook's rebuilding instructions |

For Milestone 4, accompany the code with the final algebraic formulation, a **3–5 page report**, parameter sources, actual solver results, sanity checks, limitations, and an accessible repository link.
