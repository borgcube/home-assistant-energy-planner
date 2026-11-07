/*
 * Energy Planner Lovelace card
 * @customElement energy-planner-card
 * @version 1.3.0
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
    chart_type: "bar",
    currency: DEFAULT_CURRENCY,
    show_spot: true,
    fixed_cost_sensor: "",
    last_plan_sensor: "",
    history_sensor: "",
  };

  const CSS = `
    :host { display: block; color: var(--primary-text-color); }
    ha-card { overflow: hidden; }
    .wrap { padding: 12px; }
    h2, h3, p { margin: 0; }
    h2 { font-size: 1.15rem; margin-bottom: 8px; }
    h3 { font-size: 1rem; margin: 14px 0 6px; }
    .muted { color: var(--secondary-text-color); font-size: .85rem; }
    .status { display: inline-block; padding: 3px 8px; border-radius: 999px;
      background: var(--secondary-background-color); font-size: .78rem; }
    .summary, .plan { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
    .metric { padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .metric strong { display: block; font-size: 1.1rem; margin-top: 3px; }
    .timeline { margin-top: 4px; }
    .price-chart { display: block; width: 100%; height: 320px; overflow: visible; touch-action: none; }
    .chart-grid { stroke: var(--divider-color); stroke-width: 1; stroke-dasharray: 2 4; }
    .chart-zero { stroke: var(--secondary-text-color); stroke-dasharray: none; stroke-width: 1.4; opacity: .85; }
    .chart-axis { fill: var(--secondary-text-color); font-size: 11px; }
    .chart-axis-zero { fill: var(--primary-text-color); font-weight: 600; }
    .chart-day-divider { stroke: var(--divider-color); stroke-width: 1; stroke-dasharray: 3 5; opacity: .8; }
    .chart-area { fill: var(--accent-color); opacity: .14; }
    .chart-bar { fill: var(--accent-color); opacity: .78; }
    .chart-line { fill: none; stroke: var(--accent-color); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
    .chart-spot-line { fill: none; stroke: var(--secondary-text-color); stroke-width: 1.7; stroke-dasharray: 5 4; stroke-linecap: round; stroke-linejoin: round; }
    .chart-current { stroke: var(--primary-color); stroke-width: 1.5; stroke-dasharray: 4 3; }
    .chart-dot { fill: var(--accent-color); stroke: var(--card-background-color); stroke-width: 1; opacity: .9; }
    .chart-current-dot { fill: var(--primary-color); stroke: var(--card-background-color); stroke-width: 2; }
    .chart-interaction { fill: transparent; cursor: crosshair; outline: none; }
    .chart-interaction:focus-visible { stroke: var(--primary-color); stroke-width: 1; stroke-dasharray: 3 3; }
    .chart-hover-line { stroke: var(--primary-color); stroke-width: 1.5; stroke-dasharray: 3 3; }
    .chart-hover-dot { fill: var(--primary-color); stroke: var(--card-background-color); stroke-width: 2; }
    .chart-hover-bar { fill: var(--primary-color); opacity: .22; }
    .chart-tooltip { pointer-events: none; }
    .chart-tooltip-box { fill: var(--card-background-color); stroke: var(--divider-color); stroke-width: 1; opacity: .96; }
    .chart-tooltip-text { fill: var(--primary-text-color); font-size: 11px; }
    .chart-tooltip-time { fill: var(--secondary-text-color); }
    .chart-detail { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      margin-top: 8px; padding: 10px; border: 1px solid var(--divider-color); border-radius: 8px;
      background: var(--secondary-background-color); }
    .chart-detail-value { display: block; margin-top: 3px; font-size: .95rem; font-weight: 500; }
    .chart-legend { display: flex; flex-wrap: wrap; gap: 10px 14px; margin: 2px 0 4px; }
    .legend-item { display: inline-flex; align-items: center; gap: 5px; font-size: .78rem; color: var(--secondary-text-color); }
    .legend-key { width: 18px; height: 3px; border-radius: 2px; background: var(--accent-color); }
    .legend-key.spot { height: 0; border-top: 2px dashed var(--secondary-text-color); background: transparent; }
    .chart-note { margin-top: 2px; }
    .planner-toggle { display: flex; align-items: center; justify-content: space-between; gap: 8px;
      width: 100%; margin-top: 18px; padding: 10px 12px; color: inherit;
      background: var(--secondary-background-color); border: 1px solid var(--divider-color);
      text-align: left; }
    .planner-toggle:hover { background: var(--primary-background-color); }
    .planner-toggle .status { margin-left: auto; }
    .planner-section { margin-top: 8px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    form { display: grid; gap: 9px; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); }
    label { display: grid; gap: 4px; font-size: .8rem; }
    input, select { box-sizing: border-box; width: 100%; padding: 8px; color: inherit;
      background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 4px; }
    input:disabled { opacity: .7; }
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

  function formatPower(value) {
    const parsed = number(value);
    return parsed === null ? "—" : `${parsed.toFixed(2)} kW`;
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

  function formatChartDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  function chartDayKey(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? String(value).slice(0, 10)
      : `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
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
      this._plannerOpen = false;
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

      // Home Assistant refreshes hass frequently. Keep the live form node so
      // a refresh cannot clear a value or move focus while someone is typing.
      const existingForm = this._plannerOpen ? this._root.querySelector("form") : null;
      const activeElement = this._root.activeElement;
      const activeFieldName = existingForm && activeElement?.form === existingForm
        ? activeElement.name
        : null;
      const selectionStart = activeElement && typeof activeElement.selectionStart === "number"
        ? activeElement.selectionStart
        : null;
      const selectionEnd = activeElement && typeof activeElement.selectionEnd === "number"
        ? activeElement.selectionEnd
        : null;

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
      const plannerToggle = make("button", undefined, "planner-toggle");
      plannerToggle.type = "button";
      plannerToggle.setAttribute("aria-expanded", String(this._plannerOpen));
      plannerToggle.append(make("span", "Plan an appliance"), make("span", "Plan only", "status"));
      plannerToggle.addEventListener("click", () => {
        this._plannerOpen = !this._plannerOpen;
        this._render();
      });
      wrap.append(plannerToggle);
      let renderedForm = null;
      if (this._plannerOpen) {
        const plannerSection = make("div", undefined, "planner-section");
        renderedForm = existingForm || this._planForm();
        plannerSection.append(renderedForm);
        wrap.append(plannerSection);
      }
      card.append(wrap);
      this._root.append(card);

      if (activeFieldName && renderedForm) {
        const field = Array.from(renderedForm.elements).find((element) => element.name === activeFieldName);
        if (field) {
          field.focus({ preventScroll: true });
          if (selectionStart !== null && typeof field.setSelectionRange === "function") {
            try {
              field.setSelectionRange(selectionStart, selectionEnd ?? selectionStart);
            } catch (_error) {
              // Date and number inputs do not expose a text selection range.
            }
          }
        }
      }
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
      const chartType = ["line", "bar", "area"].includes(this._config.chart_type)
        ? this._config.chart_type
        : "line";
      const plottedValues = mainSeries.flatMap((item) => (
        showSpot && item.spot !== null ? [item.value, item.spot] : [item.value]
      ));
      const min = Math.min(...plottedValues);
      const max = Math.max(...plottedValues);
      const range = Math.max(max - min, 0.001);
      const padding = range * 0.1;
      const domainMin = min < 0 ? Math.min(0, min - padding) : min - padding;
      const domainMax = max + padding;
      const width = 720;
      const height = 320;
      const left = 50;
      const right = 12;
      const top = 16;
      const bottom = 60;
      const plotWidth = width - left - right;
      const plotHeight = height - top - bottom;
      const x = (index) => left + (index / Math.max(1, mainSeries.length - 1)) * plotWidth;
      const y = (value) => top + ((domainMax - value) / (domainMax - domainMin || 1)) * plotHeight;
      const baseline = domainMin <= 0 && domainMax >= 0 ? y(0) : top + plotHeight;
      const mainPath = mainSeries.map((item, index) => `${index ? "L" : "M"}${x(index)} ${y(item.value)}`).join(" ");
      const areaPath = `${mainPath} L${x(mainSeries.length - 1)} ${baseline} L${x(0)} ${baseline} Z`;
      const svg = svgElement("svg", {
        class: "price-chart",
        viewBox: `0 0 ${width} ${height}`,
        role: "img",
        "aria-label": `${chartType} price chart with ${mainSeries.length} points from ${formatPrice(min, this._config.currency)} to ${formatPrice(max, this._config.currency)}`,
      });
      const title = svgElement("title");
      title.textContent = "Electricity price timeline";
      svg.append(title);

      const tickValues = [...new Set(
        Array.from({ length: 5 }, (_, tick) => domainMax - ((domainMax - domainMin) * tick / 4))
          .concat(domainMin <= 0 && domainMax >= 0 ? [0] : [])
          .map((value) => Number(value.toFixed(6))),
      )].sort((a, b) => b - a);
      tickValues.forEach((value) => {
        const yPosition = y(value);
        const isZero = value === 0;
        svg.append(
          svgElement("line", { class: isZero ? "chart-grid chart-zero" : "chart-grid", x1: left, x2: width - right, y1: yPosition, y2: yPosition }),
          svgElement("text", { class: isZero ? "chart-axis chart-axis-zero" : "chart-axis", x: left - 8, y: yPosition + 4, "text-anchor": "end" }),
        );
        svg.lastChild.textContent = value.toFixed(3);
      });

      const tickIndexes = [...new Set([0, Math.floor((mainSeries.length - 1) / 3), Math.floor((mainSeries.length - 1) * 2 / 3), mainSeries.length - 1])];
      tickIndexes.forEach((index) => {
        const label = svgElement("text", { class: "chart-axis", x: x(index), y: height - 28, "text-anchor": "middle" });
        label.textContent = formatChartTime(mainSeries[index].point.start_time);
        svg.append(label);
      });

      const dayIndexes = [];
      const seenDays = new Set();
      mainSeries.forEach((item, index) => {
        const day = chartDayKey(item.point.start_time);
        if (!seenDays.has(day)) {
          seenDays.add(day);
          dayIndexes.push(index);
        }
      });
      dayIndexes.forEach((index, dayIndex) => {
        if (dayIndex > 0) {
          svg.append(svgElement("line", {
            class: "chart-day-divider",
            x1: x(index), x2: x(index), y1: top, y2: top + plotHeight,
          }));
        }
        const label = svgElement("text", {
          class: "chart-axis",
          x: x(index),
          y: height - 9,
          "text-anchor": index === 0 ? "start" : "middle",
        });
        label.textContent = formatChartDate(mainSeries[index].point.start_time);
        svg.append(label);
      });

      if (chartType === "area") {
        svg.append(svgElement("path", { class: "chart-area", d: areaPath }));
      } else if (chartType === "bar") {
        const barWidth = Math.max(1.5, Math.min(16, (plotWidth / Math.max(1, mainSeries.length)) * 0.76));
        mainSeries.forEach((item, index) => {
          const valueY = y(item.value);
          svg.append(svgElement("rect", {
            class: "chart-bar",
            x: x(index) - barWidth / 2,
            y: Math.min(valueY, baseline),
            width: barWidth,
            height: Math.max(1, Math.abs(valueY - baseline)),
            rx: Math.min(2, barWidth / 3),
          }));
        });
      }
      if (showSpot) {
        const spotSeries = mainSeries
          .map((item, index) => ({ ...item, index }))
          .filter((item) => item.spot !== null);
        const spotPath = spotSeries
          .map((item, index) => `${index ? "L" : "M"}${x(item.index)} ${y(item.spot)}`).join(" ");
        svg.append(svgElement("path", { class: "chart-spot-line", d: spotPath }));
      }
      if (chartType !== "bar") {
        svg.append(svgElement("path", { class: "chart-line", d: mainPath }));
        mainSeries.forEach((item, index) => {
          const dot = svgElement("circle", { class: "chart-dot", cx: x(index), cy: y(item.value), r: 2.5 });
          const spotText = showSpot && item.spot !== null ? `; spot ${formatPrice(item.spot, this._config.currency)}` : "";
          const pointTitle = svgElement("title");
          pointTitle.textContent = `${formatTime(item.point.start_time)}: ${formatPrice(item.value, this._config.currency)}${spotText}`;
          dot.append(pointTitle);
          svg.append(dot);
        });
      }

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

      const hoverLayer = svgElement("g", { visibility: "hidden" });
      const hoverLine = svgElement("line", { class: "chart-hover-line", x1: left, x2: left, y1: top, y2: top + plotHeight });
      const hoverDot = svgElement("circle", { class: "chart-hover-dot", cx: left, cy: y(mainSeries[0].value), r: 4 });
      const hoverBar = chartType === "bar"
        ? svgElement("rect", { class: "chart-hover-bar", x: left, y: top, width: 1, height: 1, rx: 2 })
        : null;
      const tooltip = svgElement("g", { class: "chart-tooltip" });
      const tooltipBox = svgElement("rect", { class: "chart-tooltip-box", x: 0, y: 0, width: 174, height: showSpot ? 60 : 44, rx: 5 });
      const tooltipTime = svgElement("text", { class: "chart-tooltip-text chart-tooltip-time", x: 10, y: 16 });
      const tooltipMain = svgElement("text", { class: "chart-tooltip-text", x: 10, y: 34 });
      const tooltipSpot = svgElement("text", { class: "chart-tooltip-text", x: 10, y: 51 });
      tooltip.append(tooltipBox, tooltipTime, tooltipMain);
      if (showSpot) tooltip.append(tooltipSpot);
      hoverLayer.append(hoverLine);
      if (hoverBar) hoverLayer.append(hoverBar);
      hoverLayer.append(hoverDot, tooltip);
      svg.append(hoverLayer);

      const liveRegion = make("div", "", "sr-only");
      liveRegion.setAttribute("role", "status");
      liveRegion.setAttribute("aria-live", "polite");
      const detail = make("div", undefined, "chart-detail");
      const detailTime = make("strong", "—", "chart-detail-value");
      const detailPrice = make("strong", "—", "chart-detail-value");
      const detailSpot = make("strong", "—", "chart-detail-value");
      const detailBlock = (label, value) => {
        const block = make("div");
        block.append(make("span", label, "muted"), value);
        return block;
      };
      detail.append(
        detailBlock("Selected interval", detailTime),
        detailBlock(this._config.price_mode === "spot" ? "Spot price" : "All-in price", detailPrice),
        detailBlock("Spot comparison", detailSpot),
      );
      let selectedIndex = null;
      const clamp = (value, lower, upper) => Math.min(upper, Math.max(lower, value));
      const eventIndex = (event) => {
        const bounds = svg.getBoundingClientRect();
        const svgX = ((event.clientX - bounds.left) / Math.max(1, bounds.width)) * width;
        return clamp(Math.round(((svgX - left) / plotWidth) * Math.max(1, mainSeries.length - 1)), 0, mainSeries.length - 1);
      };
      const updateHover = (index) => {
        const item = mainSeries[index];
        const pointX = x(index);
        const pointY = y(item.value);
        const tooltipWidth = 174;
        const tooltipHeight = showSpot ? 60 : 44;
        const tooltipX = clamp(pointX + 8, left, width - right - tooltipWidth);
        const tooltipY = clamp(pointY - tooltipHeight - 10, top, top + plotHeight - tooltipHeight);
        hoverLine.setAttribute("x1", pointX);
        hoverLine.setAttribute("x2", pointX);
        hoverDot.setAttribute("cx", pointX);
        hoverDot.setAttribute("cy", pointY);
        if (hoverBar) {
          const barWidth = Math.max(1.5, Math.min(16, (plotWidth / Math.max(1, mainSeries.length)) * 0.76));
          hoverBar.setAttribute("x", pointX - barWidth / 2);
          hoverBar.setAttribute("y", Math.min(pointY, baseline));
          hoverBar.setAttribute("width", barWidth);
          hoverBar.setAttribute("height", Math.max(1, Math.abs(pointY - baseline)));
        }
        tooltip.setAttribute("transform", `translate(${tooltipX}, ${tooltipY})`);
        tooltipBox.setAttribute("height", tooltipHeight);
        tooltipTime.textContent = `${formatChartDate(item.point.start_time)} · ${formatChartTime(item.point.start_time)}`;
        tooltipMain.textContent = `${this._config.price_mode === "spot" ? "Spot" : "All-in"}: ${formatPrice(item.value, this._config.currency)}`;
        if (showSpot) tooltipSpot.textContent = `Spot: ${formatPrice(item.spot, this._config.currency)}`;
        detailTime.textContent = `${formatTime(item.point.start_time)} → ${formatTime(item.point.end_time)}`;
        detailPrice.textContent = formatPrice(item.value, this._config.currency);
        detailSpot.textContent = showSpot && item.spot !== null
          ? formatPrice(item.spot, this._config.currency)
          : "—";
        liveRegion.textContent = `${formatTime(item.point.start_time)}: ${formatPrice(item.value, this._config.currency)}${showSpot ? `, spot ${formatPrice(item.spot, this._config.currency)}` : ""}`;
        hoverLayer.setAttribute("visibility", "visible");
      };
      const clearHover = () => {
        if (selectedIndex === null) hoverLayer.setAttribute("visibility", "hidden");
      };
      const interaction = svgElement("rect", {
        class: "chart-interaction",
        x: left,
        y: top,
        width: plotWidth,
        height: plotHeight,
        tabindex: "0",
        role: "button",
        "aria-label": "Interactive price timeline; move across the chart to inspect each rate",
      });
      interaction.addEventListener("pointermove", (event) => updateHover(eventIndex(event)));
      interaction.addEventListener("pointerleave", clearHover);
      interaction.addEventListener("pointerdown", (event) => {
        selectedIndex = eventIndex(event);
        interaction.setPointerCapture?.(event.pointerId);
        updateHover(selectedIndex);
      });
      interaction.addEventListener("pointerup", (event) => {
        selectedIndex = eventIndex(event);
        interaction.releasePointerCapture?.(event.pointerId);
        updateHover(selectedIndex);
      });
      interaction.addEventListener("click", (event) => {
        selectedIndex = eventIndex(event);
        updateHover(selectedIndex);
      });
      interaction.addEventListener("focus", () => updateHover(selectedIndex ?? (currentIndex >= 0 ? currentIndex : 0)));
      interaction.addEventListener("keydown", (event) => {
        if (["Enter", " "].includes(event.key)) {
          event.preventDefault();
          selectedIndex = selectedIndex ?? (currentIndex >= 0 ? currentIndex : 0);
          updateHover(selectedIndex);
          return;
        }
        if (!["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(event.key)) return;
        event.preventDefault();
        if (event.key === "Escape") {
          selectedIndex = null;
          clearHover();
          return;
        }
        const current = selectedIndex ?? (currentIndex >= 0 ? currentIndex : 0);
        selectedIndex = event.key === "Home"
          ? 0
          : event.key === "End"
            ? mainSeries.length - 1
            : clamp(current + (event.key === "ArrowRight" ? 1 : -1), 0, mainSeries.length - 1);
        updateHover(selectedIndex);
      });
      svg.append(interaction);
      updateHover(currentIndex >= 0 ? currentIndex : 0);
      hoverLayer.setAttribute("visibility", "hidden");

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
      timeline.append(detail, legend, make("p", "Hover or drag across the chart; click a point to keep its rate visible.", "muted chart-note"), liveRegion, accessiblePoints);
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
      if (plan.average_power_kw != null) block.append(this._metric("Average power", formatPower(plan.average_power_kw)));
      const utilization = number(plan.historical_utilization_percent);
      if (utilization !== null) {
        block.append(this._metric("Meter history", `${utilization.toFixed(1)}% active`));
      }
      return block;
    }

    _planForm() {
      const form = document.createElement("form");
      const energySources = this._energySources();
      const energyByEntity = new Map(energySources.map((source) => [source.entity_id, source]));
      const energyOptions = [
        { value: "", label: energySources.length ? "Custom appliance (manual power)" : "Custom appliance" },
        ...energySources.map((source) => ({
          value: source.entity_id,
          label: `${source.label} (${source.unit})`,
        })),
      ];
      const energyField = this._select("Device / energy meter", "energy_entity", energyOptions);
      const energySelect = energyField.querySelector("select");
      form.append(energyField);

      const applianceField = this._input("Appliance ID", "appliance_id", "text", "dishwasher");
      const applianceInput = applianceField.querySelector("input");
      form.append(applianceField);
      form.append(this._input("Duration (minutes)", "duration_minutes", "number", "60", { min: 15, max: 1440, step: 15 }));
      const deadline = new Date(Date.now() + 24 * 60 * 60 * 1000);
      form.append(this._input("Finish by", "deadline", "datetime-local", localDateTime(deadline)));
      form.append(this._input("Earliest start", "earliest_start", "datetime-local", localDateTime(new Date())));
      const powerField = this._input("Average power (kW)", "average_power_kw", "number", "1", { min: 0.001, max: 100, step: 0.001 });
      const powerInput = powerField.querySelector("input");
      const powerNote = make("span", "Used for a custom appliance.", "muted");
      powerField.append(powerNote);
      form.append(powerField);

      let manualApplianceId = applianceInput.value;
      let manualPowerValue = powerInput.value;
      const syncSelectedEnergyEntity = () => {
        const source = energyByEntity.get(energySelect.value);
        if (source) {
          manualApplianceId = applianceInput.value || manualApplianceId;
          manualPowerValue = powerInput.value || manualPowerValue;
          applianceInput.value = source.label.slice(0, 64);
          applianceInput.readOnly = true;
          powerInput.value = "";
          powerInput.disabled = true;
          powerInput.required = false;
          powerNote.textContent = "Estimated from this meter’s recorded history when submitted.";
          return;
        }
        applianceInput.readOnly = false;
        applianceInput.value = manualApplianceId || "dishwasher";
        powerInput.disabled = false;
        powerInput.required = true;
        powerInput.value = manualPowerValue || "1";
        powerNote.textContent = "Used for a custom appliance.";
      };
      energySelect.addEventListener("change", syncSelectedEnergyEntity);
      applianceInput.addEventListener("input", () => {
        if (!applianceInput.readOnly) manualApplianceId = applianceInput.value;
      });
      powerInput.addEventListener("input", () => {
        if (!powerInput.disabled) manualPowerValue = powerInput.value;
      });
      const submit = make("button", "Find plan-only window");
      submit.type = "submit";
      form.append(submit);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submit.disabled = true;
        try {
          const data = Object.fromEntries(new FormData(form).entries());
          data.duration_minutes = Number(data.duration_minutes);
          if (data.energy_entity) {
            delete data.average_power_kw;
          } else {
            data.average_power_kw = Number(data.average_power_kw);
            if (!Number.isFinite(data.average_power_kw)) {
              throw new Error("Enter an average power or select an energy meter.");
            }
          }
          if (!data.energy_entity) delete data.energy_entity;
          if (this._config.entry_id) data.entry_id = this._config.entry_id;
          await this._hass.callService(DOMAIN, SERVICE, data, undefined, true, true);
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

    _energySources() {
      return Object.entries(this._hass?.states || {})
        .filter(([entityId, state]) => {
          if (!entityId.startsWith("sensor.") || !state?.attributes) return false;
          const unit = String(state.attributes.unit_of_measurement || "").replace(/\s/g, "").toLowerCase();
          return state.attributes.device_class === "energy"
            || ["wh", "kwh", "mwh", "w⋅h", "kw⋅h"].includes(unit);
        })
        .map(([entityId, state]) => ({
          entity_id: entityId,
          label: state.attributes.friendly_name || entityId,
          unit: state.attributes.unit_of_measurement || "energy",
        }))
        .sort((left, right) => left.label.localeCompare(right.label));
    }

    _select(label, name, options) {
      const wrapper = make("label", label);
      const select = document.createElement("select");
      select.name = name;
      options.forEach(({ value, label: optionLabel }) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = optionLabel;
        select.append(option);
      });
      wrapper.append(select);
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
