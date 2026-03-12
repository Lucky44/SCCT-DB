// Ship detail page — component picker + stats

let currentSlotId   = null;
let currentSlotType = null;
let currentItems    = [];
let currentCols     = [];
let sortColIdx      = -1;
let sortAsc         = true;
let selectedIds     = new Set();

const pickerModal        = new bootstrap.Modal(document.getElementById("pickerModal"));
const statsModal         = new bootstrap.Modal(document.getElementById("statsModal"));
const invWarningModal    = new bootstrap.Modal(document.getElementById("inventoryWarningModal"));
let pendingEquipArgs     = null;  // { componentId, weaponId } waiting on inventory confirm

// ── Picker column definitions ─────────────────────────────────────────────

// Each col: { label, key, stat (bool: value lives in item.stats), dec, customFmt }
// key "_cg" = combined class+grade display
const PICKER_COLS = {
  shield_generator: [
    { label: "Name",         key: "name",               stat: false },
    { label: "Cls/Grade",    key: "_cg",                stat: false },
    { label: "Shield HP",    key: "shield_hp",          stat: true  },
    { label: "Regen",        key: "shield_regen",       stat: true  },
    { label: "Dly (dmg)",    key: "regen_delay_damaged",stat: true, dec: 1 },
    { label: "Dly (dwn)",    key: "regen_delay_downed", stat: true, dec: 1 },
    { label: "Pwr (pips)",   key: "power_pips",         stat: false,
      customFmt: v => v ? `${v.min}–${v.max}` : "?" },
  ],
  quantum_drive: [
    { label: "Name",         key: "name",               stat: false },
    { label: "Cls/Grade",    key: "_cg",                stat: false },
    { label: "Speed (Mm/s)", key: "drive_speed",        stat: true,
      customFmt: v => v != null ? Math.round(v / 1e6) : "?" },
    { label: "Efficiency",   key: "fuel_requirement",   stat: true, dec: 4 },
  ],
  power_plant: [
    { label: "Name",         key: "name",               stat: false },
    { label: "Cls/Grade",    key: "_cg",                stat: false },
    { label: "Power Gen",    key: "power_generation",   stat: true  },
    { label: "Health",       key: "health",             stat: true  },
    { label: "EM",           key: "em_max",             stat: true  },
  ],
  cooler: [
    { label: "Name",         key: "name",               stat: false },
    { label: "Cls/Grade",    key: "_cg",                stat: false },
    { label: "Cooling",      key: "cooling_generation", stat: true  },
    { label: "Pwr (pips)",   key: "power_pips",         stat: false,
      customFmt: v => v ? `${v.min}–${v.max}` : "?" },
    { label: "Health",       key: "health",             stat: true  },
    { label: "EM",           key: "em_signature",       stat: true  },
    { label: "IR",           key: "ir_signature",       stat: true  },
  ],
  weapon: [
    { label: "Name",         key: "name",               stat: false },
    { label: "Type",         key: "type",               stat: false },
    { label: "Burst DPS",    key: "dps",                stat: false,
      customFmt: v => v != null ? Math.round(v) : "?" },
    { label: "Rnd Speed",    key: "speed",              stat: false,
      customFmt: v => v != null ? Math.round(v) : "?" },
  ],
};

function fmt(val, decimals = 0) {
  return val != null ? Number(val).toFixed(decimals) : "?";
}

function classGrade(item) {
  const cls = item.class ? item.class.charAt(0).toUpperCase() + item.class.slice(1) : null;
  return [cls, item.grade].filter(Boolean).join(" ");
}

function getRaw(item, col) {
  if (col.key === "_cg") return classGrade(item);
  return col.stat ? (item.stats || {})[col.key] : item[col.key];
}

function fmtCell(item, col) {
  const raw = getRaw(item, col);
  if (col.customFmt) return col.customFmt(raw);
  if (raw == null) return "?";
  if (typeof raw === "string") return raw;
  return Number(raw).toFixed(col.dec ?? 0);
}

