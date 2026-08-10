"use strict";

const EQUIPMENT_SLOTS = [
  { id: "head", label: "Cabeça", symbol: "♜" },
  { id: "cape", label: "Capa", symbol: "◢" },
  { id: "neck", label: "Pescoço", symbol: "◇" },
  { id: "ammo", label: "Munição", symbol: "➹" },
  { id: "weapon", label: "Arma", symbol: "†" },
  { id: "body", label: "Torso", symbol: "♟" },
  { id: "shield", label: "Escudo", symbol: "⬙" },
  { id: "legs", label: "Pernas", symbol: "Ⅱ" },
  { id: "hands", label: "Mãos", symbol: "♧" },
  { id: "feet", label: "Pés", symbol: "⌁" },
  { id: "ring", label: "Anel", symbol: "○" },
];

const STORAGE_KEY = "osrs-loadout-value:v1";
const MAX_QUANTITY = 2_147_483_647;
const integerFormatter = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

const elements = {
  equipmentGrid: document.querySelector("#equipment-grid"),
  inventoryGrid: document.querySelector("#inventory-grid"),
  equipmentTotal: document.querySelector("#equipment-total"),
  inventoryTotal: document.querySelector("#inventory-total"),
  heroTotal: document.querySelector("#hero-total"),
  summaryTotal: document.querySelector("#summary-total"),
  summaryEquipment: document.querySelector("#summary-equipment"),
  summaryInventory: document.querySelector("#summary-inventory"),
  summaryCount: document.querySelector("#summary-count"),
  refreshButton: document.querySelector("#refresh-button"),
  clearButton: document.querySelector("#clear-button"),
  lastUpdate: document.querySelector("#last-update"),
  appMessage: document.querySelector("#app-message"),
  marketStatus: document.querySelector("#market-status"),
  headerStatus: document.querySelector(".header-status"),
  picker: document.querySelector("#item-picker"),
  pickerTitle: document.querySelector("#picker-title"),
  closePicker: document.querySelector("#close-picker"),
  itemSearch: document.querySelector("#item-search"),
  searchStatus: document.querySelector("#search-status"),
  itemResults: document.querySelector("#item-results"),
  removeItem: document.querySelector("#remove-item"),
};

let state = loadState();
let pickerTarget = null;
let searchTimer = null;
let valuationTimer = null;
let searchController = null;
let valuationSequence = 0;

function emptyState() {
  return {
    equipment: Object.fromEntries(EQUIPMENT_SLOTS.map((slot) => [slot.id, null])),
    inventory: Array.from({ length: 28 }, () => null),
  };
}

function sanitizeSelection(value) {
  if (!value || !Number.isInteger(value.id) || typeof value.name !== "string") {
    return null;
  }

  return {
    id: value.id,
    name: value.name,
    examine: typeof value.examine === "string" ? value.examine : "",
    members: Boolean(value.members),
    buy_limit: Number.isInteger(value.buy_limit) ? value.buy_limit : null,
    icon_url: typeof value.icon_url === "string" ? value.icon_url : "",
    high_price: Number.isInteger(value.high_price) ? value.high_price : null,
    low_price: Number.isInteger(value.low_price) ? value.low_price : null,
    price: Number.isInteger(value.price) ? value.price : null,
    quantity: clampQuantity(value.quantity),
  };
}

function loadState() {
  const fallback = emptyState();
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (!parsed || typeof parsed !== "object") return fallback;

    for (const slot of EQUIPMENT_SLOTS) {
      const selection = sanitizeSelection(parsed.equipment?.[slot.id]);
      fallback.equipment[slot.id] = selection
        ? { ...selection, quantity: slot.id === "ammo" ? selection.quantity : 1 }
        : null;
    }
    if (Array.isArray(parsed.inventory)) {
      fallback.inventory = fallback.inventory.map((_, index) =>
        sanitizeSelection(parsed.inventory[index]),
      );
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
  return fallback;
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function clampQuantity(value) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(MAX_QUANTITY, Math.max(1, parsed));
}

function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatCoins(value) {
  return integerFormatter.format(Number.isFinite(value) ? value : 0);
}

function formatCompact(value) {
  const amount = Number.isFinite(value) ? value : 0;
  const absolute = Math.abs(amount);
  if (absolute >= 1_000_000_000) {
    return `${formatDecimal(amount / 1_000_000_000)} bi`;
  }
  if (absolute >= 1_000_000) {
    return `${formatDecimal(amount / 1_000_000)} mi`;
  }
  if (absolute >= 10_000) {
    return `${formatDecimal(amount / 1_000)} mil`;
  }
  return formatCoins(amount);
}

function formatDecimal(value) {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: value < 10 ? 1 : 0,
    maximumFractionDigits: 1,
  }).format(value);
}

