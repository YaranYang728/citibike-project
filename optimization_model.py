import os
import gurobipy as gp
from gurobipy import GRB
from typing import Dict, List, Any
def latlon_to_km(lat1,lon1,lat2,lon2):
    return round(84*abs(lon1-lon2)+111*abs(lat1-lat2),3)


def init_gurobi_env(license_path: str = "gurobi.lic") -> gp.Env:
    """Initializes Gurobi Environment using local gurobi.lic license file."""
    abs_lic_path = os.path.abspath(license_path)
    if os.path.exists(abs_lic_path) and not os.environ.get("GRB_LICENSE_FILE"):
        os.environ["GRB_LICENSE_FILE"] = abs_lic_path
        print(f"Loading Gurobi license from: {abs_lic_path}")
    
    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 1)
    env.start()
    return env


def solve_citi_bike_rebalancing(
    data: Dict[str, Any],
    depots: List[Dict[str, Any]],
    truck_capacity: int = 25,
    max_distance_w: float = 25.0,
    alpha: float = 1.5,
    beta: float = 5.0,
    license_path: str = "gurobi.lic",
    time_limit: float = 120,
    output_dir: str = "outputs_stage8"
) -> Dict[str, Any]:
    """Builds and solves the overnight rebalancing MILP (Milestone 3) with Subtour Elimination."""
    stations = data['stations']
    I = [s['id'] for s in stations]
    K = [d['truck_id'] for d in depots]
    
    C = {s['id']: s['C'] for s in stations}
    I0 = {s['id']: s['I0'] for s in stations}
    G = {s['id']: s['G'] for s in stations}
    
    depot_map = {d['truck_id']: d for d in depots}
    
    # Distance Matrix D_ij
    D = {}
    for k in K:
        nodes = I + [f"depot_{k}"]
        coords = {s['id']: (s['lat'], s['lon']) for s in stations}
        coords[f"depot_{k}"] = (depot_map[k]['lat'], depot_map[k]['lon'])
        
        for i in nodes:
            for j in nodes:
                if i != j:
                    lat1, lon1 = coords[i]
                    lat2, lon2 = coords[j]
                    D[(i, j, k)] = latlon_to_km(lat1, lon1, lat2, lon2)

    max_capacity = max(C.values()) if len(C) > 0 else 50
    M = 2 * truck_capacity + max_capacity

    env = init_gurobi_env(license_path=license_path)
    model = gp.Model("CitiBike_Midtown_Rebalancing", env=env)
    model.Params.TimeLimit = time_limit
    model.Params.Threads = 2

    # Decision Variables
    x = {}  # Routing variable x_{ijk} in {0,1}
    z = {}  # Net delivery z_{ik} in Integer
    l = {}  # Load l_{ik} >= 0
    u = {}  # Target shortfall u_i >= 0
    y = {}  # Subtour elimination sequence variable y_{ik} >= 0

    for i in I:
        u[i] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"u_{i}")

    for k in K:
        depot_k = f"depot_{k}"
        nodes_k = I + [depot_k]
        
        l[(depot_k, k)] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=0, name=f"l_{depot_k}_{k}")
        
        for i in I:
            z[(i, k)] = model.addVar(vtype=GRB.INTEGER, lb=-truck_capacity, ub=truck_capacity, name=f"z_{i}_{k}")
            l[(i, k)] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=truck_capacity, name=f"l_{i}_{k}")
            y[(i, k)] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=len(I), name=f"y_{i}_{k}")

        for i in nodes_k:
            for j in nodes_k:
                if i != j:
                    x[(i, j, k)] = model.addVar(vtype=GRB.BINARY, name=f"x_{i}_{j}_{k}")

    model.update()

    # Objective Function (Equation 3)
    transport_cost = gp.quicksum(alpha * D[(i, j, k)] * x[(i, j, k)] 
                                for k in K 
                                for i in I + [f"depot_{k}"] 
                                for j in I + [f"depot_{k}"] if i != j)
    penalty_cost = gp.quicksum(beta * u[i] for i in I)
    model.setObjective(transport_cost + penalty_cost, GRB.MINIMIZE)

    # (4) Depot Flow Balance
    for k in K:
        depot_k = f"depot_{k}"
        model.addConstr(
            gp.quicksum(x[(depot_k, j, k)] for j in I) == gp.quicksum(x[(i, depot_k, k)] for i in I),
            name=f"depot_flow_balance_{k}"
        )
        model.addConstr(
            gp.quicksum(x[(depot_k, j, k)] for j in I) <= 1,
            name=f"depot_use_{k}"
        )

    # (5) Route Continuity
    for k in K:
        depot_k = f"depot_{k}"
        nodes_k = I + [depot_k]
        for i in nodes_k:
            model.addConstr(
                gp.quicksum(x[(j, i, k)] for j in nodes_k if j != i) == 
                gp.quicksum(x[(i, j, k)] for j in nodes_k if j != i),
                name=f"continuity_{i}_{k}"
            )

    # (6) At most one visit per station
    for i in I:
        model.addConstr(
            gp.quicksum(x[(j, i, k)] for k in K for j in I + [f"depot_{k}"] if j != i) <= 1,
            name=f"single_visit_{i}"
        )

    # (7) Transfers bounded by visit
    for k in K:
        depot_k = f"depot_{k}"
        nodes_k = I + [depot_k]
        for i in I:
            visit_var = gp.quicksum(x[(j, i, k)] for j in nodes_k if j != i)
            model.addConstr(z[(i, k)] >= -I0[i] * visit_var, name=f"transfer_lb_{i}_{k}")
            model.addConstr(z[(i, k)] <= (C[i] - I0[i]) * visit_var, name=f"transfer_ub_{i}_{k}")

    # (8) Station Dock Capacity Constraints
    for i in I:
        total_transfer = gp.quicksum(z[(i, k)] for k in K)
        model.addConstr(I0[i] + total_transfer >= 0, name=f"station_min_inv_{i}")
        model.addConstr(I0[i] + total_transfer <= C[i], name=f"station_max_inv_{i}")

    # (9) Unmet Target Shortfall Penalty
    for i in I:
        total_transfer = gp.quicksum(z[(i, k)] for k in K)
        model.addConstr(G[i] - total_transfer <= u[i], name=f"penalty_pos_{i}")
        model.addConstr(G[i] - total_transfer >= -u[i], name=f"penalty_neg_{i}")

    # (10) Vehicle Load Bound
    for k in K:
        depot_k = f"depot_{k}"
        nodes_k = I + [depot_k]
        for i in I:
            visit_var = gp.quicksum(x[(j, i, k)] for j in nodes_k if j != i)
            model.addConstr(l[(i, k)] <= truck_capacity * visit_var, name=f"load_ub_{i}_{k}")

    # (11) Big-M Load Flow Balance
    for k in K:
        depot_k = f"depot_{k}"
        nodes_k = I + [depot_k]
        for j in I:
            for i in nodes_k:
                if i != j:
                    model.addConstr(
                        l[(j, k)] - l[(i, k)] + z[(j, k)] >= -M * (1 - x[(i, j, k)]),
                        name=f"load_track_lb_{i}_{j}_{k}"
                    )
                    model.addConstr(
                        l[(j, k)] - l[(i, k)] + z[(j, k)] <= M * (1 - x[(i, j, k)]),
                        name=f"load_track_ub_{i}_{j}_{k}"
                    )

    # (12) Empty Return to Depot
    for k in K:
        depot_k = f"depot_{k}"
        for i in I:
            model.addConstr(
                l[(i, k)] <= truck_capacity * (1 - x[(i, depot_k, k)]),
                name=f"empty_return_{i}_{k}"
            )

    # (13) Max Travel Budget Limit
    for k in K:
        depot_k = f"depot_{k}"
        nodes_k = I + [depot_k]
        model.addConstr(
            gp.quicksum(D[(i, j, k)] * x[(i, j, k)] for i in nodes_k for j in nodes_k if i != j) <= max_distance_w,
            name=f"dist_limit_{k}"
        )

    # (14) SUBTOUR ELIMINATION (MTZ Sequence Ordering Constraints)
    for k in K:
        depot_k = f"depot_{k}"
        for i in I:
            visit_var = gp.quicksum(x[(j, i, k)] for j in I + [depot_k] if j != i)
            model.addConstr(y[(i, k)] <= len(I) * visit_var, name=f"seq_ub_{i}_{k}")
            model.addConstr(y[(i, k)] >= 1 - len(I) * (1 - x[(depot_k, i, k)]), name=f"seq_depot_{i}_{k}")
            for j in I:
                if i != j:
                    model.addConstr(
                        y[(j, k)] >= y[(i, k)] + 1 - (len(I)+1) * (1 - x[(i, j, k)]),
                        name=f"seq_step_{i}_{j}_{k}"
                    )

    from pathlib import Path
    import json,time
    out=Path(output_dir);out.mkdir(parents=True, exist_ok=True)
    
    for k in K:
        model.addConstr(gp.quicksum(z[i,k] for i in I)==0,name=f'explicit_conservation_{k}')
    model.update();model.write(str(out/'rebalancing.mps'))
    # Build a multi-stop warm start by inserting beneficial pickup/delivery pairs; all input stations remain eligible.
    # This is a feasible MILP start only; Gurobi can change stations, quantities and order.
    routes_seed = {k: [f'depot_{k}', f'depot_{k}'] for k in K}
    transfers_seed = {k: {} for k in K}
    used_seed = set()
    def route_distance(path, k):
        return sum(D[a,b,k] for a,b in zip(path[:-1],path[1:]) if a != b)
    def feasible_loads(path, transfers):
        load = 0
        for node in path[1:-1]:
            load -= transfers[node]
            if load < 0 or load > truck_capacity:
                return False
        return load == 0
    while True:
        best = None
        for k in K:
            path = routes_seed[k]
            old_distance = route_distance(path,k)
            load = 0
            for pos in range(1,len(path)):
                if pos > 1:
                    load -= transfers_seed[k][path[pos-1]]
                a,b = path[pos-1],path[pos]
                for i in I:
                    if i in used_seed or G[i] >= 0: continue
                    for j in I:
                        if j in used_seed or G[j] <= 0: continue
                        q = min(-G[i],G[j],truck_capacity-load)
                        if q <= 0: continue
                        extra = D[a,i,k]+D[i,j,k]+D[j,b,k]-(D[a,b,k] if a != b else 0)
                        gain = 2*beta*q-alpha*extra
                        if gain <= 1e-9 or old_distance+extra > max_distance_w+1e-9: continue
                        candidate = (-gain,extra,k,pos,i,j,q)
                        if best is None or candidate < best: best=candidate
        if best is None: break
        _,_,k,pos,i,j,q = best
        routes_seed[k][pos:pos] = [i,j]
        transfers_seed[k].update({i:-q,j:q})
        used_seed.update([i,j])
    # Improve the initial route with segment reversals at fixed transfers; recheck loads each time.
    for k in K:
        path = routes_seed[k]
        while True:
            best_path = path
            best_distance = route_distance(path,k)
            for a in range(1,len(path)-2):
                for b in range(a+1,len(path)-1):
                    candidate = path[:a]+list(reversed(path[a:b+1]))+path[b+1:]
                    dist = route_distance(candidate,k)
                    if dist < best_distance-1e-9 and feasible_loads(candidate,transfers_seed[k]):
                        best_path,best_distance=candidate,dist
            if best_path is path: break
            path=best_path
        routes_seed[k]=path
    names = [v.VarName for v in model.getVars()]
    seed = dict.fromkeys(names,0.0)
    for i in I: seed[u[i].VarName]=abs(G[i])
    for k in K:
        path=routes_seed[k]
        if len(path)==2: continue
        load=0
        for a,b in zip(path[:-1],path[1:]): seed[x[a,b,k].VarName]=1
        for order,i in enumerate(path[1:-1],1):
            q=transfers_seed[k][i];load-=q
            seed[z[i,k].VarName]=q;seed[l[i,k].VarName]=load
            seed[y[i,k].VarName]=order;seed[u[i].VarName]=abs(G[i]-q)
    # Check the warm start against every MILP row, including MTZ and Big-M constraints.
    maximum_violation=0.0
    for constraint in model.getConstrs():
        row=model.getRow(constraint)
        lhs=sum(row.getCoeff(t)*seed[row.getVar(t).VarName] for t in range(row.size()))
        violation=(abs(lhs-constraint.RHS) if constraint.Sense=='=' else
                   max(lhs-constraint.RHS,0) if constraint.Sense=='<' else max(constraint.RHS-lhs,0))
        maximum_violation=max(maximum_violation,violation)
    for v in model.getVars():
        value=seed[v.VarName]
        assert v.LB-1e-6 <= value <= v.UB+1e-6
        if v.VType != GRB.CONTINUOUS: assert abs(value-round(value)) <= 1e-6
    assert maximum_violation <= 1e-6, maximum_violation
    seed_objective=sum(v.Obj*seed[v.VarName] for v in model.getVars())
    seed_audit={'objective':seed_objective,'maximum_constraint_violation':maximum_violation,
                'constraints_checked':model.NumConstrs,'routes':routes_seed,
                'transfers':transfers_seed,'visited_stations':len(used_seed)}
    (out/'warm_start_audit.json').write_text(json.dumps(seed_audit,ensure_ascii=False,indent=2))
    print('Multi-stop warm start:',len(used_seed),'stations; objective',seed_objective,
          '; maximum full-model constraint violation',maximum_violation,flush=True)
    for v in model.getVars(): v.Start=seed[v.VarName]

    values={};solver='Gurobi';gap=None;bound=None
    start=time.perf_counter()
    model.Params.LogFile=str(out/'gurobi.log')
    model.optimize()
    status={GRB.OPTIMAL:'Optimal',GRB.TIME_LIMIT:'Time limit reached',GRB.INFEASIBLE:'Infeasible'}.get(model.Status,str(model.Status))
    runtime=model.Runtime
    if model.SolCount == 0:
        raise RuntimeError('Gurobi returned no feasible incumbent. Check the log; do not reuse old results.')
    values={v.VarName:v.X for v in model.getVars()}
    gap=model.MIPGap;bound=model.ObjBound
    result={'solver':solver,'status':status,'status_code':model.Status,'solution_count':model.SolCount,'solver_objective':model.ObjVal,'runtime_seconds':runtime,'has_feasible_solution':bool(values),
            'gap':gap,'objective_bound':bound,'stations':len(I),'trucks':len(K),'truck_capacity':truck_capacity,'max_distance_km':max_distance_w,'alpha':alpha,'beta':beta,'routes':{},'station_results':[]}
    if values:
        val=lambda var:values[var.VarName]
        distance=0.0
        for k in K:
            depot=f'depot_{k}';nodes=I+[depot]
            arcs=[(i,j) for i in nodes for j in nodes if i!=j and val(x[i,j,k])>0.5]
            nxt=dict(arcs);path=[depot];cur=depot
            for step in range(len(I)+2):
                if cur not in nxt:break
                cur=nxt[cur];path.append(cur)
                if cur==depot:break
            assert not arcs or (path[-1]==depot and len(path)-1==len(arcs))
            dist=sum(D[i,j,k] for i,j in arcs);distance+=dist
            result['routes'][k]={'path':path,'distance_km':dist,
                'transfers':{i:round(val(z[i,k])) for i in I if i in path},
                'loads':{i:val(l[i,k]) for i in I if i in path}}
        for i in I:
            net=round(sum(val(z[i,k]) for k in K));final=I0[i]+net
            assert 0<=final<=C[i]
            result['station_results'].append({'id':i,'I0':I0[i],'net_delivery':net,'final_inventory':final,'target':I0[i]+G[i],'mismatch':abs(G[i]-net)})
        assert sum(r['net_delivery'] for r in result['station_results'])==0
        mismatch=sum(r['mismatch'] for r in result['station_results'])
        result.update(total_distance_km=distance,total_mismatch=mismatch,objective=alpha*distance+beta*mismatch,
            baseline_mismatch=sum(abs(v) for v in G.values()),baseline_objective=beta*sum(abs(v) for v in G.values()))
    assert abs(result['objective'] - model.ObjVal) <= 1e-4
    result['warm_start_objective']=seed_objective
    result['improved_over_warm_start']=bool(values) and result['objective'] < seed_objective-1e-6
    (out/'solution.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
