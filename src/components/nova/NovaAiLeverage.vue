<script setup lang="ts">
/**
 * "Let Sentinel choose leverage (up to 3×)": bot-wide switch for AI leverage on new trades (control service
 * /control/settings). Off by default; turning it on needs an explicit confirmation of the risk. Locked (with the
 * reason) on Macs that run the smaller Sentinel build. `compact` = one row for the Wallet page.
 */
import { controlErrorText, useNovaControl } from '@/composables/useNovaControl';

const props = defineProps<{ compact?: boolean }>();

const { t } = useI18n();
const { botSettings, loadSettings, setAiLeverage, restarting } = useNovaControl();
const { confirm } = useConfirmBox();
const toast = useToast();

const loadError = ref<string | null>(null);
const problem = ref<string | null>(null);
const busy = ref(false);
const showConfirm = ref(false);
const ack = ref(false);

async function load() {
  try {
    await loadSettings();
    loadError.value = null;
  } catch (e) {
    loadError.value = controlErrorText(e);
  }
}
onMounted(load);

const s = computed(() => botSettings.value);
const on = computed(() => !!s.value?.ai_leverage);
const locked = computed(() => !!s.value && !s.value.ai_leverage_allowed);
const live = computed(() => s.value?.mode === 'live');
const maxLev = computed(() => s.value?.max_ai_leverage ?? 3);
const working = computed(() => busy.value || restarting.value);

const statusText = computed(() =>
  locked.value
    ? t('aiLeverage.statusLocked')
    : on.value
      ? t('aiLeverage.statusOn', { max: maxLev.value })
      : t('aiLeverage.statusOff'),
);

async function apply(next: boolean) {
  busy.value = true;
  problem.value = null;
  try {
    const res = await setAiLeverage(next);
    if (!res.unchanged)
      toast.add({
        title: next ? t('aiLeverage.toastOn') : t('aiLeverage.toastOff'),
        description: res.engineBack ? res.note : `${res.note ?? ''} ${t('aiLeverage.slowBack')}`,
        color: res.engineBack ? 'success' : 'warning',
        icon: res.engineBack ? 'i-mdi-check-circle-outline' : 'i-mdi-timer-sand',
      });
  } catch (e) {
    problem.value = controlErrorText(e);
  } finally {
    busy.value = false;
  }
}

async function onToggle(next: boolean) {
  if (locked.value || working.value || next === on.value) return;
  if (next) {
    ack.value = false;
    showConfirm.value = true;
    return;
  }
  const ok = await confirm({
    title: t('aiLeverage.offTitle'),
    message: t('aiLeverage.offMessage'),
    confirmText: t('aiLeverage.offConfirm'),
  });
  if (ok) await apply(false);
}

async function confirmOn() {
  if (!ack.value) return;
  showConfirm.value = false;
  await apply(true);
}
</script>

