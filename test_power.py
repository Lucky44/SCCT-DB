from app import create_app, db
from app.models import MyShip
from app.routes.my_ships import get_power_stats

app = create_app()
app.app_context().push()

ship = MyShip.query.first()
if ship:
    stats = get_power_stats(ship)
    print('Shields max_draw:', stats['systems']['shields']['max_draw'])
    print('Weapons max_draw:', stats['systems']['weapons']['max_draw'])
    print('Thrust max_draw:', stats['systems']['thrust']['max_draw'])
    print('QD max_draw:', stats['systems']['quantum_drive']['max_draw'])
    print('Radar max_draw:', stats['systems']['radar']['max_draw'])
    print('Life Support max_draw:', stats['systems']['life_support']['max_draw'])
    print('Number of shield generators:', len(stats['systems']['shields']['equipment']))
    print('Coolers:', [(c['name'], c['draw']) for c in stats['coolers']])
else:
    print('No ships found')