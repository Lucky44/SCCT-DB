/**
 * Power Allocation Graph
 * Handles rendering and interaction with the ship's power allocation visualization
 */

// Global state
let powerGraphState = {
  systems: [],
  totalGeneration: 0,
  maxDrawPerSystem: {},
  allocation: {},
  myShipId: null
};

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("power-graph");
  if (!container) return;

  // Extract data from data attributes
  const data = {
    totalGeneration: parseFloat(container.dataset.totalGeneration) || 0,
    currentAllocation: JSON.parse(container.dataset.allocation || "{}"),
    maxDrawPerSystem: JSON.parse(container.dataset.maxDraw || "{}"),
    myShipId: parseInt(container.dataset.myShipId) || null
  };

  // Initialize state
  powerGraphState.totalGeneration = data.totalGeneration;
  powerGraphState.allocation = { ...data.currentAllocation };
  powerGraphState.maxDrawPerSystem = data.maxDrawPerSystem;
  powerGraphState.myShipId = data.myShipId;
  
  // Define systems in order
  powerGraphState.systems = [
    "weapons",
    "thrust",
    "shields",
    "quantum_drive",
    "radar",
    "life_support",
    // ...coolers added dynamically
  ];
  
  // Add coolers to systems list
  Object.keys(data.currentAllocation).forEach(key => {
    if (key.startsWith("cooler_")) {
      powerGraphState.systems.push(key);
    }
  });

  renderPowerGraph();
});

function renderPowerGraph() {
  const svg = document.getElementById("power-graph");
  if (!svg) return;

  // Clear existing graph
  svg.innerHTML = "";

  const pipHeight = 13;  // fixed pip height — same visual size on every ship

  const totalPips = Math.ceil(powerGraphState.totalGeneration);
  const systemNames = powerGraphState.systems;

  const marginTop = 10;
  const marginBottom = 36;
  const marginLeft = 0;
  const marginRight = 0;
  const columnWidth = 70;
  const graphWidth = systemNames.length * columnWidth;
  const width = graphWidth + marginLeft + marginRight;

  // SVG height driven by the tallest column, not the total power pool
  const maxColumnPips = Math.max(...systemNames.map(s => Math.ceil(powerGraphState.maxDrawPerSystem[s] || 0)));
  const actualGraphHeight = maxColumnPips * pipHeight;
  const actualTotalHeight = Math.ceil(actualGraphHeight + marginTop + marginBottom);
  svg.setAttribute("height", actualTotalHeight);
  svg.setAttribute("viewBox", `0 0 ${width} ${actualTotalHeight}`);

  // Draw each system column
  systemNames.forEach((systemName, index) => {
    const x = marginLeft + index * columnWidth;
    const columnGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    
    // Get system label and max draw
    const systemLabel = formatSystemName(systemName);
    const maxDraw = powerGraphState.maxDrawPerSystem[systemName] || 0;
    const maxPips = Math.ceil(maxDraw);
    const allocatedPips = powerGraphState.allocation[systemName] || 0;

    // Draw column background
    const colBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    colBg.setAttribute("x", x + 3);
    colBg.setAttribute("y", marginTop);
    colBg.setAttribute("width", columnWidth - 6);
    colBg.setAttribute("height", actualGraphHeight);
    colBg.setAttribute("fill", "#1a1a1a");
    colBg.setAttribute("stroke", "#333");
    columnGroup.appendChild(colBg);

    // Determine if column is unpowered (warning state)
    const isUnpowered = allocatedPips === 0 && maxPips > 0;
    const colBorder = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    colBorder.setAttribute("x", x + 3);
    colBorder.setAttribute("y", marginTop);
    colBorder.setAttribute("width", columnWidth - 6);
    colBorder.setAttribute("height", actualGraphHeight);
    colBorder.setAttribute("fill", "none");
    colBorder.setAttribute("stroke", isUnpowered ? "#cc3333" : "#555");
    colBorder.setAttribute("stroke-width", isUnpowered ? "2" : "1");
    columnGroup.appendChild(colBorder);

    // Draw pips (from bottom to top)
    for (let pip = 0; pip < maxPips; pip++) {
      const pipY = marginTop + actualGraphHeight - (pip + 1) * pipHeight;
      const pipX = x + 3 + (columnWidth - 6) * 0.1;
      const pipW = (columnWidth - 6) * 0.8;
      const pipH = Math.min((pipHeight - 2) * 2, pipHeight - 0.5);

      const pipRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      pipRect.setAttribute("x", pipX);
      pipRect.setAttribute("y", pipY);
      pipRect.setAttribute("width", pipW);
      pipRect.setAttribute("height", pipH);
      pipRect.setAttribute("fill", pip < allocatedPips ? "#ffc107" : "#444");
      pipRect.setAttribute("stroke", pip < allocatedPips ? "#ff9800" : "#666");
      pipRect.setAttribute("stroke-width", "1");
      pipRect.setAttribute("class", "power-pip");
      pipRect.setAttribute("data-system", systemName);
      pipRect.setAttribute("data-pip-index", pip);
      pipRect.style.cursor = "pointer";
      
      // Add click handler
      pipRect.addEventListener("click", () => togglePip(systemName, pip));
      
      columnGroup.appendChild(pipRect);
    }

    // Draw system label at bottom
    const labelText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    labelText.setAttribute("x", x + columnWidth / 2);
    labelText.setAttribute("y", marginTop + actualGraphHeight + 17);
    labelText.setAttribute("text-anchor", "middle");
    labelText.setAttribute("font-size", "11");
    labelText.setAttribute("fill", "#999");
    labelText.style.fontSize = "11px";
    labelText.textContent = systemLabel;
    columnGroup.appendChild(labelText);

    // Draw max draw value below label
    const drawText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    drawText.setAttribute("x", x + columnWidth / 2);
    drawText.setAttribute("y", marginTop + actualGraphHeight + 28);
    drawText.setAttribute("text-anchor", "middle");
    drawText.setAttribute("font-size", "11");
    drawText.setAttribute("fill", "#666");
    drawText.style.fontSize = "11px";
    drawText.textContent = `${maxPips}p`;
    columnGroup.appendChild(drawText);

    svg.appendChild(columnGroup);
  });

  // Update remaining pips display
  updateRemainingDisplay();
}

