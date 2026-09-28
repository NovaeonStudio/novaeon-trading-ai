<script setup lang="ts">
/** Journal: the bot log with level/topic filters, search, live follow and color coding. */
import type { LogLine } from '@/types';

const { t } = useI18n();
const { bot } = useNovaLive();
const query = ref('');
const level = ref<'all' | 'WARNING' | 'ERROR'>('all');
const topic = ref<'all' | 'trades' | 'kev' | 'clean'>('clean');
const follow = useStorage('nova-journal-follow', true);
const loading = ref(false);

async function load() {
  if (!bot.value?.isBotOnline) return;
  loading.value = true;
  try {
    await bot.value.getLogs();
  } finally {
    loading.value = false;
  }
}
onMounted(load);
useIntervalFn(() => {
  if (follow.value) load();
}, 5_000);

const TRADE_RE = /(order|entry|exit|fill|forcesell|forceexit|stoploss|trade)/i;
/** Sentinel (the AI news check; its strategy logger keeps the former name Kev). */
const KEV_RE = /kev|sentinel/i;
/** Connection chatter that hides the interesting lines. */
const NOISE_RE =
  /^(Bot heartbeat|connection (open|closed)|Connected to channel|Disconnected from channel)|"WebSocket \/api\/v1\/message\/ws/;
