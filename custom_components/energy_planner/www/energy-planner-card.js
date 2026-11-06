/*
 * Energy Planner Lovelace card
 * @customElement energy-planner-card
 * @version 1.0.0
 * @description Dependency-free, read-only price view with an explicit plan-only form.
 * Configure at least: { type: "custom:energy-planner-card", price_sensor: "sensor..." }.
 */

(function () {
  "use strict";

  const DOMAIN = "energy_planner";
  const SERVICE = "plan_appliance";
  const DEFAULT_CURRENCY = "EUR";
  const DEFAULT_CONFIG = {
    title: "Energy Planner",
    price_mode: "all_in",
    currency: DEFAULT_CURRENCY,
    show_spot: true,
    fixed_cost_sensor: "",
    last_plan_sensor: "",
    history_sensor: "",
  };

  const CSS = `
    :host { display: block; color: var(--primary-text-color); }
    ha-card { overflow: hidden; }
    .wrap { padding: 16px; }
    h2, h3, p { margin: 0; }
    h2 { font-size: 1.15rem; margin-bottom: 8px; }
    h3 { font-size: 1rem; margin: 18px 0 8px; }
    .muted { color: var(--secondary-text-color); font-size: .85rem; }
    .status { display: inline-block; padding: 3px 8px; border-radius: 999px;
      background: var(--secondary-background-color); font-size: .78rem; }
    .summary, .plan { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
    .metric { padding: 10px; border-radius: 8px; background: var(--secondary-background-color); }
    .metric strong { display: block; font-size: 1.1rem; margin-top: 3px; }
    .timeline { margin-top: 4px; }
    .price-chart { display: block; width: 100%; height: auto; min-height: 170px; overflow: visible; }
    .chart-grid { stroke: var(--divider-color); stroke-width: 1; stroke-dasharray: 2 4; }
    .chart-axis { fill: var(--secondary-text-color); font-size: 11px; }
    .chart-area { fill: var(--accent-color); opacity: .14; }
    .chart-line { fill: none; stroke: var(--accent-color); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
    .chart-spot-line { fill: none; stroke: var(--secondary-text-color); stroke-width: 1.7; stroke-dasharray: 5 4; stroke-linecap: round; stroke-linejoin: round; }
    .chart-current { stroke: var(--primary-color); stroke-width: 1.5; stroke-dasharray: 4 3; }
    .chart-dot { fill: var(--accent-color); stroke: var(--card-background-color); stroke-width: 1; opacity: .9; }
    .chart-current-dot { fill: var(--primary-color); stroke: var(--card-background-color); stroke-width: 2; }
    .chart-legend { display: flex; flex-wrap: wrap; gap: 10px 14px; margin: 2px 0 4px; }
    .legend-item { display: inline-flex; align-items: center; gap: 5px; font-size: .78rem; color: var(--secondary-text-color); }
    .legend-key { width: 18px; height: 3px; border-radius: 2px; background: var(--accent-color); }
    .legend-key.spot { height: 0; border-top: 2px dashed var(--secondary-text-color); background: transparent; }
    .chart-note { margin-top: 2px; }
    details { margin-top: 18px; }
    details > summary { display: flex; align-items: center; justify-content: space-between; gap: 8px;
      cursor: pointer; font-size: 1rem; font-weight: 500; }
    details > summary::marker { color: var(--secondary-text-color); }
    details[open] > summary { margin-bottom: 8px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    form { display: grid; gap: 9px; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); }
    label { display: grid; gap: 4px; font-size: .8rem; }
    input { box-sizing: border-box; width: 100%; padding: 8px; color: inherit;
      background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 4px; }
    button { padding: 9px 12px; border: 0; border-radius: 5px; color: var(--text-primary-color, #fff);
      background: var(--primary-color); cursor: pointer; font: inherit; }
    button[disabled] { opacity: .55; cursor: wait; }
    .form-note, .message { margin-top: 8px; }
    .error { color: var(--error-color); }
  `;

  function make(tag, text, className) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function attributes(hass, entityId) {
    return (entityId && hass && hass.states && hass.states[entityId])
      ? (hass.states[entityId].attributes || {})
      : {};
  }

  function stateValue(hass, entityId) {
    const state = entityId && hass && hass.states && hass.states[entityId];
    return state && state.state !== "unknown" && state.state !== "unavailable"
      ? state.state
      : null;
  }

  function formatPrice(value, currency) {
    const parsed = number(value);
    return parsed === null ? "—" : `${parsed.toFixed(3)} ${currency}/kWh`;
  }

  function formatMoney(value, currency) {
    const parsed = number(value);
    return parsed === null ? "—" : `${parsed.toFixed(2)} ${currency}`;
  }

  function formatTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  function formatModelStatus(value) {
    return {
      complete: "Complete",
      battery_aware: "Battery aware",
      price_only: "Price only",
      unavailable: "Unavailable",
    }[value] || String(value || "Unavailable").replace(/_/g, " ");
  }

  function formatChartTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function svgElement(tag, attributes) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes || {}).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
    });
    return element;
  }

  function localDateTime(date) {
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
      + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  class EnergyPlannerCard extends HTMLElement {
    constructor() {
      super();
      this._config = null;
      this._hass = null;
      this._root = this.attachShadow({ mode: "open" });
      // This is also the safe first paint while Lovelace is attaching hass.
      this._renderMessage("Energy Planner is loading…");
    }

    setConfig(config) {
      if (!config || typeof config !== "object" || !config.price_sensor) {
        throw new Error("energy-planner-card requires a price_sensor");
      }
      this._config = { ...DEFAULT_CONFIG, ...config };
      this._render();
    }

    set hass(value) {
      this._hass = value;
      this._render();
    }

    get hass() { return this._hass; }

    _renderMessage(message, error) {
      this._root.replaceChildren(make("style", CSS));
      const card = make("ha-card");
      const wrap = make("div", undefined, "wrap");
      wrap.append(make("h2", this._config?.title || DEFAULT_CONFIG.title));
      wrap.append(make("p", message, error ? "message error" : "message muted"));
      card.append(wrap);
      this._root.append(card);
    }

    _render() {
      if (!this._config) return;
      if (!this._hass) return this._renderMessage("Waiting for Home Assistant…");

      const priceAttrs = attributes(this._hass, this._config.price_sensor);
      const points = Array.isArray(priceAttrs.data) ? priceAttrs.data : [];
      const fixedAttrs = attributes(this._hass, this._config.fixed_cost_sensor);
      const lastAttrs = attributes(this._hass, this._config.last_plan_sensor);
      const historyAttrs = attributes(this._hass, this._config.history_sensor);
      const fixed = stateValue(this._hass, this._config.fixed_cost_sensor)
        ?? priceAttrs.fixed_monthly_cost ?? fixedAttrs.fixed_monthly_cost;
      const modelStatus = priceAttrs.model_status || lastAttrs.model_status || "unavailable";
      const mode = this._config.price_mode === "spot" ? "spot_price_per_kwh" : "price_per_kwh";

      this._root.replaceChildren(make("style", CSS));
      const card = make("ha-card");
      const wrap = make("div", undefined, "wrap");
      const heading = make("h2", this._config.title);
      heading.append(make("span", `  ${formatModelStatus(modelStatus)}`, "status"));
      wrap.append(heading);
      wrap.append(make("p", points.length ? `Source: ${priceAttrs.source_entity || this._config.price_sensor}` : "No price timeline is available yet.", "muted"));

      const summary = make("div", undefined, "summary");
      const current = priceAttrs.current_all_in_price ?? priceAttrs.current_spot_price;
      summary.append(this._metric("Current", formatPrice(this._config.price_mode === "spot" ? priceAttrs.current_spot_price : current, this._config.currency)));
      summary.append(this._metric("Fixed monthly", formatMoney(fixed, this._config.currency)));
      summary.append(this._metric("Updated", formatTime(priceAttrs.last_updated)));
      wrap.append(summary);

      wrap.append(make("h3", "Price timeline"));
      wrap.append(this._timeline(points, mode));
      wrap.append(make("p", "Prices are informational; this card never starts or schedules a device.", "muted"));

      wrap.append(make("h3", "Latest plan"));
      wrap.append(this._planContext(lastAttrs, historyAttrs));
      const planner = document.createElement("details");
      const plannerSummary = document.createElement("summary");
      plannerSummary.append(make("span", "Plan an appliance"), make("span", "Plan only", "status"));
      planner.append(plannerSummary, this._planForm());
      wrap.append(planner);
      card.append(wrap);
      this._root.append(card);
    }

    _metric(label, value) {
      const metric = make("div", undefined, "metric");
      metric.append(make("span", label, "muted"), make("strong", value));
      return metric;
    }

    _timeline(points, key) {
      if (!points.length) return make("p", "Waiting for price data…", "message muted");
      const timeline = make("div", undefined, "timeline");
      const mainSeries = points.slice(0, 192).map((point) => ({
        point,
        value: number(point[key]),
        spot: number(point.spot_price_per_kwh),
      })).filter((item) => item.value !== null);
      if (!mainSeries.length) return make("p", "Waiting for price data…", "message muted");

      const showSpot = this._config.show_spot && key !== "spot_price_per_kwh"
        && mainSeries.some((item) => item.spot !== null);
      const plottedValues = mainSeries.flatMap((item) => (
        showSpot && item.spot !== null ? [item.value, item.spot] : [item.value]
      ));
      const min = Math.min(...plottedValues);
      const max = Math.max(...plottedValues);
      const width = 720;
      const height = 210;
      const left = 50;
      const right = 12;
      const top = 14;
      const bottom = 34;
      const plotWidth = width - left - right;
      const plotHeight = height - top - bottom;
      const x = (index) => left + (index / Math.max(1, mainSeries.length - 1)) * plotWidth;
      const y = (value) => top + ((max - value) / (max - min || 1)) * plotHeight;
      const mainPath = mainSeries.map((item, index) => `${index ? "L" : "M"}${x(index)} ${y(item.value)}`).join(" ");
      const areaPath = `${mainPath} L${x(mainSeries.length - 1)} ${top + plotHeight} L${x(0)} ${top + plotHeight} Z`;
      const svg = svgElement("svg", {
        class: "price-chart",
        viewBox: `0 0 ${width} ${height}`,
        role: "img",
        "aria-label": `Price chart with ${mainSeries.length} points from ${formatPrice(min, this._config.currency)} to ${formatPrice(max, this._config.currency)}`,
      });
      const title = svgElement("title");
      title.textContent = "Electricity price timeline";
      svg.append(title);

      for (let tick = 0; tick <= 3; tick += 1) {
        const value = max - ((max - min) * tick / 3);
        const yPosition = top + (plotHeight * tick / 3);
        svg.append(
          svgElement("line", { class: "chart-grid", x1: left, x2: width - right, y1: yPosition, y2: yPosition }),
          svgElement("text", { class: "chart-axis", x: left - 8, y: yPosition + 4, "text-anchor": "end" }),
        );
        svg.lastChild.textContent = value.toFixed(3);
      }

      const tickIndexes = [...new Set([0, Math.floor((mainSeries.length - 1) / 3), Math.floor((mainSeries.length - 1) * 2 / 3), mainSeries.length - 1])];
      tickIndexes.forEach((index) => {
        const label = svgElement("text", { class: "chart-axis", x: x(index), y: height - 10, "text-anchor": "middle" });
        label.textContent = formatChartTime(mainSeries[index].point.start_time);
        svg.append(label);
      });

      svg.append(svgElement("path", { class: "chart-area", d: areaPath }));
      if (showSpot) {
        const spotSeries = mainSeries
          .map((item, index) => ({ ...item, index }))
          .filter((item) => item.spot !== null);
        const spotPath = spotSeries
          .map((item, index) => `${index ? "L" : "M"}${x(item.index)} ${y(item.spot)}`).join(" ");
        svg.append(svgElement("path", { class: "chart-spot-line", d: spotPath }));
      }
      svg.append(svgElement("path", { class: "chart-line", d: mainPath }));
      mainSeries.forEach((item, index) => {
        const dot = svgElement("circle", { class: "chart-dot", cx: x(index), cy: y(item.value), r: 2.5 });
        const spotText = showSpot && item.spot !== null ? `; spot ${formatPrice(item.spot, this._config.currency)}` : "";
        const pointTitle = svgElement("title");
        pointTitle.textContent = `${formatTime(item.point.start_time)}: ${formatPrice(item.value, this._config.currency)}${spotText}`;
        dot.append(pointTitle);
        svg.append(dot);
      });

      const now = new Date();
      const currentIndex = mainSeries.findIndex(({ point }) => {
        const start = new Date(point.start_time);
        const end = new Date(point.end_time);
        return !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && start <= now && now < end;
      });
      if (currentIndex >= 0) {
        svg.append(
          svgElement("line", { class: "chart-current", x1: x(currentIndex), x2: x(currentIndex), y1: top, y2: top + plotHeight }),
          svgElement("circle", { class: "chart-current-dot", cx: x(currentIndex), cy: y(mainSeries[currentIndex].value), r: 4 }),
        );
        const currentLabel = svgElement("text", { class: "chart-axis", x: x(currentIndex), y: top - 2, "text-anchor": "middle" });
        currentLabel.textContent = "Now";
        svg.append(currentLabel);
      }

      const accessiblePoints = make("ul", undefined, "sr-only");
      accessiblePoints.setAttribute("aria-label", "Price timeline details");
      mainSeries.forEach((item) => {
        const spotText = showSpot && item.spot !== null ? `, spot ${formatPrice(item.spot, this._config.currency)}` : "";
        accessiblePoints.append(make("li", `${formatTime(item.point.start_time)}: ${formatPrice(item.value, this._config.currency)}${spotText}`));
      });
      timeline.append(svg);

      const legend = make("div", undefined, "chart-legend");
      legend.append(this._legendItem(this._config.price_mode === "spot" ? "Spot" : "All-in", "all-in"));
      if (showSpot) legend.append(this._legendItem("Spot", "spot"));
      timeline.append(legend, make("p", "Hover a point for its exact price; the current slot is marked Now.", "muted chart-note"), accessiblePoints);
      return timeline;
    }

    _legendItem(label, kind) {
      const item = make("span", undefined, "legend-item");
      item.append(make("span", undefined, `legend-key ${kind}`), make("span", label));
      return item;
    }

    _planContext(lastAttrs, historyAttrs) {
      const plan = Object.keys(lastAttrs).length ? lastAttrs : historyAttrs;
      const block = make("div", undefined, "plan");
      if (!Object.keys(plan).length || plan.reason === "No plan has been requested yet") {
        block.append(this._metric("Status", "No plan requested"));
        block.append(this._metric("Mode", "plan-only"));
        return block;
      }
      block.append(this._metric("Status", plan.status || "unknown"));
      block.append(this._metric("Window", plan.start_time ? `${formatTime(plan.start_time)} → ${formatTime(plan.end_time)}` : (plan.reason || "Unavailable")));
      block.append(this._metric("Estimated cost", formatMoney(plan.estimated_cost, this._config.currency)));
      if (plan.estimated_saving_vs_current != null) block.append(this._metric("Saving", formatMoney(plan.estimated_saving_vs_current, this._config.currency)));
      return block;
    }

    _planForm() {
      const form = document.createElement("form");
      form.append(this._input("Appliance ID", "appliance_id", "text", "dishwasher"));
      form.append(this._input("Duration (minutes)", "duration_minutes", "number", "60", { min: 15, max: 1440, step: 15 }));
      const deadline = new Date(Date.now() + 24 * 60 * 60 * 1000);
      form.append(this._input("Finish by", "deadline", "datetime-local", localDateTime(deadline)));
      form.append(this._input("Earliest start", "earliest_start", "datetime-local", localDateTime(new Date())));
      form.append(this._input("Average power (kW)", "average_power_kw", "number", "1", { min: 0.001, max: 100, step: 0.001 }));
      const submit = make("button", "Find plan-only window");
      submit.type = "submit";
      form.append(submit);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submit.disabled = true;
        try {
          const data = Object.fromEntries(new FormData(form).entries());
          data.duration_minutes = Number(data.duration_minutes);
          data.average_power_kw = Number(data.average_power_kw);
          if (this._config.entry_id) data.entry_id = this._config.entry_id;
          await this._hass.callService(DOMAIN, SERVICE, data);
        } catch (error) {
          this._renderMessage(`Could not request a plan: ${error.message || error}`, true);
        } finally {
          submit.disabled = false;
        }
      });
      const wrapper = make("div");
      wrapper.append(form, make("p", "Plan only: no appliance action is executed.", "form-note muted"));
      return wrapper;
    }

    _input(label, name, type, value, attributesToSet) {
      const wrapper = make("label", label);
      const input = document.createElement("input");
      input.name = name;
      input.type = type;
      input.value = value;
      Object.entries(attributesToSet || {}).forEach(([key, attributeValue]) => { input[key] = attributeValue; });
      input.required = true;
      wrapper.append(input);
      return wrapper;
    }

    getCardSize() { return 6; }
  }

  if (!customElements.get("energy-planner-card")) customElements.define("energy-planner-card", EnergyPlannerCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "energy-planner-card")) {
    window.customCards.push({ type: "energy-planner-card", name: "Energy Planner", description: "Price timeline and plan-only appliance planner" });
  }
})();