function sortedItems() {
  if (sortColIdx < 0) return [...currentItems];
  const col = currentCols[sortColIdx];
  return [...currentItems].sort((a, b) => {
    let av = getRaw(a, col), bv = getRaw(b, col);
    if (av == null) av = sortAsc ? Infinity : -Infinity;
    if (bv == null) bv = sortAsc ? Infinity : -Infinity;
    if (typeof av === "string") return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortAsc ? av - bv : bv - av;
  });
}

function updateCompareBtn() {
  const btn = document.getElementById("compareBtn");
  if (!btn) return;
  const n = selectedIds.size;
  btn.textContent = n > 1 ? `Compare Selected (${n})` : "Compare Selected";
  btn.disabled = n < 2;
}

function renderPickerTable() {
  const body = document.getElementById("pickerBody");
  const items = sortedItems();
  const isWeapon = currentSlotType === "weapon";

  const headerCells = currentCols.map((col, i) => {
    const arrow = i === sortColIdx ? (sortAsc ? " ▲" : " ▼") : "";
    return `<th class="user-select-none" style="cursor:pointer;white-space:nowrap"
                onclick="toggleSort(${i})">${col.label}${arrow}</th>`;
  }).join("");

  const rows = items.map(item => {
    const checked = selectedIds.has(item.id) ? "checked" : "";
    const cells = currentCols.map(col => `<td>${fmtCell(item, col)}</td>`).join("");
    const equipFn = isWeapon ? `equipItem(null,${item.id})` : `equipItem(${item.id},null)`;
    return `<tr>
      <td><button class="btn btn-sm btn-warning py-0 px-2" onclick="${equipFn}">Equip</button></td>
      <td><input type="checkbox" class="form-check-input" data-id="${item.id}" ${checked}
                 onchange="onPickerCheck(this)"></td>
      ${cells}
    </tr>`;
  }).join("");

  body.innerHTML = `
    <div class="mb-2 d-flex gap-2 align-items-center">
      <button class="btn btn-sm btn-outline-secondary py-0" onclick="equipItem(null,null)">
        <i class="bi bi-x-circle me-1"></i>Clear slot
      </button>
      <button id="compareBtn" class="btn btn-outline-info btn-sm py-0" disabled onclick="showComparison()">Compare Selected</button>
    </div>
    <div class="table-responsive">
      <table class="table table-dark table-sm table-hover align-middle mb-0">
        <thead class="table-secondary">
          <tr><th></th><th></th>${headerCells}</tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function toggleSort(idx) {
  if (sortColIdx === idx) sortAsc = !sortAsc;
  else { sortColIdx = idx; sortAsc = true; }
  renderPickerTable();
}

function onPickerCheck(cb) {
  const id = parseInt(cb.dataset.id);
  if (cb.checked) selectedIds.add(id); else selectedIds.delete(id);
  updateCompareBtn();
}

function showComparison() {
  const items = currentItems.filter(i => selectedIds.has(i.id));
  const body  = document.getElementById("pickerBody");
  const isWeapon = currentSlotType === "weapon";

  const nameCols = items.map(item => `<th>${fmtCell(item, currentCols[0])}</th>`).join("");
  const statRows = currentCols.slice(1).map(col =>
    `<tr><td class="text-muted pe-3" style="white-space:nowrap">${col.label}</td>
         ${items.map(item => `<td>${fmtCell(item, col)}</td>`).join("")}</tr>`
  ).join("");
  const equipRow = items.map(item => {
    const fn = isWeapon ? `equipItem(null,${item.id})` : `equipItem(${item.id},null)`;
    return `<td><button class="btn btn-sm btn-warning py-0 px-2" onclick="${fn}">Equip</button></td>`;
  }).join("");

  body.innerHTML = `
    <button class="btn btn-sm btn-outline-secondary mb-3" onclick="showPickerList()">
      ← Back to list
    </button>
    <div class="table-responsive">
      <table class="table table-dark table-sm align-middle mb-0">
        <thead class="table-secondary"><tr><th></th>${nameCols}</tr></thead>
        <tbody>
          ${statRows}
          <tr><td></td>${equipRow}</tr>
        </tbody>
      </table>
    </div>`;
}

function showPickerList() {
  renderPickerTable();
}

async function openPicker(slotId, slotType, slotSize) {
  currentSlotId   = slotId;
  currentSlotType = slotType;
  selectedIds     = new Set();
  sortColIdx      = -1;
  sortAsc         = true;
  currentCols     = PICKER_COLS[slotType] || PICKER_COLS.weapon;

  const body = document.getElementById("pickerBody");
  body.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-warning"></div></div>';
  document.querySelector("#pickerModal .modal-title").textContent =
    slotType === "weapon" ? "Select Weapon" : `Select ${slotType.replace(/_/g, " ")}`;
  updateCompareBtn();
  pickerModal.show();

  const url = slotType === "weapon"
    ? `/api/weapons?size=${slotSize}`
    : `/api/components?type=${slotType}&size=${slotSize}`;

  const res = await fetch(url);
  currentItems = await res.json();

  if (!currentItems.length) {
    body.innerHTML = '<p class="text-muted">No items found for this slot.</p>';
    return;
  }
  renderPickerTable();
}

async function equipItem(componentId, weaponId) {
  if (currentSlotId === null) return;
  const res  = await fetch(`/api/loadout/${currentSlotId}/equip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ component_id: componentId || null, weapon_id: weaponId || null }),
  });
  const data = await res.json();

  if (data.status === "no_inventory") {
    pendingEquipArgs = { componentId, weaponId };
    document.getElementById("invWarnItemName").textContent = data.name;
    // Wire up the increase button with the correct item ids
    const btn = document.getElementById("invWarnIncrease");
    btn.onclick = () => confirmEquipWithIncrease(data.item_type, data.item_id, componentId, weaponId);
    pickerModal.hide();
    invWarningModal.show();
    return;
  }

  pickerModal.hide();
  location.reload();
}