function allSelections() {
  return [
    ...Object.values(state.equipment).filter(Boolean),
    ...state.inventory.filter(Boolean),
  ];
}

function selectionFor(target) {
  if (!target) return null;
  return target.area === "equipment"
    ? state.equipment[target.slot]
    : state.inventory[Number(target.slot)];
}

function setSelection(target, value) {
  if (target.area === "equipment") {
    state.equipment[target.slot] = value;
  } else {
    state.inventory[Number(target.slot)] = value;
  }
}

function makeItemImage(item, className) {
  const image = createElement("img", className);
  image.src = item.icon_url;
  image.alt = "";
  image.loading = "lazy";
  image.addEventListener("error", () => {
    image.hidden = true;
    const fallback = createElement("span", "slot-placeholder", "?");
    image.parentElement?.append(fallback);
  }, { once: true });
  return image;
}

function buildSlot(target, definition, item) {
  const wrapper = createElement(
    "div",
    target.area === "equipment" ? "equipment-slot" : "inventory-slot",
  );
  if (target.area === "equipment") wrapper.dataset.position = target.slot;

  const button = createElement("button", "slot-select");
  button.type = "button";
  button.addEventListener("click", () => openPicker(target));

  if (item) {
    button.classList.add("is-filled");
    button.setAttribute(
      "aria-label",
      `${definition.label}: ${item.name}. Clique para trocar o item.`,
    );
    button.title = `${item.name}\n${item.examine || ""}`.trim();
    button.append(makeItemImage(item, "slot-image"));

    const label = createElement("span", "slot-label", item.name);
    button.append(label);

    const subtotal = item.price === null ? null : item.price * item.quantity;
    const price = createElement(
      "span",
      "slot-price",
      subtotal === null ? "sem preço" : `${formatCompact(subtotal)} gp`,
    );
    button.append(price);

    const acceptsQuantity = target.area === "inventory" || target.slot === "ammo";
    if (acceptsQuantity) {
      const quantity = createElement("input", "quantity-input");
      quantity.type = "number";
      quantity.min = "1";
      quantity.max = String(MAX_QUANTITY);
      quantity.value = String(item.quantity);
      quantity.inputMode = "numeric";
      quantity.setAttribute("aria-label", `Quantidade de ${item.name}`);
      quantity.title = "Quantidade";
      quantity.addEventListener("click", (event) => event.stopPropagation());
      quantity.addEventListener("change", () => {
        item.quantity = clampQuantity(quantity.value);
        quantity.value = String(item.quantity);
        saveState();
        render();
        scheduleValuation();
      });
      wrapper.append(quantity);
    }
  } else {
    button.setAttribute(
      "aria-label",
      `${definition.label}: posição vazia. Clique para escolher um item.`,
    );
    button.append(createElement("span", "slot-placeholder", definition.symbol));
    button.append(createElement("span", "slot-label", definition.label));
    if (target.area === "inventory") {
      button.append(createElement("span", "inventory-index", definition.index));
    }
  }

  wrapper.prepend(button);
  return wrapper;
}

function render() {
  elements.equipmentGrid.replaceChildren();
  for (const slot of EQUIPMENT_SLOTS) {
    const target = { area: "equipment", slot: slot.id, label: slot.label };
    elements.equipmentGrid.append(
      buildSlot(target, slot, state.equipment[slot.id]),
    );
  }

  elements.inventoryGrid.replaceChildren();
  state.inventory.forEach((item, index) => {
    const definition = {
      label: `Inventário ${index + 1}`,
      symbol: "+",
      index: String(index + 1).padStart(2, "0"),
    };
    const target = {
      area: "inventory",
      slot: String(index),
      label: `posição ${index + 1} do inventário`,
    };
    elements.inventoryGrid.append(buildSlot(target, definition, item));
  });

  renderOptimisticTotals();
}

