<script setup lang="ts">
defineOptions({
  inheritAttrs: false,
});
withDefaults(
  defineProps<{
    /** The header text for the draggable container */
    header?: string;
    /** The info text for the draggable container
     * Only shown when hovering the info icon next to the header. Used to give more context about the content of the container.
     * Not compatible with usage of the header slot.
     */
    infoText?: string;
  }>(),
  {
    header: '',
    infoText: '',
  },
);
</script>

<template>
  <div class="nova-panel flex h-full w-full min-w-0 flex-col overflow-hidden">
    <div
      class="drag-header flex min-h-10 items-center border-b border-default/50 px-4 py-2 text-start text-sm font-medium text-highlighted"
    >
      <slot name="header">
        <div class="flex items-center gap-2">
          {{ header }}
          <InfoBox v-if="infoText" :hint="infoText" />
        </div>
      </slot>
    </div>
    <div class="h-full w-full overflow-auto p-0" v-bind="$attrs">
      <slot></slot>
    </div>
  </div>
</template>
