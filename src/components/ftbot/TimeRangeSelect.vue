<script setup lang="ts">
import { CalendarDate, Time } from '@internationalized/date';
import type { DateValue, TimeValue } from 'reka-ui';

const now = new Date();
const maxDateNow = new CalendarDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
const maxDateTomorrow = maxDateNow.add({ days: 1 });

/** Locale forcing the yyyy-mm-dd segment order of the date inputs */
const dateLocale = 'en-CA';

const props = defineProps<{
  /** Whether the bot this timerange is sent to supports hour/minute precision (API 2.50) */
  canUseTime: boolean;
}>();

const { t } = useI18n();

const timeRangeModel = defineModel<string>({ required: true });

const dateFrom = shallowRef<DateValue | null>(null);
const dateTo = shallowRef<DateValue | null>(null);
const timeFrom = shallowRef<TimeValue | null>(null);
const timeTo = shallowRef<TimeValue | null>(null);
/** Use hour/minute precision - requires API 2.50 */
const withTime = ref(false);
const withSeconds = ref(false);
const popoverFromOpen = ref(false);
const popoverToOpen = ref(false);

const useTime = computed(() => withTime.value && props.canUseTime);

/** Only show the seconds segment if the timerange actually uses seconds */
const granularity = computed(() => (withSeconds.value ? 'second' : 'minute'));

function timeToInputString(time: TimeValue | null): string {
  if (!time) return '';
  const result = `${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')}`;
  return time.second ? `${result}:${String(time.second).padStart(2, '0')}` : result;
}