function renderOptimisticTotals() {
  const equipmentTotal = Object.values(state.equipment).reduce(
    (total, item) => total + (item?.price ?? 0) * (item?.quantity ?? 1),
    0,
  );
  const inventoryTotal = state.inventory.reduce(
    (total, item) => total + (item?.price ?? 0) * (item?.quantity ?? 1),
    0,
  );
  applyTotals(equipmentTotal, inventoryTotal);
}

function applyTotals(equipmentTotal, inventoryTotal) {
  const total = equipmentTotal + inventoryTotal;
  const count = allSelections().length;
  elements.equipmentTotal.textContent = `${formatCompact(equipmentTotal)} gp`;
  elements.inventoryTotal.textContent = `${formatCompact(inventoryTotal)} gp`;
  elements.heroTotal.textContent = formatCoins(total);
  elements.summaryTotal.textContent = formatCoins(total);
  elements.summaryEquipment.textContent = `${formatCoins(equipmentTotal)} gp`;
  elements.summaryInventory.textContent = `${formatCoins(inventoryTotal)} gp`;
  elements.summaryCount.textContent = `${count} / 39`;
}

function openPicker(target) {
  pickerTarget = target;
  const current = selectionFor(target);
  elements.pickerTitle.textContent = `Item para ${target.label}`;
  elements.removeItem.hidden = !current;
  elements.itemSearch.value = "";
  elements.picker.showModal();
  searchItems("");
  window.setTimeout(() => elements.itemSearch.focus(), 40);
}

function closePicker() {
  if (elements.picker.open) elements.picker.close();
  searchController?.abort();
  pickerTarget = null;
}

function chooseItem(item) {
  if (!pickerTarget) return;
  setSelection(pickerTarget, { ...item, quantity: 1 });
  saveState();
  closePicker();
  render();
  scheduleValuation(0);
}

function removeCurrentItem() {
  if (!pickerTarget) return;
  setSelection(pickerTarget, null);
  saveState();
  closePicker();
  render();
  scheduleValuation(0);
}

async function fetchJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Não foi possível conectar à aplicação.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // The status message below remains useful even when a proxy returns HTML.
  }

  if (!response.ok) {
    throw new Error(payload?.detail || `A consulta falhou (${response.status}).`);
  }
  return payload;
}

async function searchItems(query) {
  searchController?.abort();
  searchController = new AbortController();
  elements.itemResults.replaceChildren(
    createElement("div", "result-loading", "Consultando a Grand Exchange…"),
  );
  elements.searchStatus.textContent = query ? "Buscando…" : "Itens populares";

  try {
    const params = new URLSearchParams({ q: query.trim(), limit: "40" });
    const data = await fetchJson(`/api/items?${params}`, {
      signal: searchController.signal,
    });
    renderSearchResults(data.items);
    elements.searchStatus.textContent = query.trim()
      ? `${data.total} resultado${data.total === 1 ? "" : "s"} encontrado${data.total === 1 ? "" : "s"}`
      : "Itens populares e catálogo em ordem alfabética";
    updateTimestamp(data.as_of);
    setMarketStatus("Mercado conectado", false);
  } catch (error) {
    if (error.name === "AbortError") return;
    elements.itemResults.replaceChildren(
      createElement("div", "result-empty", error.message),
    );
    elements.searchStatus.textContent = "Falha na consulta";
    setMarketStatus("Mercado indisponível", true);
  }
}

function renderSearchResults(items) {
  elements.itemResults.replaceChildren();
  if (!items.length) {
    elements.itemResults.append(
      createElement("div", "result-empty", "Nenhum item encontrado. Tente outro nome."),
    );
    return;
  }

  for (const item of items) {
    const button = createElement("button", "item-result");
    button.type = "button";
    button.addEventListener("click", () => chooseItem(item));

    const imageWrap = createElement("span", "result-image-wrap");
    imageWrap.append(makeItemImage(item, ""));

    const main = createElement("span", "result-main");
    const nameRow = createElement("span", "result-name-row");
    nameRow.append(createElement("span", "result-name", item.name));
    if (item.members) nameRow.append(createElement("span", "members-badge", "P2P"));
    main.append(nameRow);
    main.append(
      createElement("span", "result-examine", item.examine || "Sem descrição."),
    );

    const price = createElement("span", "result-price");
    price.append(
      createElement(
        "strong",
        "",
        item.price === null ? "Sem preço" : `${formatCoins(item.price)} gp`,
      ),
    );
    const high = item.high_price === null ? "—" : formatCompact(item.high_price);
    const low = item.low_price === null ? "—" : formatCompact(item.low_price);
    price.append(createElement("small", "", `compra ${high} · venda ${low}`));

    button.append(imageWrap, main, price);
    elements.itemResults.append(button);
  }
}

