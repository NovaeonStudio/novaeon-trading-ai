<script setup lang="ts">
const { t } = useI18n();
const values = defineModel<string[]>({ required: true });
withDefaults(
  defineProps<{
    placeholder?: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
  }>(),
  {
    placeholder: '',
    size: 'md',
  },
);
</script>

<template>
  <div class="flex flex-row gap-2">
    <div class="flex gap-1 flex-col w-full">
      <div v-for="(val, idx) in values" :key="idx" class="flex flex-row gap-1">
        <UInput
          v-model="values[idx]"
          :size="size"
          class="w-full"
          :placeholder="placeholder"
        ></UInput>
        <UButton
          color="neutral"
          variant="ghost"
          :title="t('general.stringList.delete')"
          :aria-label="t('general.stringList.delete')"
          icon="i-mdi-trash-can-outline"
          @click="values.splice(idx, 1)"
        />
      </div>
    </div>
    <UButton
      :title="t('general.stringList.add')"
      :aria-label="t('general.stringList.add')"
      color="primary"
      variant="soft"
      class="mt-auto"
      icon="i-mdi-plus"
      @click="values.push('')"
    />
  </div>
</template>
