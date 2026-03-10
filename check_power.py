from app import create_app, db
from app.models import Component

app = create_app()
app.app_context().push()

shields = Component.query.filter_by(component_type='shield_generator').limit(5).all()
for s in shields:
    print(f'{s.name}: {s.stats.get("power_max") if s.stats else None}')

coolers = Component.query.filter_by(component_type='cooler').limit(5).all()
for c in coolers:
    print(f'{c.name}: {c.stats.get("power_max") if c.stats else None}')