<script setup lang="ts">
const { t } = useI18n();
const props = withDefaults(
  defineProps<{
    modelValue: string;
    allowEdit?: boolean;
    allowAdd?: boolean;
    allowDuplicate?: boolean;
    editableName: string;
    alignVertical?: boolean;
  }>(),
  {
    allowEdit: false,
    allowAdd: false,
    allowDuplicate: false,
    alignVertical: false,
  },
);

const emit = defineEmits<{
  delete: [value: string];
  new: [value: string];
  duplicate: [oldName: string, newName: string];
  rename: [oldName: string, newName: string];
}>();

enum EditState {
  None,
  Editing,
  Adding,
  Duplicating,
}

const localName = ref<string>('');
const mode = ref<EditState>(EditState.None);
onMounted(() => {
  localName.value = props.modelValue;
});

function abort() {
  mode.value = EditState.None;
  localName.value = props.modelValue;
}

function duplicate() {
  localName.value = t('general.editValue.copyName', { name: localName.value });
  mode.value = EditState.Duplicating;
}

function addNewClick() {
  localName.value = '';
  mode.value = EditState.Adding;
}

watch(
  () => props.modelValue,
  () => {
    localName.value = props.modelValue;
  },
);

function saveNewName() {
  if (mode.value === EditState.Adding) {
    emit('new', localName.value);
  } else if (mode.value === EditState.Duplicating) {
    emit('duplicate', props.modelValue, localName.value);
  } else {
    // Editing
    emit('rename', props.modelValue, localName.value);
  }
  mode.value = EditState.None;
}
</script>

<template>
  <form class="flex flex-row items-end gap-2" @submit.prevent="saveNewName">
    <div class="min-w-0 grow">
      <slot v-if="mode === EditState.None"> </slot>
      <UInput
        v-else
        v-model="localName"
        class="w-full"
        :aria-label="t('general.editValue.nameAria', { name: editableName })"
      >
      </UInput>
    </div>
    <div class="flex shrink-0 gap-0.5" :class="alignVertical ? 'flex-col' : 'flex-row'">
      <template v-if="allowEdit && mode === EditState.None">
        <UButton
          color="neutral"
          variant="ghost"
          :title="t('general.editValue.edit', { name: editableName })"
          :aria-label="t('general.editValue.edit', { name: editableName })"
          icon="i-mdi-pencil-outline"
          @click="mode = EditState.Editing"
        />
        <UButton
          v-if="allowDuplicate"
          color="neutral"
          variant="ghost"
          :title="t('general.editValue.duplicate', { name: editableName })"
          :aria-label="t('general.editValue.duplicate', { name: editableName })"
          icon="i-mdi-content-copy"
          @click="duplicate"
        />
        <UButton
          color="neutral"
          variant="ghost"
          :title="t('general.editValue.delete', { name: editableName })"
          :aria-label="t('general.editValue.delete', { name: editableName })"
          icon="i-mdi-trash-can-outline"
          @click="$emit('delete', modelValue)"
        />
      </template>
      <UButton
        v-if="allowAdd && mode === EditState.None"
        :title="t('general.editValue.add', { name: editableName })"
        :aria-label="t('general.editValue.add', { name: editableName })"
        icon="i-mdi-plus"
        color="primary"
        variant="soft"
        @click="addNewClick"
      />
      <template v-if="mode !== EditState.None">
        <UButton
          :title="t('common.save')"
          :aria-label="t('common.save')"
          color="primary"
          variant="soft"
          icon="i-mdi-check"
          @click="saveNewName"
        />
        <UButton
          :title="t('common.cancel')"
          :aria-label="t('common.cancel')"
          color="neutral"
          variant="ghost"
          icon="i-mdi-close"
          @click="abort"
        />
      </template>
    </div>
  </form>
</template>