function buildPayload() {
  const items = [];
  for (const slot of EQUIPMENT_SLOTS) {
    const item = state.equipment[slot.id];
    if (item) {
      items.push({
        item_id: item.id,
        quantity: slot.id === "ammo" ? item.quantity : 1,
        area: "equipment",
        slot: slot.id,
      });
    }
  }
  state.inventory.forEach((item, index) => {
    if (item) {
      items.push({
        item_id: item.id,
        quantity: item.quantity,
        area: "inventory",
        slot: String(index),
      });
    }
  });
  return { items };
}

function scheduleValuation(delay = 180) {
  // Immediately invalidate a request for the previous state, even while this
  // update is waiting for the debounce timer.
  valuationSequence += 1;
  window.clearTimeout(valuationTimer);
  valuationTimer = window.setTimeout(calculateValue, delay);
}

async function calculateValue() {
  const payload = buildPayload();
  if (!payload.items.length) {
    applyTotals(0, 0);
    elements.lastUpdate.textContent = "Adicione um item para calcular.";
    hideMessage();
    return;
  }

  const sequence = ++valuationSequence;
  elements.refreshButton.disabled = true;
  elements.refreshButton.textContent = "Atualizando…";
  setMarketStatus("Atualizando preços…", false);

  try {
    const data = await fetchJson("/api/loadout/value", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (sequence !== valuationSequence) return;

    for (const line of data.items) {
      const target = { area: line.area, slot: line.slot };
      const current = selectionFor(target);
      if (current) {
        setSelection(target, { ...current, ...line, quantity: line.quantity });
      }
    }
    saveState();
    render();
    applyTotals(data.equipment_total, data.inventory_total);
    updateTimestamp(data.as_of, data.unpriced_lines);
    hideMessage();
    setMarketStatus("Mercado conectado", false);
  } catch (error) {
    if (sequence !== valuationSequence) return;
    showMessage(error.message);
    setMarketStatus("Falha ao atualizar", true);
  } finally {
    if (sequence === valuationSequence) {
      elements.refreshButton.disabled = false;
      elements.refreshButton.textContent = "Atualizar preços";
    }
  }
}

async function warmMarket() {
  setMarketStatus("Conectando ao mercado…", false);
  try {
    const data = await fetchJson("/api/items?limit=1");
    updateTimestamp(data.as_of);
    setMarketStatus("Mercado conectado", false);
  } catch (error) {
    showMessage(error.message);
    setMarketStatus("Mercado indisponível", true);
  }
}

function updateTimestamp(timestamp, unpricedLines = 0) {
  if (!timestamp) return;
  const date = new Date(timestamp * 1000);
  const formatted = date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  elements.lastUpdate.textContent = `Última negociação: ${formatted}.${
    unpricedLines ? ` ${unpricedLines} item(ns) sem preço recente.` : ""
  }`;
}

function setMarketStatus(text, isError) {
  elements.marketStatus.textContent = text;
  elements.headerStatus.classList.toggle("is-error", isError);
}

function showMessage(message) {
  elements.appMessage.textContent = message;
  elements.appMessage.hidden = false;
}

function hideMessage() {
  elements.appMessage.hidden = true;
  elements.appMessage.textContent = "";
}

elements.itemSearch.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => searchItems(elements.itemSearch.value), 260);
});

elements.closePicker.addEventListener("click", closePicker);
elements.removeItem.addEventListener("click", removeCurrentItem);
elements.picker.addEventListener("click", (event) => {
  if (event.target === elements.picker) closePicker();
});
elements.picker.addEventListener("close", () => {
  searchController?.abort();
  pickerTarget = null;
});

elements.refreshButton.addEventListener("click", calculateValue);
elements.clearButton.addEventListener("click", () => {
  if (allSelections().length && !window.confirm("Limpar todo o equipamento e inventário?")) {
    return;
  }
  valuationSequence += 1;
  window.clearTimeout(valuationTimer);
  state = emptyState();
  saveState();
  render();
  hideMessage();
  elements.lastUpdate.textContent = "Adicione um item para calcular.";
});

render();
if (allSelections().length) {
  calculateValue();
} else {
  warmMarket();
}