function togglePip(systemName, pipIndex) {
  const currentAlloc = powerGraphState.allocation[systemName] || 0;
  const remainingPips = calculateRemainingPips();

  if (pipIndex < currentAlloc) {
    // Clicked a yellow pip — deallocate down to this level
    powerGraphState.allocation[systemName] = pipIndex;
  } else {
    // Clicked a gray pip — allocate up to and including this pip
    const pipsToAdd = (pipIndex + 1) - currentAlloc;
    if (remainingPips >= pipsToAdd) {
      powerGraphState.allocation[systemName] = pipIndex + 1;
    }
  }

  renderPowerGraph();
  savePowerAllocation();
}

function calculateRemainingPips() {
  const totalPips = Math.ceil(powerGraphState.totalGeneration);
  const usedPips = Object.values(powerGraphState.allocation).reduce((sum, val) => sum + (val || 0), 0);
  return totalPips - usedPips;
}

function updateRemainingDisplay() {
  const remaining = calculateRemainingPips();
  const total = Math.ceil(powerGraphState.totalGeneration);
  const displayEl = document.getElementById("power-remaining");
  if (displayEl) {
    displayEl.textContent = `${total - remaining}`;
  }
}

function formatSystemName(name) {
  const nameMap = {
    "weapons": "Weapons",
    "thrust": "Thrust",
    "shields": "Shields",
    "quantum_drive": "QD",
    "radar": "Radar",
    "life_support": "Life Sup.",
  };
  
  if (nameMap[name]) {
    return nameMap[name];
  }
  
  if (name.startsWith("cooler_")) {
    const idx = parseInt(name.split("_")[1]);
    return `Cooler ${String.fromCharCode(65 + idx)}`; // A, B, C, ...
  }
  
  return name.replace(/_/g, " ");
}

async function savePowerAllocation() {
  if (!powerGraphState.myShipId) return;

  try {
    const response = await fetch(`/my-hangar/${powerGraphState.myShipId}/power/save`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        allocation: powerGraphState.allocation
      })
    });

    if (!response.ok) {
      console.error("Failed to save power allocation");
    }
  } catch (error) {
    console.error("Error saving power allocation:", error);
  }
}

async function resetPowerAllocation() {
  if (!powerGraphState.myShipId) return;

  try {
    const response = await fetch(`/my-hangar/${powerGraphState.myShipId}/power/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      }
    });

    if (response.ok) {
      const data = await response.json();
      powerGraphState.allocation = data.allocation;
      renderPowerGraph();
    } else {
      console.error("Failed to reset power allocation");
    }
  } catch (error) {
    console.error("Error resetting power allocation:", error);
  }
}
