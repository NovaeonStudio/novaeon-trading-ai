<script setup lang="ts">
const visible = defineModel<boolean>('visible');
defineProps<{
  columns: string[];
}>();

const { plotTemplateNames, applyPlotTemplate, getTemplateContent } = usePlotTemplates();
const { t } = useI18n();
const plotStore = usePlotConfigStore();

function fromTemplateApply() {
  if (selTemplateName.value) {
    plotStore.editablePlotConfig = {
      ...applyPlotTemplate(selTemplateName.value, plotStore.editablePlotConfig, indicatorMap.value),
    };
    visible.value = false;
  }
}

function clickStartUseTemplate() {
  showIndicatorMapping.value = !showIndicatorMapping.value;

  indicatorMap.value = plotConfigColumns(getTemplateContent(selTemplateName.value), true).reduce(
    (acc, indicator) => {
      acc[indicator] = indicator;
      return acc;
    },
    {},
  );
}

const selTemplateName = ref<string>('');
watch(
  () => visible.value,
  (v) => {
    if (v) {
      selTemplateName.value = '';
      showIndicatorMapping.value = false;
    }
  },
);

const indicatorMap = ref<Record<string, string>>({});
const showIndicatorMapping = ref(false);
</script>

<template>
  <div v-if="visible" class="pt-1">
    <UFormField v-if="!showIndicatorMapping" :label="t('plot.template.select')" class="text-md">
      <UListbox
        id="selectTemplate"
        class="rounded ring ring-accented"
        v-model="selTemplateName"
        value-key="value"
        :items="
          plotTemplateNames.map((name) => ({
            value: name,
            label: name,
          }))
        "
      >
      </UListbox>
    </UFormField>
    <div v-else>
      <h5 class="mt-1 text-center text-md mb-1">{{ t('plot.template.remap') }}</h5>
      <div
        v-for="indicator in Object.keys(indicatorMap)"
        :key="indicator"
        class="flex gap-2 align-center"
      >
        <label :for="`indicator-${indicator}`" class="grow w-full">{{ indicator }}</label>
        <USelectMenu
          :id="`indicator-${indicator}`"
          v-model="indicatorMap[indicator]"
          class="grow w-full"
          :items="columns"
        >
        </USelectMenu>
      </div>
    </div>
    <div class="mt-2 flex gap-1 justify-end">
      <UButton :title="t('plot.abort')" color="neutral" icon="mdi:close" @click="visible = false" />
      <UButton
        v-if="!showIndicatorMapping"
        :disabled="!selTemplateName"
        :title="t('plot.template.useTitle')"
        :label="t('plot.template.use')"
        class="w-40 whitespace-normal"
        variant="solid"
        icon="mdi:check"
        @click="clickStartUseTemplate"
      />
      <UButton
        v-if="showIndicatorMapping"
        :disabled="!selTemplateName"
        :title="t('plot.template.applyTitle')"
        class="w-40 whitespace-normal"
        variant="solid"
        icon="mdi:check"
        @click="fromTemplateApply"
        :label="t('plot.template.apply')"
      />
    </div>
  </div>
</template>
