"""Load fixed, audited Midtown parameters. Never synthesize missing observations."""
import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def project_path(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_problem_dataset(input_path='outputs_stage6/model_station_inputs.json'):
    path = project_path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f'Missing station input: {path}. Extract the complete project folder.')
    data = json.loads(path.read_text(encoding='utf-8'))
    stations = data['stations']
    if not stations:
        raise ValueError('Empty station set.')
    ids = [s['id'] for s in stations]
    if any(not isinstance(sid, str) for sid in ids) or len(set(ids)) != len(ids):
        raise ValueError('Station IDs must be unique strings.')
    for station in stations:
        for key in ['id', 'name', 'lat', 'lon', 'C', 'I0', 'I_star', 'G', 'case_date', 'target_method']:
            if key not in station:
                raise ValueError(f'{station.get("id")}: missing {key}')
        for key in ['C', 'I0', 'I_star', 'G']:
            value = station[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
                raise ValueError(f'{station["id"]}: invalid integer {key}')
        if not (0 <= station['I0'] <= station['C'] and 0 <= station['I_star'] <= station['C']):
            raise ValueError(f'{station["id"]}: inventory outside capacity')
        if station['G'] != station['I_star'] - station['I0']:
            raise ValueError(f'{station["id"]}: G differs from target - initial inventory')
        if not (-90 <= station['lat'] <= 90 and -180 <= station['lon'] <= 180):
            raise ValueError(f'{station["id"]}: invalid coordinates')
    if len({s['case_date'] for s in stations}) != 1:
        raise ValueError('Mixed inventory dates.')
    if sum(s['G'] for s in stations) != 0:
        raise ValueError('New fixed-fleet targets must conserve total initial inventory.')
    return data


def load_depots(depot_path='outputs_stage7/selected_depots.json'):
    depots = json.loads(project_path(depot_path).read_text(encoding='utf-8'))
    if len(depots) != 2 or len({d['truck_id'] for d in depots}) != 2:
        raise ValueError('Expected two distinct trucks/depots.')
    for depot in depots:
        if not (-90 <= depot['lat'] <= 90 and -180 <= depot['lon'] <= 180):
            raise ValueError('Invalid depot coordinates.')
    return depots


def latlon_to_km(lat1, lon1, lat2, lon2):
    return round(84 * abs(lon1 - lon2) + 111 * abs(lat1 - lat2), 3)
