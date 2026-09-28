<script setup lang="ts">
export interface ConfirmDialogBoxProps {
  title: string;
  description?: string;
  message: string;
  cancelText?: string;
  confirmText?: string;
}
withDefaults(defineProps<ConfirmDialogBoxProps>(), {
  description: '',
  cancelText: '',
  confirmText: '',
});
const { t } = useI18n();
defineEmits<{
  close: [value: boolean];
}>();
</script>

<template>
  <UModal
    :title="title"
    :description="description || undefined"
    :ui="{
      content: 'rounded-2xl',
      title: 'text-lg font-semibold text-highlighted',
      footer: 'justify-end gap-2',
    }"
  >
    <template #body>
      <p class="text-sm text-pretty whitespace-pre-wrap text-default">
        {{ message }}
      </p>
    </template>
    <template #footer>
      <UButton
        class="min-w-28 justify-center"
        :label="cancelText || t('common.cancel')"
        variant="outline"
        color="neutral"
        autofocus
        @click="$emit('close', false)"
      />
      <UButton
        class="min-w-28 justify-center font-semibold"
        :label="confirmText || t('common.confirm')"
        color="primary"
        variant="solid"
        @click="$emit('close', true)"
      />
    </template>
  </UModal>
</template>
