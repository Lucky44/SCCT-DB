from flask import Blueprint, render_template, request, abort
from app import db
from app.models import Ship, Component, Weapon, ShipDefaultLoadout

browser_bp = Blueprint("browser", __name__, url_prefix="/browse")


@browser_bp.route("/ships")
def ships():
    q = db.session.query(Ship)

    manufacturer = request.args.get("manufacturer", "").strip()
    size_category = request.args.get("size_category", "").strip()
    search = request.args.get("q", "").strip()

    if manufacturer:
        q = q.filter(Ship.manufacturer == manufacturer)
    if size_category:
        q = q.filter(Ship.size_category == size_category)
    if search:
        q = q.filter(Ship.name.ilike(f"%{search}%"))

    seen = set()
    ships_list = []
    for ship in q.order_by(Ship.name).all():
        if ship.name not in seen:
            seen.add(ship.name)
            ships_list.append(ship)

    ships_list.sort(key=lambda s: s.name.split(' ', 1)[1] if ' ' in s.name else s.name)

    manufacturers = [r[0] for r in db.session.query(Ship.manufacturer).distinct().order_by(Ship.manufacturer) if r[0]]
    size_categories = [r[0] for r in db.session.query(Ship.size_category).distinct().order_by(Ship.size_category) if r[0]]

    return render_template(
        "ships.html",
        ships=ships_list,
        manufacturers=manufacturers,
        size_categories=size_categories,
        filters={"manufacturer": manufacturer, "size_category": size_category, "q": search},
    )


@browser_bp.route("/components")
def components():
    q = db.session.query(Component)

    comp_type = request.args.get("type", "").strip()
    size = request.args.get("size", "").strip()
    grade = request.args.get("grade", "").strip()
    class_ = request.args.get("class", "").strip()
    manufacturer = request.args.get("manufacturer", "").strip()
    search = request.args.get("q", "").strip()

    if comp_type:
        q = q.filter(Component.component_type == comp_type)
    if size:
        q = q.filter(Component.size == int(size))
    if grade:
        q = q.filter(Component.grade == grade)
    if class_:
        q = q.filter(Component.class_ == class_)
    if manufacturer:
        q = q.filter(Component.manufacturer == manufacturer)
    if search:
        q = q.filter(Component.name.ilike(f"%{search}%"))

    components_list = q.order_by(Component.component_type, Component.size, Component.grade).all()

    types = [r[0] for r in db.session.query(Component.component_type).distinct().order_by(Component.component_type) if r[0]]
    grades = [r[0] for r in db.session.query(Component.grade).distinct().order_by(Component.grade) if r[0]]
    classes = [r[0] for r in db.session.query(Component.class_).distinct().order_by(Component.class_) if r[0]]
    manufacturers = [r[0] for r in db.session.query(Component.manufacturer).distinct().order_by(Component.manufacturer) if r[0]]

    return render_template(
        "components.html",
        components=components_list,
        types=types,
        grades=grades,
        classes=classes,
        manufacturers=manufacturers,
        filters={"type": comp_type, "size": size, "grade": grade, "class": class_, "manufacturer": manufacturer, "q": search},
    )


@browser_bp.route("/weapons")
def weapons():
    q = db.session.query(Weapon)

    weapon_type = request.args.get("type", "").strip()
    size = request.args.get("size", "").strip()
    manufacturer = request.args.get("manufacturer", "").strip()
    search = request.args.get("q", "").strip()

    if weapon_type:
        q = q.filter(Weapon.weapon_type == weapon_type)
    if size:
        q = q.filter(Weapon.size == int(size))
    if manufacturer:
        q = q.filter(Weapon.manufacturer == manufacturer)
    if search:
        q = q.filter(Weapon.name.ilike(f"%{search}%"))

    weapons_list = q.order_by(Weapon.weapon_type, Weapon.size, Weapon.name).all()

    types = [r[0] for r in db.session.query(Weapon.weapon_type).distinct().order_by(Weapon.weapon_type) if r[0]]
    manufacturers = [r[0] for r in db.session.query(Weapon.manufacturer).distinct().order_by(Weapon.manufacturer) if r[0]]

    return render_template(
        "weapons.html",
        weapons=weapons_list,
        types=types,
        manufacturers=manufacturers,
        filters={"type": weapon_type, "size": size, "manufacturer": manufacturer, "q": search},
    )


@browser_bp.route("/ships/<int:ship_id>")
def ship_detail(ship_id):
    ship = db.session.get(Ship, ship_id) or abort(404)
    slots = (
        db.session.query(ShipDefaultLoadout)
        .filter_by(ship_id=ship_id)
        .order_by(ShipDefaultLoadout.slot_type, ShipDefaultLoadout.slot_number)
        .all()
    )
    return render_template("ship_browser_detail.html", ship=ship, slots=slots)