async function confirmEquipWithIncrease(itemType, itemId, componentId, weaponId) {
  invWarningModal.hide();
  const payload = itemType === "component" ? { component_id: itemId } : { weapon_id: itemId };
  await fetch("/api/inventory/increment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  // Retry equip — inventory now has room
  const res  = await fetch(`/api/loadout/${currentSlotId}/equip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ component_id: componentId || null, weapon_id: weaponId || null }),
  });
  location.reload();
}

// ── Stats (right-click) ──────────────────────────────────────────────────────

const POWER_PLANT_STAT_LABELS = {
  power_generation:          "Power Generation",
  em_max:                    "EM Max",
  health:                    "Health",
  distortion_shutdown_damage:"Distortion Shutdown Damage",
  distortion_decay_delay:    "Distortion Decay Delay",
  distortion_decay_rate:     "Distortion Decay Rate",
  distortion_recovery_ratio: "Distortion Recovery Ratio",
  distortion_warning_ratio:  "Distortion Warning Ratio",
};

const SHIELD_STAT_LABELS = {
  shield_hp:                 "Shield HP",
  shield_regen:              "Shield Regen (per sec)",
  regen_delay_damaged:       "Regen Delay (damaged)",
  regen_delay_downed:        "Regen Delay (downed)",
  power_min:                 "Power Minimum",
  power_max:                 "Power Maximum",
  em_signature:              "EM Signature",
  ir_signature:              "IR Signature",
  health:                    "Health",
  distortion_shutdown_damage:"Distortion Shutdown Damage",
  distortion_decay_delay:    "Distortion Decay Delay",
  distortion_decay_rate:     "Distortion Decay Rate",
  distortion_recovery_ratio: "Distortion Recovery Ratio",
  distortion_warning_ratio:  "Distortion Warning Ratio",
};

const QUANTUM_DRIVE_STAT_LABELS = {
  spool_time:                "Spool Time (sec)",
  cooldown:                  "Cooldown (sec)",
  drive_speed:               "Drive Speed (m/s)",
  fuel_requirement:          "Fuel Requirement",
  health:                    "Health",
};

const COOLER_STAT_LABELS = {
  cooling_generation:        "Cooling Generation",
  power_min:                 "Power Minimum",
  power_max:                 "Power Maximum",
  em_signature:              "EM Signature",
  ir_signature:              "IR Signature",
  health:                    "Health",
  distortion_shutdown_damage:"Distortion Shutdown Damage",
  distortion_decay_delay:    "Distortion Decay Delay",
  distortion_decay_rate:     "Distortion Decay Rate",
  distortion_recovery_ratio: "Distortion Recovery Ratio",
  distortion_warning_ratio:  "Distortion Warning Ratio",
};

const WEAPON_STAT_LABELS = {
  dps:             "DPS",
  damage_per_shot: "Damage Per Shot",
  fire_rate:       "Fire Rate (RPM)",
  ammo_count:      "Ammo Count",
  range:           "Effective Range (m)",
  health:          "Health",
};

function buildStatsModal(titleEl, bodyEl, name, subtitle, manufacturer, stats, labels) {
  titleEl.textContent = name;
  const keys = Object.keys(labels).filter(k => stats[k] !== undefined && stats[k] !== null);
  if (!keys.length) {
    bodyEl.innerHTML = '<p class="text-muted">No detailed stats available.</p>';
    return;
  }
  const rows = keys.map(k => {
    const val = typeof stats[k] === "number"
      ? (Number.isInteger(stats[k]) ? stats[k] : stats[k].toFixed(2))
      : stats[k];
    return `<tr><td class="text-muted">${labels[k]}</td><td class="text-end fw-semibold">${val}</td></tr>`;
  }).join("");
  bodyEl.innerHTML = `
    <div class="mb-1 text-muted small">${subtitle || ""}</div>
    <div class="mb-2 text-muted small">${manufacturer || ""}</div>
    <table class="table table-sm table-borderless mb-0 w-auto">
      <tbody>${rows}</tbody>
    </table>`;
}

async function showStatsModal(componentId, weaponId) {
  const titleEl = document.getElementById("statsModalTitle");
  const bodyEl  = document.getElementById("statsModalBody");
  titleEl.textContent = "Loading…";
  bodyEl.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-warning"></div></div>';
  statsModal.show();

  if (componentId) {
    const res  = await fetch(`/api/component/${componentId}`);
    const comp = await res.json();
    const labelMap = {
      cooler:            COOLER_STAT_LABELS,
      power_plant:       POWER_PLANT_STAT_LABELS,
      shield_generator:  SHIELD_STAT_LABELS,
      quantum_drive:     QUANTUM_DRIVE_STAT_LABELS,
    };
    const subtitle = `S${comp.size} ${comp.grade || ""} ${comp.class || ""}`.trim();
    buildStatsModal(titleEl, bodyEl, comp.name, subtitle, comp.manufacturer, comp.stats || {}, labelMap[comp.type] || {});
  } else {
    const res    = await fetch(`/api/weapon/${weaponId}`);
    const weapon = await res.json();
    const subtitle = `S${weapon.size} ${weapon.type || ""} ${weapon.mount_type || ""}`.trim();
    buildStatsModal(titleEl, bodyEl, weapon.name, subtitle, weapon.manufacturer, weapon.stats || {}, WEAPON_STAT_LABELS);
  }
}

document.addEventListener("contextmenu", async (e) => {
  const compCard   = e.target.closest("[data-component-id]");
  const weaponCard = e.target.closest("[data-weapon-id]");
  if (!compCard && !weaponCard) return;
  e.preventDefault();
  showStatsModal(compCard?.dataset.componentId || null, weaponCard?.dataset.weaponId || null);
});