<template>
  <div
    :class="props.compact ? 'nova-panel p-4 sm:p-6' : ''"
    data-testid="nova-ai-leverage"
    class="text-left"
  >
    <!-- loading / error -->
    <div v-if="!s && loadError" class="flex flex-wrap items-center gap-3 text-sm text-muted">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-cloud-off-outline" class="size-5 text-muted" />
      </span>
      <span class="min-w-0 flex-1 text-pretty">{{ t('aiLeverage.loadError') }}</span>
      <UButton color="neutral" variant="outline" icon="i-mdi-refresh" @click="load">{{
        t('common.retry')
      }}</UButton>
    </div>
    <div v-else-if="!s" class="flex flex-col gap-3">
      <USkeleton class="h-4 w-64 rounded-full" />
      <USkeleton class="h-4 w-80 max-w-full rounded-full" />
    </div>

    <div v-else class="flex flex-col gap-4">
      <div class="flex items-start justify-between gap-4 sm:gap-6">
        <div class="flex min-w-0 items-start gap-3">
          <span
            class="flex size-10 shrink-0 items-center justify-center rounded-full"
            :class="
              locked
                ? 'bg-accented text-muted'
                : on
                  ? 'bg-brand-400/15 text-brand-600 dark:text-brand-300'
                  : 'bg-secondary/15 text-secondary'
            "
          >
            <UIcon
              :name="
                locked
                  ? 'i-mdi-lock-outline'
                  : on
                    ? 'i-mdi-scale-unbalanced'
                    : 'i-mdi-scale-balance'
              "
              class="size-5"
            />
          </span>
          <div class="min-w-0">
            <label for="setting-ai-leverage" class="text-sm font-medium text-highlighted">{{
              t('aiLeverage.label', { max: maxLev })
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">{{ statusText }}</p>
          </div>
        </div>
        <USwitch
          id="setting-ai-leverage"
          :model-value="on"
          :disabled="locked || working"
          :loading="working"
          class="mt-2 shrink-0"
          aria-describedby="setting-ai-leverage-help"
          @update:model-value="onToggle"
        />
      </div>

      <div id="setting-ai-leverage-help" class="flex flex-col gap-2 text-sm text-pretty text-muted">
        <p v-if="locked" class="nova-tile flex items-start gap-2 p-3 text-default">
          <UIcon name="i-mdi-lock-outline" class="mt-0.5 size-4 shrink-0 text-muted" />
          <span>{{ s.locked_reason }}</span>
        </p>
        <template v-else-if="!compact">
          <p>{{ t('aiLeverage.explainNews') }}</p>
          <p>{{ t('aiLeverage.explainRisk') }}</p>
        </template>
        <p v-else>
          {{ t('aiLeverage.compactRisk') }}
          <ULink to="/settings#trading" class="text-default underline underline-offset-4">{{
            t('aiLeverage.moreInSettings')
          }}</ULink>
        </p>
        <p v-if="!compact || on">
          {{ t('aiLeverage.newOnly') }}
          <template v-if="!compact">{{ t('aiLeverage.manualHint') }}</template>
        </p>
      </div>

      <div
        v-if="restarting && busy"
        class="nova-tile flex items-start gap-3 p-4"
        role="status"
        aria-live="polite"
      >
        <span class="relative mt-1 flex size-3 shrink-0">
          <span class="absolute inline-flex size-full animate-ping rounded-full bg-secondary/60" />
          <span class="relative inline-flex size-3 rounded-full bg-secondary" />
        </span>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-highlighted">
            {{ t('aiLeverage.restartingTitle') }}
          </div>
          <p class="mt-1 text-sm text-pretty text-muted">
            {{ t('aiLeverage.restartingText') }}
          </p>
        </div>
      </div>

      <UAlert
        v-if="problem"
        color="error"
        variant="subtle"
        icon="i-mdi-alert-circle-outline"
        :title="t('aiLeverage.failed')"
        :description="problem"
        :close="true"
        @update:open="problem = null"
      />
    </div>

    <!-- Confirm turning it on -->
    <UModal
      v-model:open="showConfirm"
      :title="t('aiLeverage.confirm.title')"
      :ui="{ content: 'max-w-lg rounded-2xl' }"
    >
      <template #body>
        <div class="flex flex-col gap-4 text-left text-sm text-pretty">
          <p class="text-default">
            {{ t('aiLeverage.confirm.intro', { max: maxLev }) }}
          </p>
          <ul class="flex flex-col gap-2 text-muted">
            <li class="flex items-start gap-2">
              <UIcon name="i-mdi-arrow-expand-vertical" class="mt-0.5 size-4 shrink-0" />
              <span>{{ t('aiLeverage.confirm.bigger') }}</span>
            </li>
            <li class="flex items-start gap-2">
              <UIcon name="i-mdi-flash-alert-outline" class="mt-0.5 size-4 shrink-0" />
              <span>{{ t('aiLeverage.confirm.crash') }}</span>
            </li>
            <li class="flex items-start gap-2">
              <UIcon name="i-mdi-history" class="mt-0.5 size-4 shrink-0" />
              <span>{{ t('aiLeverage.confirm.newOnly') }}</span>
            </li>
          </ul>
          <p v-if="live" class="flex items-center gap-2 font-semibold text-rose-400">
            <UIcon name="i-mdi-cash-multiple" class="size-4 shrink-0" />
            {{ t('aiLeverage.confirm.live') }}
          </p>
          <p v-else class="flex items-center gap-2 text-muted">
            <UIcon name="i-mdi-school-outline" class="size-4 shrink-0 text-secondary" />
            {{ t('aiLeverage.confirm.practice') }}
          </p>
          <UCheckbox v-model="ack" :label="t('aiLeverage.confirm.ack')" />
        </div>
      </template>
      <template #footer>
        <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <UButton
            color="neutral"
            variant="outline"
            class="justify-center max-sm:min-h-10"
            autofocus
            @click="showConfirm = false"
            >{{ t('aiLeverage.confirm.keep') }}</UButton
          >
          <UButton
            :color="live ? 'error' : 'primary'"
            variant="solid"
            icon="i-mdi-scale-unbalanced"
            class="justify-center font-semibold max-sm:min-h-10"
            :disabled="!ack"
            @click="confirmOn"
            >{{ t('aiLeverage.confirm.turnOn') }}</UButton
          >
        </div>
      </template>
    </UModal>
  </div>
</template>
