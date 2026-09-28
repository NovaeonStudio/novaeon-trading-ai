<script setup lang="ts">
const props = defineProps<{
  profitRatio?: number | null;
  profitAbs?: number;
  stakeCurrency: string;
  profitDesc?: string;
}>();
const isProfitable = computed<boolean | null>(() => {
  if (!isDefined(props.profitRatio) && !isDefined(props.profitAbs)) {
    return null;
  }
  return (
    (isDefined(props.profitRatio) && props.profitRatio > 0) ||
    (props.profitRatio === undefined && props.profitAbs !== undefined && props.profitAbs > 0)
  );
});

const profitString = computed((): string => {
  if (props.profitRatio !== undefined && props.profitAbs !== undefined) {
    return `(${formatPrice(props.profitAbs, 3)})`;
  } else if (props.profitAbs !== undefined) {
    if (props.stakeCurrency !== undefined) {
      return `${formatPriceCurrency(props.profitAbs, props.stakeCurrency, 3)}`;
    } else {
      return `${formatPrice(props.profitAbs, 3)}`;
    }
  }
  return '';
});
</script>

<template>
  <div
    class="nova-num flex items-center justify-between gap-1 rounded-full px-3 py-0.5 text-sm font-medium"
    :class="{
      'bg-emerald-500/15 text-emerald-400': isProfitable === true,
      'bg-rose-500/15 text-rose-400': isProfitable === false,
      'bg-accented/60 text-muted': isProfitable === null,
    }"
    :title="profitDesc"
  >
    <ProfitSymbol :profit="profitRatio || profitAbs" />

    <div class="flex grow items-center justify-center">
      <span class="nova-money">{{
        profitRatio !== undefined ? formatPercent(profitRatio, 2) : ''
      }}</span>
      <span
        v-if="profitString"
        class="nova-money ms-1"
        :class="profitRatio ? 'text-xs opacity-80' : ''"
        :title="stakeCurrency"
        >{{ profitString }}</span
      >
    </div>
  </div>
</template>