/** Never display credentials that the engine writes into its log (e.g. websocket JWTs). */
function redact(msg: string) {
  return msg.replace(/(token=)[^\s"&]+/gi, '$1•••').replace(/(Bearer\s+)[\w.-]+/g, '$1•••');
}

const lines = computed(() => {
  const q = query.value.trim().toLowerCase();
  const logs: LogLine[] = [...(bot.value?.lastLogs ?? [])].reverse();
  return logs.filter(([, , logger, lvl, msg]) => {
    if (level.value === 'WARNING' && !['WARNING', 'ERROR', 'CRITICAL'].includes(lvl)) return false;
    if (level.value === 'ERROR' && !['ERROR', 'CRITICAL'].includes(lvl)) return false;
    if (topic.value === 'trades' && !TRADE_RE.test(msg)) return false;
    if (topic.value === 'kev' && !KEV_RE.test(msg) && !KEV_RE.test(logger)) return false;
    if (topic.value === 'clean' && NOISE_RE.test(msg)) return false;
    return !q || msg.toLowerCase().includes(q) || logger.toLowerCase().includes(q);
  });
});
const topicLabels = computed<Record<'clean' | 'all' | 'trades' | 'kev', string>>(() => ({
  clean: t('journal.topic.clean'),
  all: t('journal.topic.all'),
  trades: t('journal.topic.trades'),
  kev: t('journal.topic.sentinel'),
}));
const counts = computed(() => {
  const logs = bot.value?.lastLogs ?? [];
  return {
    warn: logs.filter((l) => l[3] === 'WARNING').length,
    err: logs.filter((l) => ['ERROR', 'CRITICAL'].includes(l[3])).length,
  };
});

function levelClass(lvl: string) {
  if (lvl === 'ERROR' || lvl === 'CRITICAL') return 'bg-rose-500/15 text-rose-400 font-semibold';
  if (lvl === 'WARNING') return 'bg-brand-400/15 text-brand-700 dark:text-brand-300 font-semibold';
  return 'text-dimmed';
}
function msgClass(msg: string, logger: string) {
  if (KEV_RE.test(msg) || KEV_RE.test(logger)) return 'text-secondary';
  if (TRADE_RE.test(msg)) return 'text-highlighted';
  return 'text-default';
}
</script>

<template>
  <div
    class="mx-auto flex min-h-full w-full max-w-[1680px] flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8 lg:h-full"
  >
    <section class="nova-panel flex flex-col gap-4 p-4 sm:p-6">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0">
          <h1 class="text-2xl font-semibold text-balance text-highlighted">
            {{ t('journal.title') }}
          </h1>
          <div class="nova-num mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span class="rounded-full bg-accented px-3 py-1 font-medium text-muted">{{
              t('journal.linesShown', { n: lines.length })
            }}</span>
            <span
              class="rounded-full px-3 py-1 font-medium"
              :class="
                counts.warn
                  ? 'bg-brand-400/15 text-brand-700 dark:text-brand-300'
                  : 'bg-accented text-muted'
              "
              >{{ t('journal.warnings', counts.warn) }}</span
            >
            <span
              class="rounded-full px-3 py-1 font-medium"
              :class="counts.err ? 'bg-rose-500/15 text-rose-400' : 'bg-accented text-muted'"
              >{{ t('journal.errors', counts.err) }}</span
            >
          </div>
        </div>
        <div class="flex items-center gap-2">
          <USwitch v-model="follow" :label="t('journal.live')" />
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-mdi-refresh"
            :aria-label="t('journal.reload')"
            :loading="loading"
            @click="load"
          />
        </div>
      </div>
      <!-- filters: one row that wraps -->
      <div class="flex flex-wrap items-center gap-3">
        <UInput
          v-model="query"
          icon="i-mdi-magnify"
          :placeholder="t('journal.searchPlaceholder')"
          class="w-full sm:w-64"
          :ui="{ base: 'rounded-xl' }"
        />
        <div class="nova-seg text-sm" role="group" :aria-label="t('journal.filterLevel')">
          <button
            v-for="opt in ['all', 'WARNING', 'ERROR'] as const"
            :key="opt"
            type="button"
            :aria-pressed="level === opt"
            @click="level = opt"
          >
            {{
              opt === 'all'
                ? t('journal.level.all')
                : opt === 'WARNING'
                  ? t('journal.level.warnings')
                  : t('journal.level.errors')
            }}
          </button>
        </div>
        <div class="nova-seg text-sm" role="group" :aria-label="t('journal.filterTopic')">
          <button
            v-for="opt in ['clean', 'all', 'trades', 'kev'] as const"
            :key="opt"
            type="button"
            :aria-pressed="topic === opt"
            @click="topic = opt"
          >
            {{ topicLabels[opt] }}
          </button>
        </div>
      </div>
    </section>

    <section class="nova-panel flex min-h-0 flex-col overflow-hidden lg:flex-1">
      <div class="min-h-0 flex-1 overflow-auto font-mono text-xs">
        <div
          class="sticky top-0 z-10 hidden grid-cols-[10rem_5.5rem_12rem_minmax(0,1fr)] gap-3 border-b border-default/70 bg-elevated px-6 py-3 font-sans font-medium text-muted md:grid"
        >
          <span>{{ t('journal.col.time') }}</span
          ><span>{{ t('journal.col.level') }}</span
          ><span>{{ t('journal.col.source') }}</span
          ><span>{{ t('journal.col.message') }}</span>
        </div>
        <div
          v-for="(l, i) in lines"
          :key="`${l[1]}-${i}`"
          class="grid grid-cols-[auto_auto_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1 border-t border-default/40 px-4 py-2 first:border-t-0 hover:bg-accented/40 md:grid-cols-[10rem_5.5rem_12rem_minmax(0,1fr)] md:px-6"
        >
          <span class="nova-num whitespace-nowrap text-dimmed">{{ l[0] }}</span>
          <span>
            <span class="rounded-full px-2 py-px" :class="levelClass(l[3])">{{ l[3] }}</span>
          </span>
          <span class="truncate text-dimmed" :title="l[2]">{{ l[2] }}</span>
          <span
            class="col-span-3 leading-relaxed break-words md:col-span-1"
            :class="msgClass(l[4], l[2])"
            >{{ redact(l[4]) }}</span
          >
        </div>
        <div
          v-if="!lines.length"
          class="flex items-center justify-center gap-3 px-4 py-12 font-sans"
        >
          <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
            <UIcon name="i-mdi-text-search" class="size-5 text-muted" />
          </span>
          <p class="text-sm text-muted">{{ t('journal.empty') }}</p>
        </div>
      </div>
    </section>
  </div>
</template>
