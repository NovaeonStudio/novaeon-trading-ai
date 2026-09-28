<script setup lang="ts">
const { t } = useI18n();
const botStore = useBotStore();
const scrollContainer = ref<HTMLElement | null>(null);

onMounted(async () => {
  refreshLogs();
});

async function refreshLogs() {
  await botStore.activeBot.getLogs();
  scrollToBottom();
}

function getLogColor(logLevel: string) {
  switch (logLevel) {
    case 'WARNING':
      return 'text-yellow-500';
    case 'ERROR':
      return 'text-red-500';
    default:
      return 'text-muted';
  }
}

function scrollToBottom() {
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
  }
}
</script>

<template>
  <div class="flex h-full p-0 align-items-start">
    <div
      ref="scrollContainer"
      class="border border-default/70 p-1 text-start text-sm pb-5 w-full h-full overflow-auto"
    >
      <pre
        v-for="(log, index) in botStore.activeBot.lastLogs"
        :key="index"
        class="m-0 overflow-visible"
        style="line-height: unset"
      ><span class="text-muted">{{ log[0] }} <span :class="getLogColor(log[3])">{{ log[3].padEnd(7, ' ') }}</span> {{ log[2] }} - </span
      ><span class="text-default">{{ log[4] }}</span
        ></pre>
    </div>
    <div class="flex flex-col gap-1 ms-1">
      <UButton
        id="refresh-logs"
        color="neutral"
        size="sm"
        :title="t('logs.reload')"
        @click="refreshLogs"
        icon="mdi:refresh"
      />
      <UButton
        size="sm"
        :title="t('logs.scrollToBottom')"
        color="neutral"
        @click="scrollToBottom"
        icon="mdi:arrow-down-thick"
      />
    </div>
  </div>
</template>

<style lang="css" scoped>
textarea {
  width: 100%;
  min-height: 6em;
  resize: none;
}
</style>
