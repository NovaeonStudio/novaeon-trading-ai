<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
  }>(),
  {
    size: 'lg',
  },
);
const open = defineModel('open', {
  type: Boolean,
  default: false,
});
defineOptions({
  inheritAttrs: false,
});
</script>

<template>
  <UCollapsible class="rounded-xl border border-default/70" v-model:open="open">
    <UButton
      block
      :size="size"
      color="neutral"
      variant="ghost"
      class="group rounded-xl font-medium"
      trailing-icon="i-mdi-chevron-down"
      :ui="{
        trailingIcon:
          'group-data-[state=open]:rotate-180 transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]',
      }"
      :label="title"
    />
    <template #content>
      <div v-bind="$attrs">
        <slot />
      </div>
    </template>
  </UCollapsible>
</template>
