<script setup lang="ts">
import { I18nT } from 'vue-i18n';
import { FtWsMessageTypes } from '@/types/wsMessageTypes';
import novaeonWordmark from '@/assets/novaeon-wordmark.svg';

const { t } = useI18n();
const settingsStore = useSettingsStore();
const colorStore = useColorStore();

const timezoneOptions = ['UTC', Intl.DateTimeFormat().resolvedOptions().timeZone];
const openTradesOptions = computed(() => [
  { value: OpenTradeVizOptions.showPill, text: t('settings.openTrades.pill') },
  { value: OpenTradeVizOptions.asTitle, text: t('settings.openTrades.title') },
  { value: OpenTradeVizOptions.noOpenTrades, text: t('settings.openTrades.none') },
]);
const colorPreferenceOptions = computed(() => [
  { value: ColorPreferences.GREEN_UP, text: t('settings.colors.greenUp') },
  { value: ColorPreferences.RED_UP, text: t('settings.colors.redUp') },
]);
const chartSideOptions = computed(
  () =>
    [
      { label: t('settings.scaleSide.left'), value: 'left' },
      { label: t('settings.scaleSide.right'), value: 'right' },
    ] as const,
);
const notificationOptions = computed(() => [
  {
    key: FtWsMessageTypes.entryFill,
    label: t('settings.notifications.entryFill'),
    hint: t('settings.notifications.entryFillHint'),
  },
  {
    key: FtWsMessageTypes.exitFill,
    label: t('settings.notifications.exitFill'),
    hint: t('settings.notifications.exitFillHint'),
  },
  {
    key: FtWsMessageTypes.entryCancel,
    label: t('settings.notifications.entryCancel'),
    hint: t('settings.notifications.entryCancelHint'),
  },
  {
    key: FtWsMessageTypes.exitCancel,
    label: t('settings.notifications.exitCancel'),
    hint: t('settings.notifications.exitCancelHint'),
  },
]);

const uiVersionShort = computed(() => settingsStore.uiVersion.replace(/^not_installed-/, ''));

const rowBase = 'border-t border-default/50 py-4 first:border-t-0 first:pt-0 last:pb-0';
/** Label and hint left, control right; stacks on phones (selects, sliders, buttons). */
const rowClass = `${rowBase} flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6`;
/** Rows with a small control (switch) stay side by side on phones too. */
const switchRowClass = `${rowBase} flex items-center justify-between gap-4 sm:gap-6`;
</script>

