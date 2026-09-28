<script setup lang="ts">
import type { BotDescriptor } from '@/types';
const props = defineProps<{
  bot: BotDescriptor;
}>();
const emit = defineEmits<{ cancelled: []; saved: [] }>();

const { t } = useI18n();
const botStore = useBotStore();
const newName = ref<string>('');

onMounted(() => {
  newName.value = props.bot.botName;
});

const save = () => {
  botStore.updateBot(props.bot.botId, {
    botName: newName.value,
  });

  emit('saved');
};
</script>

<template>
  <form class="flex w-full items-center gap-2" @submit.prevent="save" @click.stop>
    <UInput
      v-model="newName"
      class="w-full"
      :placeholder="t('bots.rename.name')"
      :aria-label="t('bots.rename.name')"
      autofocus
    />
    <div class="flex shrink-0 gap-0.5">
      <UTooltip :text="t('bots.rename.save')">
        <UButton
          type="submit"
          color="primary"
          variant="soft"
          size="sm"
          icon="i-mdi-check"
          :aria-label="t('bots.rename.save')"
        />
      </UTooltip>
      <UTooltip :text="t('common.cancel')">
        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          icon="i-mdi-close"
          :aria-label="t('common.cancel')"
          @click="$emit('cancelled')"
        />
      </UTooltip>
    </div>
  </form>
</template>
