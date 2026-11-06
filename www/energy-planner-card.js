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
    .timeline { display: grid; grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
      gap: 5px; align-items: end; min-height: 120px; }
    .slot { min-width: 0; }
    .bar { min-height: 8px; border-radius: 4px 4px 0 0; background: var(--accent-color); }
    .slot.current .bar { outline: 2px solid var(--primary-color); outline-offset: 1px; }
    .slot time, .slot .price { display: block; font-size: .75rem; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap; }
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
      heading.append(make("span", `  ${modelStatus}`, "status"));
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
      wrap.append(make("h3", "Plan an appliance"));
      wrap.append(this._planForm());
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
      const values = points.map((point) => number(point[key])).filter((value) => value !== null);
      const min = Math.min(...values);
      const max = Math.max(...values);
      const timeline = make("div", undefined, "timeline");
      points.slice(0, 48).forEach((point) => {
        const value = number(point[key]);
        if (value === null) return;
        const slot = make("div", undefined, "slot");
        const start = new Date(point.start_time);
        const end = new Date(point.end_time);
        if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && start <= new Date() && new Date() < end) slot.classList.add("current");
        const bar = make("div", undefined, "bar");
        bar.style.height = `${Math.max(8, ((value - min) / (max - min || 1)) * 72 + 8)}px`;
        bar.title = `${formatPrice(value, this._config.currency)}${this._config.show_spot && point.spot_price_per_kwh != null ? `; spot ${formatPrice(point.spot_price_per_kwh, this._config.currency)}` : ""}`;
        slot.append(bar, make("span", formatTime(point.start_time), "time"), make("span", formatPrice(value, this._config.currency), "price"));
        timeline.append(slot);
      });
      return timeline;
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
