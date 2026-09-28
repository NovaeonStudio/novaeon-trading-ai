<script setup lang="ts">
import type { AuthStorageWithBotId, BotDescriptor } from '@/types';
import { useSortable } from '@vueuse/integrations/useSortable';

defineProps<{
  small?: boolean;
}>();

const { t } = useI18n();
const botStore = useBotStore();

const editingBots = ref<string[]>([]);
const loginDialog = useLoginDialog();
const sortContainer = ref<HTMLElement | null>(null);
const botListComp = computed<BotDescriptor[]>(() => {
  //Convert to array
  return botStore.availableBotsSorted;
});

useSortable(sortContainer, botListComp, {
  handle: '.handle',
  onUpdate: (e) => {
    if (e.oldIndex === undefined || e.newIndex === undefined) {
      return;
    }
    const oldBotId = botListComp.value[e.oldIndex]?.botId;
    const newBotId = botListComp.value[e.newIndex]?.botId;
    if (oldBotId && newBotId) {
      botStore.updateBot(oldBotId, { sortId: e.newIndex });
      botStore.updateBot(newBotId, { sortId: e.oldIndex });
    }
  },
});

function editBot(botId: string) {
  if (!editingBots.value.includes(botId)) {
    editingBots.value.push(botId);
  }
}

function editBotLogin(botId: string) {
  const bot = botStore.botStores[botId];
  if (!bot) {
    console.error('Bot not found');
    return;
  }
  const loginInfo: AuthStorageWithBotId = {
    ...bot.getLoginInfo(),
    botId,
  };

  loginDialog({ loginInfo: loginInfo });
}

function stopEditBot(botId: string) {
  if (!editingBots.value.includes(botId)) {
    return;
  }

  editingBots.value.splice(editingBots.value.indexOf(botId), 1);
}
</script>

<template>
  <div v-if="botStore.botCount > 0" class="flex w-full flex-col gap-3">
    <ul ref="sortContainer" class="flex flex-col gap-3" :aria-label="t('bots.list.aria')">
      <li
        v-for="bot in botListComp"
        :key="bot.botId"
        tabindex="0"
        :aria-current="bot.botId === botStore.selectedBot ? 'true' : undefined"
        :title="
          botStore.botStores[bot.botId]?.isBotLoggedIn
            ? `${bot.botName || bot.botId} · ${bot.botUrl}`
            : t('bots.list.loginExpired', { name: bot.botName || bot.botId })
        "
        class="nova-panel flex cursor-pointer items-center gap-3 p-3 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98] sm:p-4"
        :class="{
          'ring-1 ring-brand-400/60': bot.botId === botStore.selectedBot,
        }"
        @click="botStore.selectBot(bot.botId)"
        @keydown.enter.self="botStore.selectBot(bot.botId)"
        @keydown.space.self.prevent="botStore.selectBot(bot.botId)"
      >
        <UButton
          v-if="!small"
          color="neutral"
          variant="ghost"
          size="sm"
          icon="i-mdi-drag-vertical"
          class="handle -ms-1 cursor-grab text-dimmed"
          :aria-label="t('bots.list.drag')"
          :title="t('bots.list.drag')"
          @click.stop
        />
        <span
          class="hidden size-10 shrink-0 items-center justify-center rounded-full sm:flex"
          :class="
            bot.botId === botStore.selectedBot
              ? 'bg-brand-400/15 text-brand-400'
              : 'bg-accented text-muted'
          "
        >
          <UIcon name="i-mdi-robot-outline" class="size-5" />
        </span>
        <BotRename
          v-if="editingBots.includes(bot.botId)"
          :bot="bot"
          @saved="stopEditBot(bot.botId)"
          @cancelled="stopEditBot(bot.botId)"
        />

        <BotEntry
          v-else
          :bot="bot"
          :no-buttons="small"
          @edit="editBot"
          @edit-login="editBotLogin"
        />
      </li>
    </ul>
    <button
      v-if="!small"
      type="button"
      class="flex min-h-14 items-center justify-center gap-2 rounded-2xl border border-dashed border-default text-sm font-medium text-muted transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40 hover:text-highlighted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
      @click="loginDialog({})"
    >
      <UIcon name="i-mdi-plus" class="size-5" />
      {{ t('bots.list.add') }}
    </button>
  </div>
</template>
