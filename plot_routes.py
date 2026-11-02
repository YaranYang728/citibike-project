"""Plot Gurobi visiting sequences; connecting lines are not street navigation."""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pyproj import Transformer


def plot_rebalancing_solution(dataset, depots, solution, save_filename='outputs_stage8/routes.png', basemap=True):
    stations = dataset['stations']
    transform = Transformer.from_crs(4326, 3857, always_xy=True)
    coords = {s['id']: transform.transform(s['lon'], s['lat']) for s in stations}
    for d in depots:
        coords[f'depot_{d["truck_id"]}'] = transform.transform(d['lon'], d['lat'])
    fig, ax = plt.subplots(figsize=(17, 18))
    for sign, color, label in [(-1, '#1f4e78', 'Surplus: pickup (G < 0)'), (1, '#d9381e', 'Deficit: deliver (G > 0)'), (0, '#aaaaaa', 'Balanced (G = 0)')]:
        selected = [s for s in stations if (s['G'] > 0) - (s['G'] < 0) == sign]
        if selected:
            points = [coords[s['id']] for s in selected]
            ax.scatter(*zip(*points), c=color, s=35, edgecolor='white', linewidth=0.5, label=label, zorder=4)
    colors = ['#27ae60', '#8e44ad']
    names = {s['id']: s['name'] for s in stations}
    gaps = {s['id']: s['G'] for s in stations}
    texts = []
    for k, depot in enumerate(depots):
        truck = depot['truck_id']
        color = colors[k % len(colors)]
        route = solution['routes'][truck]
        path = route['path']
        ax.plot([], [], color=color, lw=2, label=f'{truck}: {len(path[1:-1])} stops, {route["distance_km"]:.3f} km')
        for a, b in zip(path, path[1:]):
            ax.annotate('', xy=coords[b], xytext=coords[a], arrowprops=dict(arrowstyle='->', color=color, lw=2, alpha=0.85), zorder=3)
        for order, sid in enumerate(path[1:-1], 1):
            x, y = coords[sid]
            q = route['transfers'].get(sid, 0)
            texts.append(ax.text(x + 20, y + 20, f'{order}. {names[sid]}\nG={gaps[sid]}, transfer={q:+d}', fontsize=7,
                                 color=color, bbox=dict(facecolor='white', alpha=0.85, edgecolor=color, pad=1.5), zorder=6))
        dx, dy = coords[f'depot_{truck}']
        ax.scatter(dx, dy, marker='*', s=450, c='gold', edgecolor='black', zorder=10, label=f'{truck} depot')
        ax.annotate(depot.get('name', truck), (dx, dy), xytext=(0, -20), textcoords='offset points', ha='center', fontsize=8,
                    bbox=dict(facecolor='gold', alpha=0.9, edgecolor='black'), zorder=10)
    ax.margins(0.09)
    ax.set_aspect('equal')
    if basemap:
        try:
            import contextily as cx
            cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap, zoom=15, alpha=0.55)
        except Exception as exc:
            print(f'Map tiles unavailable: {exc}. Routes are still plotted correctly.')
    try:
        from adjustText import adjust_text
        adjust_text(texts, ax=ax, iter_lim=100, arrowprops=dict(arrowstyle='-', color='grey', lw=0.5))
    except ImportError:
        pass
    ax.set_title(f'Citi Bike Midtown — Gurobi candidate routes\nInventory date: {stations[0]["case_date"]}; {len(stations)} input stations; {solution["status"]}\nConnecting lines show visit order, not actual roads', fontsize=13)
    ax.set_xlabel('Web Mercator eastings (m)'); ax.set_ylabel('Web Mercator northings (m)')
    handles, labels = ax.get_legend_handles_labels()
    handles.append(Line2D([], [], color='none', label=f'Total absolute target mismatch: {solution["total_mismatch"]} bikes'))
    ax.legend(handles=handles, loc='upper left', fontsize=8)
    fig.tight_layout()
    destination = Path(save_filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=200)
    fig.savefig(destination.with_suffix('.pdf'))
    plt.close(fig)
    print(f'Map saved to {destination}')
