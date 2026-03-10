from app import db


# ---------------------------------------------------------------------------
# Reference tables — populated from scunpacked-data
# ---------------------------------------------------------------------------

class Ship(db.Model):
    __tablename__ = "ships"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    manufacturer = db.Column(db.String(80))
    size_category = db.Column(db.String(20))   # small / medium / large / capital
    crew_size = db.Column(db.Integer)
    cargo_scu = db.Column(db.Integer)
    source_file = db.Column(db.String(200))
    power_generation_pips = db.Column(db.Float, nullable=True)  # Power.GenerationSegments from ships.json
    power_segments = db.Column(db.JSON, nullable=True)  # Power.UsedSegmentsGrouped from ships.json
    ship_stats = db.Column(db.JSON, nullable=True)  # armor, speed, maneuverability, dimensions
    image_path = db.Column(db.String(200), nullable=True)  # local path relative to static/, e.g. images/ships/gladius.jpg

    default_loadout = db.relationship("ShipDefaultLoadout", back_populates="ship", cascade="all, delete-orphan")
    my_ships = db.relationship("MyShip", back_populates="ship")

    def __repr__(self):
        return f"<Ship {self.manufacturer} {self.name}>"


class Component(db.Model):
    __tablename__ = "components"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    component_type = db.Column(db.String(40))  # cooler / power_plant / shield_generator / quantum_drive
    size = db.Column(db.Integer)
    grade = db.Column(db.String(2))            # A / B / C / D
    class_ = db.Column("class", db.String(20)) # civilian / competition / industrial / military / stealth
    manufacturer = db.Column(db.String(80))
    stats = db.Column(db.JSON, nullable=True)  # type-specific stats dict

    def __repr__(self):
        return f"<Component {self.name} S{self.size} {self.grade}>"


class Weapon(db.Model):
    __tablename__ = "weapons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    weapon_type = db.Column(db.String(40))     # cannon / repeater / scattergun / distortion / missile_rack / etc.
    size = db.Column(db.Integer)
    mount_type = db.Column(db.String(20))      # fixed / gimbal / turret
    damage_type = db.Column(db.String(20))     # energy / ballistic / distortion
    manufacturer = db.Column(db.String(80))
    stats = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<Weapon {self.name} S{self.size}>"


class ShipDefaultLoadout(db.Model):
    __tablename__ = "ship_default_loadout"

    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey("ships.id"), nullable=False)
    slot_type = db.Column(db.String(40))       # cooler / power_plant / shield_generator / quantum_drive / weapon
    slot_number = db.Column(db.Integer, default=1)
    slot_size = db.Column(db.Integer)
    default_component_id = db.Column(db.Integer, db.ForeignKey("components.id"), nullable=True)
    default_weapon_id = db.Column(db.Integer, db.ForeignKey("weapons.id"), nullable=True)
    mount_type  = db.Column(db.String(20), nullable=True)   # pilot / remote_turret / manned_turret
    mount_group = db.Column(db.Integer, default=0)           # 0=pilot; 1+ = each distinct turret
    mount_label = db.Column(db.String(80), nullable=True)    # e.g. "Rear Remote Turret"

    ship = db.relationship("Ship", back_populates="default_loadout")
    default_component = db.relationship("Component")
    default_weapon = db.relationship("Weapon")

    def __repr__(self):
        return f"<ShipDefaultLoadout ship={self.ship_id} {self.slot_type}#{self.slot_number}>"


# ---------------------------------------------------------------------------
# User tables — personal data
# ---------------------------------------------------------------------------

class MyShip(db.Model):
    __tablename__ = "my_ships"

    id = db.Column(db.Integer, primary_key=True)
    ship_id = db.Column(db.Integer, db.ForeignKey("ships.id"), nullable=False)
    nickname = db.Column(db.String(80))
    notes = db.Column(db.Text)
    display_order = db.Column(db.Integer, nullable=True)

    ship = db.relationship("Ship", back_populates="my_ships")
    loadout = db.relationship("MyShipLoadout", back_populates="my_ship", cascade="all, delete-orphan")
    power_allocation = db.relationship("ShipPowerAllocation", back_populates="my_ship", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        label = self.nickname or (self.ship.name if self.ship else str(self.ship_id))
        return f"<MyShip {label}>"


class MyShipLoadout(db.Model):
    __tablename__ = "my_ship_loadout"

    id = db.Column(db.Integer, primary_key=True)
    my_ship_id = db.Column(db.Integer, db.ForeignKey("my_ships.id"), nullable=False)
    slot_type = db.Column(db.String(40))
    slot_number = db.Column(db.Integer, default=1)
    component_id = db.Column(db.Integer, db.ForeignKey("components.id"), nullable=True)
    weapon_id = db.Column(db.Integer, db.ForeignKey("weapons.id"), nullable=True)

    my_ship = db.relationship("MyShip", back_populates="loadout")
    component = db.relationship("Component")
    weapon = db.relationship("Weapon")

    def __repr__(self):
        return f"<MyShipLoadout ship={self.my_ship_id} {self.slot_type}#{self.slot_number}>"


class MyInventory(db.Model):
    __tablename__ = "my_inventory"

    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey("components.id"), nullable=True)
    weapon_id = db.Column(db.Integer, db.ForeignKey("weapons.id"), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    location = db.Column(db.String(120), default="storage")  # free text: "storage", "on ship", etc.
    notes = db.Column(db.Text)

    component = db.relationship("Component")
    weapon = db.relationship("Weapon")

    def __repr__(self):
        item = self.component or self.weapon
        return f"<MyInventory {item} x{self.quantity}>"


class ShipPowerAllocation(db.Model):
    __tablename__ = "ship_power_allocation"

    id = db.Column(db.Integer, primary_key=True)
    my_ship_id = db.Column(db.Integer, db.ForeignKey("my_ships.id"), nullable=False, unique=True)
    allocation_data = db.Column(db.JSON, nullable=False, default={})  # {"weapons": 5, "thrust": 4, "shields": 6, ...}

    my_ship = db.relationship("MyShip", back_populates="power_allocation")

    def __repr__(self):
        return f"<ShipPowerAllocation my_ship={self.my_ship_id}>"