<template>
  <div class="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8">
    <header>
      <h1 class="text-2xl font-semibold text-balance text-highlighted">
        {{ t('settings.title') }}
      </h1>
      <p class="mt-1 text-sm text-pretty text-muted">
        {{ t('settings.intro') }}
      </p>
    </header>

    <NovaPanel
      id="trading"
      class="scroll-mt-6"
      :title="t('settings.trading.title')"
      :subtitle="t('settings.trading.subtitle')"
    >
      <NovaAiLeverage />
    </NovaPanel>

    <NovaPanel :title="t('settings.interface.title')" :subtitle="t('settings.interface.subtitle')">
      <div class="flex flex-col">
        <div :class="rowClass">
          <div class="min-w-0">
            <span id="setting-language" class="text-sm font-medium text-highlighted">{{
              $t('common.language')
            }}</span>
            <p class="mt-1 text-sm text-pretty text-muted">{{ $t('common.languageHint') }}</p>
          </div>
          <LanguageSelect aria-labelledby="setting-language" class="shrink-0 sm:w-72" />
        </div>

        <div :class="rowClass">
          <div class="min-w-0">
            <label for="setting-open-trades" class="text-sm font-medium text-highlighted">{{
              t('settings.openTrades.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.openTrades.hint') }}
            </p>
          </div>
          <USelect
            id="setting-open-trades"
            v-model="settingsStore.openTradesInTitle"
            :items="openTradesOptions"
            label-key="text"
            value-key="value"
            class="w-full shrink-0 sm:w-72"
          />
        </div>

        <div :class="rowClass">
          <div class="min-w-0">
            <label for="setting-timezone" class="text-sm font-medium text-highlighted">{{
              t('settings.timezone.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.timezone.hint') }}
            </p>
          </div>
          <USelect
            id="setting-timezone"
            v-model="settingsStore.timezone"
            :items="timezoneOptions"
            class="w-full shrink-0 sm:w-72"
          />
        </div>

        <div :class="switchRowClass">
          <div class="min-w-0">
            <label for="setting-confirm" class="text-sm font-medium text-highlighted">{{
              t('settings.confirm.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.confirm.hint') }}
            </p>
          </div>
          <USwitch id="setting-confirm" v-model="settingsStore.confirmDialog" class="shrink-0" />
        </div>

        <div :class="switchRowClass">
          <div class="min-w-0">
            <label for="setting-bg-sync" class="text-sm font-medium text-highlighted">{{
              t('settings.bgSync.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.bgSync.hint') }}
            </p>
          </div>
          <USwitch id="setting-bg-sync" v-model="settingsStore.backgroundSync" class="shrink-0" />
        </div>

        <div :class="switchRowClass">
          <div class="min-w-0">
            <label for="setting-multipane" class="text-sm font-medium text-highlighted">{{
              t('settings.multiPane.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.multiPane.hint') }}
            </p>
          </div>
          <USwitch
            id="setting-multipane"
            v-model="settingsStore.multiPaneButtonsShowText"
            class="shrink-0"
          />
        </div>
      </div>
    </NovaPanel>

    <NovaPanel :title="t('settings.charts.title')" :subtitle="t('settings.charts.subtitle')">
      <div class="flex flex-col">
        <div :class="rowClass">
          <div class="min-w-0">
            <span class="text-sm font-medium text-highlighted">{{
              t('settings.scaleSide.label')
            }}</span>
            <p class="mt-1 text-sm text-pretty text-muted">{{ t('settings.scaleSide.hint') }}</p>
          </div>
          <div
            class="nova-seg shrink-0 self-start text-sm sm:self-auto"
            role="group"
            :aria-label="t('settings.scaleSide.label')"
          >
            <button
              v-for="opt in chartSideOptions"
              :key="opt.value"
              type="button"
              class="min-h-8 px-4 font-medium"
              :aria-pressed="settingsStore.chartLabelSide === opt.value"
              @click="settingsStore.chartLabelSide = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div :class="switchRowClass">
          <div class="min-w-0">
            <label for="setting-heikin" class="text-sm font-medium text-highlighted">{{
              t('settings.heikin.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.heikin.hint') }}
            </p>
          </div>
          <USwitch
            id="setting-heikin"
            v-model="settingsStore.useHeikinAshiCandles"
            class="shrink-0"
          />
        </div>

        <div :class="switchRowClass">
          <div class="min-w-0">
            <label for="setting-reduced" class="text-sm font-medium text-highlighted">{{
              t('settings.reduced.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.reduced.hint') }}
            </p>
          </div>
          <USwitch
            id="setting-reduced"
            v-model="settingsStore.useReducedPairCalls"
            class="shrink-0"
          />
        </div>

        <div :class="rowClass">
          <div class="min-w-0">
            <label for="setting-candles" class="text-sm font-medium text-highlighted">{{
              t('settings.candles.label')
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('settings.candles.hint') }}
            </p>
          </div>
          <div class="flex w-full shrink-0 items-center gap-4 sm:w-72">
            <USlider
              v-model="settingsStore.chartDefaultCandleCount"
              class="flex-1"
              :step="50"
              :min="100"
              :max="2000"
              :aria-label="t('settings.candles.label')"
            />
            <UInputNumber
              id="setting-candles"
              v-model="settingsStore.chartDefaultCandleCount"
              :step="50"
              :min="100"
              :max="2000"
              size="sm"
              class="nova-num w-28"
            />
          </div>
        </div>

        <div :class="rowClass">
          <div class="min-w-0">
            <span class="text-sm font-medium text-highlighted">{{
              t('settings.colors.label')
            }}</span>
            <p class="mt-1 text-sm text-pretty text-muted">{{ t('settings.colors.hint') }}</p>
          </div>
          <URadioGroup
            v-model="colorStore.colorPreference"
            :items="colorPreferenceOptions"
            label-key="text"
            value-key="value"
            orientation="vertical"
            class="shrink-0"
          >
            <template #label="{ item }">
              <span class="flex items-center gap-1 text-sm">
                {{ item.text }}
                <UIcon
                  name="i-mdi-arrow-up-thin"
                  :style="{
                    color:
                      item.value === ColorPreferences.GREEN_UP
                        ? colorStore.colorProfit
                        : colorStore.colorLoss,
                  }"
                  class="size-5"
                />
                <UIcon
                  name="i-mdi-arrow-down-thin"
                  :style="{
                    color:
                      item.value === ColorPreferences.GREEN_UP
                        ? colorStore.colorLoss
                        : colorStore.colorProfit,
                  }"
                  class="-ms-2 size-5"
                />
              </span>
            </template>
          </URadioGroup>
        </div>
      </div>
    </NovaPanel>

    <NovaPanel
      :title="t('settings.notifications.title')"
      :subtitle="t('settings.notifications.subtitle')"
    >
      <div class="flex flex-col">
        <div v-for="n in notificationOptions" :key="n.key" :class="switchRowClass">
          <div class="min-w-0">
            <label :for="`setting-notify-${n.key}`" class="text-sm font-medium text-highlighted">{{
              n.label
            }}</label>
            <p class="mt-1 text-sm text-pretty text-muted">{{ n.hint }}</p>
          </div>
          <USwitch
            :id="`setting-notify-${n.key}`"
            v-model="settingsStore.notifications[n.key]"
            class="shrink-0"
          />
        </div>
      </div>
    </NovaPanel>

    <NovaPanel
      :title="t('settings.backtesting.title')"
      :subtitle="t('settings.backtesting.subtitle')"
    >
      <div class="flex flex-col gap-2">
        <label for="backtestMetrics" class="text-sm font-medium text-highlighted">{{
          t('settings.backtesting.metrics')
        }}</label>
        <USelectMenu
          id="backtestMetrics"
          v-model="settingsStore.backtestAdditionalMetrics"
          multiple
          :items="availableBacktestMetrics"
          label-key="header"
          value-key="field"
          class="w-full"
          display="chip"
        />
        <p class="text-sm text-pretty text-muted">{{ t('settings.backtesting.metricsHint') }}</p>
      </div>
    </NovaPanel>

    <NovaPanel :title="t('settings.about.title')">
      <div class="flex flex-col gap-2 text-sm text-muted">
        <p class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-pretty">
          <span>{{ t('general.madeBy') }}</span>
          <img :src="novaeonWordmark" alt="novæon" class="inline-block h-3.5 w-auto" />
          <span aria-hidden="true">·</span>
          <I18nT keypath="general.openSource" tag="span" scope="global">
            <template #license>
              <a
                class="rounded-sm text-default underline decoration-default underline-offset-4 hover:text-highlighted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
                href="https://www.gnu.org/licenses/gpl-3.0.html"
                target="_blank"
                rel="noopener noreferrer"
                >GPL-3.0</a
              >
            </template>
          </I18nT>
        </p>
        <I18nT keypath="common.version" tag="p" scope="global">
          <template #version>
            <span class="nova-num text-default">{{ uiVersionShort }}</span>
          </template>
        </I18nT>
      </div>
    </NovaPanel>
  </div>
</template>
