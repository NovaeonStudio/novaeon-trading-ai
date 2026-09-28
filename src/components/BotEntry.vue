<script setup lang="ts">
import type { BotDescriptor } from '@/types';
const { confirm } = useConfirmBox();
const { t } = useI18n();

const props = defineProps<{
  bot: BotDescriptor;
  noButtons?: boolean;
  noRefreshSwitch?: boolean;
  noText?: boolean;
}>();

defineEmits<{ edit: [botId: string]; editLogin: [botId: string] }>();

const botStore = useBotStore();

function confirmRemoveBot() {
  botStore.removeBot(props.bot.botId);
}

async function removeBotQuestion() {
  if (
    await confirm({
      title: t('bots.entry.removeTitle'),
      message: t('bots.entry.removeMessage', { name: props.bot.botName || props.bot.botId }),
      confirmText: t('common.remove'),
    })
  ) {
    confirmRemoveBot();
  }
}

const selectedBotStore = computed<BotSubStore>(() => {
  return botStore.botStores[props.bot.botId]!;
});

const autoRefreshLoc = computed({
  get() {
    return selectedBotStore.value.autoRefresh;
  },
  set(newValue) {
    selectedBotStore.value.setAutoRefresh(newValue);
  },
});
</script>

<template>
  <div v-if="bot" class="flex w-full min-w-0 items-center justify-between gap-3">
    <div v-if="!noText" class="min-w-0 flex-1 text-start">
      <div class="truncate text-sm font-medium text-highlighted">
        {{ bot.botName || bot.botId }}
      </div>
      <div v-if="!noButtons" class="truncate text-sm text-muted" :title="bot.botUrl">
        {{ bot.botUrl }}
      </div>
    </div>

    <div class="flex shrink-0 items-center gap-3">
      <USwitch
        v-if="!noRefreshSwitch"
        v-model="autoRefreshLoc"
        size="sm"
        :aria-label="t('bots.autoRefreshFor', { name: bot.botName || bot.botId })"
        :title="t('bots.autoRefreshFor', { name: bot.botName || bot.botId })"
        @click.stop
      />
      <span
        v-if="selectedBotStore.isBotLoggedIn"
        class="flex items-center gap-1.5 text-xs text-muted"
        :title="selectedBotStore.isBotOnline ? t('common.online') : t('common.offline')"
      >
        <span
          class="inline-flex size-2 rounded-full"
          :class="selectedBotStore.isBotOnline ? 'bg-emerald-400' : 'bg-rose-500'"
        />
        <span :class="noButtons ? 'sr-only' : 'hidden sm:inline'">{{
          selectedBotStore.isBotOnline ? t('common.online') : t('common.offline')
        }}</span>
      </span>
      <span
        v-else
        class="flex items-center gap-1.5 text-xs text-rose-400"
        :title="t('bots.entry.loginExpiredHint')"
      >
        <UIcon name="i-mdi-cancel" class="size-4" />
        <span :class="noButtons ? 'sr-only' : 'hidden sm:inline'">{{
          t('bots.entry.loginExpired')
        }}</span>
      </span>

      <div
        v-if="!noButtons || (!noRefreshSwitch && !selectedBotStore.isBotLoggedIn)"
        class="flex items-center gap-0.5"
      >
        <UTooltip
          v-if="!noButtons && selectedBotStore.isBotLoggedIn"
          :text="t('bots.entry.rename')"
        >
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            icon="i-mdi-pencil-outline"
            :aria-label="t('bots.entry.rename')"
            @click.stop="$emit('edit', bot.botId)"
          />
        </UTooltip>
        <UTooltip
          v-if="!noRefreshSwitch && !selectedBotStore.isBotLoggedIn"
          :text="t('bots.logInAgain')"
        >
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            icon="i-mdi-login"
            :aria-label="t('bots.logInAgain')"
            @click.stop="$emit('editLogin', bot.botId)"
          />
        </UTooltip>
        <UTooltip v-if="!noButtons" :text="t('bots.entry.remove')">
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            icon="i-mdi-trash-can-outline"
            :aria-label="t('bots.entry.remove')"
            class="hover:text-rose-400"
            @click.stop="removeBotQuestion"
          />
        </UTooltip>
      </div>
    </div>
  </div>
</template>