function parseTimeText(text: string): Time | null {
  const match = text.match(/^(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (match) {
    return new Time(parseInt(match[1]!), parseInt(match[2]!), match[3] ? parseInt(match[3]) : 0);
  }
  return null;
}

function dateToInputString(d: DateValue | null): string {
  if (!d) return '';
  return `${String(d.year).padStart(4, '0')}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`;
}

function parseInputText(text: string): CalendarDate | null {
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    return new CalendarDate(parseInt(match[1]!), parseInt(match[2]!), parseInt(match[3]!));
  }
  return null;
}

const timeRange = computed(() => {
  const fromTime = useTime.value ? timeToInputString(timeFrom.value) : '';
  const toTime = useTime.value ? timeToInputString(timeTo.value) : '';
  const from = inputToTimeRangePart(dateToInputString(dateFrom.value), fromTime);
  const to = inputToTimeRangePart(dateToInputString(dateTo.value), toTime);
  if (from || to) {
    return `${from}-${to}`;
  }
  return '';
});

function onFromCalendarSelect(v: unknown) {
  dateFrom.value = v as DateValue;
  popoverFromOpen.value = false;
}

function onToCalendarSelect(v: unknown) {
  dateTo.value = v as DateValue;
  popoverToOpen.value = false;
}

function updateInput() {
  const tr = timeRangeModel.value.split('-');
  const from = timeRangePartToInput(tr[0] ?? '');
  const to = timeRangePartToInput(tr[1] ?? '');
  dateFrom.value = parseInputText(from?.date ?? '');
  timeFrom.value = parseTimeText(from?.time ?? '');
  dateTo.value = parseInputText(to?.date ?? '');
  timeTo.value = parseTimeText(to?.time ?? '');
  withSeconds.value = !!(timeFrom.value?.second || timeTo.value?.second);
  if (timeFrom.value || timeTo.value) {
    withTime.value = true;
  }
}

watch(
  () => timeRange.value,
  () => {
    timeRangeModel.value = timeRange.value;
  },
);
watch(timeRangeModel, (newValue) => {
  if (newValue !== timeRange.value) {
    updateInput();
  }
});

onMounted(() => {
  if (!timeRangeModel.value) {
    const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    dateFrom.value = new CalendarDate(d.getFullYear(), d.getMonth() + 1, d.getDate());
  } else {
    updateInput();
  }
  timeRangeModel.value = timeRange.value;
});
</script>

<template>
  <div class="flex flex-col gap-3 text-start">
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div class="flex min-w-0 gap-2">
        <UFormField :label="t('timerange.startDate')" class="min-w-0 flex-1">
          <UInputDate
            v-model="dateFrom"
            :locale="dateLocale"
            :max-value="maxDateNow"
            :ui="{ base: 'pe-14' }"
            class="w-full"
            :title="t('timerange.startDateTitle')"
          >
            <template #trailing>
              <UButton
                v-if="dateFrom"
                icon="i-mdi-close"
                color="neutral"
                variant="ghost"
                size="xs"
                :title="t('timerange.clearStartDate')"
                @click="dateFrom = null"
              />
              <UPopover v-model:open="popoverFromOpen">
                <UButton
                  icon="i-mdi-calendar-blank"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  :aria-label="t('timerange.pickStartDate')"
                />
                <template #content>
                  <UCalendar
                    :model-value="dateFrom"
                    :max-value="maxDateNow"
                    @update:model-value="onFromCalendarSelect"
                  />
                </template>
              </UPopover>
            </template>
          </UInputDate>
        </UFormField>
        <UFormField v-if="useTime" :label="t('timerange.time')">
          <UInputTime
            v-model="timeFrom"
            :hour-cycle="24"
            :granularity="granularity"
            :title="t('timerange.startTimeTitle')"
          >
            <template #trailing>
              <UButton
                v-if="timeFrom"
                icon="i-mdi-close"
                color="neutral"
                variant="ghost"
                size="xs"
                :title="t('timerange.clearStartTime')"
                @click="timeFrom = null"
              />
            </template>
          </UInputTime>
        </UFormField>
      </div>
      <div class="flex min-w-0 gap-2">
        <UFormField :label="t('timerange.endDate')" class="min-w-0 flex-1">
          <UInputDate
            v-model="dateTo"
            :locale="dateLocale"
            :max-value="maxDateTomorrow"
            :ui="{ base: 'pe-14' }"
            class="w-full"
            :title="t('timerange.endDateTitle')"
          >
            <template #trailing>
              <UButton
                v-if="dateTo"
                icon="i-mdi-close"
                color="neutral"
                variant="ghost"
                size="xs"
                :title="t('timerange.clearEndDate')"
                @click="dateTo = null"
              />
              <UPopover v-model:open="popoverToOpen">
                <UButton
                  icon="i-mdi-calendar-blank"
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  :aria-label="t('timerange.pickEndDate')"
                />
                <template #content>
                  <UCalendar
                    :model-value="dateTo"
                    :max-value="maxDateTomorrow"
                    @update:model-value="onToCalendarSelect"
                  />
                </template>
              </UPopover>
            </template>
          </UInputDate>
        </UFormField>
        <UFormField v-if="useTime" :label="t('timerange.time')">
          <UInputTime
            v-model="timeTo"
            :hour-cycle="24"
            :granularity="granularity"
            :title="t('timerange.endTimeTitle')"
          >
            <template #trailing>
              <UButton
                v-if="timeTo"
                icon="i-mdi-close"
                color="neutral"
                variant="ghost"
                size="xs"
                :title="t('timerange.clearEndTime')"
                @click="timeTo = null"
              /> </template
          ></UInputTime>
        </UFormField>
      </div>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <BaseCheckbox v-if="canUseTime" v-model="withTime" :title="t('timerange.useTimeTitle')">
        {{ t('timerange.useTime') }}
      </BaseCheckbox>
      <div class="flex items-center gap-2 text-sm">
        <span class="text-muted">{{ t('timerange.timeRange') }}</span>
        <span class="nova-num rounded-lg bg-accented/60 px-2 py-0.5 font-medium text-highlighted">{{
          timeRange || t('timerange.allData')
        }}</span>
      </div>
    </div>
  </div>
</template>
