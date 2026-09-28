<script setup lang="ts">
import type { AuthStorageWithBotId } from '@/types';

export interface LoginModalProps {
  loginInfo?: AuthStorageWithBotId;
}

defineProps<LoginModalProps>();
const { t } = useI18n();
const emit = defineEmits<{
  close: [value: boolean];
}>();

function loginResult(result: boolean) {
  if (result) {
    // Only close if
    emit('close', result);
  }
}
</script>

<template>
  <UModal
    :title="loginInfo ? t('login.titleAgain') : t('login.title')"
    :description="t('login.intro')"
    :ui="{ content: 'rounded-2xl', title: 'text-lg font-semibold text-highlighted' }"
  >
    <template #body>
      <BotLogin in-modal :existing-auth="loginInfo" @login-result="loginResult" />
    </template>
  </UModal>
</template>
