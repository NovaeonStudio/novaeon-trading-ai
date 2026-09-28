<script setup lang="ts">
/** Cockpit dial: 220° arc gauge. The arc carries severity; the readout stays in text ink. */
import type { EChartsOption } from 'echarts';
import ECharts from 'vue-echarts';
import { GaugeChart } from 'echarts/charts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

use([GaugeChart, CanvasRenderer]);

const props = withDefaults(
  defineProps<{
    label: string;
    display: string;
    sub?: string;
    /** Position on the dial between min and max. */
    value: number;
    min?: number;
    max?: number;
    /** Fraction of the scale where the arc turns amber / red. Set `inverse` for "higher is better". */
    warnAt?: number;
    badAt?: number;
    inverse?: boolean;
    /** Center-zero dial (e.g. regime): pointer from the middle, profit right / loss left. */
    centered?: boolean;
  }>(),
  { sub: undefined, min: 0, max: 1, warnAt: 0.5, badAt: 0.8, inverse: false, centered: false },
);

const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart token set below, so the translator is aliased.
const { t: tr } = useI18n();

const fraction = computed(() => {
  const f = (props.value - props.min) / (props.max - props.min);
  return Math.min(1, Math.max(0, f));
});

const level = computed<'ok' | 'warn' | 'bad' | 'up' | 'down'>(() => {
  if (props.centered) return props.value >= 0 ? 'up' : 'down';
  const f = props.inverse ? 1 - fraction.value : fraction.value;
  return f >= props.badAt ? 'bad' : f >= props.warnAt ? 'warn' : 'ok';
});

const color = computed(() => {
  const t = tokens.value;
  switch (level.value) {
    case 'bad':
    case 'down':
      return t.loss;
    case 'warn':
      return t.warn;
    default:
      return t.profit;
  }
});

const status = computed(
  () =>
    ({
      ok: tr('widgets.dial.healthy'),
      warn: tr('widgets.dial.watch'),
      bad: tr('widgets.dial.nearLimit'),
      up: tr('widgets.dial.riskOn'),
      down: tr('widgets.dial.riskOff'),
    })[level.value],
);

const option = computed((): EChartsOption => {
  const t = tokens.value;
  const clamped = Math.min(props.max, Math.max(props.min, props.value));
  const mid = (props.min + props.max) / 2;
  const track = t.track;
  const base = {
    type: 'gauge' as const,
    startAngle: 200,
    endAngle: -20,
    min: props.min,
    max: props.max,
    radius: '94%',
    center: ['50%', '60%'],
    axisLabel: { show: false },
    detail: { show: false },
    title: { show: false },
  };
  return {
    animationDuration: 700,
    series: [
      {
        ...base,
        splitNumber: 4,
        axisLine: { roundCap: true, lineStyle: { width: 8, color: [[1, track]] } },
        progress: props.centered
          ? { show: false }
          : { show: true, width: 8, roundCap: true, itemStyle: { color: color.value } },
        pointer: props.centered
          ? {
              show: true,
              length: '58%',
              width: 3,
              itemStyle: { color: color.value, borderColor: t.surface, borderWidth: 0 },
            }
          : { show: false },
        anchor: {
          show: props.centered,
          size: 10,
          itemStyle: { color: t.text, borderColor: t.surface, borderWidth: 2 },
        },
        axisTick: { distance: -16, length: 3, lineStyle: { color: t.axis, width: 1 } },
        splitLine: { distance: -18, length: 6, lineStyle: { color: t.pointer, width: 1.5 } },
        data: [{ value: clamped }],
      },
      ...(props.centered
        ? [
            {
              ...base,
              axisLine: {
                lineStyle: {
                  width: 8,
                  color: [
                    [0.5, t.lossArea],
                    [1, t.profitArea],
                  ] as [number, string][],
                },
              },
              pointer: { show: false },
              axisTick: { show: false },
              splitLine: { show: false },
              data: [{ value: mid }],
            },
          ]
        : []),
    ],
  };
});
</script>

<template>
  <div class="relative flex flex-col items-center">
    <div class="relative h-32 w-full max-w-52">
      <ECharts :option="option" :theme="chartTheme" autoresize class="h-full w-full" />
      <div class="pointer-events-none absolute inset-x-0 bottom-2 text-center">
        <div class="nova-num text-xl font-semibold tracking-tight text-highlighted">
          {{ display }}
        </div>
      </div>
    </div>
    <div class="mt-1 flex flex-col items-center gap-0.5 text-center">
      <div class="nova-label text-default">{{ label }}</div>
      <div class="inline-flex items-center gap-1.5 text-xs text-muted">
        <span class="size-1.5 shrink-0 rounded-full" :style="{ backgroundColor: color }" />
        {{ status }}
      </div>
      <div v-if="sub" class="nova-num text-xs text-pretty text-dimmed">{{ sub }}</div>
    </div>
  </div>
</template>
