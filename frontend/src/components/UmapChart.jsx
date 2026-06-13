import { useEffect, useMemo, useRef } from "react";
import { EffectScatterChart, LinesChart, ScatterChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, ToolboxComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { init as initEcharts, use as useEcharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

import { CHART_PALETTE, EXPRESSION_PALETTE } from "../constants";

useEcharts([GridComponent, TooltipComponent, VisualMapComponent, DataZoomComponent, ToolboxComponent, ScatterChart, EffectScatterChart, LinesChart, CanvasRenderer]);

function buildColorMap(stats, points) {
  const entries = stats?.by_color?.length ? stats.by_color : stats?.by_dataset || [];
  const map = new Map(entries.map((entry, index) => [entry.value, CHART_PALETTE[index % CHART_PALETTE.length]]));
  points.forEach((point) => {
    const value = point.color_value || point.dataset_id;
    if (!map.has(value)) map.set(value, CHART_PALETTE[map.size % CHART_PALETTE.length]);
  });
  return map;
}

function matchesFilters(point, filters = {}) {
  return Object.entries(filters).every(([fieldName, value]) => !value || point?.[fieldName] === value);
}

function escapeHtml(value) {
  return String(value ?? "-").replace(
    /[&<>"']/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character],
  );
}

function paddedAxisExtent(values) {
  const finiteValues = values.map(Number).filter(Number.isFinite);
  if (!finiteValues.length) return { min: -1, max: 1 };

  const min = Math.min(...finiteValues);
  const max = Math.max(...finiteValues);
  if (min === max) {
    const fallbackPadding = Math.max(Math.abs(min) * 0.08, 1);
    return { min: min - fallbackPadding, max: max + fallbackPadding };
  }

  const padding = (max - min) * 0.09;
  return { min: min - padding, max: max + padding };
}

export function UmapChart({
  points,
  queryCell,
  hits,
  colorBy,
  stats,
  filters,
  onPickCell,
  variant = "workspace",
  emptyMessage,
}) {
  const ref = useRef(null);
  const visibleHits = useMemo(
    () => (hits || []).filter((hit) => hit.umap && matchesFilters(hit, filters)),
    [filters, hits],
  );
  const visibleQueryCell = useMemo(
    () => (queryCell?.umap && matchesFilters(queryCell, filters) ? queryCell : null),
    [filters, queryCell],
  );
  const hitKeys = useMemo(
    () => new Set(visibleHits.map((hit) => `${hit.dataset_id}:${hit.cell_id}`)),
    [visibleHits],
  );
  const isExpression = colorBy?.startsWith("gene:");
  const isBackdrop = variant === "backdrop";

  useEffect(() => {
    if (!ref.current || !points?.length) return undefined;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const chart = initEcharts(ref.current);
    const colorMap = buildColorMap(stats, points);
    const data = points.map((point) => {
      const pointKey = `${point.dataset_id}:${point.cell_id}`;
      const expression = Number(point.expression || 0);
      return {
        value: isExpression ? [point.x, point.y, expression] : [point.x, point.y],
        name: point.cell_id,
        dataset_id: point.dataset_id,
        dataset_name: point.dataset_name,
        cell_type: point.cell_type,
        disease: point.disease,
        AgeGroup: point.AgeGroup,
        tissue: point.tissue,
        row_index: point.row_index,
        color_value: point.color_value,
        expression,
        itemStyle: {
          color: isExpression ? undefined : colorMap.get(point.color_value || point.dataset_id),
          opacity: isBackdrop ? 0.62 : hitKeys.has(pointKey) ? 0.96 : 0.64,
        },
      };
    });
    const hitData = visibleHits.map((hit) => ({
        value: hit.umap,
        name: hit.cell_id,
        dataset_id: hit.dataset_id,
        dataset_name: hit.dataset_name,
        cell_type: hit.cell_type,
        disease: hit.disease,
        AgeGroup: hit.AgeGroup,
        tissue: hit.tissue,
        rank: hit.rank,
      }));
    const queryData = visibleQueryCell
      ? [
          {
            value: visibleQueryCell.umap,
            name: visibleQueryCell.cell_id,
            dataset_id: visibleQueryCell.dataset_id,
            dataset_name: visibleQueryCell.dataset_name,
            cell_type: visibleQueryCell.cell_type,
          },
        ]
      : [];
    const lineData =
      visibleQueryCell?.umap && hitData.length
        ? hitData.map((hit) => ({
            coords: [visibleQueryCell.umap, hit.value],
            name: `${visibleQueryCell.cell_id}-${hit.name}`,
          }))
        : [];
    const plottedCoordinates = [
      ...points.map((point) => [point.x, point.y]),
      ...hitData.map((hit) => hit.value),
      ...queryData.map((query) => query.value),
    ].filter((coordinate) => Number.isFinite(Number(coordinate?.[0])) && Number.isFinite(Number(coordinate?.[1])));
    const xExtent = paddedAxisExtent(plottedCoordinates.map((coordinate) => coordinate[0]));
    const yExtent = paddedAxisExtent(plottedCoordinates.map((coordinate) => coordinate[1]));

    chart.setOption({
      animation: !isBackdrop && !reduceMotion,
      animationDuration: isBackdrop || reduceMotion ? 0 : 320,
      grid: isBackdrop ? { left: 0, right: 0, top: 0, bottom: 0 } : { left: 30, right: 30, top: 28, bottom: isExpression ? 58 : 34 },
      tooltip: isBackdrop
        ? { show: false }
        : {
            trigger: "item",
            borderColor: "#d7e2df",
            borderWidth: 1,
            padding: [9, 11],
            textStyle: { color: "#17312f", fontSize: 12 },
            backgroundColor: "rgba(255, 255, 255, 0.96)",
            formatter: (params) => {
              const item = params.data || {};
              const expressionLine = isExpression ? `<br/>表达量 ${Number(item.expression || 0).toFixed(3)}` : "";
              return `<b>${escapeHtml(item.name)}</b><br/>${escapeHtml(item.cell_type)}<br/>${escapeHtml(item.disease)} / ${escapeHtml(item.AgeGroup)}${expressionLine}`;
            },
          },
      toolbox: isBackdrop
        ? undefined
        : {
            right: 10,
            top: 8,
            itemSize: 15,
            feature: {
              restore: { title: "恢复视图" },
              saveAsImage: { title: "导出图片", pixelRatio: 2, backgroundColor: "#ffffff" },
            },
          },
      visualMap: isExpression
        ? {
            min: stats?.expression?.min ?? 0,
            max: stats?.expression?.max ?? 1,
            calculable: true,
            orient: "horizontal",
            left: "center",
            bottom: 4,
            itemWidth: 12,
            itemHeight: 110,
            textStyle: { color: "#6c7d79", fontSize: 11 },
            inRange: { color: EXPRESSION_PALETTE },
          }
        : undefined,
      dataZoom: isBackdrop
        ? undefined
        : [
            { type: "inside", xAxisIndex: 0, filterMode: "none" },
            { type: "inside", yAxisIndex: 0, filterMode: "none" },
          ],
      xAxis: { type: "value", show: false, scale: true, min: xExtent.min, max: xExtent.max },
      yAxis: { type: "value", show: false, scale: true, min: yExtent.min, max: yExtent.max },
      series: [
        {
          name: "cells",
          type: "scatter",
          silent: isBackdrop,
          symbolSize: isBackdrop ? 4.5 : 5.5,
          progressive: 2000,
          data,
          z: 1,
        },
        ...(isBackdrop
          ? []
          : [
              {
                name: "top-k-links",
                type: "lines",
                coordinateSystem: "cartesian2d",
                data: lineData,
                lineStyle: { color: "#e66c32", opacity: 0.42, width: 1.3, type: "dashed" },
                symbol: "none",
                silent: true,
                z: 2,
              },
              {
                name: "top-k",
                type: "scatter",
                symbolSize: 13,
                data: hitData,
                animationDelay: reduceMotion ? 0 : (index) => index * 24,
                animationDuration: reduceMotion ? 0 : 280,
                itemStyle: { color: "#e66c32", borderColor: "#ffffff", borderWidth: 1.5 },
                z: 3,
              },
              {
                name: "query",
                type: reduceMotion ? "scatter" : "effectScatter",
                symbol: "diamond",
                symbolSize: 18,
                data: queryData,
                ...(reduceMotion
                  ? {}
                  : {
                      rippleEffect: {
                        period: 3.6,
                        scale: 2.2,
                        brushType: "stroke",
                      },
                    }),
                itemStyle: { color: "#17312f", borderColor: "#ffffff", borderWidth: 2 },
                z: 4,
              },
            ]),
      ],
    });

    if (!isBackdrop) {
      chart.on("click", (params) => {
        if (params?.data?.name && params?.data?.dataset_id) {
          onPickCell?.(params.data);
        }
      });
    }
    const resize = () => chart.resize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(ref.current);
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      observer?.disconnect();
      chart.dispose();
    };
  }, [colorBy, hitKeys, isBackdrop, isExpression, onPickCell, points, stats, visibleHits, visibleQueryCell]);

  if (!points?.length) {
    return (
      <div key={`empty-${variant}`} className={`plot-empty ${isBackdrop ? "backdrop-empty" : ""}`}>
        <span>{emptyMessage || "等待 UMAP 数据"}</span>
      </div>
    );
  }

  return <div key={`chart-${variant}`} ref={ref} className={isBackdrop ? "login-umap-chart" : "umap-chart"} />;
}
